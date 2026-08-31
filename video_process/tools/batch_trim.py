# -*- coding: utf-8 -*-
"""批量裁剪开头结尾（时长语义）。

与 trim_edges 的区别：
    本工具参数是**要切掉的时长** —— 切掉开头 X 秒、结尾 Y 秒，
    适用于批量处理片头片尾一致的剧集或录播。原脚本输出到子目录 cut/。

两种实现：
    fast: 转 TS 中间流后 copy 裁剪（无损、秒级完成）
    amd:  AMD AMF 硬件重编码（帧级精确，可指定质量预设）
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.amf import build_encode_args, require_amf
from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    cleanup_dir,
    ensure_dir,
    scan_videos,
    temp_dir_for,
    validate_path,
)
from ..core.probe import get_duration
from ..core.timeparse import TimeParseError, parse_time

OUTPUT_SUBDIR = "cut"


def _resolve_output_dir(input_dir: str, output_dir: Optional[str]) -> str:
    """未指定输出目录时使用子目录 cut/（与原 batch_trim_edges.py 一致）。"""
    if output_dir:
        ensure_dir(output_dir)
        return output_dir
    out = os.path.join(input_dir, OUTPUT_SUBDIR)
    ensure_dir(out)
    return out


def _trim_fast(
    runner: FFmpegRunner,
    input_file: str,
    start_cut: float,
    end_cut: float,
    output_dir: str,
) -> bool:
    """TS 中间流无损裁剪。"""
    ctx = runner.ctx
    duration = get_duration(input_file)
    if duration is None:
        ctx.error("  无法获取视频时长")
        return False

    keep_start = start_cut
    keep_end = duration - end_cut
    keep_duration = keep_end - keep_start

    if keep_duration <= 0:
        ctx.error(
            f"  裁剪后时长 <= 0（总长 {duration:.2f}s，"
            f"切开头 {start_cut:.2f}s，切结尾 {end_cut:.2f}s）"
        )
        return False

    ctx.log(f"  总长 {duration:.2f}s，保留 {keep_start:.2f}s - {keep_end:.2f}s "
            f"（{keep_duration:.2f}s）")

    base_name = os.path.basename(input_file)
    out_file = os.path.join(output_dir, base_name)
    temp_dir = temp_dir_for(output_dir, "trimmed")
    temp_ts = os.path.join(temp_dir, f"{base_name}.ts")

    try:
        runner.run(
            ["ffmpeg", "-y", "-i", input_file, "-c", "copy",
             "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", temp_ts],
            description="  步骤1/2: 转 TS（无损）...",
        )
        runner.run(
            ["ffmpeg", "-y", "-i", temp_ts, "-ss", str(keep_start),
             "-t", str(keep_duration), "-c", "copy", out_file],
            description="  步骤2/2: 精确裁剪...",
        )
        ctx.success(f"  完成: {out_file}")
        return True
    except ToolError as exc:
        ctx.error(f"  失败: {exc}")
        return False
    finally:
        try:
            if os.path.exists(temp_ts):
                os.remove(temp_ts)
        except OSError:
            pass
        cleanup_dir(temp_dir)


def _trim_amd(
    runner: FFmpegRunner,
    input_file: str,
    start_cut: float,
    end_cut: float,
    output_dir: str,
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
) -> bool:
    """AMD AMF 硬件重编码裁剪（帧级精确）。"""
    ctx = runner.ctx
    duration = get_duration(input_file)
    if duration is None:
        ctx.error("  无法获取视频时长")
        return False

    keep_start = start_cut
    keep_duration = duration - end_cut - start_cut
    if keep_duration <= 0:
        ctx.error(f"  裁剪后时长 <= 0（总长 {duration:.2f}s）")
        return False

    ctx.log(f"  总长 {duration:.2f}s，保留 {keep_start:.2f}s 起 {keep_duration:.2f}s")

    base_name = os.path.basename(input_file)
    out_file = os.path.join(output_dir, base_name)

    try:
        enc_args = build_encode_args(
            ctx, input_file, quality=quality, usage=usage,
            bitrate=bitrate, cqp=cqp, qp=qp,
        )
        runner.run(
            ["ffmpeg", "-y", "-hwaccel", "amf", "-hwaccel_output_format", "d3d11",
             "-i", input_file, "-ss", str(keep_start), "-t", str(keep_duration),
             *enc_args,
             "-c:a", "copy", "-avoid_negative_ts", "make_zero", out_file],
            duration=keep_duration,
            description="  AMD 重编码裁剪中...",
        )
        ctx.success(f"  完成: {out_file}")
        return True
    except (ToolError, RuntimeError) as exc:
        ctx.error(f"  失败: {exc}")
        return False


def batch_trim(
    directory: str,
    start_cut: str = "0",
    end_cut: str = "0",
    output_dir: str = "",
    mode: str = "fast",
    quality: str = "balanced",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """批量裁剪文件夹内所有视频的开头与结尾。

    参数:
        directory:  输入文件夹
        start_cut:  开头要切掉的时长（支持 1:30 / 90 / 0:01:00）
        end_cut:    结尾要切掉的时长
        output_dir: 输出文件夹，空表示 {输入目录}/cut
        mode:       "fast"（TS 无损）或 "amd"（AMF 重编码）
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(directory, kind="dir")
    if not ok:
        return TaskResult(success=False, message=err)

    try:
        start_sec = parse_time(start_cut) if str(start_cut).strip() else 0.0
        end_sec = parse_time(end_cut) if str(end_cut).strip() else 0.0
    except TimeParseError as exc:
        return TaskResult(success=False, message=f"时间格式错误: {exc}")

    files = scan_videos(resolved, recursive=False)
    if not files:
        return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")

    out_dir = _resolve_output_dir(resolved, output_dir or None)
    ctx.log(f"找到 {len(files)} 个视频文件")
    ctx.log(f"切掉开头: {start_sec:.2f}s | 切掉结尾: {end_sec:.2f}s")
    ctx.log(f"输出目录: {out_dir}")
    ctx.log(f"模式: {'AMD AMF 重编码' if mode == 'amd' else 'TS 流无损'}")

    if mode == "amd":
        require_amf(ctx)

    outputs: List[str] = []
    success = 0
    failed = 0

    for i, f in enumerate(files, 1):
        ctx.check_cancel()
        ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
        ctx.progress(percent=i / len(files) * 100, file=os.path.basename(f))

        if mode == "amd":
            ok_one = _trim_amd(runner, f, start_sec, end_sec, out_dir,
                               quality, usage, bitrate, cqp, qp)
        else:
            ok_one = _trim_fast(runner, f, start_sec, end_sec, out_dir)

        if ok_one:
            success += 1
            outputs.append(os.path.join(out_dir, os.path.basename(f)))
        else:
            failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )
