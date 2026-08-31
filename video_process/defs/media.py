# -*- coding: utf-8 -*-
"""音视频提取类工具定义。"""

from __future__ import annotations

from ..core.paths import VIDEO_EXTENSIONS
from ..param_spec import ParamSpec, ToolDefinition
from ..tools.extract_audio import extract_audio
from ..tools.extract_frame import extract_frame

GROUP = "音视频提取"

VIDEO_EXTS = list(VIDEO_EXTENSIONS)

AUDIO = ToolDefinition(
    id="audio",
    title="音轨提取（转 MP3）",
    group=GROUP,
    description=(
        "提取视频中的所有音轨，逐条重编码为 MP3。\n"
        "使用 libmp3lame VBR 最高压缩（-q:a 9），约 65-85 kbps。\n"
        "命名: 单音轨 {原名}.mp3；多音轨 {原名}_track{N}_{语言}.mp3"
    ),
    specs=[
        ParamSpec(
            name="input_path",
            label="视频文件或文件夹",
            kind="path",
            file_patterns=VIDEO_EXTS,
            help="支持单个视频或整个文件夹批量处理",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="outdir",
            default="",
            required=False,
            help="留空时按下方策略自动推断",
        ),
        ParamSpec(
            name="find_video_root_dir",
            label="向上查找名为 video 的目录作为输出根",
            kind="bool",
            default=True,
            required=False,
            help="原项目的隐含约定：找不到 video 目录时才回退到输入目录",
        ),
        ParamSpec(
            name="recursive",
            label="递归子目录",
            kind="bool",
            default=True,
            required=False,
        ),
    ],
    runner=extract_audio,
)

FRAME = ToolDefinition(
    id="frame",
    title="视频截图",
    group=GROUP,
    description=(
        "截取视频指定时间点的单帧画面为 JPG。\n"
        "输出命名: {原名}_time{NN}s.jpg（超过 1 分钟为 {原名}_time{MmSS}s.jpg）\n"
        "支持单文件与文件夹批量截图。"
    ),
    specs=[
        ParamSpec(
            name="input_path",
            label="视频文件或文件夹",
            kind="path",
            file_patterns=VIDEO_EXTS,
            help="支持单个视频或整个文件夹批量处理",
        ),
        ParamSpec(
            name="time_position",
            label="截取时间点",
            kind="text",
            default="0",
            required=False,
            help="支持 30（秒）/ 1:30（分:秒）/ 1:2:3（时:分:秒），0 表示第 0 秒",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="outdir",
            default="",
            required=False,
            help="留空=输出到输入同目录",
        ),
    ],
    runner=extract_frame,
)

DEFS = [AUDIO, FRAME]

__all__ = ["GROUP", "DEFS"]
