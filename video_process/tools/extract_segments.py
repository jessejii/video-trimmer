# -*- coding: utf-8 -*-
"""提取视频中的多个时间段，每段输出为独立文件。

两种模式（对应原 extract_segments.py）:
    fast: 流复制（-c copy），无损、速度极快，切点对齐关键帧
    amd:  AMD AMF 硬件重编码，帧级精确，可指定质量预设与码率

输出命名: {原文件名}_{序号:03d}_{开始}-{结尾}.mp4
    例: video_001_01.00.00.000-02.00.00.000.mp4
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.amf import build_encode_args, require_amf
from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import ensure_dir, validate_path
from ..core.probe import get_duration
from ..core.timeparse import (
    format_seconds,
    format_seconds_compact,
    parse_segments,
    segments_to_csv,
)

MODE_CHOICES = [
    ("快速模式（流复制，无损极快）", "fast"),
    ("AMD 硬件加速（帧级精确）", "amd"),
]


def _output_name(base_name: str, index: int, start: float, end: float) -> str:
    return f"{base_name}_{index:03d}_{format_seconds_compact(start)}-{format_seconds_compact(end)}.mp4"


def _extract_one(
    runner: FFmpegRunner,
    input_file: str,
    segs: List[tuple],
    output_dir: str,
    duration: Optional[float] = None,
    mode: str = "fast",
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
) -> List[str]:
    """提取单个文件的所有时间段，返回输出文件列表。"""
    ctx = runner.ctx
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    outputs: List[str] = []

    for i, (start, end) in enumerate(segs):
        ctx.check_cancel()
        seg_duration = end - start
        out_file = os.path.join(output_dir, _output_name(base_name, i + 1, start, end))

        if mode == "amd":
            enc_args = build_encode_args(
                ctx, input_file, quality=quality, usage=usage,
                bitrate=bitrate, cqp=cqp, qp=qp,
            )
            cmd = [
                "ffmpeg", "-y",
                "-hwaccel", "amf", "-hwaccel_output_format", "d3d11",
                "-i", input_file,
                "-ss", str(start), "-t", str(seg_duration),
                *enc_args,
                "-c:a", "copy",
                "-avoid_negative_ts", "make_zero",
                out_file,
            ]
        else:
            # -ss 放在 -i 之后（输出 seek）。
            # 若放在 -i 之前（输入 seek），视频轨会被拉回上一个关键帧而音频轨
            # 精确 seek，两者起点不一致 -> 音画不同步且片段时长远超请求值。
            # 输出 seek 会先对齐音视频再开始输出，对 copy 模式几乎没有性能损失。
            cmd = [
                "ffmpeg", "-y",
                "-i", input_file,
                "-ss", str(start),
                "-t", str(seg_duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                out_file,
            ]

        try:
            runner.run(
                cmd,
                duration=seg_duration,
                description=f"  提取 {i + 1}/{len(segs)}: "
                            f"{format_seconds(start)} - "
                            f"{format_seconds(end, duration, use_end_label=True)}",
            )
            outputs.append(out_file)
            ctx.success(f"    输出: {os.path.basename(out_file)}")
        except ToolError as exc:
            ctx.error(f"    提取片段 {i + 1} 失败: {exc}")

    return outputs


def extract_segments(
    input_path: str,
    segments: str,
    output_dir: str = "",
    mode: str = "fast",
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """提取视频中的指定时间段。

    参数:
        input_path: 输入视频文件
        segments:   提取时间段，如 "开头-2:00,5:00-结尾"，支持"开头"/"结尾"关键字
        output_dir: 输出文件夹，空表示输入同目录
        mode:       "fast" 或 "amd"
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path, kind="file")
    if not ok:
        return TaskResult(success=False, message=err)

    if mode == "amd":
        try:
            require_amf(ctx)
        except RuntimeError as exc:
            return TaskResult(success=False, message=str(exc))

    duration = get_duration(resolved)
    if duration is None:
        return TaskResult(success=False, message="无法获取视频时长")

    ctx.log(f"文件: {os.path.basename(resolved)}")
    ctx.log(f"总时长: {duration:.2f}s ({duration / 60:.2f}min)")

    segs, warnings = parse_segments(segments, duration)
    for w in warnings:
        ctx.warn(w)
    if not segs:
        return TaskResult(success=False, message="没有有效的时间段需要提取")

    out_dir = output_dir or (os.path.dirname(resolved) or ".")
    ensure_dir(out_dir)

    ctx.log(f"要提取的时间段: {segments_to_csv(segs, duration, use_end_label=True)}")
    ctx.log(f"提取模式: {'AMD 硬件加速' if mode == 'amd' else '快速流复制'}")
    outputs = _extract_one(runner, resolved, segs, out_dir, duration, mode,
                           quality, usage, bitrate, cqp, qp)
    failed = len(segs) - len(outputs)

    return TaskResult(
        success=failed == 0 and bool(outputs),
        message=f"完成，成功 {len(outputs)} 个片段，失败 {failed} 个",
        outputs=outputs,
        warnings=warnings,
    )
