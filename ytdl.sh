#!/bin/sh
# ytdl · 一键运行（缺什么自动装什么）
set -u
cd "$(dirname "$0")" || exit 1

need() { command -v "$1" >/dev/null 2>&1; }

# ---------- Termux ----------
if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
  missing=""
  need python || missing="$missing python"
  need yt-dlp || missing="$missing yt-dlp"
  need ffmpeg || missing="$missing ffmpeg"
  if [ -n "$missing" ]; then
    echo "[ytdl] 缺少依赖:$missing"
    echo "[ytdl] 正在自动安装（Termux）…"
    pkg update -y >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    pkg install -y $missing || {
      echo "[ytdl] 自动安装失败，请手动执行：  pkg install python ffmpeg yt-dlp"
      exit 1
    }
    echo
  fi
  if [ ! -d "$HOME/storage" ]; then
    echo "[ytdl] 首次运行，建议授权存储权限（弹窗里选“允许”）"
    if need termux-setup-storage; then
      termux-setup-storage
      sleep 2
    fi
  fi
# ---------- 普通 Linux ----------
else
  if ! need python3 && ! need python; then
    echo "[ytdl] 未找到 python3，请先安装（例如 apt install python3）"
    exit 1
  fi
  if ! need yt-dlp; then
    echo "[ytdl] 提示：未找到 yt-dlp，可先运行 sh install.sh"
  fi
  if ! need ffmpeg; then
    echo "[ytdl] 提示：未找到 ffmpeg，1080p 合并会失败（apt install ffmpeg）"
  fi
fi

PY=$(command -v python3 || command -v python)
exec "$PY" ytdl.py "$@"
