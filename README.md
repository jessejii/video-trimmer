# 视频处理工具集

这是一个基于 FFmpeg 的视频处理工具集，提供了多种常用的视频编辑功能，包括格式转换、合并、裁剪、片段删除和字幕转换等。

## 功能特性

- 🎬 **视频格式转换** - 将各种视频格式转换为 MP4
- 🔗 **视频合并** - 将多个视频文件合并为一个
- ✂️ **视频裁剪** - 批量去除视频开头和结尾
- 🎯 **开头结尾裁剪** - 精确裁剪视频开头和结尾时间段
- 🗑️ **片段删除** - 删除视频中的指定时间段
- 📝 **字幕转换** - SRT 字幕转换为 ASS 格式

## 系统要求

- Python 3.6+
- FFmpeg (必须安装并添加到系统 PATH)

### FFmpeg 安装

**Windows:**
1. 从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载
2. 解压到任意目录
3. 将 bin 目录添加到系统 PATH 环境变量

**验证安装:**
```bash
ffmpeg -version
```

## 工具说明

### 1. 视频格式转换 (convert_to_mp4)

将各种视频格式转换为 MP4 格式。

**使用方法:**
- 双击 `convert_to_mp4.bat` 启动交互式界面
- 支持拖拽文件到窗口
- 提供快速模式和重新编码两种选项

**支持格式:** AVI, MKV, MOV, FLV, WMV, WEBM 等

### 2. 视频合并 (merge_videos)

将多个视频文件按文件名顺序合并为一个文件。

**使用方法:**

**交互式:**
```bash
# 双击运行
merge_videos.bat

# 或直接运行 Python 脚本
python merge_videos.py
```

**功能特点:**
- 自动按文件名排序
- 使用 FFmpeg concat demuxer 快速合并
- 不重新编码，保持原始质量
- 输出文件名: `merged_output.mp4`

### 3. 视频裁剪 (trim_videos)

批量去除视频开头和结尾的指定时长。

**使用方法:**

**交互式:**
```bash
trim_videos.bat
```

**命令行:**
```bash
python trim_videos.py <开头时间> <结尾时间> [输入文件夹] [输出文件夹]
```

**时间格式:**
- 秒数: `90`
- 分:秒: `1:30`
- 时:分:秒: `1:30:30`
- 不裁剪: 留空或输入 `""`

**示例:**
```bash
# 去掉开头60秒，结尾120秒
python trim_videos.py 60 120

# 去掉开头1分30秒，结尾2分钟
python trim_videos.py 1:30 2:00

# 只去掉开头60秒
python trim_videos.py 60 ""

# 指定输入输出文件夹
python trim_videos.py 10 10 video trimmed
```

### 4. 开头结尾裁剪 (trim_edges)

精确裁剪视频的开头和结尾部分，保留中间内容。

**使用方法:**

**交互式:**
```bash
# 双击运行
trim_edges.bat
```

**命令行:**
```bash
# 裁剪开头和结尾
python trim_edges.py <视频文件> <开头时间> <结尾时间>

# 批量处理文件夹
python trim_edges.py <文件夹> <开头时间> <结尾时间> [输出文件夹]
```

**裁剪说明:**
- **开头时间**: 从 0:00 到该时间点的内容会被删除
- **结尾时间**: 从该时间点到视频结束的内容会被删除
- 支持的时间格式: `HH:MM:SS`, `MM:SS`, `SS`

**示例:**
```bash
# 删除开头0:00-1:00和结尾32:00-结束的内容
python trim_edges.py video.mp4 1:00 32:00

# 只删除开头1分钟
python trim_edges.py video.mp4 1:00

# 只删除结尾从32分钟开始的部分
python trim_edges.py video.mp4 0 32:00

# 指定输出文件
python trim_edges.py video.mp4 1:00 32:00 output.mp4

# 批量处理文件夹
python trim_edges.py video_folder 1:00 32:00 output_folder
```

**输出文件:** 自动命名为 `原文件名_trimmed.mp4`

### 5. 片段删除 (remove_segments)

删除视频中的指定时间段，保留其余部分并自动合并。

**使用方法:**

**交互式:**
```bash
remove_segments.bat
```

**命令行:**
```bash
# 处理单个文件
python remove_segments.py <视频文件> "<删除时间段>"

# 批量处理文件夹
python remove_segments.py <文件夹> "<删除时间段>" [输出文件夹]
```

**时间段格式:**
- 单个时间段: `1:00-2:00`
- 多个时间段: `1:00-2:00,5:00-6:00`
- 支持的时间格式: `HH:MM:SS`, `MM:SS`, `SS`

**示例:**
```bash
# 删除1-2分钟和5-6分钟的内容
python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00"

# 批量处理文件夹
python remove_segments.py video_folder "1:00-2:00,5:00-6:00" output_folder
```

### 6. 字幕转换 (srt_to_ass)

将 SRT 格式字幕转换为 ASS 格式。

**使用方法:**

**交互式:**
```bash
srt_to_ass.bat
```

**命令行:**
```bash
python srt_to_ass.py <srt文件路径>
```

**功能特点:**
- 自动检测文件编码 (UTF-8, GBK)
- 保持时间轴精度
- 生成标准 ASS 格式文件
- 输出文件与输入文件同名，扩展名为 `.ass`

## 文件结构

```
├── convert_to_mp4.bat      # 视频格式转换 (批处理)
├── merge_videos.bat        # 视频合并 (批处理)
├── merge_videos.py         # 视频合并 (Python脚本)
├── remove_segments.bat     # 片段删除 (批处理)
├── remove_segments.py      # 片段删除 (Python脚本)
├── srt_to_ass.bat         # 字幕转换 (批处理)
├── srt_to_ass.py          # 字幕转换 (Python脚本)
├── trim_edges.bat         # 开头结尾裁剪 (批处理)
├── trim_edges.py          # 开头结尾裁剪 (Python脚本)
├── trim_videos.bat        # 视频裁剪 (批处理)
├── trim_videos.py         # 视频裁剪 (Python脚本)
├── requirements.txt       # Python依赖 (当前为空)
└── README.md             # 使用说明
```

## 使用建议

1. **批处理文件 (.bat)** - 适合不熟悉命令行的用户，提供交互式界面
2. **Python 脚本 (.py)** - 适合需要自动化或批量处理的用户
3. **文件夹结构** - 建议创建 `video` 文件夹存放原始视频，`trimmed` 等文件夹存放处理结果

## 注意事项

- 确保 FFmpeg 已正确安装并添加到 PATH
- 处理大文件时请确保有足够的磁盘空间
- 建议在处理前备份重要视频文件
- 某些操作会生成临时文件，处理完成后会自动清理

## 常见问题

**Q: 提示找不到 ffmpeg？**
A: 请确保已安装 FFmpeg 并添加到系统 PATH 环境变量

**Q: 视频合并后音视频不同步？**
A: 确保所有视频文件具有相同的编码格式和参数

**Q: 字幕转换后中文显示乱码？**
A: 脚本会自动尝试 UTF-8 和 GBK 编码，如仍有问题请检查原始 SRT 文件编码

## 许可证

本项目仅供学习和个人使用。