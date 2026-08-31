# -*- coding: utf-8 -*-
"""按多个时间点分割视频。

两种模式（对应原 split_video.py）:
    fast:    快速无损分割 —— 逐段提取 TS 后 remux（不重编码），关键帧对齐更稳
    precise: 精确分割     —— 按源编码选择 libx265/libvpx-vp9/libx264 重编码，帧级精确

关键帧对齐（可选，仅用于无损模式）:
    off      不对齐
    previous 对齐到请求点之前最近的关键帧（推荐，保证 copy 切割稳定）
    nearest  对齐到最近关键帧
    strict   要求请求点附近必须有关键帧，偏差超过 tolerance 则报错

输出命名: {原文件名}_1.ext, {原文件名}_2.ext ...
"""

from __future__ import annotations

import bisect
import os
from typing import List, Optional, Tuple

from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    cleanup_dir,
    ensure_dir,
    remove_files,
    temp_dir_for,
    validate_path,
)
from ..core.probe import get_codec, get_duration, get_keyframes
from ..core.timeparse import TimeParseError, format_seconds, parse_time

KEYFRAME_MODE_CHOICES = [
    ("off（不对齐）", "off"),
    ("previous（向前对齐，推荐）", "previous"),
    ("nearest（最近关键帧）", "nearest"),
    ("strict（严格，受容差约束）", "strict"),
]

MODE_CHOICES = [
    ("快速无损分割（copy，关键帧对齐更稳）", "fast"),
    ("精确分割（重编码，帧级精确）", "precise"),
    ("AMD 加速分割（AMF 重编码，帧级精确）", "amd"),
]


def align_cut_points_to_keyframes(
    requested: List[float],
    keyframes: List[float],
    duration: float,
    mode: str = "previous",
    tolerance: float = 0.30,
) -> Tuple[List[float], List[Tuple[float, float, float]]]:
    """把请求切点对齐到关键帧。

    返回: (对齐后的切点列表, [(请求点, 实际点, 偏差), ...])
    """
    if not keyframes:
        raise ToolError("未检测到关键帧，无法执行关键帧对齐")

    aligned: List[float] = []
    mapping: List[Tuple[float, float, float]] = []

    for req in requested:
        if req <= 0 or req >= duration:
            raise ToolError(f"分割时间 {req:.3f}s 超出有效范围 (0, {duration:.3f})")

        prev_kf = None
        next_kf = None
        idx = bisect.bisect_right(keyframes, req)
        if idx > 0:
            prev_kf = keyframes[idx - 1]
        if idx < len(keyframes):
            next_kf = keyframes[idx]

        if mode == "previous":
            if prev_kf is None:
                raise ToolError(f"{req:.3f}s 之前没有可用关键帧，无法向前对齐")
            chosen = prev_kf
        elif mode == "nearest":
            candidates = [kf for kf in (prev_kf, next_kf) if kf is not None]
            if not candidates:
                raise ToolError(f"{req:.3f}s 附近无可用关键帧")
            chosen = min(candidates, key=lambda x: abs(x - req))
        elif mode == "strict":
            candidates = []
            if prev_kf is not None:
                candidates.append(prev_kf)
            if next_kf is not None and next_kf != prev_kf:
                candidates.append(next_kf)
            if not candidates:
                raise ToolError(f"{req:.3f}s 附近无可用关键帧")
            chosen = min(candidates, key=lambda x: abs(x - req))
            if abs(chosen - req) > tolerance:
                raise ToolError(
                    f"严格关键帧模式: 请求点 {req:.3f}s 与最近关键帧 {chosen:.3f}s "
                    f"偏差 {abs(chosen - req):.3f}s 超过容差 {tolerance:.3f}s"
                )
        else:
            raise ToolError(f"未知关键帧对齐模式: {mode}")

        aligned.append(chosen)
        mapping.append((req, chosen, chosen - req))

    return sorted(set(aligned)), mapping


def _build_segments(split_times: List[float], duration: float) -> List[Tuple[float, float]]:
    """切点列表 -> 时间段列表。"""
    segments: List[Tuple[float, float]] = []
    prev = 0.0
    for t in split_times:
        segments.append((prev, t))
        prev = t
    segments.append((prev, duration))
    return segments


