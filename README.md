# 视频处理工具集

基于 [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) 的桌面图形界面（GUI）视频/字幕处理工具集。

本项目将原先分散在 11 个 `.bat` 批处理文件中的交互式操作，全部迁移到统一的
桌面界面中完成。

**单一入口**：`python main.py`（启动 PyQt6 图形界面）

---

## 环境要求

| 依赖 | 说明 |
|---|---|
| Python ≥ 3.9 | 已实测 3.11。**仅源码运行需要**，打包后的 exe 不需要 |
| `PyQt6` ≥ 6.5 | `pip install -r requirements.txt`。仅界面与打包需要 |
| ffmpeg / ffprobe | 需加入 `PATH`。AMD 相关功能需要**编译时启用 AMF** 的构建 |

> 打包成 exe 后 ffmpeg 会一起内置，运行机无需安装（见「打包为可执行程序」）。

验证环境：

```powershell
python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
```

> 界面启动时会在标题栏自动检测 ffmpeg/ffprobe 与 AMD AMF 编码器，
> 并以状态芯片显示检测结果。AMF 不可用时，仅 AMD 相关模式会失败，其余功能不受影响。

---

## 启动

```powershell
# 图形界面（会弹出控制台窗口）
python main.py

# 图形界面（无控制台黑窗）
run.bat
```

### 界面概览

```
┌──────────────────────────────────────────────────────────────┐
│ 视频处理工具集  v1.1.0          ● ffmpeg: xxx  ● AMF: xxx    │ 标题栏
├────────────┬─────────────────────────────────────────────────┤
│ 功能       │  工具标题                                        │
│ 视频处理   │  功能说明                                        │
│   视频合并 │  ────────────────────────────────────────────   │
│   批量裁剪 │  参数行（标签 / 说明 / 输入控件）                 │
│   …        │  ────────────────────────────────────────────   │
│ 工具箱     │  [开始执行] [重置参数]                            │
│            ├─────────────────────────────────────────────────┤
│            │  日志输出                              [清空]    │
│            │  A.mp4                                    42%   │
│            │  ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░      │
│            │  ✔ 输出 1 个文件:                                │
├────────────┴─────────────────────────────────────────────────┤
│ 空闲                        Ctrl+Q 退出 · Ctrl+C 停止任务 …   │ 状态栏
└──────────────────────────────────────────────────────────────┘
```

日志区与参数区的高度比例可用鼠标拖动中间分隔条调节。
共有 17 个工具，分为 4 个分组：视频处理（8 个）、音视频提取（2 个）、字幕工具（5 个）、工具箱（2 个）。

### 快捷键

| 按键 | 功能 |
|---|---|
| `↑` `↓` | 在左侧功能列表中切换 |
| `Tab` | 在参数控件间移动 |
| `Ctrl+Q` | 退出 |
| `Ctrl+C` | 停止当前任务 |
| `Ctrl+L` | 清空日志 |
| `F1` | 快捷键帮助 |

### 填写路径

路径输入框支持三种填法：

- **拖入**：从资源管理器把文件/文件夹拖到路径框上松手（原生拖放，路径框会高亮）。
  - 目录类字段拖入文件时，自动取其所在文件夹；
  - 一次拖入多个时只取第一个，其余忽略。
- **粘贴**：在路径框内 `Ctrl+V`，会自动剥离引号、还原 `file://` 形式的路径。
- **浏览**：点击右侧「浏览」按钮，在**系统原生文件对话框**中选择
  （目录模式 / 按扩展名过滤的文件模式）。

---

## 功能一览

### 视频处理

