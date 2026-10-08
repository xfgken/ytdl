#!/bin/sh
# ytdl · 安装环境与引擎工具
set -u
cd "$(dirname "$0")" || exit 1

echo "=== ytdl 环境安装 ==="
echo

if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
  echo "[1/3] Termux：更新软件源"
  pkg update -y >/dev/null 2>&1 || true

  echo "[2/3] 安装 python / ffmpeg / yt-dlp"
  pkg install -y python ffmpeg yt-dlp || true

  echo "[3/3] 存储权限（弹窗里选允许，已授权可忽略）"
  command -v termux-setup-storage >/dev/null 2>&1 && termux-setup-storage || true
else
  echo "[1/3] Linux：安装 ffmpeg"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq ffmpeg 2>/dev/null || true
  fi

  echo "[2/3] 安装 yt-dlp"
  if ! command -v yt-dlp >/dev/null 2>&1; then
    case "$(uname -m)" in
      aarch64|arm64) A=yt-dlp_linux_aarch64 ;;
      armv7l) A=yt-dlp_linux_armv7l ;;
      *) A=yt-dlp_linux ;;
    esac
    if [ "$(id -u)" = "0" ] && [ -w /usr/local/bin ]; then
      curl -L -o /usr/local/bin/yt-dlp "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$A" && chmod 755 /usr/local/bin/yt-dlp || true
    else
      mkdir -p bin && curl -L -o bin/yt-dlp "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$A" && chmod 755 bin/yt-dlp || true
    fi
  fi
  echo "[3/3] 完成"
fi

echo
echo "=== 环境检查 ==="
if command -v yt-dlp >/dev/null 2>&1; then
  echo "  yt-dlp : $(yt-dlp --version 2>/dev/null || echo '不可用')"
elif [ -x bin/yt-dlp ]; then
  echo "  yt-dlp : 项目 bin/ 内"
else
  echo "  yt-dlp : 未找到"
fi
if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ffmpeg : 已就绪"
else
  echo "  ffmpeg : 未找到"
fi
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  echo "  python : 已就绪"
else
  echo "  python : 未找到"
fi
echo
echo "完成。启动：  sh ytdl.sh"
echo
