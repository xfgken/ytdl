#!/bin/sh
# ytdl · 一条命令入口
# 用法（Termux / Linux）：
#   curl -fsSL https://raw.githubusercontent.com/xfgken/ytdl/main/get.sh | sh
# 它会：1) 装 git（如果缺）  2) 下载/更新源码  3) 启动（启动时再自检环境并自动补装）
set -u

REPO="${YTDL_REPO:-https://github.com/xfgken/ytdl.git}"
DIR="${YTDL_DIR:-$HOME/ytdl}"

# 从管道运行时（curl | sh），把标准输入接回终端，否则没法交互输入链接
if [ ! -t 0 ]; then
  if [ -r /dev/tty ]; then
    exec < /dev/tty || true
  fi
fi

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '%s\n' "$*"; }

say ''
say '=== ytdl 一条命令安装 ==='
say ''

# 1) git
if have git; then
  say '[1/3] git 已就绪'
else
  if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
    say '[1/3] 安装 git…'
    pkg install -y git || { say 'git 安装失败，请手动执行： pkg install git'; exit 1; }
  else
    say '[1/3] 未找到 git，请先安装（apt install git）'
    exit 1
  fi
fi

# 2) 源码
if [ -d "$DIR/.git" ]; then
  say "[2/3] 更新已有源码：$DIR"
  git -C "$DIR" pull --ff-only 2>/dev/null || say '（更新跳过，继续用当前版本）'
else
  say "[2/3] 下载源码到：$DIR"
  git clone --depth 1 "$REPO" "$DIR" || { say '下载失败，请检查网络后重试'; exit 1; }
fi

# 3) 启动
say "[3/3] 启动（缺什么会自动装）"
exec sh "$DIR/ytdl.sh" "$@"