| 功能 | 说明 |
|---|---|
| 视频合并 | 按文件名排序合并。TS 流快速 / CPU(lix264) / GPU(h264_amf) 三模式 |
| 开头结尾裁剪 | **按绝对时间点**裁剪，保留 `[开头, 结尾)`。TS 无损 |
| 批量裁剪 | **按要切掉的时长**批量裁剪，默认输出到 `cut/` |
| 片段删除 | 删除多个时间段并合并剩余部分，可自动同步同名 SRT 字幕 |
| 片段提取 | 每段输出为独立文件。快速流复制 / AMD 硬件加速 |
| 视频分割 | 按多个时间点分割。快速无损 / 精确重编码 / AMD 加速 + 关键帧对齐 |
| 视频压缩 | AMF 硬件压缩，三档质量预设，递归跳过已压缩文件 |
| 转换 MP4 | 极速换容器 / CPU 重编码 / AMD 重编码 |

### 音视频提取

| 功能 | 说明 |
|---|---|
| 音轨提取 | 提取全部音轨重编码为 MP3，多音轨自动编号带语言标签 |
| 视频截图 | 指定时间点截取单帧为 JPG，支持批量 |

### 字幕工具

| 功能 | 说明 |
|---|---|
| SRT 转 ASS | 中文字体优化样式（文泉驿正黑、48 号字、带阴影） |
| SRT 时间段删除 | 删除指定时间段并将后续字幕时间整体前移 |
| 字幕重命名 | `.srt/.ass/.vtt/.lrc` 递归批量加 `.txt` 后缀 |
| 剪映字幕导出 | 解析剪映草稿文件 `draft_info.json`，导出文本轨道为 SRT 或 TXT |
| 必剪字幕导出 | 解析必剪草稿文件 `*.bjson`，导出字幕轨道为 SRT 或 TXT |

### 工具箱

| 功能 | 说明 |
|---|---|
| 时间线计算器 | 识别 `[广告]` 段落并重算后续时间点，输出广告区间 CSV，可一键填入「片段删除」 |
| 全局设置 | AMF 默认值、输出策略等，持久化到 `~/.video-process/config.json`（仅界面） |

---

## 时间格式

| 写法 | 含义 |
|---|---|
| `90` | 90 秒 |
| `1:30` | 1 分 30 秒 |
| `1:30:45` | 1 小时 30 分 45 秒 |
| `1:30:45.500` | 带毫秒 |
| `结尾` | 视频总时长（时间段结束位置） |

导出时间段用 `-` 连接起止，多个段用 `,` 分隔：`1:00-2:00,5:00-结尾`

---

## 输出命名规则

| 工具 | 输出命名 |
|---|---|
| 视频合并 | `{首文件名}_{末文件名}_merge_videos.mp4` |
| 开头结尾裁剪 | `{原名}_trim_edges.mp4` |
| 批量裁剪 | 原名（输出到 `cut/` 子目录） |
| 片段删除 | `{原名}_processed.mp4` |
| 片段提取 | `{原名}_{序号}_{开始}-{结束}.mp4` |
| 视频分割 | `{原名}_1.ext`、`{原名}_2.ext` … |
| 视频压缩 | `{原名}_compressed{原扩展名}` |
| 转换 MP4 | `{原名}.mp4`（已存在则 `{原名}_converted.mp4`） |
| 音轨提取 | `{原名}.mp3` / `{原名}_track{N}_{语言}.mp3` |
| 视频截图 | `{原名}_time{NN}s.jpg` |
| SRT 转 ASS | `{原名}.ass` |
| SRT 删除 | `{原名}_removed.srt` |
| 字幕重命名 | `{原名}.srt.txt` |
| 剪映字幕导出 | 单轨道 `{草稿名}.srt`，多轨道 `{草稿名}_track{N}.srt` |
| 必剪字幕导出 | 单轨道 `{草稿名}.srt`，多轨道 `{草稿名}_track{N}.srt` |

---

## 架构

四层单向依赖：

```
main.py（源码入口）/ bundle/entry_gui.py（打包入口）
   ↓
entry.py（统一初始化）
   ↓
ui/app.py                     PyQt6 主窗口
   ↓ 调用
defs/                        工具定义：参数规格 + 业务函数（无 UI 依赖）
   ↓
tools/                       纯业务逻辑（无 print / input）
   ↓
core/                        ffmpeg 执行器 / ffprobe 探测 /
                             时间解析 / 路径处理 / AMF 参数
```

