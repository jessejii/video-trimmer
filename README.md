# 视频处理工具集

一套简单易用的 Python 视频处理脚本，支持批量视频合并和裁剪功能。

## 功能特性

- **视频合并** (`merge_videos.py`)：自动读取文件夹中的所有视频，按名称排序后合并
- **视频裁剪** (`trim_videos.py`)：批量裁剪视频开头和结尾
- **删除视频片段** (`remove_segments.py`)：删除视频中的指定时间段，保留其余部分并自动合并

## 环境要求

- Python 3.6+
- FFmpeg（需要添加到系统 PATH）

### 安装 FFmpeg

**Windows:**
```bash
# 使用 Chocolatey
choco install ffmpeg

# 或从官网下载: https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg  # CentOS/RHEL
```

## 使用说明

### 1. 视频合并 (merge_videos.py)

自动读取 `video` 文件夹中的所有视频文件，按文件名排序后合并为一个视频。

#### 基本用法

```bash
# 合并 video 文件夹中的所有视频，输出到 out/output.mp4
python merge_videos.py
```

#### 高级用法

```bash
# 指定输入文件夹
python merge_videos.py my_videos

# 指定输入文件夹和输出文件名
python merge_videos.py my_videos merged.mp4
```

#### 文件夹结构

```
project/
├── video/              # 输入文件夹
│   ├── 1.mp4
│   ├── 2.mp4
│   └── 3.mp4
└── out/                # 输出文件夹（自动创建）
    └── output.mp4
```

#### 支持的视频格式

- MP4, AVI, MOV, MKV, FLV, WMV, M4V, WEBM

### 2. 删除视频片段 (remove_segments.py)

删除视频中的指定时间段，保留其余部分并自动合并成新视频。适合删除广告、不需要的片段等。

#### 基本用法

```bash
# 删除 1:00-2:00 和 5:00-6:00 两个时间段
python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00"

# 指定输出文件
python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00" output.mp4
```

#### 时间段格式

- 使用逗号分隔多个时间段：`"1:00-2:00,5:00-6:00"`
- 每个时间段使用连字符连接开始和结束时间：`"开始-结束"`
- 时间格式支持：`HH:MM:SS`、`MM:SS`、`SS`

#### 示例

```bash
# 删除开头1分钟的片头
python remove_segments.py video.mp4 "0:00-1:00"

# 删除多个广告片段
python remove_segments.py movie.mp4 "5:30-7:00,15:20-17:45,45:00-47:30"

# 使用秒数格式（删除 60-120 秒和 300-360 秒）
python remove_segments.py video.mp4 "60-120,300-360"
```

#### 工作原理

1. 解析要删除的时间段
2. 计算要保留的时间段
3. 提取每个保留片段到临时文件
4. 合并所有保留片段为最终视频
5. 自动清理临时文件

### 3. 视频裁剪 (trim_videos.py)

批量裁剪 `video` 文件夹中的所有视频，去掉开头和结尾指定时长。

#### 基本用法

```bash
# 去掉开头 60 秒，结尾 120 秒
python trim_videos.py 60 120
```

#### 时间格式

支持多种时间格式输入：

| 格式 | 示例 | 说明 |
|------|------|------|
| 秒数 | `90` | 90秒 |
| 分:秒 | `1:30` | 1分30秒 |
| 时:分:秒 | `1:30:30` | 1小时30分30秒 |

```bash
# 秒数格式
python trim_videos.py 60 120

# 分:秒 格式（去掉开头1分30秒，结尾2分钟）
python trim_videos.py 1:30 2:00

# 时:分:秒 格式（去掉开头1小时30分30秒，结尾45分钟）
python trim_videos.py 1:30:30 0:45:00
```

#### 高级用法

```bash
# 指定输入和输出文件夹
python trim_videos.py 60 120 video trimmed
```

#### 文件夹结构

```
project/
├── video/              # 输入文件夹
│   ├── 1.mp4
│   ├── 2.mp4
│   └── 3.mp4
└── trimmed/            # 输出文件夹（自动创建）
    ├── 1.mp4
    ├── 2.mp4
    └── 3.mp4
```

## 使用示例

### 场景 1：合并多个视频片段

```bash
# 1. 将视频文件放入 video 文件夹，命名为 1.mp4, 2.mp4, 3.mp4
# 2. 运行合并脚本
python merge_videos.py

# 3. 合并后的视频保存在 out/output.mp4
```

### 场景 2：批量去除视频片头片尾

```bash
# 1. 将视频文件放入 video 文件夹
# 2. 去掉开头 10 秒，结尾 5 秒
python trim_videos.py 10 5

# 或使用时分秒格式：去掉开头1分钟，结尾30秒
python trim_videos.py 1:00 30

# 3. 处理后的视频保存在 trimmed 文件夹
```

### 场景 3：删除视频中的多个时间段

```bash
# 删除 1:00-2:00 和 5:00-6:00 两个时间段
python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00"

# 指定输出文件名
python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00" out/edited.mp4

# 删除多个片段（例如删除广告）
python remove_segments.py movie.mp4 "10:30-12:00,45:00-47:30,1:20:00-1:22:00"
```

### 场景 4：先裁剪再合并

```bash
# 1. 裁剪视频（去掉开头1分钟，结尾2分钟）
python trim_videos.py 1:00 2:00

# 2. 将裁剪后的视频从 trimmed 文件夹移动到 video 文件夹
# 3. 合并视频
python merge_videos.py
```

## 技术说明

### 视频合并原理

使用 FFmpeg 的 concat demuxer 进行无损合并：
- 创建临时文件列表 `list.txt`
- 使用 `-c copy` 参数直接复制流，不重新编码
- 合并速度快，无质量损失

### 视频裁剪原理

使用 FFmpeg 的时间裁剪功能：
- 使用 `-ss` 参数指定开始时间
- 使用 `-t` 参数指定持续时间
- 使用 `-c copy` 参数避免重新编码
- 自动获取视频时长并验证裁剪参数

## 注意事项

1. 视频文件名建议使用数字或字母顺序命名，以确保正确的合并顺序
2. 合并的视频需要具有相同的编码格式、分辨率和帧率，否则可能出现问题
3. 裁剪时间不能超过视频总时长
4. 使用 `-c copy` 模式处理速度快但可能在某些情况下不够精确

## 常见问题

**Q: 提示找不到 ffmpeg？**

A: 请确保已安装 FFmpeg 并添加到系统 PATH 环境变量。

**Q: 合并后的视频播放有问题？**

A: 确保所有视频具有相同的编码格式、分辨率和帧率。

**Q: 裁剪不够精确？**

A: 使用 `-c copy` 模式会在关键帧处裁剪，如需精确裁剪可以修改脚本去掉 `-c copy` 参数（但会重新编码，速度较慢）。

## 许可证

MIT License
