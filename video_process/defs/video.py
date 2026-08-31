# -*- coding: utf-8 -*-
"""视频处理类工具定义。

每个 ToolDefinition 由「参数规格 + 业务函数」组成，与界面无关：
界面据此渲染表单并在后台线程调用业务函数。
"""

from __future__ import annotations

from typing import List

from ..core.amf import QUALITY_CHOICES, USAGE_CHOICES
from ..param_spec import (
    ParamSpec,
    ToolDefinition,
    validate_segments,
    validate_time_points,
)
from ..tools.batch_trim import batch_trim
from ..tools.compress import QUALITY_CHOICES as COMPRESS_QUALITY_CHOICES
from ..tools.compress import compress_video
from ..tools.convert import MODE_CHOICES as CONVERT_MODE_CHOICES
from ..tools.convert import convert_to_mp4
from ..tools.extract_segments import extract_segments
from ..tools.merge import MODE_CHOICES as MERGE_MODE_CHOICES
from ..tools.merge import merge_videos
from ..tools.remove_segments import remove_segments
from ..tools.split_video import (
    KEYFRAME_MODE_CHOICES,
    MODE_CHOICES as SPLIT_MODE_CHOICES,
)
from ..tools.split_video import split_video
from ..tools.trim_edges import trim_edges

GROUP = "视频处理"

VIDEO_EXTS = [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv",
              ".m4v", ".webm", ".ts"]

#: AMD 专属参数（质量 / 用途 / 码率 / CQP），多个工具共用
def amd_specs(trigger_value: str = "amd") -> List[ParamSpec]:
    return [
        ParamSpec(
            name="quality",
            label="AMF 质量预设",
            kind="choice",
            default="balanced",
            choices=QUALITY_CHOICES,
            required=False,
            visible_when=("mode", trigger_value),
        ),
        ParamSpec(
            name="usage",
            label="AMF 用途预设",
            kind="choice",
            default="transcoding",
            choices=USAGE_CHOICES,
            required=False,
            visible_when=("mode", trigger_value),
        ),
        ParamSpec(
            name="bitrate",
            label="目标码率 kbps（可选）",
            kind="int",
            default=None,
            required=False,
            visible_when=("mode", trigger_value),
            help="留空=自动匹配原视频码率 × 0.9",
        ),
        ParamSpec(
            name="cqp",
            label="使用恒定质量模式（CQP）",
            kind="bool",
            default=False,
            required=False,
            visible_when=("mode", trigger_value),
        ),
        ParamSpec(
            name="qp",
            label="CQP 量化参数（0-51）",
            kind="int",
            default=22,
            required=False,
            visible_when=("cqp", True),
            help="越小质量越好",
        ),
    ]


MERGE = ToolDefinition(
    id="merge",
    title="视频合并",
    group=GROUP,
    description=(
        "将文件夹内的多个视频按文件名排序后合并为一个文件。\n"
        "输出: {第一个文件名}_{最后一个文件名}_merge_videos.mp4"
    ),
    specs=[
        ParamSpec(
            name="directory",
            label="视频文件夹",
            kind="dir",
            help="包含待合并视频的文件夹，按文件名排序",
        ),
        ParamSpec(
            name="mode",
            label="合并模式",
            kind="choice",
            default=1,
            choices=MERGE_MODE_CHOICES,
            help="源视频格式不一致时建议用 GPU 直接合并，可修复音画不同步",
        ),
    ],
    runner=merge_videos,
)

TRIM_EDGES = ToolDefinition(
    id="trim-edges",
    title="开头结尾裁剪（按时间点）",
    group=GROUP,
    description=(
        "按绝对时间点裁剪：保留 [开头时间, 结尾时间) 之间的内容。\n"
        "  · 开头时间：该时间点之前的内容被删除\n"
        "  · 结尾时间：该时间点之后的内容被删除（留空或填 结尾 =到视频结束）\n"
        "TS 中间流无损裁剪，不重编码。输出: {原名}_trim_edges.mp4"
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
            name="start",
            label="开头裁剪时间点",
            kind="text",
            default="0",
            required=False,
            help="支持 90 / 1:30 / 1:30:45，填 0 或留空表示不裁剪开头",
        ),
        ParamSpec(
            name="end",
            label="结尾裁剪时间点",
            kind="text",
            default="",
            required=False,
            help="支持 90 / 1:30 / 1:30:45；留空或填 结尾 表示裁剪到视频末尾（不裁结尾）",
        ),
        ParamSpec(
            name="output",
            label="输出路径（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入同目录；文件夹模式可指定为输出文件夹",
        ),
    ],
    runner=trim_edges,
)

