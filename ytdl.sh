#!/bin/sh
# ytdl · 启动器
# 每次运行先自检环境（python / yt-dlp / ffmpeg / JS运行时 / 存储权限），缺什么自动装，然后启动
set -u

# 解析脚本真实位置（兼容软链接，例如直接敲 `ytdl` 命令时）
SELF="$0"
while [ -L "$SELF" ]; do
  L=$(readlink "$SELF")
  case "$L" in
    /*) SELF="$L" ;;
    *) SELF="$(dirname "$SELF")/$L" ;;
  esac
done
cd "$(dirname "$SELF")" || exit 1

is_termux=0
if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then is_termux=1; fi

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[33m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

# 下载「自带库的静态 ffmpeg」到项目 bin/：绕开 Termux 的库版本问题
install_static_ffmpeg() {
  mkdir -p bin
  case "$(uname -m)" in
    aarch64|arm64) URL='https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz' ;;
    armv7l|armv7)  URL='https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz' ;;
    *) say '（这个架构没有现成静态包，请手动修复）'; return 1 ;;
  esac
  T="$HOME/.ytdl-tmp"
  mkdir -p "$T"
  if ! curl -L --progress-bar -o "$T/ff.tar.xz" "$URL"; then
    say '下载失败（网络问题）。可稍后重试，或手动：  pkg upgrade -y'
    return 1
  fi
  # 用 python 解压（xz 支持是标准库自带，不依赖外部 tar/xz）
  if ! python3 -c 'import tarfile,sys; tarfile.open(sys.argv[1]).extractall(sys.argv[2])' "$T/ff.tar.xz" "$T"; then
    say '解压失败'; return 1
  fi
  D=$(ls -d "$T"/ffmpeg-*-static 2>/dev/null | head -1)
  if [ -z "$D" ] || [ ! -f "$D/ffmpeg" ]; then say '解压结果不对'; return 1; fi
  cp "$D/ffmpeg" bin/ffmpeg 2>/dev/null || true
  cp "$D/ffprobe" bin/ffprobe 2>/dev/null || true
  chmod 755 bin/ffmpeg bin/ffprobe 2>/dev/null || true
  rm -rf "$T" 2>/dev/null || true
  if bin/ffmpeg -version >/dev/null 2>&1; then
    ok '静态 ffmpeg 就绪（项目 bin/ 内，自带库）'
    return 0
  fi
  rm -f bin/ffmpeg bin/ffprobe
  say '静态版也跑不起来（可能是系统限制），请手动修复 Termux 包'
  return 1
}

# ---------------- 环境自检 ----------------
step '环境自检'
missing=""
JS_MISSING=0
FF_BROKEN=0

PY=""
if have python3; then PY=python3; elif have python; then PY=python; fi
if [ -n "$PY" ]; then ok "python   $(command -v "$PY")"; else bad 'python   未安装'; missing="$missing python"; fi

if [ -x bin/yt-dlp ]; then ok 'yt-dlp   项目 bin/ 内';
elif have yt-dlp; then ok "yt-dlp   $(command -v yt-dlp)";
else bad 'yt-dlp   未安装'; missing="$missing yt-dlp"; fi

# ffmpeg：Termux 里经常“装了却跑不起来”（包与库版本错位），必须实际执行一次才算可用
# 优先用项目自带的 bin/ffmpeg（静态版，不受 Termux 库问题影响）
FF_OK=0
if [ -x bin/ffmpeg ]; then
  if bin/ffmpeg -version >/dev/null 2>&1; then
    FF_OK=1
    ok 'ffmpeg   项目 bin/ 内（自带库）'
  else
    rm -f bin/ffmpeg bin/ffprobe
    say '（项目 bin/ffmpeg 跑不起来，已清掉）'
  fi
fi
if [ "$FF_OK" = '0' ]; then
  if have ffmpeg && ffmpeg -version >/dev/null 2>&1; then
    FF_OK=1
    ok "ffmpeg   $(command -v ffmpeg)"
  elif have ffmpeg; then
    FF_BROKEN=1
    bad 'ffmpeg   已安装但无法运行（库版本错位）'
  else
    bad 'ffmpeg   未安装（无法合并音视频 → 成品会没有声音）'
    missing="$missing ffmpeg"
  fi
fi

# JS 运行时：yt-dlp 新版需要它完整解析 YouTube，缺了会“丢格式”（常见后果：拿不到音频流）
JS_OK=0
for j in deno node qjs bun; do
  if have "$j"; then JS_OK=1; ok "JS运行时  $j"; break; fi
done
if [ "$JS_OK" = '0' ]; then
  JS_MISSING=1
  bad 'JS运行时  缺失（yt-dlp 新版需要，缺了可能丢音频格式）'
fi

# ---------------- 缺失则自动安装 / 修复 ----------------
need_work=0
if [ -n "$missing" ]; then need_work=1; fi
if [ "$JS_MISSING" = '1' ]; then need_work=1; fi
if [ "$FF_BROKEN" = '1' ]; then need_work=1; fi

if [ "$need_work" = '1' ]; then
  msg=''
  if [ -n "$missing" ]; then msg="$missing"; fi
  if [ "$FF_BROKEN" = '1' ]; then msg="$msg 修复ffmpeg"; fi
  if [ "$JS_MISSING" = '1' ]; then msg="$msg 安装JS运行时"; fi
  step "需要处理：$msg"

  if [ "$is_termux" = '1' ]; then
    if [ -n "$missing" ]; then
      say '使用 pkg 安装缺失的包（首次可能会慢一点）…'
      pkg update -y >/dev/null 2>&1 || true
      # shellcheck disable=SC2086
      if ! pkg install -y $missing </dev/null; then
        say '自动安装失败，请手动执行：  pkg install python ffmpeg yt-dlp'
      fi
    fi
    if [ "$JS_MISSING" = '1' ]; then
      say '安装 JS 运行时（deno）…'
      pkg install -y deno </dev/null 2>&1 | tail -2 || say '（deno 没装上也没关系，继续）'
    fi
    if [ "$FF_BROKEN" = '1' ]; then
      # 关键：坏掉的 ffmpeg 安装后脚本会一直失败，并把整个 dpkg 操作中断，
      # 导致其他包（含 libc++）永远配不完。所以先把它卸下来，让 dpkg 恢复干净。
      say '修复 1/3：先把报错的 ffmpeg 卸下来，让 dpkg 恢复干净…'
      pkg uninstall -y ffmpeg </dev/null 2>&1 | tail -2 || true
      pkg install -y --reinstall openssl </dev/null 2>&1 | tail -2 || true
      apt --fix-broken install -y </dev/null 2>&1 | tail -2 || true
      dpkg --configure -a </dev/null 2>&1 | tail -2 || true
      say '修复 2/3：升级全部包，然后重装 ffmpeg…'
      pkg upgrade -y </dev/null 2>&1 | tail -2 || true
      pkg install -y ffmpeg </dev/null 2>&1 | tail -2 || true
      if ! ffmpeg -version >/dev/null 2>&1; then
        say '修复 3/3：改下载「自带库的静态 ffmpeg」放进项目 bin/（绕开 Termux 库问题）…'
        install_static_ffmpeg
      fi
    fi
  else
    case "$missing" in
      *ffmpeg*)
        if have apt-get; then
          say '使用 apt 安装 ffmpeg…'
          apt-get update -qq >/dev/null 2>&1 || true
          apt-get install -y -qq ffmpeg >/dev/null 2>&1 || true
        fi ;;
    esac
    if ! have yt-dlp && [ ! -x bin/yt-dlp ]; then
      say '下载 yt-dlp 二进制…'
      case "$(uname -m)" in
        aarch64|arm64) A=yt-dlp_linux_aarch64 ;;
        armv7l) A=yt-dlp_linux_armv7l ;;
        *) A=yt-dlp_linux ;;
      esac
      if [ "$(id -u)" = '0' ] && [ -w /usr/local/bin ]; then
        curl -L -o /usr/local/bin/yt-dlp "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$A" && chmod 755 /usr/local/bin/yt-dlp || true
      else
        mkdir -p bin && curl -L -o bin/yt-dlp "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$A" && chmod 755 bin/yt-dlp || true
      fi
    fi
  fi

  step '安装后复查'
  if have python3 || have python; then ok 'python 就绪'; else say 'python 仍不可用'; exit 1; fi
  if [ -x bin/yt-dlp ] || have yt-dlp; then ok 'yt-dlp 就绪'; else say 'yt-dlp 仍不可用'; exit 1; fi
  if ffmpeg -version >/dev/null 2>&1; then
    ok 'ffmpeg 就绪'
  else
    say 'ffmpeg 仍不可用 —— 请在 Termux 里手动执行：  pkg upgrade -y'
    say '（没有 ffmpeg 就无法合并音视频，成品会没有声音；脚本这次会改用「自带声音的单文件流」尽量保证有声音）'
  fi
fi

# ---------------- Termux 存储权限 ----------------
if [ "$is_termux" = '1' ] && [ ! -d "$HOME/storage" ]; then
  step '存储权限'
  say '首次运行需要授权存储（弹窗里选“允许”）'
  if have termux-setup-storage; then
    termux-setup-storage
    sleep 2
  fi
fi

# ---------------- 启动 ----------------
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then say '未找到 python，无法运行'; exit 1; fi
exec "$PY" ytdl.py "$@"