```
video_process/
├── core/        ffmpeg 执行器（流式日志、真实进度、可取消）、ffprobe 探测（带缓存）、
│                时间解析、路径容错与扫描、AMF 参数构造、数据契约
├── tools/       17 个业务逻辑模块，全部通过 ToolContext 回调上报日志与进度
├── defs/        工具定义层：每个工具一份「参数规格 + 业务函数」，不依赖任何 UI 框架
├── ui/          主窗口、通用表单面板、时间线/设置定制面板、
│                路径选择控件、日志与进度控件、QSS 主题、后台任务执行器
├── param_spec.py   声明式参数规格（ParamSpec / ToolDefinition）
├── settings_store.py  全局设置持久化
├── entry.py       统一初始化入口（utf-8 控制台 + ffmpeg PATH 注入）
├── _frozen.py     打包与源码两种运行模式的资源路径适配
```

### 设计要点

- **tools 层不含任何 `print()` / `input()`**，全部通过回调上报，界面是唯一消费者
- **定义与渲染分离**：参数规格与业务函数放在 `defs/`，界面只负责渲染
- **声明式表单**：`ParamSpec` 驱动界面控件，新增工具只需一份定义加一个业务函数
- **异步执行**：ffmpeg 任务跑在 `QThread` 后台线程，通过信号槽（自动 QueuedConnection）
  回到主线程更新进度条与日志，后台线程绝不直接触碰控件；可随时 `Ctrl+C` 停止
- **日志抗洪峰**：长任务可能瞬间产生数千行输出，日志区用 100 ms 定时器批量合并写入，
  并限制保留 2000 行
- **环境自检**：启动时在后台线程检测 ffmpeg/ffprobe 与 AMF 编码器，结果常驻标题栏

---

## 校验脚本

```powershell
python e2e_check.py   # 14 个工具端到端真实 ffmpeg 调用（自动生成测试素材）
```

脚本会调用真实 ffmpeg/ffprobe 并逐项输出 `PASS`/`FAIL`，最后汇总通过与失败数量。
无 AMF 编码器的环境会自动跳过 AMD 相关用例。
剪映/必剪字幕导出不涉及 ffmpeg，未包含在端到端测试中。

---

## 打包为可执行程序