BATCH_TRIM = ToolDefinition(
    id="batch-trim",
    title="批量裁剪（切掉固定时长）",
    group=GROUP,
    description=(
        "按「要切掉的时长」批量裁剪文件夹内所有视频。\n"
        "  · 开头切掉：从 0 秒开始往后切这么长\n"
        "  · 结尾切掉：从末尾往前切这么长\n"
        "适用于片头片尾一致的剧集或录播。默认输出到子目录 cut/。"
    ),
    specs=[
        ParamSpec(
            name="directory",
            label="视频文件夹",
            kind="dir",
            help="文件夹内的所有视频都会被处理",
        ),
        ParamSpec(
            name="start_cut",
            label="开头切掉的时长",
            kind="text",
            default="0",
            required=False,
            help="支持 90 / 1:30 / 0:01:00，0 表示不切",
        ),
        ParamSpec(
            name="end_cut",
            label="结尾切掉的时长",
            kind="text",
            default="0",
            required=False,
            help="支持 90 / 1:30 / 0:01:00，0 表示不切",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到 {输入目录}/cut",
        ),
        ParamSpec(
            name="mode",
            label="裁剪模式",
            kind="choice",
            default="fast",
            choices=[
                ("快速无损（TS 流 copy，秒级完成）", "fast"),
                ("AMD 硬件加速（AMF 重编码，帧级精确）", "amd"),
            ],
            help="快速模式切点对齐关键帧；AMD 模式帧级精确",
        ),
        ParamSpec(
            name="quality",
            label="AMF 质量预设",
            kind="choice",
            default="balanced",
            choices=QUALITY_CHOICES,
            required=False,
            visible_when=("mode", "amd"),
            help="仅 AMD 模式生效",
        ),
    ],
    runner=batch_trim,
)

REMOVE_SEGMENTS = ToolDefinition(
    id="remove-segments",
    title="片段删除（去广告）",
    group=GROUP,
    description=(
        "删除视频中的一个或多个时间段，自动合并剩余部分。\n"
        "示例: 1:00-2:00,5:00-6:00 或 1:00:00-结尾\n"
        "未指定输出文件夹时，生成 {原名}_processed.mp4（原文件保留）。"
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
            name="segments",
            label="要删除的时间段",
            kind="text",
            default="",
            validator=validate_segments,
            help="格式 开始-结束,开始-结束；时间支持 90 / 1:30 / 1:30:45 / 结尾",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入同目录",
        ),
        ParamSpec(
            name="sync_srt",
            label="自动同步同名 SRT 字幕",
            kind="bool",
            default=True,
            required=False,
            help="按实际切割边界同步字幕时间（copy 裁剪会对齐关键帧，"
                 "实际边界与请求边界有偏差，必须以实际边界同步）",
        ),
    ],
    runner=remove_segments,
)

EXTRACT_SEGMENTS = ToolDefinition(
    id="extract-segments",
    title="片段提取",
    group=GROUP,
    description=(
        "提取视频中的多个时间段，每个段输出为独立文件。\n"
        "示例: 1:00-2:00,5:00-结尾\n"
        "输出命名: {原名}_{序号}_{开始}-{结束}.mp4"
    ),
    specs=[
        ParamSpec(
            name="input_path",
            label="视频文件",
            kind="file",
            file_patterns=VIDEO_EXTS,
            help="要提取片段的单个视频文件",
        ),
        ParamSpec(
            name="segments",
            label="要提取的时间段",
            kind="text",
            default="",
            validator=validate_segments,
            help="格式 开始-结束,开始-结束；支持 结尾 表示到视频末尾",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入同目录",
        ),
        ParamSpec(
            name="mode",
            label="提取模式",
            kind="choice",
            default="fast",
            choices=[
                ("快速模式（流复制，无损极快）", "fast"),
                ("AMD 硬件加速（帧级精确）", "amd"),
            ],
            help="快速模式切点对齐关键帧；AMD 模式重新编码，帧级精确",
        ),
        *amd_specs(),
    ],
    runner=extract_segments,
)

