# -*- coding: utf-8 -*-
"""视频压缩：AMD AMF 硬件编码，三档质量预设。

质量预设（QP 值越低质量越高、文件越大）:
    low    QP 28 / speed     文件最小
    medium QP 23 / balanced  平衡（默认）
    high   QP 18 / quality   文件较大

输出: {原文件名}_compressed{原扩展名}，保存到输入文件所在目录。
批量模式递归扫描子目录，并**跳过文件名含 _compressed 的文件**，
否则重复运行会对已压缩文件反复压缩。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.amf import build_encode_args, require_amf
from ..core.ffmpeg import FFmpegRunner, build_progress_args
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    ensure_dir,
    human_size,
    remove_files,
    scan_videos,
    validate_path,
)
from ..core.probe import get_codec, get_duration, get_bitrate

QUALITY_CHOICES = [
    ("低质量（文件最小，QP 28）", "low"),
    ("中等质量（平衡，QP 23）", "medium"),
    ("高质量（文件较大，QP 18）", "high"),
]

QUALITY_PRESETS = {
    "low": {"qp": "28", "amf_quality": "speed"},
    "medium": {"qp": "23", "amf_quality": "balanced"},
    "high": {"qp": "18", "amf_quality": "quality"},
}

COMPRESSED_MARKER = "_compressed"


def _compress_one(
    runner: FFmpegRunner,
    input_file: str,
    output_dir: str,
    quality: str = "low",
    usage: str = "transcoding",
    bitrate: Optional[int] = None,
    cqp: bool = True,
    qp: int = 28,
) -> Optional[str]:
    """压缩单个文件，返回输出路径。"""
    ctx = runner.ctx
    name = os.path.basename(input_file)

    duration = get_duration(input_file)
    if duration is None:
        ctx.error(f"  无法获取视频信息: {name}")
        return None

    codec = get_codec(input_file)
    src_bitrate = get_bitrate(input_file)

    stem, ext = os.path.splitext(name)
    out_file = os.path.join(output_dir, f"{stem}{COMPRESSED_MARKER}{ext}")

    if os.path.exists(out_file):
        try:
            os.remove(out_file)
        except OSError:
            pass

    ctx.log(f"  编码: {codec or 'unknown'} | 原码率: {src_bitrate or '未知'} kbps")
    ctx.log(f"  质量: {quality} | 时长: {duration:.2f}s")

    enc_args = build_encode_args(
        ctx, input_file, quality=quality, usage=usage,
        bitrate=bitrate, cqp=cqp, qp=qp,
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        *enc_args,
        "-c:a", "copy",
        "-movflags", "+faststart",
    ]
    if duration:
        cmd += build_progress_args()
    cmd.append(out_file)

    try:
        runner.run(cmd, duration=duration, description="  压缩中...")
    except ToolError as exc:
        ctx.error(f"  失败: {exc}")
        remove_files([out_file])
        return None

    if not os.path.exists(out_file):
        return None

    # 体积对比
    src_size = os.path.getsize(input_file)
    out_size = os.path.getsize(out_file)
    ratio = (1 - out_size / src_size) * 100 if src_size else 0
    ctx.success(
        f"  完成: {human_size(src_size)} -> {human_size(out_size)} "
        f"({'减少' if ratio >= 0 else '增加'} {abs(ratio):.1f}%)"
    )
    return out_file


def compress_video(
    input_path: str,
    quality: str = "medium",
    usage: str = "transcoding",
    output_dir: str = "",
    recursive: bool = True,
    bitrate: Optional[int] = None,
    cqp: bool = True,
    qp: int = 23,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """压缩视频。

    参数:
        input_path: 输入视频文件或文件夹
        quality:    low / medium / high
        usage:      AMF 用途 (transcoding / lowlatency / ultralowlatency)
        output_dir: 输出目录，空表示输入同目录
        recursive:  文件夹模式是否递归子目录
        bitrate:    目标码率 (kbps)，None 时自动检测
        cqp:        True=恒定质量模式，False=VBR 模式
        qp:         CQP 模式下的 QP 值
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    if quality not in QUALITY_PRESETS:
        return TaskResult(
            success=False,
            message=f"无效的质量预设 '{quality}'，可选: low / medium / high",
        )

    try:
        require_amf(ctx)
    except RuntimeError as exc:
        return TaskResult(success=False, message=str(exc))

    outputs: List[str] = []
    success = 0
    failed = 0
    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])

    if os.path.isfile(resolved):
        out_dir = output_dir or (os.path.dirname(resolved) or ".")
        ensure_dir(out_dir)
        ctx.log(f"处理: {os.path.basename(resolved)}")
        out = _compress_one(
            runner, resolved, out_dir,
            quality=preset["amf_quality"], usage=usage,
            bitrate=bitrate, cqp=cqp, qp=preset["qp"],
        )
        if out:
            outputs.append(out)
            success += 1
        else:
            failed += 1
    else:
        # 关键：排除已压缩文件，避免重复压缩
        files = scan_videos(
            resolved, recursive=recursive, exclude_contains=COMPRESSED_MARKER
        )
        if not files:
            return TaskResult(
                success=False,
                message=f"文件夹中没有找到未压缩的视频文件: {resolved}",
            )
        ctx.log(f"批量模式（递归={recursive}）：找到 {len(files)} 个视频")
        ctx.log(f"质量预设: {quality}")

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            rel = os.path.relpath(f, resolved)
            ctx.log(f"[{i}/{len(files)}] {rel}")
            ctx.progress(percent=i / len(files) * 100, file=rel)

            if output_dir:
                out_dir = output_dir
            else:
                out_dir = os.path.dirname(f)
            ensure_dir(out_dir)

            out = _compress_one(
                runner, f, out_dir,
                quality=preset["amf_quality"], usage=usage,
                bitrate=bitrate, cqp=cqp, qp=preset["qp"],
            )
            if out:
                outputs.append(out)
                success += 1
            else:
                failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )
