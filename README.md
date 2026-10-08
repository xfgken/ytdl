# ytdl · YouTube 下载器（Termux 版）

输入链接 → 选分辨率 → 选格式 → 自动下载合并 → 成品存到下载目录。

只依赖 Python 3 标准库，不需要 pip 安装任何东西。

---

## 三步使用（Termux）

```sh
# 1. 从 GitHub 拉取脚本
git clone https://github.com/xfgken/ytdl.git
cd ytdl

# 2. 安装所需环境与引擎工具（python / ffmpeg / yt-dlp）
sh install.sh

# 3. 运行脚本，然后输入链接、选分辨率、选格式
sh ytdl.sh
```

> 也可以跳过第 2 步：直接 `sh ytdl.sh`，缺什么它会自动用 `pkg` 装上。

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
