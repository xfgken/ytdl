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
import shutil
import subprocess
import sys
import time

ESC = chr(27)
BOLD = ESC + '[1m'
DIM = ESC + '[2m'
GREEN = ESC + '[32m'
YELLOW = ESC + '[33m'
RED = ESC + '[31m'
CYAN = ESC + '[36m'
RESET = ESC + '[0m'


def out(m=''):
    print(m)


def head(m):
    print(BOLD + CYAN + m + RESET)


def ok(m):
    print(GREEN + '  ✓ ' + RESET + m)


def warn(m):
    print(YELLOW + '  ! ' + RESET + m)


def bad(m):
    print(RED + '  ✗ ' + m + RESET)


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


def media_info(path, ffprobe, ffmpeg):
    """读取成品里的视频/音频编码。返回 (vcodec, acodec)，取不到返回 (None, None)。"""
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


def refetch_with_audio(yt, ff, url, work, on_line=None):
    """成品没有音轨时，改用「自带声音的单文件流」重新下载一次。"""
    sel = 'b[ext=mp4][acodec!=none]/b[acodec!=none]/b'
    c = [yt, '--no-playlist', '--newline', '-f', sel,
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


def probe(yt, url):
    rc, txt = run_capture([yt, '-J', '--no-warnings', '--no-playlist', url], timeout=240)
    i = txt.find('{')
    if i < 0:
        raise RuntimeError('解析失败：' + (txt.strip()[:280] or '没有返回数据'))
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


def ask(prompt, default=''):
    try:
        s = input(BOLD + prompt + RESET).strip()
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


def bar(pct, width=28):
    pct = max(0.0, min(100.0, float(pct)))
    fill = int(width * pct / 100.0)
    return '[' + ('#' * fill) + ('-' * (width - fill)) + '] %5.1f%%' % pct


def main():
    args = [a for a in sys.argv[1:]]
    auto = False
    if '-y' in args or '--yes' in args:
        auto = True
        args = [a for a in args if a not in ('-y', '--yes')]
    url_arg = args[0] if args else ''

    yt = shutil.which('yt-dlp') or '/usr/local/bin/yt-dlp'
    ff = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'
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

    print()
    head('=' * 58)
    head('  ytdl · YouTube 下载器（Termux）')
    head('=' * 58)
    vtxt = '?'
    if shutil.which('yt-dlp'):
        rc0, t0 = run_capture([yt, '--version'], 30)
        if t0.strip():
            vtxt = t0.strip().splitlines()[0]
    print('  yt-dlp : %s' % vtxt)
    print('  ffmpeg : %s' % ('已就绪' if (shutil.which('ffmpeg') or os.path.exists(ff)) else '未找到（合并会失败）'))
    print('  保存到 : %s' % out_dir)
    print()

    while True:
        url = url_arg or ask('请粘贴视频链接（q 退出）> ')
        url_arg = ''
        if not url or url.lower() in ('q', 'quit', 'exit'):
            break

        print()
        print(DIM + '  正在解析，请稍候…' + RESET)
        try:
            info = probe(yt, url)
        except Exception as e:
            bad(str(e))
            continue

        print()
        head('  ' + str(info.get('title') or '(无标题)'))
        meta = []
        if info.get('uploader'):
            meta.append(str(info['uploader']))
        if info.get('duration'):
            meta.append('时长 ' + dur(info['duration']))
        if info.get('view_count'):
            meta.append(str(info['view_count']) + ' 次观看')
        print(DIM + '  ' + ' | '.join(meta) + RESET)
        print()

        fmts = formats_of(info)
        chosen = None
        if fmts:
            print('  可选分辨率：')
            for i, f in enumerate(fmts, 1):
                tag = '原生 H.264' if f['avc'] else '需转码'
                extra = ''
                if f['size']:
                    extra = ' · 约 ' + human(f['size'])
                elif f['note']:
                    extra = ' · ' + f['note']
                print('   %2d) %-6s %-10s %dx%d%s' % (i, str(f['short']) + 'p', tag, f['w'], f['h'], extra))
            print()
            if auto:
                pick = 1
            else:
                pick = ask_num('  请选择分辨率 [1]: ', len(fmts), 1)
                if pick < 0:
                    break
            chosen = fmts[pick - 1]
            print()

        print('  输出格式：')
        print('    1) 视频 MP4（H.264 + AAC，手机直接能播）')
        print('    2) 仅音频 M4A')
        print('    3) 视频（保留原始编码，速度最快）')
        print()
        if auto:
            fmt_mode = 1
        else:
            fmt_mode = ask_num('  请选择 [1]: ', 3, 1)
            if fmt_mode < 0:
                break
        print()

        work = os.path.join(tmp_root, 'job-' + str(int(time.time())))
        os.makedirs(work, exist_ok=True)
        label = (str(chosen['short']) + 'p') if chosen else ''

        cmd = [yt, '--no-playlist', '--newline']
        if fmt_mode == 2:
            cmd += ['-f', 'ba/b', '-x', '--audio-format', 'm4a', '--audio-quality', '0']
            title_show = '仅音频 M4A'
        else:
            if chosen:
                cid = chosen['id']
                # 音频优先挑 mp4a/aac：安卓播放器对 mp4 里的 opus 音频往往放不出声
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

        print(BOLD + '  开始制作：' + title_show + RESET)
        print()

        state = {'pct': None, 'last': 0.0}

        def on_line(line):
            if '[download]' in line and '%' in line:
                seg = line.split('[download]')[1].strip()
                num = seg.split('%')[0].strip()
                try:
                    pct = float(num)
                except Exception:
                    return
                now = time.time()
                if pct < 100 and now - state['last'] < 0.2:
                    return
                state['last'] = now
                state['pct'] = pct
                sys.stdout.write(chr(13) + '  ' + GREEN + bar(pct) + RESET + ' ' + seg.split(' of ')[-1][:40] + '    ')
                sys.stdout.flush()
            elif '[Merger]' in line or 'Merging formats' in line:
                print(chr(10) + '  ' + CYAN + '合并音视频…' + RESET)
            elif '[ExtractAudio]' in line:
                print(chr(10) + '  ' + CYAN + '提取音频…' + RESET)
            elif '[VideoRemuxer]' in line:
                print(chr(10) + '  ' + CYAN + '重封装容器…' + RESET)
            elif '[VideoConvertor]' in line:
                print(chr(10) + '  ' + CYAN + '转码中…' + RESET)
            elif line.startswith('ERROR'):
                print(chr(10) + '  ' + RED + line[:150] + RESET)

        rc = run_stream(cmd, on_line)
        if state['pct'] is not None:
            print()

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

        # ---- 成品校验：必须有音轨，而且音频要手机能播 ----
        fp_path = shutil.which('ffprobe') or ''
        if not fp_path:
            cand2 = os.path.join(os.path.dirname(ff), 'ffprobe')
            if os.path.exists(cand2):
                fp_path = cand2
        vcodec, acodec = media_info(src, fp_path, ff)
        if not acodec:
            warn('这个成品里没有音轨，正在改用「自带声音的单文件流」重新下载…')
            newf = refetch_with_audio(yt, ff, url, work, on_line)
            if newf:
                src = newf
                vcodec, acodec = media_info(src, fp_path, ff)
        if not acodec:
            warn('这个视频源本身可能就没有声音（YouTube 上确实有静音视频）')
        elif acodec.lower() not in ('aac', 'mp4a', 'mp3'):
            warn('音频编码是 %s，安卓播放器常常放不出声，正在转成 AAC（视频不重编码）…' % acodec)
            fixed = to_aac(ff, src)
            if fixed:
                src = fixed
                vcodec, acodec = media_info(src, fp_path, ff)
                if acodec:
                    ok('音频已转成 %s' % acodec)
            else:
                warn('音频转换失败，文件保持原样（可能这台设备没装 ffmpeg）')

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

        size = os.path.getsize(dst)
        print()
        ok('完成')
        print('     ' + dst)
        print('     ' + DIM + human(size) + ' · 时长 ' + dur(info.get('duration')) + RESET)
        fp = shutil.which('ffprobe')
        if fp:
            rc2, t2 = run_capture([fp, '-v', 'error', '-show_entries',
                                    'stream=codec_name,width,height,channels', '-of', 'csv=p=0', dst], 60)
            if t2.strip():
                print('     ' + DIM + '轨道 ' + ' / '.join(t2.strip().splitlines()) + RESET)
        print()

        if auto:
            break
        if ask('  继续下一个链接？[y/N]: ', 'n').lower() not in ('y', 'yes'):
            break
        print()

    print()
    print(DIM + '  文件都在：' + out_dir + RESET)
    print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(chr(10) + '  已取消。')
        sys.exit(130)
