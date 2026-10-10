# ytdl · YouTube 下载器（Termux 版）

粘贴一个链接 → 选清晰度 → 选格式 → 自动下载 + 合并音视频 → 成品带声音存进手机下载目录。

只依赖 **Python 3 标准库**，不需要 pip 装任何东西。作者：**by xfgken**

---

## 1. 安装（第一次，一条命令）

打开 Termux，粘贴执行：

```sh
curl -fsSL https://raw.githubusercontent.com/xfgken/ytdl/main/get.sh -o "$TMPDIR/get.sh" && sh "$TMPDIR/get.sh"
```

普通 Linux 把 `"$TMPDIR/get.sh"` 换成 `/tmp/get.sh`。

这一条命令会自动做完：装 git（如果缺）→ 把源码放到 `~/ytdl` → 装好 `ytdl` 命令 → 启动程序。

> 装完会顺便建一个 `ytdl` 命令，以后不用再敲这条长命令。

**建议**：全新环境的 Termux，先跑一次 `pkg update -y && pkg upgrade -y` 再装，能避开 90% 的依赖问题。

---

## 2. 日常使用（命令就这几条）

| 想干什么 | 命令 |
|---|---|
| 进入交互（最常用） | `ytdl` |
| 带上链接直接开始 | `ytdl "https://youtu.be/xxxx"` |
| 全自动（全部用默认选项，不用点回车） | `ytdl "链接" -y` |
| 更新到最新版 | `cd ~/ytdl && git pull` |
| 只装/修环境，不启动 | `sh ~/ytdl/ytdl.sh`（启动即自检）或 `sh ~/ytdl/install.sh` |
| 换一种方式启动（没建软链接时） | `sh ~/ytdl/ytdl.sh` |

如果 `ytdl` 命令没生效，手动建软链：

```sh
ln -sf ~/ytdl/ytdl.sh $PREFIX/bin/ytdl        # Termux
ln -sf ~/ytdl/ytdl.sh /usr/local/bin/ytdl     # 有权限的 Linux
```

> 链接前后的引号建议保留 —— 有些分享链接带 `&`，不加引号会被 shell 当成后台符号。

---

## 3. 一次下载的完整流程

启动后会先自检，然后出现输入提示，粘贴链接回车即可（输入 `q` 退出）：

```
  ██╗   ██╗████████╗██████╗ ██╗  by xfgken
  ╚██╗ ██╔╝╚══██╔══╝██╔══██╗██║
   ╚████╔╝    ██║   ██║  ██║██║
    ╚██╔╝     ██║   ██║  ██║██║
     ██║      ██║   ██████╔╝███████╗
     ╚═╝      ╚═╝   ╚═════╝ ╚══════╝
  YouTube 下载器 · Termux 版

  ✓ python 3.12.3
  ✓ yt-dlp 2026.08.19
  ✓ ffmpeg  /data/data/com.termux/files/home/ytdl/bin/ffmpeg
  ✓ JS 运行时 node
  /sdcard/Download
  请输入解析的链接（q 退出）> https://youtube.com/shorts/xxxx

 1. 开始解析
  [youtube] Extracting URL: https://youtube.com/shorts/xxxx
  [youtube] xxxx: Downloading webpage
  [info] xxxx: Downloading 1 format(s): 616+251-1
  标题：    给老父亲气笑了 #影视
  作者：    笑点剧场
  时长：    0:26
  观看：    33.0 万次
  发布：    2026-09-10
  清晰度：  共 7 档，最高 1080p
  1) 1080p  1080×1920   原生 H.264
  2)  720p  720×1280    原生 H.264
  ...

 2. 格式
  1) 视频 MP4 · H.264 + AAC
  2) 仅音频 M4A · 只要声音
  3) 视频原画 · 不转码，最快

 3. 开始制作
  视频 MP4 · 1080p
  [download] 100.0% ...
 ✓ 音轨正常：h264 + aac
✓ 完成
  给老父亲气笑了 影视_1080p.mp4
  /sdcard/Download
  6.4 MB · 0:26 · h264 · 1080×1920 · aac
```

流程里你只需要回两次车：

1. **粘贴链接** → 回车（开始解析，会顺便刷出 yt-dlp 的原始日志和视频信息）
2. **选清晰度**（回车 = 默认 1080p）→ **选格式**（回车 = 默认「视频 MP4」）

想全程不回车：`ytdl "链接" -y`。

三个区域的含义：

| 区域 | 说明 |
|---|---|
| `1. 开始解析` | 取视频信息：标题/作者/时长/观看/发布/清晰度，并列出所有可选清晰度 |
| `2. 格式` | `1` 视频 MP4（H.264+AAC，手机直接能播）；`2` 仅音频 M4A；`3` 原画不转码（最快） |
| `3. 开始制作` | 下载 + 合并，结束后校验音轨，输出成品名、路径、体积、时长、编码 |

