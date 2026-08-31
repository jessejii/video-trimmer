# -*- coding: utf-8 -*-
"""提取视频中的所有音轨，逐条重编码为 MP3。

使用 libmp3lame VBR 最高压缩模式 (-q:a 9)，约 65-85 kbps。

输出策略（原项目隐含约定，此处显式暴露为参数）:
    find_video_root=True 时，从输入路径**向上查找名为 video 的目录**作为统一输出根；
    找不到才回退到输入文件所在目录。
    —— 该约定在 UI 中默认勾选，可在设置里关闭。

命名: 单音轨 {原文件名}.mp3；多音轨 {原文件名}_track{N}_{语言}.mp3

注意：未使用 aresample=async=1，避免 TS 文件 PTS 不连续导致音频时长被错误拉伸。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.ffmpeg import FFmpegRunner, build_progress_args
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    ensure_dir,
    find_video_root,
    human_size,
    safe_filename,
    scan_videos,
    validate_path,
)
from ..core.probe import get_audio_streams, get_duration


def _describe_streams(ctx: ToolContext, streams: List[dict]) -> None:
    ctx.log(f"找到 {len(streams)} 条音轨:")
    for i, s in enumerate(streams, 1):
        lang = s.get("language") or "und"
        title = f" - {s['title']}" if s.get("title") else ""
        ch = s.get("channels") or "?"
        codec = s.get("codec_name") or "未知"
        ctx.log(f"  音轨 {i}: 编码={codec}, 声道={ch}, 语言={lang}{title}")


def _extract_one(
    runner: FFmpegRunner,
    input_file: str,
    output_dir: str,
) -> List[str]:
    """提取单个视频的所有音轨，返回输出文件列表。"""
    ctx = runner.ctx
    streams = get_audio_streams(input_file)
    if not streams:
        ctx.error(f"  文件中没有找到音轨: {os.path.basename(input_file)}")
        return []

    _describe_streams(ctx, streams)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    duration = get_duration(input_file)
    outputs: List[str] = []

    for i, stream in enumerate(streams):
        ctx.check_cancel()
        track_num = i + 1
        lang = safe_filename(stream.get("language") or "und")

        if len(streams) > 1:
            out_name = f"{base_name}_track{track_num}_{lang}.mp3"
        else:
            out_name = f"{base_name}.mp3"
        out_file = os.path.join(output_dir, out_name)

        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-map", f"0:a:{i}",
            "-vn",
            "-c:a", "libmp3lame",
            "-q:a", "9",
            "-map_metadata", "0",
            "-id3v2_version", "3",
        ]
        if duration:
            cmd += build_progress_args()
        cmd.append(out_file)

        try:
            runner.run(cmd, duration=duration,
                       description=f"  提取音轨 {track_num}/{len(streams)}...")
            outputs.append(out_file)
            ctx.success(f"    输出: {out_name} ({human_size(os.path.getsize(out_file))})")
        except ToolError as exc:
            ctx.error(f"    提取音轨 {track_num} 失败: {exc}")

    return outputs


def extract_audio(
    input_path: str,
    output_dir: str = "",
    find_video_root_dir: bool = True,
    recursive: bool = True,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """提取视频中的音轨为 MP3。

    参数:
        input_path:           输入视频文件或文件夹
        output_dir:           输出目录，为空时按 find_video_root_dir 策略推断
        find_video_root_dir:  是否向上查找名为 video 的目录作为输出根
        recursive:            文件夹模式是否递归子目录
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    # ---- 推断输出根目录 ----
    if output_dir:
        out_root = output_dir
        ensure_dir(out_root)
    elif find_video_root_dir:
        found = find_video_root(resolved)
        if found:
            out_root = found
            ctx.log(f"音频输出目录（自动找到 video 目录）: {out_root}")
        else:
            out_root = resolved if os.path.isdir(resolved) else (
                os.path.dirname(resolved) or "."
            )
            ctx.log(f"未找到上层 video 目录，音频输出目录: {out_root}")
    else:
        out_root = resolved if os.path.isdir(resolved) else (
            os.path.dirname(resolved) or "."
        )
    ensure_dir(out_root)

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        ctx.log(f"处理: {os.path.basename(resolved)}")
        outs = _extract_one(runner, resolved, out_root)
        outputs.extend(outs)
        success += int(bool(outs))
        failed += int(not outs)
    else:
        files = scan_videos(resolved, recursive=recursive)
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")
        ctx.log(f"批量模式（递归={recursive}）：找到 {len(files)} 个视频")

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            rel = os.path.relpath(f, resolved)
            ctx.log(f"[{i}/{len(files)}] {rel}")
            ctx.progress(percent=i / len(files) * 100, file=rel)
            outs = _extract_one(runner, f, out_root)
            outputs.extend(outs)
            success += int(bool(outs))
            failed += int(not outs)

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个文件（{len(outputs)} 条音轨），失败 {failed} 个",
        outputs=outputs,
    )
