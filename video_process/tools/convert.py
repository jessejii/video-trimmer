# -*- coding: utf-8 -*-
"""任意视频格式转标准 MP4。

三种模式（对应原 convert_to_mp4.py）:
    1. 极速模式  - 仅换容器（-c copy），不重编码，秒级完成
    2. CPU 编码  - libx264 重编码，兼容性最好，速度慢
    3. AMD 编码  - h264_amf 硬件重编码，速度快

输出: 与输入同目录同名 .mp4；若已存在则输出 {stem}_converted.mp4
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.amf import require_amf
from ..core.ffmpeg import FFmpegRunner, build_progress_args
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import ensure_dir, human_size, remove_files, scan_videos, validate_path
from ..core.probe import get_duration

MODE_CHOICES = [
    ("极速模式（仅换容器，不重编码）", 1),
    ("CPU 编码（libx264，兼容性最好）", 2),
    ("AMD 显卡加速（h264_amf，速度快）", 3),
]


def _default_output(input_path: str) -> str:
    """生成输出路径：同名 .mp4，已存在则加 _converted。"""
    directory = os.path.dirname(input_path) or "."
    stem, ext = os.path.splitext(os.path.basename(input_path))
    out = os.path.join(directory, f"{stem}.mp4")
    if ext.lower() != ".mp4" and os.path.exists(out):
        out = os.path.join(directory, f"{stem}_converted.mp4")
    elif ext.lower() == ".mp4":
        # 源就是 mp4 时重命名输入会冲突，统一走 _converted
        out = os.path.join(directory, f"{stem}_converted.mp4")
    return out


def _convert_one(
    runner: FFmpegRunner,
    input_file: str,
    output_file: str,
    mode: int,
) -> bool:
    ctx = runner.ctx
    duration = get_duration(input_file)

    if mode == 2:
        v_args = ["-c:v", "libx264", "-crf", "23", "-preset", "medium",
                  "-c:a", "aac", "-b:a", "128k"]
        label = "CPU 编码 (libx264)"
    elif mode == 3:
        v_args = ["-c:v", "h264_amf", "-quality", "balanced",
                  "-rc", "cqp", "-qp", "23",
                  "-c:a", "aac", "-b:a", "128k"]
        label = "AMD 显卡加速 (h264_amf)"
    else:
        v_args = ["-c", "copy"]
        label = "极速模式（仅换容器）"

    cmd = ["ffmpeg", "-y", "-i", input_file, *v_args]
    if mode != 1 and duration:
        cmd += build_progress_args()
    cmd.append(output_file)

    ctx.log(f"  模式: {label}")
    try:
        runner.run(cmd, duration=duration if mode != 1 else None,
                   description="  转换中...")
    except ToolError as exc:
        ctx.error(f"  失败: {exc}")
        remove_files([output_file])
        return False

    if not os.path.exists(output_file):
        ctx.error("  失败：未生成输出文件")
        return False

    ctx.success(f"  完成: {output_file} ({human_size(os.path.getsize(output_file))})")
    return True


def convert_to_mp4(
    input_path: str,
    mode: int = 1,
    output_dir: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """转换视频为 MP4。

    参数:
        input_path: 输入视频文件或文件夹
        mode:       1=极速, 2=CPU, 3=AMD
        output_dir: 输出目录，空表示输入同目录
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    if mode == 3:
        try:
            require_amf(ctx)
        except RuntimeError as exc:
            return TaskResult(success=False, message=str(exc))

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        if output_dir:
            ensure_dir(output_dir)
            stem, _ = os.path.splitext(os.path.basename(resolved))
            out = os.path.join(output_dir, f"{stem}.mp4")
        else:
            out = _default_output(resolved)
        ctx.log(f"处理: {os.path.basename(resolved)}")
        if _convert_one(runner, resolved, out, mode):
            outputs.append(out)
            success += 1
        else:
            failed += 1
    else:
        files = scan_videos(resolved, recursive=False)
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")
        ctx.log(f"批量模式：找到 {len(files)} 个视频")

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            if output_dir:
                ensure_dir(output_dir)
                stem, _ = os.path.splitext(os.path.basename(f))
                out = os.path.join(output_dir, f"{stem}.mp4")
            else:
                out = _default_output(f)
            ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
            ctx.progress(percent=i / len(files) * 100, file=os.path.basename(f))
            if _convert_one(runner, f, out, mode):
                outputs.append(out)
                success += 1
            else:
                failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )
