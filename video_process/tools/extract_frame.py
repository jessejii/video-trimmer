# -*- coding: utf-8 -*-
"""视频截图：截取指定时间点的单帧为 JPG。

输出命名: {原文件名}_time{NN}s.jpg；超过 1 分钟时为 {原文件名}_time{MmSS}s.jpg
支持单文件与文件夹批量。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import ensure_dir, human_size, scan_videos, validate_path
from ..core.probe import get_duration
from ..core.timeparse import TimeParseError, parse_time


def _frame_name(base_name: str, time_pos: float) -> str:
    if time_pos >= 60:
        minutes = int(time_pos // 60)
        seconds = int(time_pos % 60)
        time_str = f"{minutes}m{seconds}s"
    else:
        time_str = f"{int(time_pos)}s"
    return f"{base_name}_time{time_str}.jpg"


def extract_frame(
    input_path: str,
    time_position: str = "0",
    output_dir: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """截取视频指定时间点的画面。

    参数:
        input_path:    输入视频文件或文件夹
        time_position: 时间点，支持 30 / 1:30 / 1:2:3
        output_dir:    输出目录，空表示输入同目录
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    try:
        time_sec = parse_time(time_position) if str(time_position).strip() else 0.0
    except TimeParseError as exc:
        return TaskResult(success=False, message=f"时间格式错误: {exc}")

    if time_sec < 0:
        return TaskResult(success=False, message="时间必须大于等于 0")

    ctx.log(f"截取时间点: {time_sec:.2f}s")

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        out_dir = output_dir or (os.path.dirname(resolved) or ".")
        ensure_dir(out_dir)
        stem = os.path.splitext(os.path.basename(resolved))[0]
        out_file = os.path.join(out_dir, _frame_name(stem, time_sec))
        ctx.log(f"处理: {os.path.basename(resolved)}")
        if _shot_one(runner, resolved, out_file, time_sec):
            outputs.append(out_file)
            success += 1
        else:
            failed += 1
    else:
        files = scan_videos(resolved, recursive=False)
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")
        ctx.log(f"批量模式：找到 {len(files)} 个视频")

        out_dir = output_dir or resolved
        ensure_dir(out_dir)

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            stem = os.path.splitext(os.path.basename(f))[0]
            out_file = os.path.join(out_dir, _frame_name(stem, time_sec))
            ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
            ctx.progress(percent=i / len(files) * 100, file=os.path.basename(f))
            if _shot_one(runner, f, out_file, time_sec):
                outputs.append(out_file)
                success += 1
            else:
                failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )


def _shot_one(
    runner: FFmpegRunner,
    input_file: str,
    out_file: str,
    time_sec: float,
) -> bool:
    ctx = runner.ctx
    duration = get_duration(input_file)
    if duration is not None and time_sec > duration:
        ctx.warn(f"  时间点 {time_sec:.2f}s 超过视频时长 {duration:.2f}s，将截取末尾帧")

    # -ss 放在 -i 之后（输出 seek），保证取帧位置准确；
    # 放在 -i 之前时视频轨会被拉回上一个关键帧，截图时间点会偏早。
    cmd = [
        "ffmpeg", "-y", "-i", input_file, "-ss", str(time_sec),
        "-frames:v", "1", "-q:v", "2", out_file,
    ]
    try:
        runner.run(cmd, description="  截图中...")
    except ToolError as exc:
        ctx.error(f"  失败: {exc}")
        return False

    if not os.path.exists(out_file):
        ctx.error("  失败：未生成图片")
        return False

    ctx.success(f"  完成: {os.path.basename(out_file)} "
                f"({human_size(os.path.getsize(out_file))})")
    return True
