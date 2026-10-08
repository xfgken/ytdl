# ytdl · YouTube 下载器（Termux 版）

输入链接 → 选分辨率 → 选格式 → 自动下载合并 → 成品存到下载目录。

只依赖 Python 3 标准库，不需要 pip 安装任何东西。

---

## 一条命令（推荐）

```sh
curl -fsSL https://raw.githubusercontent.com/xfgken/ytdl/main/get.sh | sh

```

这一条命令会自动完成：

1. 安装 git（如果缺）
2. 下载（或更新）源码到 `~/ytdl`
3. 启动脚本 —— 启动时会**先自检环境**，缺什么装什么，然后进入交互

---

## 或者分步来（Termux）

```sh
git clone https://github.com/xfgken/ytdl.git && cd ytdl
sh install.sh     # 只装环境（可选，ytdl.sh 也会自动装）
sh ytdl.sh        # 启动（每次都会先自检）

```

---

## 启动时都检查什么

每次运行 `sh ytdl.sh` 都会先过一遍：

| 检查项 | 缺失时的处理 |

|---|---|

| python3 | Termux 自动 `pkg install python` |

| yt-dlp | Termux 自动 `pkg install yt-dlp`；Linux 自动下载对应架构二进制 |

| ffmpeg | Termux 自动 `pkg install ffmpeg`；Linux 用 apt |

| 存储权限 | 首次运行自动调起 `termux-setup-storage` |

| 成品目录 | 自动选择第一个可写目录 |

检查本身只花零点几秒，不会拖慢启动。

---

## 运行时的交互

```
  请粘贴视频链接（q 退出）> https://www.youtube.com/watch?v=...

  给老父亲气笑了 #影视 #影视混剪 #搞笑
  笑点剧场 | 时长 0:26 | 329991 次观看

  可选分辨率：
    1) 1080p  原生 H.264   1080x1920
    2) 720p   原生 H.264   720x1280
    3) 608p   需转码        608x1080
    ...

  输出格式：
    1) 视频 MP4（H.264 + AAC，手机直接能播）
    2) 仅音频 M4A
    3) 视频（保留原始编码，速度最快）

  请选择分辨率 [1]: 1
  请选择 [1]: 1
  开始制作：视频 MP4 · 1080p
  [############################] 100.0%
  合并音视频…
  ✓ 完成
     /sdcard/Download/YouTube/标题_1080p.mp4
     6.4 MB · 时长 0:26
     轨道 h264,1080,1920 / aac,2

```

---

## 成品保存位置

按顺序自动选择第一个可写入的目录：

1. 环境变量 `YTDL_OUT_DIR`（如果设置了）
2. `/sdcard/Download/YouTube`
3. `~/storage/downloads/YouTube`（Termux 已授权存储时）
4. `~/YouTube`

文件名不以点开头，重名自动加 `_1` / `_2`，**绝不覆盖旧文件**。

---

## 其他用法

```sh
sh ytdl.sh                    # 交互式
sh ytdl.sh "<链接>"           # 带上链接
sh ytdl.sh "<链接>" -y        # 全部默认选项（无人值守）

```

---

## 文件说明

| 文件 | 作用 |

|---|---|

| `ytdl.sh` | 启动入口（Termux 里缺依赖会自动装） |

| `ytdl.py` | 交互主程序：解析、选分辨率、选格式、下载合并、命名 |

| `install.sh` | 只装环境：python、ffmpeg、yt-dlp、存储权限 |

| `bin/` | 可选：自带引擎放这里（优先使用，仓库不收录） |

---

## 常见问题

**Q：提示找不到 yt-dlp？**
A：执行 `sh install.sh`，或 `pkg install yt-dlp ffmpeg`。

**Q：相册看不到成品？**
A：成品默认在 `/sdcard/Download/YouTube`，Termux 需先 `termux-setup-storage` 授权；
若授权使用了 `~/storage/downloads/YouTube`，那就是手机共享存储的“下载”目录。

**Q：1080p 为什么不是一条流的直链？**
A：YouTube 对 720p 以上采用音视频分离流，脚本会自动下载两条流并用 ffmpeg 合并成
H.264 + AAC 单文件，所以成片是带声音的。