用 [PyInstaller](https://pyinstaller.org/) 打成 Windows 可执行程序，双击即用，
**目标机器既不需要安装 Python，也不需要安装 ffmpeg**——二者都随程序一起分发。

```powershell
build.bat                    # 单目录模式（推荐）+ 内置 ffmpeg
python build.py              # 等价命令
python build.py --onefile    # 单文件模式
python build.py --clean      # 先清掉上次的构建产物
python build.py --no-ffmpeg  # 不内置 ffmpeg（改用运行机上的）
python build.py --ffmpeg-dir D:\sdk\ffmpeg\bin   # 指定用哪份 ffmpeg
```

首次执行会自动 `pip install pyinstaller`；也可以提前装好：

```powershell
pip install -e ".[build]"
```

### 内置 ffmpeg

构建时自动从 PATH 里找 ffmpeg / ffprobe 并一起打进产物，启动时把它们的目录
挂到 PATH 最前面，因此业务代码不用改，界面自动用上内置副本。

打包的取舍：

- **静态链接版**（gyan.dev / BtbN 的 full build）：只收 `ffmpeg` + `ffprobe`
  两个可执行文件，干净利落
- **动态链接版**：额外把 exe 同目录的 `*.dll`（`avcodec-*.dll` 等）一并收进来，
  漏了程序就起不来
- `ffplay.exe` 用不到，不收

运行时按以下顺序查找，前者优先：

1. 环境变量 `VIDEO_PROCESS_FFMPEG_DIR` 指向的目录（可临时改用别的 ffmpeg）
2. 内置副本（单目录模式在 `_internal/`，单文件模式在临时目录）
3. exe 同目录（自己丢一份 `ffmpeg.exe` 进去即可覆盖，无需重新打包）
4. 系统 PATH

> 顺序 3 意味着：**把 `ffmpeg.exe` / `ffprobe.exe` 复制到 exe 旁边就能换版本**，
> 不必重新打包。界面标题栏的状态芯片会用「内置」/「系统」标明当前生效的来源。

### 产物

构建产物为单个图形界面程序（单目录模式的 `dist/video-process/` 目录，或单文件模式的单个 exe）：

| 文件 | 说明 |
|---|---|
| `视频处理工具集.exe` | 双击启动，**不弹控制台黑窗**，带应用图标与版本信息 |

### 两种模式怎么选

| 模式 | 优点 | 缺点 |
|---|---|---|
| 单目录（默认） | 启动快，升级只替换改动的库 | 分发要拷贝整个目录 |
| `--onefile` | 只有一个 exe，便于传文件 | 每次启动都要解压到临时目录，慢 2~5 秒 |

> 单文件模式把依赖与 ffmpeg 全部内嵌进一个 exe，体积数百 MB，
> 冷启动明显变慢，**建议用单目录模式**。

### 打包相关文件

```
build.py                    构建驱动：检查图标/ffmpeg → 生成版本资源 → 调 spec
build.bat                   Windows 一键打包
bundle/video_process.spec   PyInstaller 配置（单入口 + ffmpeg）
bundle/entry_gui.py         图形界面入口（无控制台）
bundle/ffmpeg_bins.py       定位并收集 ffmpeg / ffprobe 及其动态库
bundle/version_info.py      生成 Windows exe 的版本资源
assets/app.ico              应用图标（自备，缺失时打包仍可正常完成）
video_process/_frozen.py    资源路径 + 内置 ffmpeg 的 PATH 注入
video_process/entry.py      统一初始化入口（utf-8 控制台 + ffmpeg PATH 注入）
```

### 注意事项

- **体积**：内置 ffmpeg 后单目录产物约 480 MB（ffmpeg 本体就占 385 MB）。
  嫌大可以用 `--ffmpeg-dir` 指定一份精简构建，或 `--no-ffmpeg` 干脆不打包。
- **位数要一致**：64 位 Python 打出 64 位 exe，32 位系统请用 32 位 Python 打包。
- **建议在干净虚拟环境中打包**，否则容易把无关依赖一起打进去，体积膨胀。
- 界面启动后会像源码模式一样在标题栏检测 ffmpeg 与 AMF 并显示状态芯片。
- 全局设置仍写在 `~/.video-process/config.json`，与源码模式共用一份。
- 杀毒软件对 PyInstaller 产物的误报是行业通病，必要时加白名单或做代码签名。

---

## 与旧项目的对应关系

| 原 video-trimmer | 本项目 |
|---|---|
| `merge_videos.bat/.py` | `merge` |
| `trim_edges.bat/.py` | `trim-edges` |
| `batch_trim_edges*.bat/.py` | `batch-trim --mode fast\|amd` |
| `remove_segments.bat/.py` | `remove-segments` |
| `extract_segments.bat/.py` | `extract-segments` |
| `split_video*.bat/.py` | `split --mode fast\|precise\|amd` |
| `compress_video.bat/.py` | `compress` |
| `convert_to_mp4.bat/.py` | `convert` |
| `extract_audio.bat/.py` | `audio` |
| `extract_frame.bat/.py` | `frame` |
| `srt_to_ass.bat/.py` | `srt2ass` |
| `remove_srt_segments.bat/.py` | `srt-remove` |
| `rename_srt_to_txt.bat` | `srt-rename` |
| `video_timeline_calculator.html` | `timeline` |
| 无 | `jianying-subtitle`（剪映字幕导出） |
| 无 | `bcut-subtitle`（必剪字幕导出） |

原项目 `D:\work\python\video-trimmer` 保持原样未作改动，本项目为自包含重写。