---

## 4. 成品保存位置

按顺序取**第一个可写**的目录：

1. 环境变量 `YTDL_OUT_DIR`（设置了就用它）
2. `/sdcard/Download`
3. `~/storage/downloads`（Termux 已授权存储时）
4. `~/Downloads`

文件名不以点开头（相册能扫到），重名自动加 `_1` / `_2`，**绝不覆盖旧文件**。

想强制指定目录：

```sh
YTDL_OUT_DIR=/sdcard/Movies ytdl "链接"
```

---

## 5. 启动时自检了什么

每次运行都会先过一遍（只花零点几秒）：

| 检查项 | 缺失时的处理 |
|---|---|
| python3 | Termux 自动 `pkg install python`；Linux 用 apt |
| yt-dlp | Termux 自动 `pkg install yt-dlp`；Linux 自动下载对应架构二进制 |
| ffmpeg | 优先用项目 `bin/ffmpeg` → Termux `pkg install ffmpeg` → 自动下载**静态版**（自带库，绕开 Termux 库错位） |
| JS 运行时 | 检查 deno / node / qjs / bun，一个都没有会给出安装建议 |
| 存储权限 | 首次运行自动调起 `termux-setup-storage` |
| 成品目录 | 自动挑第一个可写目录 |

自检里 `✓` 是就位、`✗` 是没就位（会同时给出修复提示）。

---

## 6. 常见问题

**Q：下载出来有画面没声音？**

A：两种原因。①音轨是 opus 塞进 mp4（安卓放不出声）—— 本程序会在完成后自动检测并只转音频（不重编码视频）修好；②你的 ffmpeg 坏了，导致根本合不出音轨 —— 启动自检的 `ffmpeg` 那一行如果是 `✗`，说明就是它，程序会自动尝试重装，不行就用自带的静态 ffmpeg。

**Q：提示 `Sign in to confirm you're not a bot`（解析失败）？**

A：这是 YouTube 的风控 —— 它认为这次请求像机器人（常见于机房/代理 IP、短时间请求过多、没有登录态）。跟脚本无关，换个网络或带上 cookies 就能过。

**① 带 cookies（最稳）**

`ytdl` 会自动在这些位置找 `cookies.txt`：

```
/sdcard/Download/cookies.txt        ← 推荐放这里
~/ytdl/cookies.txt
~/cookies.txt
~/storage/downloads/cookies.txt
```

也可以手动指定：

```sh
ytdl --cookies /sdcard/Download/cookies.txt "链接"
YTDL_COOKIES=/sdcard/Download/cookies.txt ytdl "链接"
```

导出 cookies 的步骤（手机上）：

1. 装一个支持 Chrome 扩展的浏览器，例如 **Kiwi Browser**
2. 在它里面装扩展 **Get cookies.txt LOCALLY**
3. 用它打开 `youtube.com` 并登录
4. 打开扩展 → **Export** → 导出 `cookies.txt`
5. 把文件保存/移动到 `/sdcard/Download/cookies.txt`（文件名保持 `cookies.txt`）

> cookies 有有效期（通常几周到几个月），过期了就重新导出一次。启动画面里如果多出一行 `cookies /sdcard/Download/cookies.txt`，说明已经被识别到了。想看当前状态可以运行： `ytdl cookies`

> ⚠️ **cookies 必须每个人用「自己的账号」导出**：不要提交到仓库、不要发给别人、不要传网盘 —— 它等于你 YouTube 账号的钥匙；多人共用一份 cookies（尤其是不同 IP），会被 Google 判为异常登录，很快一起失效。仓库的 `.gitignore` 已经忽略 `cookies.txt`，防止误提交。

**② 换个网络再试**

Wi-Fi ⇄ 手机流量切换，或重启路由器换 IP，风控常常是临时的，换个出口就过了。

**③ 装上 JS 运行时**

`pkg install -y deno`（yt-dlp 官方推荐的 JavaScript 运行时）。若只有 node，脚本会自动加 `--js-runtimes node`，但 deno 更稳，能减少风控触发。

**Q：能不能把 `cookies.txt` 一起打包/提交，让别人下载我的源码后直接用？**

A：**不行，也不建议**，原因有三：

1. 它是你账号的**登录凭据**（里面就是你的登录态），公开出去等于把 YouTube 账号交出去；
2. 多人共用同一份 cookies、尤其是从不同 IP 访问，Google 会直接判定**异常登录** → 会话被注销，你自己也用不了；
3. GitHub 是公开仓库，爬虫会扫到这类文件。

正确的做法：**每个使用者自己导出一次**（1 分钟，见上一条），放到 `/sdcard/Download/cookies.txt` 即可，`ytdl` 会自动识别。检查自己是否就绪：

```sh
ytdl cookies
```

