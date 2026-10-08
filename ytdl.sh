#!/bin/sh
# ytdl · 启动器
# 每次运行先自检环境（python / yt-dlp / ffmpeg / 存储权限），缺什么自动装，然后启动
set -u
cd "$(dirname "$0")" || exit 1

is_termux=0
if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then is_termux=1; fi

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[33m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

# ---------------- 环境自检 ----------------
step '环境自检'
missing=""
PY=""
if have python3; then PY=python3; elif have python; then PY=python; fi
if [ -n "$PY" ]; then ok "python   $(command -v "$PY")"; else bad 'python   未安装'; missing="$missing python"; fi
if [ -x bin/yt-dlp ]; then ok 'yt-dlp   项目 bin/ 内';
elif have yt-dlp; then ok "yt-dlp   $(command -v yt-dlp)";
else bad 'yt-dlp   未安装'; missing="$missing yt-dlp"; fi
if have ffmpeg; then ok "ffmpeg   $(command -v ffmpeg)"; else bad 'ffmpeg   未安装（合并会失败）'; missing="$missing ffmpeg"; fi

# ---------------- 缺失则自动安装 ----------------
if [ -n "$missing" ]; then
  step "需要安装：$missing"
  if [ "$is_termux" = '1' ]; then
    say '使用 pkg 安装（首次可能会慢一点）…'
    pkg update -y >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    if ! pkg install -y $missing; then
      say '自动安装失败，请手动执行：  pkg install python ffmpeg yt-dlp'
      exit 1
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
  if have ffmpeg; then ok 'ffmpeg 就绪'; else say 'ffmpeg 仍不可用（转码/合并会失败）'; fi
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
