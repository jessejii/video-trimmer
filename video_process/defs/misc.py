# -*- coding: utf-8 -*-
"""工具箱：时间线计算器与全局设置。"""

from __future__ import annotations

from ..core.amf import QUALITY_CHOICES, USAGE_CHOICES
from ..param_spec import (
    ParamSpec,
    ToolDefinition,
    validate_positive_int,
)
from ..settings_store import CONFIG_PATH
from ..tools.timeline import calculate_timeline
from ..tools.zh_convert import (
    CONVERSION_CHOICES as ZH_CONVERSION_CHOICES,
    DEFAULT_CONVERSION as ZH_DEFAULT_CONVERSION,
    convert_text,
)

GROUP = "工具箱"

TIMELINE = ToolDefinition(
    id="timeline",
    title="时间线计算器",
    group=GROUP,
    description=(
        "粘贴视频时间线，自动识别 [广告] 段落并重算后续所有时间点。\n"
        "每行格式: 时间 标题      例如: 01:33:00 [广告] 广告内容"
    ),
    specs=[
        ParamSpec(
            name="text",
            label="时间线内容",
            kind="text",
            default="",
            help="每行一条，格式如 00:00 开场介绍",
            multiline=True,
        ),
    ],
    runner=calculate_timeline,
    panel_class="timeline",
    confirm_before_run=False,
)

ZH_CONVERT = ToolDefinition(
    id="zh-convert",
    title="文本繁简转换（OpenCC）",
    group=GROUP,
    description=(
        "粘贴文本，用 OpenCC 转换简体与繁体，支持台湾正体。\n"
        "  · 简体 → 台湾正体（含习惯用语）: 软件→軟體、鼠标→滑鼠\n"
        "  · 其余方向见下方「转换方向」\n"
        "执行后结果直接替换输入框内容（Ctrl+Z 可撤销）。"
    ),
    specs=[
        ParamSpec(
            name="text",
            label="待转换文本",
            kind="text",
            default="",
            help="粘贴任意文本，不限长度",
            multiline=True,
        ),
        ParamSpec(
            name="conversion",
            label="转换方向",
            kind="choice",
            default=ZH_DEFAULT_CONVERSION,
            choices=ZH_CONVERSION_CHOICES,
            help="带「习惯用语」的会一并转换地区用词",
        ),
    ],
    runner=convert_text,
    panel_class="zh-convert",
    confirm_before_run=False,
)

#: 全局设置
SETTINGS = ToolDefinition(
    id="settings",
    title="全局设置",
    group=GROUP,
    description=(
        "这些选项会作为各工具的默认值使用。\n"
        f"配置文件: {CONFIG_PATH}"
    ),
    specs=[
        ParamSpec(
            name="amf_quality",
            label="AMF 默认质量预设",
            kind="choice",
            default="balanced",
            choices=QUALITY_CHOICES,
        ),
        ParamSpec(
            name="amf_usage",
            label="AMF 默认用途预设",
            kind="choice",
            default="transcoding",
            choices=USAGE_CHOICES,
        ),
        ParamSpec(
            name="amf_bitrate",
            label="AMF 默认目标码率 kbps（可选）",
            kind="int",
            default=None,
            required=False,
            help="留空=自动匹配原视频码率 × 0.9",
        ),
        ParamSpec(
            name="amf_cqp",
            label="AMF 默认使用恒定质量模式（CQP）",
            kind="bool",
            default=False,
            required=False,
        ),
        ParamSpec(
            name="amf_qp",
            label="AMF 默认 CQP 量化参数（0-51）",
            kind="int",
            default=22,
            required=False,
            validator=validate_positive_int,
        ),
        ParamSpec(
            name="auto_sync_srt",
            label="片段删除后自动同步同名 SRT",
            kind="bool",
            default=True,
            required=False,
        ),
        ParamSpec(
            name="find_video_root",
            label="音轨提取向上查找 video 目录",
            kind="bool",
            default=True,
            required=False,
        ),
        ParamSpec(
            name="overwrite",
            label="输出文件已存在时直接覆盖",
            kind="bool",
            default=False,
            required=False,
            help="关闭时遇到已存在的输出将报错中止",
        ),
        ParamSpec(
            name="recursive_scan",
            label="文件夹模式默认递归子目录",
            kind="bool",
            default=True,
            required=False,
        ),
    ],
    panel_class="settings",
    confirm_before_run=False,
)

DEFS = [TIMELINE, ZH_CONVERT, SETTINGS]

__all__ = ["GROUP", "DEFS", "TIMELINE", "ZH_CONVERT", "SETTINGS"]
