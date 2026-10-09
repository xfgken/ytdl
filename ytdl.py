#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytdl · Termux 版 YouTube 下载器

流程：粘贴链接 → 选分辨率 → 选格式 → 自动下载合并 → 成品存到下载目录

用法：
  sh ytdl.sh                 交互式
  sh ytdl.sh <链接>          带上链接
  sh ytdl.sh <链接> -y       全部默认选项（无人值守）
"""
import glob
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata

# ---------------- 颜色（管道/日志场景自动关闭） ----------------
ESC = chr(27)
BOLD = ESC + '[1m'
DIM = ESC + '[2m'
GREEN = ESC + '[92m'
YELLOW = ESC + '[93m'
RED = ESC + '[91m'
CYAN = ESC + '[96m'
MAGENTA = ESC + '[95m'
BLUE = ESC + '[94m'
# 本轮主色：品红系（标签 / 小标题 / 框线 / 提示）
ACC = ESC + '[95m'
ACC_D = ESC + '[35m'
WHITE = ESC + '[97m'
GRAY = ESC + '[90m'
RESET = ESC + '[0m'


def _init_colors():
    global BOLD, DIM, GREEN, YELLOW, RED, CYAN, MAGENTA, BLUE, WHITE, GRAY, RESET, ACC, ACC_D
    if sys.stdout.isatty():
        return
    BOLD = DIM = GREEN = YELLOW = RED = CYAN = MAGENTA = BLUE = WHITE = GRAY = RESET = ''
    ACC = ACC_D = ''


_init_colors()
TTY = sys.stdout.isatty()
KILL = ESC + '[K' if TTY else ''          # 清到行尾

FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

# ---------------- 显示原语 ----------------


def term_width(default=80):
    try:
        return max(40, shutil.get_terminal_size((default, 24)).columns)
    except Exception:
        return default


def dwidth(s):
    n = 0
    for ch in s:
        n += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
    return n


def wrap(s, limit):
    out = []
    cur = ''
    w = 0
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if w + cw > limit and cur:
            out.append(cur)
            cur = ''
            w = 0
        cur += ch
        w += cw
    if cur:
        out.append(cur)
    return out or ['']


def pad(s, target):
    return s + ' ' * max(0, target - dwidth(s))


def out(m=''):
    print(m)


_SEC_N = [0]


def section(title):
    """区域：数字序号 + 标题（每轮从 1. 重新开始）"""
    if title == '开始解析':
        _SEC_N[0] = 0
    _SEC_N[0] += 1
    print(BOLD + ACC + ' %d. %s' % (_SEC_N[0], title) + RESET)


def clear_line():
    if TTY:
        sys.stdout.write('\r' + KILL)
        sys.stdout.flush()


def raw_line(text, color=None):
    """原样输出一行工具信息（缩进 + 灰，按显示宽度截断）"""
    w = term_width()
    if dwidth(text) > w - 3:
        t = ''
        for ch in text:
            if dwidth(t) + dwidth(ch) > w - 4:
                break
            t += ch
        t += '…'
    else:
        t = text
    clear_line()
    print((color or GRAY) + '  ' + t + RESET)


_SEEN = set()


def raw_once(key, text, color=None):
    if key in _SEEN:
        return
    _SEEN.add(key)
    raw_line(text, color)


def head(m):
    print(BOLD + CYAN + m + RESET)


def ok(m):
    print(' ' + GREEN + '✓' + RESET + ' ' + m)


def warn(m):
    print(' ' + YELLOW + '!' + RESET + ' ' + YELLOW + m + RESET)


def bad(m):
    print(' ' + RED + '✗' + RESET + ' ' + RED + m + RESET)


_ONCE = set()


def warn_once(key, msg):
    if key in _ONCE:
        return
    _ONCE.add(key)
    warn(msg)


def note(m):
    print(' ' + GRAY + m + RESET)


def bullet(m, hot=False):
    """重点行（亮白加粗）/ 次要行（灰），无装饰"""
    col = (BOLD + WHITE) if hot else GRAY
    print(col + '  ' + m + RESET)


_spin = {'i': 0}


def spin_step(text, extra=''):
    """原地转 spinner（非终端不刷屏）"""
    if not TTY:
        return
    _spin['i'] += 1
    line = ' ' + CYAN + FRAMES[_spin['i'] % len(FRAMES)] + RESET + ' ' + text
    if extra:
        line += ' ' + DIM + extra + RESET
    sys.stdout.write('\r' + KILL + line)
    sys.stdout.flush()


def spin_done(text=''):
    if not TTY:
        if text:
            print(text)
        return
    if text:
        sys.stdout.write('\r' + KILL + text + '\n')
    else:
        sys.stdout.write('\r' + KILL)
    sys.stdout.flush()


def bar(pct, width=22):
    pct = max(0.0, min(100.0, float(pct)))
    fill = int(round(width * pct / 100.0))
    return GREEN + '█' * fill + GRAY + '░' * (width - fill) + RESET


def prog_show(label, pct, info=''):
    if not TTY:
        return
    line = ' ' + label + ' ' + bar(pct) + ' ' + WHITE + '%5.1f%%' % pct + RESET
    if info:
        line += ' ' + GRAY + info + RESET
    sys.stdout.write('\r' + KILL + line)
    sys.stdout.flush()


def prog_finish(text, plain=None):
    if TTY:
        sys.stdout.write('\r' + KILL + text + '\n')
        sys.stdout.flush()
    elif plain:
        print(plain)


# ---------------- 小工具 ----------------


def human(n):
    try:
        n = float(n)
    except Exception:
        return '-'
    for u in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return ('%.1f %s' % (n, u)) if n < 10 else ('%.0f %s' % (n, u))
        n /= 1024
    return '%.1f TB' % n


def dur(sec):
    try:
        sec = int(sec)
    except Exception:
        return '-'
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return '%d:%02d:%02d' % (h, m, s)
    return '%d:%02d' % (m, s)


def viewers(n):
    try:
        n = int(n)
    except Exception:
        return '-'
    if n >= 100000000:
        return '%.1f 亿' % (n / 100000000.0)
    if n >= 10000:
        return '%.1f 万' % (n / 10000.0)
    return str(n)


def pretty_date(v):
    d = str(v or '')
    if len(d) == 8 and d.isdigit():
        return '%s-%s-%s' % (d[:4], d[4:6], d[6:8])
    return d


def fmt_size_and_speed(size, speed):
    parts = []
    if size:
        parts.append(size)
    if speed:
        parts.append(speed)
    return ' · '.join(parts)


# ---------------- 子进程 ----------------


def run_capture(args, timeout=300):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        txt = (p.stdout or b'').decode('utf-8', 'replace') + (p.stderr or b'').decode('utf-8', 'replace')
        return p.returncode, txt
    except subprocess.TimeoutExpired:
        return -1, '命令超时'
    except Exception as e:
        return -1, str(e)


def run_stream(args, on_line=None):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors='replace', bufsize=1)
    for line in p.stdout:
        line = line.rstrip()
        if on_line:
            on_line(line)
    p.wait()
    return p.returncode


def run_stream_tick(args, on_line=None, tick=None, interval=0.12, timeout=None):
    """逐行读输出；空闲时调用 tick() 转 spinner。timeout 单位秒。"""
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors='replace', bufsize=1)
    q = queue.Queue()

    def reader():
        try:
            for line in p.stdout:
                q.put(line.rstrip())
        finally:
            q.put(None)

    threading.Thread(target=reader, daemon=True).start()
    start = time.time()
    while True:
        try:
            line = q.get(timeout=interval)
        except queue.Empty:
            if timeout and (time.time() - start) > timeout:
                try:
                    p.kill()
                except Exception:
                    pass
                return -1
            if tick:
                tick(time.time() - start)
            continue
        if line is None:
            break
        if on_line:
            on_line(line)
    p.wait()
    return p.returncode


# ---------------- 路径与命名 ----------------


def pick_out_dir():
    home = os.path.expanduser('~')
    cands = []
    env = os.environ.get('YTDL_OUT_DIR')
    if env:
        cands.append(env)
    cands.append('/sdcard/Download/YouTube')
    cands.append(os.path.join(home, 'storage', 'downloads', 'YouTube'))
    cands.append(os.path.join(home, 'storage', 'shared', 'Download', 'YouTube'))
    cands.append(os.path.join(home, 'YouTube'))
    for c in cands:
        try:
            os.makedirs(c, exist_ok=True)
            f = open(os.path.join(c, '.wtest'), 'w')
            f.write('x')
            f.close()
            os.remove(os.path.join(c, '.wtest'))
            return c
        except Exception:
            continue
    return ''


def safe_name(name, max_len=70):
    name = (name or 'video').strip()
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '#', '&', ';', '%', '\n', '\r', '\t']:
        name = name.replace(ch, ' ')
    while '  ' in name:
        name = name.replace('  ', ' ')
    name = name.strip().lstrip('. ').rstrip('. ')
    if not name:
        name = 'video'
    return name[:max_len]


def unique_path(d, base, ext):
    p = os.path.join(d, base + ext)
    i = 1
    while os.path.exists(p):
        p = os.path.join(d, base + '_' + str(i) + ext)
        i += 1
    return p


# ---------------- mp4 容器解析（不依赖 ffprobe） ----------------


def _boxes(buf, start, end):
    i = start
    out = []
    while i + 8 <= end:
        size = int.from_bytes(buf[i:i + 4], 'big')
        typ = buf[i + 4:i + 8]
        if size == 1:
            if i + 16 > end:
                break
            size = int.from_bytes(buf[i + 8:i + 16], 'big')
            hdr = 16
        elif size == 0:
            size = end - i
            hdr = 8
        else:
            hdr = 8
        if size < hdr or i + size > end:
            break
        out.append((typ, i + hdr, i + size))
        i += size
    return out


_MP4_CODEC = {
    b'mp4a': 'aac', b'Opus': 'opus', b'opus': 'opus', b'alac': 'alac',
    b'ec-3': 'eac3', b'ac-3': 'ac3', b'sowt': 'pcm',
    b'avc1': 'h264', b'avc3': 'h264', b'hvc1': 'hevc', b'hev1': 'hevc',
    b'vp09': 'vp9', b'av01': 'av1', b'mp4v': 'mpeg4',
}


def _parse_moov(buf, s_, e_):
    vcodec = acodec = None
    for typ, ps, pe in _boxes(buf, s_, e_):
        if typ != b'trak':
            continue
        hand = None
        codec = None
        for t2, p2, e2 in _boxes(buf, ps, pe):
            if t2 != b'mdia':
                continue
            for t3, p3, e3 in _boxes(buf, p2, e2):
                if t3 == b'hdlr':
                    hand = buf[p3 + 8:p3 + 12]
                elif t3 == b'minf':
                    for t4, p4, e4 in _boxes(buf, p3, e3):
                        if t4 != b'stbl':
                            continue
                        for t5, p5, e5 in _boxes(buf, p4, e4):
                            if t5 == b'stsd':
                                off = p5 + 8
                                if off + 8 <= e5:
                                    codec = buf[off + 4:off + 8]
        name = _MP4_CODEC.get(codec or b'', (codec or b'').decode('latin-1') or None)
        if hand == b'vide' and not vcodec:
            vcodec = name
        elif hand == b'soun' and not acodec:
            acodec = name
    return vcodec, acodec


def mp4_info(path):
    """纯 Python 解析 mp4 容器，返回 (vcodec, acodec)。不依赖 ffprobe / ffmpeg。"""
    try:
        size = os.path.getsize(path)
    except Exception:
        return None, None
    chunks = []
    try:
        with open(path, 'rb') as f:
            head_buf = f.read(4 * 1024 * 1024)
            chunks.append(head_buf)
            if size > 8 * 1024 * 1024:
                f.seek(size - 4 * 1024 * 1024)
                chunks.append(f.read())
    except Exception:
        return None, None
    for buf in chunks:
        idx = 0
        while True:
            j = buf.find(b'moov', idx)
            if j < 0:
                break
            mstart = j - 4
            if mstart >= 0:
                msize = int.from_bytes(buf[mstart:mstart + 4], 'big')
                mend = len(buf) if (msize < 8 or mstart + msize > len(buf)) else mstart + msize
                v, a = _parse_moov(buf, mstart + 8, mend)
                if v or a:
                    return v, a
            idx = j + 4
    return None, None


# ---------------- ffmpeg / ffprobe 挑选 ----------------


def pick_ffmpeg():
    """项目 bin/ 优先（静态版不受 Termux 库问题影响），其次系统。"""
    base = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(base, 'bin', 'ffmpeg')]
    w = shutil.which('ffmpeg')
    if w:
        cands.append(w)
    cands.append('/usr/bin/ffmpeg')
    for c in cands:
        if not os.path.exists(c):
            continue
        rc, t = run_capture([c, '-version'], 60)
        low = t.lower()
        if 'version' in low and 'cannot link' not in low:
            return c, True
    return cands[0], False


def pick_ffprobe(ffpath):
    base = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(base, 'bin', 'ffprobe')]
    w = shutil.which('ffprobe')
    if w:
        cands.append(w)
    if ffpath:
        cands.append(os.path.join(os.path.dirname(ffpath), 'ffprobe'))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return ''


def media_info(path, ffprobe, ffmpeg):
    """优先纯 Python 解析 mp4；再退 ffprobe / ffmpeg。返回 (vcodec, acodec)。"""
    ext = os.path.splitext(str(path))[1].lower()
    if ext in ('.mp4', '.m4a', '.mov'):
        v0, a0 = mp4_info(path)
        if v0 or a0:
            return v0, a0
    if ffprobe and os.path.exists(ffprobe):
        rc, t = run_capture([ffprobe, '-v', 'error', '-show_entries',
                             'stream=codec_type,codec_name', '-of', 'csv=p=0', path], 180)
        if rc == 0 and t.strip():
            v = a = None
            for line in t.strip().splitlines():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    if parts[0] == 'video' and not v:
                        v = parts[1]
                    elif parts[0] == 'audio' and not a:
                        a = parts[1]
            if v or a:
                return v, a
    if ffmpeg and os.path.exists(ffmpeg):
        rc, t = run_capture([ffmpeg, '-hide_banner', '-i', path], 180)
        v = a = None
        for line in t.splitlines():
            ln = line.strip()
            if not ln.startswith('Stream #'):
                continue
            if 'Video:' in ln and not v:
                v = ln.split('Video:')[1].strip().split(',')[0].strip().split(' ')[0]
            elif 'Audio:' in ln and not a:
                a = ln.split('Audio:')[1].strip().split(',')[0].strip().split(' ')[0]
        return v, a
    return None, None


def to_aac(ffmpeg, path):
    """只把音频转成 AAC（视频流直接复制，很快）。成功返回新文件路径。"""
    out = os.path.splitext(path)[0] + '.aac.mp4'
    rc, t = run_capture([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', path,
                         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                         '-movflags', '+faststart', out], timeout=3600)
    if rc == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
        try:
            os.remove(path)
        except Exception:
            pass
        return out
    return None


def has_single_file(yt, url):
    """这个视频有没有「自带音轨的单文件流」（很多视频已经没有，不能想当然）。"""
    rc, t = run_capture([yt, '--simulate', '--no-warnings'] + compat_args()
                        + ['-f', 'b', '--print', '%(format_id)s', url], 180)
    return rc == 0 and bool(t.strip())


def refetch_with_audio(yt, ff, url, work, on_line=None):
    """成品没有音轨时，改用「自带声音的单文件流」重下；没有这种流则返回 None。"""
    if not has_single_file(yt, url):
        return None
    sel = 'b[ext=mp4]/b'
    c = [yt, '--no-playlist', '--newline'] + compat_args() + ['-f', sel,
         '--merge-output-format', 'mp4', '--remux-video', 'mp4']
    if os.path.dirname(ff):
        c += ['--ffmpeg-location', os.path.dirname(ff)]
    c += ['-o', os.path.join(work, 'retry-audio.%(ext)s'), url]
    try:
        run_stream(c, on_line)
    except Exception:
        return None
    best = None
    for f in glob.glob(os.path.join(work, 'retry-audio*')):
        b = os.path.basename(f)
        if b.startswith('.') or '.f' in b:
            continue
        if os.path.splitext(f)[1].lower() not in ('.mp4', '.mkv', '.webm', '.m4a'):
            continue
        best = f
    return best


# ---------------- 解析（流式） ----------------

_STAGES = [
    ('Downloading webpage', '读取视频页面'),
    ('Downloading player', '加载播放器脚本'),
    ('Downloading API JSON', '读取视频信息'),
    ('Downloading tv client', '加载客户端配置'),
    ('Downloading initial data', '读取初始数据'),
    ('Downloading ios client', '加载客户端配置'),
    ('Extracting URL', '解析链接'),
    ('[youtube]', '解析视频信息'),
    ('[generic]', '识别链接'),
]


def _stage_of(line):
    for key, txt in _STAGES:
        if key in line:
            return txt
    return ''


COOKIES = None
_JS_ARGS = None


def pick_ytdlp():
    """优先用项目自带的 bin/yt-dlp（自检会自动更新到最新版），其次 PATH 里的。"""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        here = ''
    cand = os.path.join(here, 'bin', 'yt-dlp')
    if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
        return cand
    return shutil.which('yt-dlp') or '/usr/local/bin/yt-dlp'


def pick_cookies():
    """找一个可用的 cookies.txt（环境变量优先，其次常见路径）。"""
    cands = []
    v = os.environ.get('YTDL_COOKIES')
    if v:
        cands.append(v)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        here = ''
    cands += [
        os.path.join(here, 'cookies.txt'),
        os.path.expanduser('~/cookies.txt'),
        '/sdcard/Download/cookies.txt',
        os.path.expanduser('~/storage/downloads/cookies.txt'),
        os.path.expanduser('~/storage/shared/Download/cookies.txt'),
    ]
    for c in cands:
        try:
            if c and os.path.isfile(c) and os.path.getsize(c) > 0:
                return c
        except Exception:
            pass
    return None


def pick_jsargs():
    """deno 是 yt-dlp 默认启用的 JS 运行时；只有其它运行时时需要显式指定。"""
    for name, args in (('deno', []),
                       ('bun', ['--js-runtimes', 'bun']),
                       ('node', ['--js-runtimes', 'node']),
                       ('qjs', ['--js-runtimes', 'quickjs'])):
        if shutil.which(name):
            return args
    return []


def compat_args():
    """所有 yt-dlp 调用都附带的参数（cookies / JS 运行时）。"""
    a = []
    if COOKIES:
        a += ['--cookies', COOKIES]
    if _JS_ARGS:
        a += _JS_ARGS
    return a


def guide_bot(err):
    """YouTube 风控提示：教用户怎么把 cookies 弄到手。"""
    t = str(err).lower()
    if not ('sign in' in t or 'bot' in t or 'login' in t or 'cookie' in t):
        return
    print()
    print('  ' + YELLOW + 'YouTube 认为这次请求像机器人，带上浏览器 cookies 就能过：' + RESET)
    print('   ' + GRAY + '1) 手机上装 Kiwi Browser，加扩展 “Get cookies.txt LOCALLY”' + RESET)
    print('   ' + GRAY + '2) 打开 youtube.com 并登录，用扩展导出 cookies.txt' + RESET)
    print('   ' + GRAY + '3) 把文件放到 /sdcard/Download/cookies.txt' + RESET)
    print('   ' + GRAY + '4) 重新运行 ytdl（会自动识别）' + RESET)
    print('   ' + GRAY + '   也可手动指定： ytdl --cookies /sdcard/Download/cookies.txt "链接"' + RESET)
    print('   ' + GRAY + '先换个网络（Wi-Fi ⇄ 流量）再试一次，有时也能过。' + RESET)
    print()


def print_cookie_help():
    """`ytdl cookies`：看状态 + 教怎么导出自己的 cookies。"""
    c = pick_cookies()
    print()
    print(' ' + BOLD + ACC + 'cookies' + RESET)
    print()
    if c:
        print(' ' + GREEN + '✓ 已找到：' + RESET + c)
        print('  ' + GRAY + 'ytdl 会自动带上它，不用加任何参数。' + RESET)
    else:
        print(' ' + YELLOW + '✗ 还没有找到 cookies.txt' + RESET)
        print('  ' + GRAY + '不带 cookies 时，YouTube 常会要求“确认你不是机器人”。' + RESET)
    print()
    print('  ' + GRAY + '导出自己的 cookies（1 分钟）：' + RESET)
    print('  ' + GRAY + '1) 装 Kiwi Browser，加扩展 “Get cookies.txt LOCALLY”' + RESET)
    print('  ' + GRAY + '2) 打开 youtube.com 并登录，用扩展导出 cookies.txt' + RESET)
    print('  ' + GRAY + '3) 把文件放到 /sdcard/Download/cookies.txt' + RESET)
    print()
    print('  ' + GRAY + '也可以手动指定： ytdl --cookies <路径> "链接"' + RESET)
    print('  ' + GRAY + '或设环境变量： YTDL_COOKIES=<路径> ytdl "链接"' + RESET)
    print()
    print('  ' + YELLOW + '注意：cookies 等于你账号的钥匙 —— 别提交到仓库，也别分享给别人。' + RESET)
    print()


def probe_stream(yt, url):
    """解析视频信息：把 yt-dlp 的原始输出直接流式显示出来。"""
    buf = []
    logs = []

    def on_line(line):
        s = line.rstrip()
        st = s.strip()
        if not st:
            return
        if st.startswith('{'):
            buf.append(st)          # JSON 数据本身不显示
            return
        if st.startswith('ERROR'):
            logs.append(st)
            raw_line(st, RED)
            return
        if st.startswith('WARNING'):
            logs.append(st)
            if 'JavaScript runtime' not in st:
                raw_once(st[:70], st, YELLOW)
            return
        # 只外露 yt-dlp 的原生信息行，过滤 [debug] 之类的噪声
        if not st.startswith(('[youtube]', '[info]', '[hlsnative]', '[generic]',
                              '[vimeo]', '[soundcloud]', '[bilibili]', '[twitter]')):
            return
        raw_line(st)

    def tick(elapsed):
        if elapsed > 2.0:
            spin_step('%.1fs' % elapsed)

    try:
        run_stream_tick([yt, '-J', '--verbose', '--no-playlist', '--newline']
                        + compat_args() + [url],
                        on_line, tick, interval=0.15, timeout=300)
    finally:
        spin_done()
    txt = ''.join(buf)
    i = txt.find('{')
    if i < 0:
        msg = logs[-1][:200] if logs else '没有返回数据'
        raise RuntimeError('解析失败：' + msg)
    return json.loads(txt[i:])


def formats_of(info):
    by = {}
    for f in (info.get('formats') or []):
        v = str(f.get('vcodec') or 'none')
        if v == 'none' or not f.get('format_id'):
            continue
        w = int(f.get('width') or 0)
        h = int(f.get('height') or 0)
        if w <= 0 or h <= 0:
            continue
        short = min(w, h)
        tbr = float(f.get('tbr') or 0)
        is_avc = v.startswith('avc') or ('h264' in v)
        cur = by.get(short)
        better = False
        if cur is None:
            better = True
        elif is_avc and not cur['avc']:
            better = True
        elif is_avc == cur['avc'] and tbr > cur['tbr']:
            better = True
        if better:
            by[short] = {'id': str(f['format_id']), 'short': short, 'w': w, 'h': h,
                         'tbr': tbr, 'avc': is_avc, 'vcodec': v,
                         'size': int(f.get('filesize') or 0),
                         'note': str(f.get('format_note') or '')}
    return [by[k] for k in sorted(by.keys(), reverse=True)]


# ---------------- 交互 ----------------


def ask(prompt, default=''):
    try:
        s = input(' ' + ACC + prompt + RESET).strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return s or default


def ask_num(prompt, n, default=1):
    while True:
        s = ask(prompt, str(default))
        if s.isdigit() and 1 <= int(s) <= n:
            return int(s)
        if s.lower() in ('q', 'quit', 'exit'):
            return -1
        warn('请输入 1 - %d 之间的数字（q 退出）' % n)


# ---------------- 展示 ----------------


BIG_TITLE = [
    '██╗   ██╗████████╗██████╗ ██╗',
    '╚██╗ ██╔╝╚══██╔══╝██╔══██╗██║',
    ' ╚████╔╝    ██║   ██║  ██║██║',
    '  ╚██╔╝     ██║   ██║  ██║██║',
    '   ██║      ██║   ██████╔╝███████╗',
    '   ╚═╝      ╚═╝   ╚═════╝ ╚══════╝',
]


def show_banner(ytver, ff_ok, ffpath, out_dir):
    """多行 ASCII 大字标题 + 右上角署名"""
    w = term_width()
    blk = max(dwidth(x) for x in BIG_TITLE)
    sign = 'by xfgken'
    print()
    if w >= 40:
        room = (w >= blk + dwidth(sign) + 8)
        for i, ln in enumerate(BIG_TITLE):
            col = ACC_D if i in (0, 1) else ACC
            extra = ''
            if i == 0 and room:
                extra = '  ' + ACC + sign + RESET
            print('  ' + BOLD + col + ln + RESET + extra)
    else:
        tail = ('  ' + ACC + sign + RESET) if w >= 26 else ''
        print('  ' + BOLD + ACC + 'ytdl' + RESET + tail)
    print('  ' + GRAY + 'YouTube 下载器 · Termux 版' + RESET)


def show_checks(ytver, ff_ok, ffpath, out_dir):
    """就位状态：✓ 就位 / ✗ 未就位"""

    def row(good, name, extra=''):
        mark = (GREEN + '✓' + RESET) if good else (RED + '✗' + RESET)
        tail = (GRAY + '  ' + extra + RESET) if extra else ''
        print('  ' + mark + ' ' + WHITE + name + RESET + tail)

    row(True, 'python ' + sys.version.split()[0])
    row(bool(ytver and ytver != '?'), 'yt-dlp ' + (ytver or '未安装'))
    if ff_ok:
        row(True, 'ffmpeg', ffpath)
    else:
        row(False, 'ffmpeg 未就位', '无法合并音视频 → pkg upgrade -y')
    js = ''
    for j in ('deno', 'node', 'qjs', 'bun'):
        if shutil.which(j):
            js = j
            break
    if js:
        row(True, 'JS 运行时 ' + js)
    else:
        row(False, 'JS 运行时缺失', '建议： pkg install deno')
    print(GRAY + '  ' + out_dir + RESET)


def show_info(info, fmts=None):
    """解析结果：带标签的详细信息"""
    title = str(info.get('title') or '(无标题)')
    lim = max(20, term_width() - 10)
    lines = wrap(title, lim)
    print('  ' + ACC + pad('标题：', 10) + RESET + BOLD + WHITE + lines[0] + RESET)
    for ln in lines[1:]:
        print('  ' + ' ' * 10 + BOLD + WHITE + ln + RESET)

    def row(label, value):
        print('  ' + ACC + pad(label + '：', 10) + RESET + WHITE + value + RESET)

    if info.get('uploader'):
        row('作者', str(info['uploader']))
    if info.get('duration'):
        row('时长', dur(info['duration']))
    if info.get('view_count'):
        row('观看', viewers(info['view_count']) + '次')
    d = pretty_date(info.get('upload_date'))
    if d:
        row('发布', d)
    if fmts:
        row('清晰度', '共 %d 档，最高 %dp' % (len(fmts), fmts[0]['short']))


def show_formats(fmts, default=0):
    for i, f in enumerate(fmts):
        tag = '原生 H.264' if f['avc'] else '需转码'
        size = ('≈ ' + human(f['size'])) if f['size'] else ''
        left = '%d) ' % (i + 1) + pad('%4sp' % f['short'], 7) + pad('%d×%d' % (f['w'], f['h']), 12)
        tail = tag + (('  ' + size) if size else '')
        print('  ' + WHITE + left + RESET + GRAY + tail + RESET)


def show_formats_choice(mode, default=1):
    items = [
        ('视频 MP4', 'H.264 + AAC'),
        ('仅音频 M4A', '只要声音'),
        ('视频原画', '不转码，最快'),
    ]
    for i, (name, desc) in enumerate(items):
        print('  ' + WHITE + '%d) ' % (i + 1) + name + RESET +
              GRAY + ' · ' + desc + RESET)


def show_summary(title, res_label, mode, size):
    names = {1: '视频 MP4（H.264 + AAC）', 2: '仅音频 M4A', 3: '视频原画（不转码）'}
    lim = max(20, term_width() - 2)
    for ln in wrap(title, lim)[:2]:
        bullet(ln, hot=True)
    extra = []
    if res_label:
        extra.append(res_label)
    extra.append(names.get(mode, '视频'))
    if size:
        extra.append('≈ ' + human(size))
    print()
    bullet(' · '.join(extra))


# ---------------- 主流程 ----------------


def main():
    args = [a for a in sys.argv[1:]]
    auto = False
    if '-y' in args or '--yes' in args:
        auto = True
        args = [a for a in args if a not in ('-y', '--yes')]
    # --cookies <文件> / --cookies=<文件>：手动指定 cookies.txt
    for i in range(len(args)):
        a = args[i]
        if a == '--cookies' and i + 1 < len(args):
            os.environ['YTDL_COOKIES'] = args[i + 1]
            del args[i:i + 2]
            break
        if a.startswith('--cookies='):
            os.environ['YTDL_COOKIES'] = a.split('=', 1)[1]
            del args[i]
            break
    url_arg = args[0] if args else ''
    if url_arg in ('cookies', 'cookie', '--cookies-help'):
        print_cookie_help()
        return 0

    global COOKIES, _JS_ARGS
    COOKIES = pick_cookies()
    _JS_ARGS = pick_jsargs()

    yt = pick_ytdlp()
    ff, FF_OK = pick_ffmpeg()
    if not shutil.which('yt-dlp') and not os.path.exists(yt):
        bad('未找到 yt-dlp，请先运行：  sh install.sh')
        return 1

    out_dir = pick_out_dir() or os.path.expanduser('~/Downloads')
    tmp_root = os.path.join(os.path.expanduser('~'), '.ytdl-work')
    try:
        os.makedirs(tmp_root, exist_ok=True)
    except Exception:
        tmp_root = os.path.join(out_dir, '.work')
        os.makedirs(tmp_root, exist_ok=True)

    vtxt = '?'
    rc0, t0 = run_capture([yt, '--version'], 30)
    if t0.strip():
        vtxt = t0.strip().splitlines()[0]
    show_banner(vtxt, FF_OK, ff, out_dir)
    print()
    show_checks(vtxt, FF_OK, ff, out_dir)
    if COOKIES:
        print('  ' + GRAY + 'cookies ' + COOKIES + RESET)
    else:
        print('  ' + YELLOW + 'cookies 未提供（YouTube 要求验证时会失败，运行 ytdl cookies 看指引）'
              + RESET)

    while True:
        if auto and not url_arg:
            break
        url = url_arg or ask('请输入解析的链接（q 退出）> ')
        url_arg = ''
        if not url or url.lower() in ('q', 'quit', 'exit'):
            break
        if ' ' in url.strip():
            warn('这看起来不是视频链接（里面有空格）—— 要执行终端命令，请先输入 q 退出本程序。')
            print()
            continue

        # ---------- ① 解析 ----------
        section('开始解析')
        try:
            info = probe_stream(yt, url)
        except Exception as e:
            bad(str(e))
            if not COOKIES:
                guide_bot(e)
            continue

        fmts = formats_of(info)
        show_info(info, fmts)
        chosen = None
        if fmts:
            show_formats(fmts, 0)
            print()
            if auto:
                pick = 1
            else:
                pick = ask_num('请选择清晰度 [1]: ', len(fmts), 1)
                if pick < 0:
                    break
            chosen = fmts[pick - 1]

        # ---------- 格式选择 ----------
        section('格式')
        show_formats_choice(1, 1)
        print()
        if auto:
            fmt_mode = 1
        else:
            fmt_mode = ask_num('请选择 [1]: ', 3, 1)
            if fmt_mode < 0:
                break

        work = os.path.join(tmp_root, 'job-' + str(int(time.time())))
        os.makedirs(work, exist_ok=True)
        label = (str(chosen['short']) + 'p') if chosen else ''
        picked_size = chosen['size'] if chosen else 0

        cmd = [yt, '--no-playlist', '--newline'] + compat_args()
        if not FF_OK:
            if fmt_mode == 2:
                warn('ffmpeg 不可用，无法转成 M4A，将直接下载原始音频流。')
                cmd += ['-f', 'ba']
                title_show = '仅音频（原始流）'
            else:
                spin_step('检查是否有「自带声音的单文件流」…')
                ok_single = has_single_file(yt, url)
                spin_done()
                if ok_single:
                    warn('ffmpeg 不可用 → 无法合并音视频，已改用「自带声音的单文件流」'
                         '（画质可能偏低，但保证有声音）。')
                    cmd += ['-f', 'b[ext=mp4]/b']
                    title_show = '视频（单文件流 · 带声音）'
                    label = ''
                else:
                    bad('这个视频没有「自带声音的单文件流」，'
                        '必须用 ffmpeg 合并音视频才能做出带声音的成品。')
                    bad('请先修好 ffmpeg（Termux）：  pkg upgrade -y')
                    bad('若还不行：  pkg install -y --reinstall libc++ libplacebo ffmpeg')
                    bad('修好后重新运行即可。本次跳过，不生成无声文件。')
                    print()
                    continue
        elif fmt_mode == 2:
            cmd += ['-f', 'ba/b', '-x', '--audio-format', 'm4a', '--audio-quality', '0']
            title_show = '仅音频 M4A'
        else:
            if chosen:
                cid = chosen['id']
                sel = ('%s+ba[acodec^=mp4a]/%s+ba[acodec^=aac]/%s+ba' % (cid, cid, cid))
                need_tc = (fmt_mode == 1) and (not chosen['avc'])
            else:
                sel = ('bv*[ext=mp4]+ba[acodec^=mp4a]/bv*+ba[acodec^=aac]/'
                       'bv*[ext=mp4]+ba/bv*+ba/b[acodec!=none]/b')
                need_tc = False
            cmd += ['-f', sel, '--merge-output-format', 'mp4', '--remux-video', 'mp4']
            if need_tc:
                cmd += ['--recode-video', 'mp4']
            title_show = ('视频 MP4 · ' + label) if fmt_mode == 1 else ('视频原画 · ' + (label or '最佳'))
        if os.path.dirname(ff):
            cmd += ['--ffmpeg-location', os.path.dirname(ff)]
        cmd += ['-o', os.path.join(work, '%(title).70s.%(ext)s'), url]

        # ---------- 确认 ----------
        if not auto:
            show_summary(str(info.get('title') or ''), label, fmt_mode, picked_size)
            ans = ask('按回车开始制作（q 返回）> ', '')
            if ans.lower() in ('q', 'quit', 'exit'):
                print()
                continue

        # ---------- 制作（原样流式） ----------
        section('开始制作')
        print(GRAY + '  ' + title_show + RESET)

        state = {'cur': '视频流' if fmt_mode != 2 else '音频流',
                 'dest_n': 0, 'last': 0.0, 'done': False, 'fin': set()}

        def stage_done_text():
            return state['cur'] + '下载完成'

        def on_line(line):
            s = line.rstrip()
            st = s.strip()
            if not st:
                return
            # 进度行：原样显示，只是原地刷新
            if (st.startswith('[download]') and '%' in st and ' of ' in st
                    and 'Destination' not in st):
                w = term_width()
                show = st if len(st) <= w - 3 else st[:max(10, w - 6)] + '…'
                if TTY:
                    sys.stdout.write('\r' + KILL + GRAY + '  ' + show + RESET)
                    sys.stdout.flush()
                elif '100%' in st:
                    print(GRAY + '  ' + show + RESET)
                return
            if st.startswith('ERROR'):
                raw_line(st, RED)
                return
            if st.startswith('WARNING'):
                if 'JavaScript runtime' in st:
                    raw_once('js-hint',
                             'yt-dlp 提示：缺少 JS 运行时（deno）→ pkg install deno',
                             YELLOW)
                else:
                    raw_once(st[:70], st, YELLOW)
                return
            raw_line(st)

        rc = run_stream(cmd, on_line)
        spin_done()
        if TTY and not state['done']:
            sys.stdout.write('\r' + KILL)
            sys.stdout.flush()

        files = []
        for f in glob.glob(os.path.join(work, '*')):
            b = os.path.basename(f)
            if b.startswith('.'):
                continue
            if os.path.splitext(f)[1].lower() in ('.mp4', '.m4a', '.mkv', '.webm'):
                files.append(f)
        if rc != 0 or not files:
            bad('制作失败（退出码 %s）' % rc)
            continue

        src = files[0]
        for f in files:
            if '.f' not in os.path.basename(f):
                src = f
                break

        # ---- 音轨校验（静默，只在需要处理时说话）----
        fp_path = pick_ffprobe(ff)
        vcodec, acodec = media_info(src, fp_path, ff)
        if not (vcodec or acodec):
            warn('检测不到音轨信息（ffprobe / ffmpeg 都不可用）—— 建议： pkg upgrade -y')
        elif not acodec:
            warn('这个成品里没有音轨，正在改用「自带声音的单文件流」重新下载…')
            newf = refetch_with_audio(yt, ff, url, work, on_line=None)
            if newf:
                src = newf
                vcodec, acodec = media_info(src, fp_path, ff)
        if not acodec:
            if FF_OK:
                warn('这个视频源本身可能就没有声音（YouTube 上确实有静音视频）')
            else:
                warn('没有可用的 ffmpeg，合并音视频这一步做不了 → 请先修复：  pkg upgrade -y')
        elif acodec.lower() not in ('aac', 'mp4a', 'mp3'):
            raw_line('[fix] 音频 %s 手机常放不出声 → 转成 AAC（视频不重编码）' % acodec,
                     YELLOW)
            fixed = to_aac(ff, src)
            if fixed:
                src = fixed
                vcodec, acodec = media_info(src, fp_path, ff)
                if acodec:
                    ok('音频已转成 %s' % acodec)
            else:
                warn('音频转换失败，文件保持原样')
        else:
            ok('音轨正常：%s + %s' % (vcodec or '?', acodec))

        ext = os.path.splitext(src)[1].lower()
        base = safe_name(os.path.splitext(os.path.basename(src))[0])
        if fmt_mode == 2:
            base += ' 音频'
        elif label:
            base += '_' + label
        dst = unique_path(out_dir, base, ext)
        try:
            shutil.move(src, dst)
        except Exception as e:
            bad('移动到成品目录失败：' + str(e))
            continue
        shutil.rmtree(work, ignore_errors=True)

        # ---------- 完成 ----------
        size = os.path.getsize(dst)
        print(GREEN + '✓ 完成' + RESET)
        bullet(os.path.basename(dst), hot=True)
        bullet(os.path.dirname(dst))
        line2 = [human(size), dur(info.get('duration'))]
        if vcodec:
            line2.append(vcodec)
        if chosen:
            line2.append('%d×%d' % (chosen['w'], chosen['h']))
        if acodec:
            line2.append(acodec)
        bullet(' · '.join([x for x in line2 if x]))
        print()

        if auto:
            break
        if ask('继续下一个链接？[y/N]: ', 'n').lower() not in ('y', 'yes'):
            break
        print()

    print()
    note('文件都在 ' + out_dir)
    print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(chr(10) + '  已取消。')
        sys.exit(130)
