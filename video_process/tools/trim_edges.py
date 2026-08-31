# -*- coding: utf-8 -*-
"""视频开头结尾裁剪（时间点语义，TS 中间流无损）。

语义说明（易与 batch_trim 混淆，务必区分）:
    trim_edges:    参数是**绝对时间点** —— 保留 [start_time, end_time)
    batch_trim:    参数是**切掉的时长** —— 切掉开头 X 秒、结尾 Y 秒

实现：先无损转 TS 容器（mp4toannexb），再在 TS 上精确 seek 裁剪，
避免直接在 MP4 上 copy 裁剪导致的开头黑屏/时间戳错乱。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    cleanup_dir,
    ensure_dir,
    scan_videos,
    sibling_path,
    temp_dir_for,
    validate_path,
)
from ..core.probe import get_duration
from ..core.timeparse import TimeParseError, format_seconds, is_end_keyword, parse_time

DEFAULT_SUFFIX = "_trim_edges"


def _trim_one(
    runner: FFmpegRunner,
    input_file: str,
    start_time: Optional[float],
    end_time: Optional[float],
    output_file: str,
) -> bool:
    """裁剪单个文件，返回是否成功。"""
    ctx = runner.ctx
    duration = get_duration(input_file)
    if duration is None:
        ctx.error(f"无法获取视频时长，跳过: {os.path.basename(input_file)}")
        return False

    start = 0.0 if start_time is None else max(0.0, start_time)
    end = duration if end_time is None else end_time

    if end > duration:
        ctx.warn(f"  结尾时间 {end:.2f}s 超过视频时长 {duration:.2f}s，改用视频时长")
        end = duration
    if start >= end:
        ctx.error(f"  开头时间 {start:.2f}s 必须小于结尾时间 {end:.2f}s")
        return False

    keep_duration = end - start
    ctx.log(f"  总时长: {duration:.2f}s | 保留: {format_seconds(start)} - "
            f"{format_seconds(end, duration, use_end_label=True)} "
            f"({keep_duration:.2f}s)")

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file) or "."
    temp_dir = temp_dir_for(input_dir, "trimmed")
    temp_ts = os.path.join(temp_dir, f"{base_name}_temp.ts")

    try:
        # 步骤1: 无损转 TS 容器
        runner.run(
            ["ffmpeg", "-y", "-i", input_file, "-c", "copy",
             "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", temp_ts],
            description="  步骤1/2: 转换为 TS 容器（无损）...",
        )
        # 步骤2: 在 TS 上精确裁剪
        runner.run(
            ["ffmpeg", "-y", "-i", temp_ts, "-ss", str(start),
             "-t", str(keep_duration), "-c", "copy", output_file],
            description="  步骤2/2: 精确裁剪...",
        )
        return os.path.exists(output_file)
    except ToolError as exc:
        ctx.error(f"  裁剪失败: {exc}")
        return False
    finally:
        try:
            if os.path.exists(temp_ts):
                os.remove(temp_ts)
        except OSError:
            pass
        cleanup_dir(temp_dir)


def trim_edges(
    input_path: str,
    start: str = "0",
    end: str = "",
    output: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """裁剪视频的开头和结尾。

    参数:
        input_path: 输入视频文件或文件夹
        start:      开头裁剪时间点（该点之前的内容删除），空/0 表示不裁
        end:        结尾裁剪时间点（该点之后的内容删除），空表示不裁
        output:     输出文件或文件夹，空表示自动命名到同目录
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    # 解析时间（此时还不知道时长，按绝对时间点解析）
    raw_end = str(end or "").strip()
    try:
        start_sec = parse_time(start) if str(start).strip() else 0.0
        # 留空或"结尾"都表示不裁剪结尾（等价于裁剪到视频末尾）
        end_sec = None if (not raw_end or is_end_keyword(raw_end)) else parse_time(raw_end)
    except TimeParseError as exc:
        return TaskResult(success=False, message=f"时间格式错误: {exc}")

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        out = output or sibling_path(resolved, DEFAULT_SUFFIX, ".mp4")
        ensure_dir(os.path.dirname(out) or ".")
        ctx.log(f"处理: {os.path.basename(resolved)}")
        if _trim_one(runner, resolved, start_sec, end_sec, out):
            outputs.append(out)
            success += 1
            ctx.success(f"完成: {out}")
        else:
            failed += 1
    else:
        files = scan_videos(resolved, recursive=False)
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")
        ctx.log(f"批量模式：找到 {len(files)} 个视频")

        out_dir = output or resolved
        ensure_dir(out_dir)

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            out = sibling_path(f, DEFAULT_SUFFIX, ".mp4")
            if out_dir != resolved:
                out = os.path.join(out_dir, os.path.basename(out))
            ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
            if _trim_one(runner, f, start_sec, end_sec, out):
                outputs.append(out)
                success += 1
            else:
                failed += 1

    msg = f"完成，成功 {success} 个，失败 {failed} 个"
    return TaskResult(
        success=failed == 0 and success > 0,
        message=msg,
        outputs=outputs,
    )