仓库侧已经做了两层保护：`.gitignore` 忽略 `cookies.txt`（防止误提交），程序内没找到 cookies 时会在自检里明确提示并打印导出指引。

**Q：报 `The page needs to be reloaded.`（cookies、JS 运行时都正常，还是失败）？**

A：**yt-dlp 版本太旧了** —— YouTube 改动频繁，旧版跟不上就会报这个错（跟 cookies、deno 都无关）。

`ytdl` 启动自检现在会检查版本：**超过 30 天就自动下载最新版**到项目 `bin/yt-dlp` 并优先使用 —— 不动系统包、不怕 `pkg upgrade` 覆盖，7 天内也不重复联网下载。

想立刻强制更新一次：

```sh
cd ~/ytdl && rm -f bin/yt-dlp bin/.ytdlp-check && ytdl
```

> Termux 仓库里的 `pkg install yt-dlp` 常常滞后一两个月（例：仓库还是 `2026.06.09`，官方已到 `2026.08.19`），所以本项目自带的更新比系统包更及时；两者互不影响。

**Q：安装时报 `429 Too Many Requests` 或 `repository ... is not signed`？**

A：这是 Termux 官方镜像被限流（或临时未签名），跟你手机无关。新版 `get.sh` / `ytdl.sh` 遇到这种情况会**自动依次切换清华 / 中科大 / 阿里镜像再重试**，原来的源会备份在 `$PREFIX/etc/apt/sources.list.ytdl.bak`。

也可以手动换（推荐国内源）：

```sh
termux-change-repo                    # 选 Mirror group → 挑 Tsinghua 或 USTC
pkg update -y && pkg install -y git
```

**Q：Termux 里 `pkg upgrade` 报错 / ffmpeg 装了跑不起来（`CANNOT LINK EXECUTABLE`）？**

A：这是 Termux 仓库里 `libplacebo` 和 `libc++` 版本错位导致的，而且坏 ffmpeg 会让 dpkg 卡在半配置状态。修复顺序（先卸载再升级，顺序不能反）：

```sh
pkg uninstall -y ffmpeg
apt --fix-broken install -y
dpkg --configure -a
pkg upgrade -y
pkg install -y ffmpeg
ffmpeg -version
```

跑完还是不行，直接让 ytdl 走自带静态版（启动自检会自动做，或手动）：程序会把 `bin/ffmpeg` 当作首选，不参与 Termux 的动态链接。

**Q：日志里有 `缺少 JS 运行时（deno）` 提示？**

A：不影响下载。想消掉提示：`pkg install deno`，或改用已安装的 node（yt-dlp 需要显式指定运行时时才用）。

**Q：相册看不到成品？**

A：成品默认在 `/sdcard/Download`。Termux 需要先 `termux-setup-storage` 授权，授权后也可能落在 `~/storage/downloads`（就是手机「下载」目录）。

**Q：1080p 为什么不是一条直链？**

A：YouTube 720p 以上是音视频分离流，程序会下载两条流并用 ffmpeg 合并成 H.264 + AAC 单文件，所以成片带声音。

**Q：提示 `Requested format is not available`？**

A：同样是 ffmpeg 不可用时的连锁反应（拿不到可合并的组合）。先在自检里把 ffmpeg 修好即可。

**Q：终端颜色乱码 / 显示错位？**

A：颜色只在真正的终端里启用；如果被重定向到文件或管道，会自动关掉颜色，不会有杂码。

---

## 7. 卸载

```sh
rm -f $PREFIX/bin/ytdl        # 删命令
rm -rf ~/ytdl                 # 删程序（成品在下载目录，不受影响）
```

---

## 8. 文件说明

| 文件 | 作用 |
|---|---|
| `get.sh` | 一条命令入口：装 git、拉源码、建 `ytdl` 命令、启动 |
| `ytdl.sh` | 启动器：每次运行先自检环境，缺什么装什么，然后启动 `ytdl.py` |
| `ytdl.py` | 交互主程序：解析、清晰度/格式选择、下载合并、音轨校验、命名 |
| `install.sh` | 只装环境（python / ffmpeg / yt-dlp / 存储权限） |
| `bin/` | 可选：自带引擎放这里（优先使用；仓库不收录） |

---

## 9. 给想改代码的人

- 显示层是集中写的：`section()`（区域标题 + `1. 2. 3.` 序号）、`raw_line()`（透传工具原始输出）、`show_info()`（带标签的视频信息）、`show_formats()`（清晰度列表）、`prog_show()`（进度条）。
- 颜色常量在文件顶部：`ACC` 品红（主色）、`ACC_D` 深品红、`GRAY` 次要、`GREEN` 就位/成功、`RED` 错误。非 TTY 自动全部关闭。
- 改完自测：
  ```sh
  python3 -m py_compile ytdl.py
  sh -n ytdl.sh
  ytdl "https://youtu.be/xxxx" -y
  ```