SPLIT = ToolDefinition(
    id="split",
    title="视频分割",
    group=GROUP,
    description=(
        "按一个或多个时间点把视频分割成多段。\n"
        "示例: 1:30 或 1:30,3:00,5:20\n"
        "输出命名: {原名}_1.ext、{原名}_2.ext …"
    ),
    specs=[
        ParamSpec(
            name="input_file",
            label="视频文件",
            kind="file",
            file_patterns=VIDEO_EXTS,
            help="要分割的视频文件",
        ),
        ParamSpec(
            name="split_points",
            label="分割时间点",
            kind="text",
            default="",
            validator=validate_time_points,
            help="多个时间点用逗号分隔，支持 90 / 1:30 / 1:30:45",
        ),
        ParamSpec(
            name="mode",
            label="分割模式",
            kind="choice",
            default="fast",
            choices=SPLIT_MODE_CHOICES,
            help="AMD 模式需要支持 AMF 的 ffmpeg 与 AMD 显卡",
        ),
        ParamSpec(
            name="keyframe_mode",
            label="关键帧对齐",
            kind="choice",
            default="off",
            choices=KEYFRAME_MODE_CHOICES,
            required=False,
            visible_when=("mode", "fast"),
            help="仅快速无损模式生效；previous 可保证 copy 切割稳定",
        ),
        ParamSpec(
            name="keyframe_tolerance",
            label="严格模式容差（秒）",
            kind="float",
            default=0.30,
            required=False,
            visible_when=("keyframe_mode", "strict"),
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入同目录",
        ),
        *amd_specs(),
    ],
    runner=split_video,
)

COMPRESS = ToolDefinition(
    id="compress",
    title="视频压缩",
    group=GROUP,
    description=(
        "使用 AMD AMF 硬件编码压缩视频，音频直接复制不重编码。\n"
        "输出: {原名}_compressed{原扩展名}，保存到输入文件所在目录。\n"
        "文件夹模式递归扫描子目录，并自动跳过已压缩文件。"
    ),
    specs=[
        ParamSpec(
            name="input_path",
            label="视频文件或文件夹",
            kind="path",
            file_patterns=VIDEO_EXTS,
            help="文件夹模式会递归处理子目录",
        ),
        ParamSpec(
            name="quality",
            label="质量预设",
            kind="choice",
            default="medium",
            choices=COMPRESS_QUALITY_CHOICES,
            help="QP 值越低质量越高、文件越大",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入文件所在目录",
        ),
        ParamSpec(
            name="recursive",
            label="递归子目录",
            kind="bool",
            default=True,
            required=False,
        ),
    ],
    runner=compress_video,
)

CONVERT = ToolDefinition(
    id="convert",
    title="转换为 MP4",
    group=GROUP,
    description=(
        "将任意视频格式转换为标准 MP4。\n"
        "  · 极速模式：仅换容器，不重编码，秒级完成\n"
        "  · CPU / AMD 模式：重新编码，可修复编码错误或压缩体积\n"
        "源已是 .mp4 时输出为 {原名}_converted.mp4。"
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
            name="mode",
            label="转换模式",
            kind="choice",
            default=1,
            choices=CONVERT_MODE_CHOICES,
            help="源与目标容器兼容时优先用极速模式",
        ),
        ParamSpec(
            name="output_dir",
            label="输出文件夹（可选）",
            kind="text",
            default="",
            required=False,
            help="留空=输出到输入同目录",
        ),
    ],
    runner=convert_to_mp4,
)

DEFS = [
    MERGE,
    TRIM_EDGES,
    BATCH_TRIM,
    REMOVE_SEGMENTS,
    EXTRACT_SEGMENTS,
    SPLIT,
    COMPRESS,
    CONVERT,
]

__all__ = ["GROUP", "DEFS", "amd_specs", "VIDEO_EXTS"]
