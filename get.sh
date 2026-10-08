#!/bin/sh
# ytdl · 一条命令入口
# 用法（Termux / Linux）：
#   curl -fsSL https://raw.githubusercontent.com/xfgken/ytdl/main/get.sh | sh
# 它会：1) 装 git（如果缺）  2) 下载/更新源码  3) 启动（启动时再自检环境并自动补装）
set -u

REPO="${YTDL_REPO:-https://github.com/xfgken/ytdl.git}"
DIR="${YTDL_DIR:-$HOME/ytdl}"

# 注意：这里绝对不能写 `exec < /dev/tty`。
# 在 `curl | sh` 场景下，sh（尤其是 Termux 的 mksh）是边读边执行的：
# 一旦把 stdin 换成终端，它就会转而从终端继续读取“脚本剩余内容”，
# 于是你在终端里敲的字会被当成脚本命令执行，出现 `sh:39: i: not found` 之类的怪错。
# 正确做法：交互输入只在脚本最后（真正启动程序时）重定向到终端。

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '%s\n' "$*"; }

fix_mirror() {
  # 软件源被限流(429)/未签名时，自动换到可用镜像再试
  [ -n "${PREFIX:-}" ] || return 1
  SL="$PREFIX/etc/apt/sources.list"
  [ -f "$SL" ] || return 1
  [ -f "$SL.ytdl.bak" ] || cp "$SL" "$SL.ytdl.bak" 2>/dev/null || true
  SD="$PREFIX/etc/apt/sources.list.d"
  if [ -d "$SD" ]; then
    for f in "$SD"/*.sources "$SD"/*.list; do
      [ -e "$f" ] || continue
      mv "$f" "$f.ytdl.off" 2>/dev/null || true
    done
  fi
  for M in \
    https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main \
    https://mirrors.ustc.edu.cn/termux/apt/termux-main \
    https://mirrors.aliyun.com/termux/apt/termux-main \
    https://packages.termux.dev/apt/termux-main
  do
    printf 'deb %s stable main\n' "$M" > "$SL" 2>/dev/null || return 1
    say "  试用镜像：$M"
    if pkg update -y </dev/null >/dev/null 2>&1; then
      say '  已切换到可用镜像'
      return 0
    fi
  done
  cp "$SL.ytdl.bak" "$SL" 2>/dev/null || true
  if [ -d "$SD" ]; then
    for f in "$SD"/*.ytdl.off; do
      [ -e "$f" ] || continue
      mv "$f" "${f%.ytdl.off}" 2>/dev/null || true
    done
  fi
  say '  所有镜像都不通，已还原原来的源'
  return 1
}

say ''
say '=== ytdl 一条命令安装 ==='
say ''

# 1) git
if have git; then
  say '[1/3] git 已就绪'
else
  if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
    say '[1/3] 安装 git…'
    if ! pkg install -y git </dev/null; then
      say '        源不通（常见：官方镜像 429 / 未签名），自动换个源再试…'
      if fix_mirror && pkg install -y git </dev/null; then
        :
      else
        say ''
        say '无法自动装上 git。请手动换源后重试安装：'
        say '  termux-change-repo                # 选 Mirror group → 挑一个（如 Tsinghua / USTC）'
        say '  pkg update -y && pkg install -y git'
        exit 1
      fi
    fi
  else
    say '[1/3] 未找到 git，请先安装（apt install git）'
    exit 1
  fi
fi

# 2) 源码
if [ -d "$DIR/.git" ]; then
  say "[2/3] 更新已有源码：$DIR"
  git -C "$DIR" pull --ff-only </dev/null 2>/dev/null || say '（更新跳过，继续用当前版本）'
else
  say "[2/3] 下载源码到：$DIR"
  git clone --depth 1 "$REPO" "$DIR" </dev/null || { say '下载失败，请检查网络后重试'; exit 1; }
fi

# 2.5) 安装 `ytdl` 命令，以后直接敲 ytdl 就行
if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ] && [ -w "$PREFIX/bin" ]; then
  if ln -sf "$DIR/ytdl.sh" "$PREFIX/bin/ytdl" 2>/dev/null; then
    chmod 755 "$PREFIX/bin/ytdl" 2>/dev/null || true
    say "        以后直接敲： ytdl"
  fi
elif [ -d /usr/local/bin ] && [ -w /usr/local/bin ]; then
  if ln -sf "$DIR/ytdl.sh" /usr/local/bin/ytdl 2>/dev/null; then
    say "        以后直接敲： ytdl"
  fi
fi

# 3) 启动（缺什么会自动装）
# 交互输入只在这里重定向到终端：exec 之后本脚本进程就被替换掉，
# 不会再从 stdin 继续读脚本内容，所以是安全的。
say "[3/3] 启动（缺什么会自动装）"
if [ -r /dev/tty ] && [ -t 1 ]; then
  exec sh "$DIR/ytdl.sh" "$@" < /dev/tty
fi
exec sh "$DIR/ytdl.sh" "$@"
