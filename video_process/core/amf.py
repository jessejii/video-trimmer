# -*- coding: utf-8 -*-
"""AMD AMF 硬件编码参数构造。

集中原项目中重复的编码器选择、quality/usage 映射与码率控制逻辑。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .probe import check_amf_support, get_bitrate, get_codec
from .models import ToolContext

# AMF quality 预设 -> ffmpeg -quality 数值
QUALITY_MAP = {"balanced": 0, "speed": 1, "quality": 2}
QUALITY_CHOICES = [("balanced（平衡）", "balanced"), ("speed（速度优先）", "speed"), ("quality（质量优先）", "quality")]

# AMF usage 预设 -> ffmpeg -usage 数值
USAGE_MAP = {"transcoding": 0, "lowlatency": 1, "ultralowlatency": 2}
USAGE_CHOICES = [
    ("transcoding（转码）", "transcoding"),
    ("lowlatency（低延迟）", "lowlatency"),
    ("ultralowlatency（超低延迟）", "ultralowlatency"),
]


def pick_encoder(codec: Optional[str], available: Optional[List[str]] = None) -> str:
    """根据源编码选择对应的 AMF 编码器，不可用时回退。

    原项目回退顺序：目标编码器 -> h264_amf -> 列表中第一个 -> 报错。
    """
    if codec in ("hevc", "h265", "libx265"):
        wanted = "hevc_amf"
    elif codec in ("av1", "libaom-av1"):
        wanted = "av1_amf"
    else:
        wanted = "h264_amf"

    encoders = available if available is not None else check_amf_support()
    if wanted in encoders:
        return wanted
    if "h264_amf" in encoders:
        return "h264_amf"
    if encoders:
        return encoders[0]
    raise RuntimeError("没有可用的 AMF 编码器")


def build_rate_control(
    ctx: ToolContext,
    input_file: str,
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
) -> Tuple[List[str], str]:
    """构造码率控制参数。

    返回: (参数列表, 人类可读描述)

    CQP 模式:  -qp_i N -qp_p N
    VBR 模式:  -rc vbr_peak -b:v {br}k -maxrate {br*1.5}k
               未指定时取原码率 * 0.9（最低 500），检测不到则 4000
    """
    if cqp:
        return ["-qp_i", str(qp), "-qp_p", str(qp)], f"CQP={qp}"

    target = bitrate
    if target is None:
        src = get_bitrate(input_file)
        if src is not None:
            target = max(500, int(src * 0.9))
            ctx.log(f"  检测到原视频码率: {src} kbps，目标码率: {target} kbps")
        else:
            target = 4000
            ctx.log(f"  无法检测原视频码率，使用默认目标码率: {target} kbps")

    return [
        "-rc", "vbr_peak",
        "-b:v", f"{target}k",
        "-maxrate", f"{int(target * 1.5)}k",
    ], f"{target} kbps VBR"


def quality_value(quality: str) -> int:
    return QUALITY_MAP.get(str(quality).lower(), 0)


def usage_value(usage: str) -> int:
    return USAGE_MAP.get(str(usage).lower(), 0)


def require_amf(ctx: ToolContext) -> List[str]:
    """检测 AMF 可用性，不可用则抛出带明确指引的异常。"""
    encoders = check_amf_support()
    if not encoders:
        ctx.error("未检测到 AMD AMF 编码器！")
        ctx.error("请确保: 1) 已安装含 AMF 运行时的 AMD 显卡驱动")
        ctx.error("        2) 使用的 ffmpeg 编译时启用了 AMF 支持")
        ctx.error("        3) 可用 `ffmpeg -encoders | findstr amf` 确认")
        raise RuntimeError("未检测到 AMD AMF 编码器")
    ctx.log(f"检测到 AMF 编码器: {', '.join(encoders)}")
    return encoders


def build_encode_args(
    ctx: ToolContext,
    input_file: str,
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    encoder: Optional[str] = None,
) -> List[str]:
    """构造完整的视频编码参数段（-c:v ... 及后续控制参数）。"""
    available = require_amf(ctx)
    codec = get_codec(input_file)
    enc = encoder or pick_encoder(codec, available)
    if enc not in available:
        ctx.warn(f"编码器 {enc} 不可用，回退为 {available[0]}")
        enc = available[0]

    rate_args, rc_desc = build_rate_control(ctx, input_file, bitrate, cqp, qp)
    ctx.log(f"  编码器: {enc} | 质量: {quality} | 用途: {usage} | 码率控制: {rc_desc}")

    return [
        "-c:v", enc,
        "-quality", str(quality_value(quality)),
        "-usage", str(usage_value(usage)),
        *rate_args,
    ]
