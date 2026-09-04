# -*- coding: utf-8 -*-
"""视频合并：按名称排序合并文件夹内多个视频。

三种模式（对应原 merge_videos.py）:
    1. TS 流快速合并  - 逐文件转 TS 再拼接，速度极快，兼容性强
    2. CPU 转换合并   - libx264 统一重编码后合并，兼容性最好
    3. GPU 直接合并   - concat demuxer + h264_amf 一次性重编码，修复音画不同步

关键回归点（原项目实战补丁，不可省略）:
    - mp4/mov/m4v 转 TS 需 -bsf:v h264_mp4toannexb，失败回退 hevc_mp4toannexb
    - TS 拼接后 remux 到 MP4 需 -bsf:a aac_adtstoasc，失败回退去掉该参数
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.amf import build_encode_args, require_amf
from ..core.ffmpeg import FFmpegRunner, build_progress_args
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    cleanup_dir,
    ensure_dir,
    human_size,
    remove_files,
    scan_videos,
    temp_dir_for,
    validate_path,
    write_concat_list,
)
from ..core.probe import get_duration

MODE_CHOICES = [
    ("1. TS 流快速合并（速度快，兼容性好）", 1),
    ("2. CPU 转换合并（libx264，兼容性最好但慢）", 2),
    ("3. GPU 直接合并（h264_amf，推荐，修复卡顿）", 3),
]

# 需要 h264_mp4toannexb 比特流过滤的容器
ANNEXB_EXT = (".mp4", ".mov", ".m4v")


def _output_name(video_files: List[str]) -> str:
    """输出文件名：{first}_{last}_merge_videos.mp4"""
    first = os.path.splitext(os.path.basename(video_files[0]))[0]
    last = os.path.splitext(os.path.basename(video_files[-1]))[0]
    return f"{first}_{last}_merge_videos.mp4"


def _convert_one(
    runner: FFmpegRunner,
    input_path: str,
    output_path: str,
    encoder: str,
    index: int,
    total: int,
) -> None:
    """用 libx264 或 AMF 把单个视频转成标准 MP4。"""
    name = os.path.basename(input_path)
    duration = get_duration(input_path)
    if encoder == "gpu":
        # 走统一的 AMF 参数构造，可按源编码选 hevc_amf / av1_amf 并回退 h264_amf
        v_args = build_encode_args(
            runner.ctx, input_path, quality="balanced", cqp=True, qp=23
        )
    else:
        v_args = ["-c:v", "libx264", "-crf", "23", "-preset", "medium"]

    cmd = ["ffmpeg", "-y", "-i", input_path, *v_args,
           "-c:a", "aac", "-b:a", "128k"]
    if duration:
        cmd += [*build_progress_args()]
    cmd.append(output_path)

    runner.run(
        cmd,
        duration=duration,
        description=f"  [{index}/{total}] 转换中: {name}",
    )


def _to_ts(
    runner: FFmpegRunner,
    input_path: str,
    ts_path: str,
    index: int,
    total: int,
) -> None:
    """把单个视频无损转为 TS（含 HEVC 回退）。"""
    name = os.path.basename(input_path)
    ext = os.path.splitext(name)[1].lower()
    v_bsf = "h264_mp4toannexb" if ext in ANNEXB_EXT else None

    base = ["ffmpeg", "-y", "-i", input_path, "-c", "copy"]
    if v_bsf:
        base += ["-bsf:v", v_bsf]
    base += ["-f", "mpegts", "-avoid_negative_ts", "make_zero", ts_path]

    result = runner.run(base, description=f"  [{index}/{total}] 转 TS: {name}", check=False)
    if result.returncode == 0:
        return

    # HEVC 回退（原项目针对 HEVC 源视频的兼容补丁）
    if v_bsf == "h264_mp4toannexb":
        runner.ctx.warn("      h264_mp4toannexb 失败，尝试 hevc_mp4toannexb 回退...")
        remove_files([ts_path])
        retry = [
            "ffmpeg", "-y", "-i", input_path, "-c", "copy",
            "-bsf:v", "hevc_mp4toannexb",
            "-f", "mpegts", "-avoid_negative_ts", "make_zero", ts_path,
        ]
        result = runner.run(retry, description="      回退重试中...", check=False)

    if result.returncode != 0:
        raise ToolError(f"转换失败: {name}")


def merge_videos(
    directory: str,
    mode: int = 1,
    output_file: Optional[str] = None,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """合并目录中的所有视频。

    参数:
        directory:   视频所在文件夹
        mode:        1=TS快速, 2=CPU转换, 3=GPU直接
        output_file: 输出文件路径，None 时自动生成
        ctx:         执行上下文
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(directory, kind="dir")
    if not ok:
        return TaskResult(success=False, message=err)

    files = scan_videos(resolved, recursive=False)
    if len(files) == 0:
        return TaskResult(success=False, message=f"目录中没有找到视频文件: {resolved}")
    if len(files) == 1:
        return TaskResult(success=False, message="只找到一个视频文件，无需合并")

    ctx.log(f"找到 {len(files)} 个视频文件：")
    for i, f in enumerate(files, 1):
        ctx.log(f"  {i}. {os.path.basename(f)}")

    out = output_file or os.path.join(resolved, _output_name(files))
    ensure_dir(os.path.dirname(out) or ".")

    if os.path.exists(out) and not ctx.settings.overwrite:
        return TaskResult(
            success=False,
            message=f"输出文件已存在（可在设置中开启覆盖）: {out}",
        )

    ctx.log(f"输出文件：{out}")

    try:
        if mode == 2:
            _merge_convert(runner, resolved, files, out, encoder="cpu")
        elif mode == 3:
            _merge_direct_gpu(runner, resolved, files, out)
        else:
            _merge_fast_ts(runner, resolved, files, out)
    except ToolError as exc:
        return TaskResult(success=False, message=str(exc))

    if not os.path.exists(out):
        return TaskResult(success=False, message="合并失败：未生成输出文件")

    size = human_size(os.path.getsize(out))
    ctx.success(f"合并成功！文件大小：{size}")
    ctx.success(f"保存位置：{out}")
    return TaskResult(success=True, message=f"合并成功（{size}）", outputs=[out])