def _precise_codec_args(codec: Optional[str]) -> List[str]:
    """根据源编码选择重编码参数。"""
    if codec in ("hevc", "h265", "libx265"):
        return ["-c:v", "libx265", "-crf", "18", "-preset", "medium"]
    if codec in ("vp9", "libvpx-vp9"):
        return ["-c:v", "libvpx-vp9", "-crf", "18", "-b:v", "0"]
    return ["-c:v", "libx264", "-crf", "18", "-preset", "medium"]


def split_video(
    input_file: str,
    split_points: str,
    mode: str = "fast",
    keyframe_mode: str = "off",
    keyframe_tolerance: float = 0.30,
    output_dir: str = "",
    # AMD 模式专用
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """按时间点分割视频。

    参数:
        input_file:         输入视频文件
        split_points:       分割时间点，逗号分隔，如 "1:30,3:00,5:20"
        mode:               "fast" / "precise" / "amd"
        keyframe_mode:      关键帧对齐模式（仅 fast 模式有意义）
        keyframe_tolerance: strict 模式容差（秒）
        output_dir:         输出目录，空表示输入同目录
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_file, kind="file")
    if not ok:
        return TaskResult(success=False, message=err)

    duration = get_duration(resolved)
    if duration is None:
        return TaskResult(success=False, message="无法获取视频时长")
    codec = get_codec(resolved)

    # ---- 解析分割点 ----
    try:
        requested = sorted({parse_time(s.strip())
                            for s in split_points.split(",") if s.strip()})
    except TimeParseError as exc:
        return TaskResult(success=False, message=f"时间格式错误: {exc}")

    if not requested:
        return TaskResult(success=False, message="未提供有效的分割时间点")
    if any(t <= 0 for t in requested):
        return TaskResult(success=False, message="分割时间必须大于 0")
    if requested[-1] >= duration:
        return TaskResult(
            success=False,
            message=f"最大分割时间 {format_seconds(requested[-1])} 超过视频总时长 "
                    f"{format_seconds(duration)}",
        )

    split_times = list(requested)

    # ---- 关键帧对齐（仅无损模式） ----
    if keyframe_mode != "off" and mode == "fast":
        ctx.log("正在检测关键帧...")
        keyframes = get_keyframes(resolved)
        if not keyframes:
            ctx.warn("未能获取关键帧，回退为不对齐模式")
        else:
            try:
                split_times, mapping = align_cut_points_to_keyframes(
                    requested, keyframes, duration, keyframe_mode, keyframe_tolerance
                )
                ctx.log("关键帧对齐详情（请求 -> 实际, 偏差）:")
                for req, actual, delta in mapping:
                    sign = "+" if delta >= 0 else ""
                    ctx.log(f"  {format_seconds(req)} -> {format_seconds(actual)} "
                            f"({sign}{delta:.3f}s)")
            except ToolError as exc:
                return TaskResult(success=False, message=str(exc))

    segments = _build_segments(split_times, duration)

    ctx.log(f"文件: {os.path.basename(resolved)}")
    ctx.log(f"时长: {duration:.2f}s | 编码: {codec or 'unknown'}")
    ctx.log(f"请求分割点: {', '.join(format_seconds(t) for t in requested)}")
    ctx.log(f"实际分割点: {', '.join(format_seconds(t) for t in split_times)}")
    ctx.log(f"模式: {mode}")

    # ---- 输出路径 ----
    out_dir = output_dir or (os.path.dirname(resolved) or ".")
    if output_dir:
        ensure_dir(out_dir)
    name_wo_ext, ext = os.path.splitext(os.path.basename(resolved))
    out_files = [os.path.join(out_dir, f"{name_wo_ext}_{i}{ext}")
                 for i in range(1, len(segments) + 1)]

    try:
        if mode == "precise":
            _split_precise(runner, resolved, segments, out_files, codec)
        elif mode == "amd":
            _split_amd(runner, resolved, segments, out_files,
                       quality, usage, bitrate, cqp, qp)
        else:
            _split_fast(runner, resolved, segments, out_files, out_dir, name_wo_ext)
    except ToolError as exc:
        remove_files(out_files)
        return TaskResult(success=False, message=str(exc))

    ctx.success(f"分割完成！共 {len(segments)} 段")
    for i, f in enumerate(out_files):
        start, end = segments[i]
        ctx.success(f"  {i + 1}. {os.path.basename(f)} "
                    f"({format_seconds(start)} - {format_seconds(end)})")

    return TaskResult(
        success=True,
        message=f"分割完成，共 {len(segments)} 段",
        outputs=out_files,
    )


def _split_fast(
    runner: FFmpegRunner,
    input_file: str,
    segments: List[Tuple[float, float]],
    out_files: List[str],
    out_dir: str,
    name_wo_ext: str,
) -> None:
    """逐段提取 TS -> 逐段 remux 为目标格式（不重编码）。"""
    ctx = runner.ctx
    temp_dir = temp_dir_for(out_dir, "trimmed_split")
    ts_files: List[str] = []

    try:
        ctx.log("逐段提取 TS（无损）...")
        remove_files(out_files)
        for i, (start, end) in enumerate(segments):
            ctx.check_cancel()
            ts_path = os.path.join(temp_dir, f"{name_wo_ext}_seg_{i:03d}.ts")
            seg_duration = max(0.0, end - start)
            runner.run(
                ["ffmpeg", "-y", "-i", input_file, "-ss", str(start),
                 "-t", str(seg_duration), "-c", "copy",
                 "-bsf:v", "h264_mp4toannexb", "-f", "mpegts",
                 "-avoid_negative_ts", "make_zero", ts_path],
                duration=seg_duration,
                description=f"  提取 {i + 1}/{len(segments)}: "
                            f"{format_seconds(start)}-{format_seconds(end)}",
            )
            ts_files.append(ts_path)

        ctx.log("逐段 remux 为输出格式...")
        for i, ts_file in enumerate(ts_files):
            ctx.check_cancel()
            runner.run(
                ["ffmpeg", "-y", "-i", ts_file, "-c", "copy",
                 "-movflags", "+faststart", out_files[i]],
                description=f"  转封装 {i + 1}/{len(segments)} -> "
                            f"{os.path.basename(out_files[i])}",
            )
    finally:
        remove_files(ts_files)
        cleanup_dir(temp_dir)


def _split_precise(
    runner: FFmpegRunner,
    input_file: str,
    segments: List[Tuple[float, float]],
    out_files: List[str],
    codec: Optional[str],
) -> None:
    """精确分割：重编码视频，帧级精确。"""
    ctx = runner.ctx
    v_args = _precise_codec_args(codec)
    ctx.log(f"精确分割（重编码: {v_args[1]}）...")

    for i, (start, end) in enumerate(segments):
        ctx.check_cancel()
        seg_duration = max(0.0, end - start)
        runner.run(
            ["ffmpeg", "-y", "-ss", str(start), "-i", input_file,
             "-t", str(seg_duration), *v_args,
             "-c:a", "copy", "-avoid_negative_ts", "make_zero", out_files[i]],
            duration=seg_duration,
            description=f"  生成第 {i + 1}/{len(segments)} 段 "
                        f"({format_seconds(start)} - {format_seconds(end)})",
        )


def _split_amd(
    runner: FFmpegRunner,
    input_file: str,
    segments: List[Tuple[float, float]],
    out_files: List[str],
    quality: str,
    usage: str,
    bitrate: Optional[int],
    cqp: bool,
    qp: int,
) -> None:
    """AMD AMF 硬件加速分割（帧级精确，无需关键帧对齐）。"""
    from ..core.amf import build_encode_args, require_amf

    ctx = runner.ctx
    require_amf(ctx)

    for i, (start, end) in enumerate(segments):
        ctx.check_cancel()
        seg_duration = max(0.0, end - start)
        enc_args = build_encode_args(
            ctx, input_file, quality=quality, usage=usage,
            bitrate=bitrate, cqp=cqp, qp=qp,
        )
        runner.run(
            ["ffmpeg", "-y", "-hwaccel", "amf", "-hwaccel_output_format", "d3d11",
             "-i", input_file, "-ss", str(start), "-t", str(seg_duration),
             *enc_args,
             "-c:a", "copy", "-avoid_negative_ts", "make_zero", out_files[i]],
            duration=seg_duration,
            description=f"  AMD 生成第 {i + 1}/{len(segments)} 段 "
                        f"({format_seconds(start)} - {format_seconds(end)})",
        )