def _merge_fast_ts(
    runner: FFmpegRunner,
    directory: str,
    files: List[str],
    out: str,
) -> None:
    """模式1：逐文件转 TS -> concat 成单一 TS -> remux 为 MP4。"""
    temp_dir = temp_dir_for(directory, "temp")
    ts_files: List[str] = []
    list_file = os.path.join(temp_dir, "filelist.txt")
    concat_ts = os.path.join(temp_dir, "concat_all.ts")

    ctx = runner.ctx
    try:
        ctx.log("开始转换为 TS 流...")
        for i, video in enumerate(files, 1):
            ctx.check_cancel()
            ts_out = os.path.join(temp_dir, f"temp_{i:03d}.ts")
            _to_ts(runner, video, ts_out, i, len(files))
            ts_files.append(ts_out)

        ctx.log("开始拼接 TS 流...")
        write_concat_list(ts_files, list_file)
        runner.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             "-c", "copy", "-f", "mpegts", concat_ts],
            description="  拼接中...",
        )

        ctx.log("正在 remux 为 MP4...")
        result = runner.run(
            ["ffmpeg", "-y", "-i", concat_ts, "-c", "copy",
             "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", out],
            description="  remux 中...",
            check=False,
        )
        if result.returncode != 0:
            ctx.warn("  aac_adtstoasc 失败，回退为纯 copy remux...")
            runner.run(
                ["ffmpeg", "-y", "-i", concat_ts, "-c", "copy",
                 "-movflags", "+faststart", out],
                description="  回退 remux 中...",
            )
    finally:
        ctx.log("清理临时文件...")
        remove_files([*ts_files, list_file, concat_ts])
        cleanup_dir(temp_dir)


def _merge_convert(
    runner: FFmpegRunner,
    directory: str,
    files: List[str],
    out: str,
    encoder: str = "cpu",
) -> None:
    """模式2：逐个重编码为统一 MP4 -> concat 合并。"""
    temp_dir = temp_dir_for(directory, "temp")
    converted: List[str] = []
    list_file = os.path.join(temp_dir, "filelist.txt")
    ctx = runner.ctx

    label = "AMD 显卡加速 (h264_amf)" if encoder == "gpu" else "CPU (libx264)"
    try:
        ctx.log(f"开始转换视频为标准 MP4 格式 [{label}]...")
        for i, video in enumerate(files, 1):
            ctx.check_cancel()
            tmp_out = os.path.join(temp_dir, f"temp_{i:03d}.mp4")
            _convert_one(runner, video, tmp_out, encoder, i, len(files))
            converted.append(tmp_out)

        ctx.log("开始合并转换后的视频...")
        write_concat_list(converted, list_file)
        runner.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             "-c", "copy", out],
            description="  合并中...",
        )
    finally:
        ctx.log("清理临时文件...")
        remove_files([*converted, list_file])
        cleanup_dir(temp_dir)


def _merge_direct_gpu(
    runner: FFmpegRunner,
    directory: str,
    files: List[str],
    out: str,
) -> None:
    """模式3：concat demuxer + AMF 一次性重编码。"""
    ctx = runner.ctx
    require_amf(ctx)
    # 探测首个源文件的编码来选 AMF 编码器：concat 列表本身无法探测
    enc_args = build_encode_args(ctx, files[0], quality="balanced", cqp=True, qp=23)

    temp_dir = temp_dir_for(directory, "temp")
    list_file = os.path.join(temp_dir, "filelist.txt")
    try:
        write_concat_list(files, list_file)
        ctx.log("开始直接使用 GPU 合并视频（重编码整个流，可修复音画不同步）...")
        runner.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             *enc_args,
             "-c:a", "aac", "-b:a", "128k", out],
            description="  GPU 合并中...",
        )
    finally:
        remove_files([list_file])
        cleanup_dir(temp_dir)
