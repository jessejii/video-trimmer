# -*- coding: utf-8 -*-
"""删除视频中指定的多个时间段，并自动合并剩余部分。

移植自 remove_segments.py。核心流程：
    1. 解析删除区间 -> calculate_keep_segments 反算保留区间
    2. 单个保留段：直接 copy 裁剪
       多个保留段：逐段提取（.ts 源用 TS 中间格式，其他用 MP4）后 concat 合并
    3. 【关键】用输出文件的**实际时长**反算真实删除边界，同步同名 SRT 字幕

第 3 步是原项目的精髓：copy 裁剪会对齐关键帧，实际边界与请求边界有偏差，
必须以实际边界去同步字幕，否则字幕会越走越偏。

输出策略：
    - 指定 output_dir：直接输出到该目录
    - 未指定：先写临时文件，成功后替换为 {base}_processed.mp4（原文件保留）
"""

from __future__ import annotations

import os
import tempfile
import time
from typing import List, Optional, Tuple

from ..core.ffmpeg import FFmpegRunner
from ..core.models import TaskResult, ToolContext, ToolError
from ..core.paths import (
    cleanup_dir,
    ensure_dir,
    remove_files,
    scan_videos,
    temp_dir_for,
    validate_path,
    write_concat_list,
)
from ..core.probe import get_duration
from ..core.timeparse import (
    calculate_keep_segments,
    format_seconds,
    parse_segments,
    segments_to_csv,
)
from .remove_srt import remove_srt_segments

PROCESSED_SUFFIX = "_processed"


def _find_sibling_srt(input_file: str) -> Optional[str]:
    """查找同名 SRT 字幕（优先 .srt，其次 .srt.txt）。"""
    base_no_ext = os.path.splitext(input_file)[0]
    for candidate in (f"{base_no_ext}.srt", f"{base_no_ext}.srt.txt"):
        if os.path.exists(candidate):
            return candidate
    return None


def _sync_srt(
    ctx: ToolContext,
    input_file: str,
    final_video_path: str,
    actual_removed_csv: str,
) -> Optional[str]:
    """用实际删除区间同步同名字幕。

    actual_removed_csv 为空（没有实际删除内容）时跳过。
    """
    if not actual_removed_csv.strip():
        ctx.log("  没有实际删除内容，跳过字幕同步")
        return None

    srt_file = _find_sibling_srt(input_file)
    if not srt_file:
        base_no_ext = os.path.splitext(input_file)[0]
        ctx.log(f"  未找到同名字幕，跳过同步: {base_no_ext}.srt 或 .srt.txt")
        return None

    out_srt = os.path.splitext(final_video_path)[0] + ".srt"
    ctx.log(f"  同步字幕: {os.path.basename(srt_file)} -> {os.path.basename(out_srt)}")
    ctx.log(f"  实际删除区间: {actual_removed_csv}")

    result = remove_srt_segments(srt_file, actual_removed_csv, out_srt, ctx)
    if result.success:
        ctx.success(f"  字幕已同步: {out_srt}")
        return out_srt
    ctx.warn(f"  字幕同步失败: {result.message}")
    return None


def _compute_actual_removed(
    keep_segments: List[Tuple[float, float]],
    actual_durations: List[float],
    duration: float,
) -> str:
    """根据实际片段时长反算真实被删除的区间 CSV。

    keep_segments:     计划的保留区间 [(start, end), ...]
    actual_durations:  每个保留片段的实际时长
    """
    actual_keep: List[Tuple[float, float]] = []
    for (start, _end), seg_dur in zip(keep_segments, actual_durations):
        actual_keep.append((start, start + seg_dur))

    removed: List[Tuple[float, float]] = []
    current = 0.0
    for ks, ke in actual_keep:
        if current < ks - 0.001:
            removed.append((current, ks))
        current = max(current, ke)
    if current < duration - 0.001:
        removed.append((current, duration))

    return segments_to_csv(removed)


def _remove_one(
    runner: FFmpegRunner,
    input_file: str,
    remove_segs: List[Tuple[float, float]],
    output_dir: Optional[str],
    sync_srt: bool = True,
) -> Tuple[bool, List[str]]:
    """处理单个文件，返回 (是否成功, 输出文件列表)。"""
    ctx = runner.ctx
    name = os.path.basename(input_file)
    input_dir = os.path.dirname(input_file) or "."
    base_name = os.path.splitext(name)[0]

    duration = get_duration(input_file)
    if duration is None:
        ctx.error(f"  无法获取视频时长: {name}")
        return False, []

    # 过滤超出视频长度的区间
    remove_segs = [(s, min(e, duration)) for s, e in remove_segs if s < duration]
    if not remove_segs:
        ctx.error(f"  没有落在视频时长内的有效删除区间: {name}")
        return False, []

    keep_segments = calculate_keep_segments(remove_segs, duration)
    if not keep_segments:
        ctx.error("  删除后没有剩余内容")
        return False, []

    ctx.log(f"  总时长: {duration:.2f}s")
    # 计划边界：末尾段显示为"结尾"，便于核对（实际边界仍为数值，见下方日志）
    ctx.log(f"  保留片段: {segments_to_csv(keep_segments, duration, use_end_label=True)}")

    # ---- 决定输出路径（未指定目录时用临时文件，最后替换） ----
    replace_original = False
    if output_dir:
        ensure_dir(output_dir)
        output_file = os.path.join(output_dir, f"{base_name}.mp4")
    else:
        fd, output_file = tempfile.mkstemp(suffix=".mp4", dir=input_dir)
        os.close(fd)
        os.remove(output_file)  # 只占位路径，ffmpeg 会重建
        replace_original = True

    final_output = (
        os.path.join(input_dir, f"{base_name}{PROCESSED_SUFFIX}.mp4")
        if replace_original else output_file
    )

    outputs: List[str] = []

    # ================= 情况 A：只有一个保留段 =================
    if len(keep_segments) == 1:
        start, end = keep_segments[0]
        seg_duration = end - start

        # 同样走 TS 中间流：直接对 MP4 做 -ss + copy 会让视频轨退到上一个
        # 关键帧而音频轨精确 seek，造成音画不同步与时长漂移。
        temp_dir = temp_dir_for(input_dir, "trimmed")
        temp_ts = os.path.join(temp_dir, f"{base_name}_single.ts")
        ctx.log("  单个保留段，TS 中间格式裁剪...")
        try:
            runner.run(
                ["ffmpeg", "-y", "-i", input_file,
                 "-ss", str(start), "-t", str(seg_duration), "-c", "copy",
                 "-bsf:v", "h264_mp4toannexb", "-f", "mpegts",
                 "-avoid_negative_ts", "make_zero", temp_ts],
                duration=seg_duration,
                description="  步骤1/2: 转 TS 并裁剪...",
            )
            runner.run(
                ["ffmpeg", "-y", "-i", temp_ts, "-c", "copy",
                 "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart",
                 output_file],
                description="  步骤2/2: remux 为 MP4...",
            )
        except ToolError as exc:
            ctx.error(f"  裁剪失败: {exc}")
            remove_files([output_file])
            return False, []
        finally:
            remove_files([temp_ts])
            cleanup_dir(temp_dir)

        actual = get_duration(output_file)
        actual_dur = actual if actual is not None else seg_duration
        removed_csv = _compute_actual_removed(keep_segments, [actual_dur], duration)
        ctx.log(f"  实际删除区间: {removed_csv or '(无)'}")

        if sync_srt:
            srt_out = _sync_srt(ctx, input_file, final_output, removed_csv)
            if srt_out:
                outputs.append(srt_out)

        if replace_original:
            _safe_replace(ctx, output_file, final_output, input_file)
        outputs.append(final_output)
        ctx.success(f"  完成: {final_output}")
        return True, outputs

    # ============ 情况 B：多个保留段，逐段提取后 concat ============
    # 一律走 TS 中间流。原因（实测）：直接对 MP4 做 -ss + -c copy 时，
    # 视频轨会被拉回上一个关键帧、而音频轨精确到 -ss 位置，
    # 两者起点不一致导致音画不同步，且片段实际时长会远超请求值
    # （例如请求 3s 实际得到 8.1s）。TS 容器不依赖 moov atom，
    # 配合 -bsf:v h264_mp4toannexb 可保证音视频起点一致。
    # 本代码库中 split_video / merge_videos 的快速模式同样采用该策略。
    temp_dir = temp_dir_for(input_dir, "trimmed")
    seg_files: List[str] = []
    concat_list = os.path.join(temp_dir, f"{base_name}_concat_list.txt")

    try:
        ctx.log(f"  多个保留段（{len(keep_segments)} 段），TS 中间格式提取...")

        for i, (start, end) in enumerate(keep_segments):
            ctx.check_cancel()
            seg_file = os.path.join(temp_dir, f"segment_{i:03d}.ts")
            seg_duration = end - start
            cmd = ["ffmpeg", "-y", "-i", input_file,
                   "-ss", str(start), "-t", str(seg_duration), "-c", "copy",
                   "-bsf:v", "h264_mp4toannexb",
                   "-f", "mpegts",
                   "-avoid_negative_ts", "make_zero", seg_file]

            runner.run(cmd, duration=seg_duration,
                       description=f"  提取片段 {i + 1}/{len(keep_segments)}: "
                                   f"{format_seconds(start)}-{format_seconds(end)}")
            seg_files.append(seg_file)

        ctx.log("  合并片段...")
        write_concat_list(seg_files, concat_list)
        runner.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
             "-c", "copy", "-bsf:a", "aac_adtstoasc",
             "-movflags", "+faststart", output_file],
            description="  合并中...",
        )

        # 用每段实际时长反算真实删除边界
        actual_durations: List[float] = []
        for seg_file in seg_files:
            d = get_duration(seg_file)
            actual_durations.append(d if d is not None else 0.0)

        removed_csv = _compute_actual_removed(keep_segments, actual_durations, duration)
        ctx.log(f"  实际删除区间: {removed_csv or '(无)'}")

        if sync_srt:
            srt_out = _sync_srt(ctx, input_file, final_output, removed_csv)
            if srt_out:
                outputs.append(srt_out)

        if replace_original:
            _safe_replace(ctx, output_file, final_output, input_file)
        outputs.append(final_output)
        ctx.success(f"  完成: {final_output}")
        return True, outputs

    except ToolError as exc:
        ctx.error(f"  处理失败: {exc}")
        remove_files([output_file])
        return False, []
    finally:
        remove_files([*seg_files, concat_list])
        cleanup_dir(temp_dir)


def _safe_replace(ctx: ToolContext, tmp: str, final: str, original: str) -> None:
    """替换输出文件，处理 Windows 上的文件占用（短暂重试）。"""
    try:
        os.replace(tmp, final)
    except PermissionError:
        time.sleep(0.5)
        try:
            os.replace(tmp, final)
        except PermissionError as exc:
            raise ToolError(f"无法写入输出文件（可能被占用）: {final} - {exc}") from exc
    ctx.log(f"  原始文件已保留: {original}")


def remove_segments(
    input_path: str,
    segments: str,
    output_dir: str = "",
    sync_srt: bool = True,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """删除视频中的指定时间段。

    参数:
        input_path: 输入视频文件或文件夹
        segments:   删除时间段，如 "1:00-2:00,5:00-6:00"，支持"结尾"关键字
        output_dir: 输出文件夹，空表示输出到输入同目录（生成 _processed.mp4）
        sync_srt:   是否自动同步同名 SRT 字幕
    """
    ctx = ctx or ToolContext()
    runner = FFmpegRunner(ctx)

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    # 解析时间需要总时长（支持"结尾"），先探测
    duration = get_duration(resolved) if os.path.isfile(resolved) else None
    segs, warnings = parse_segments(segments, duration)
    for w in warnings:
        ctx.warn(w)
    if not segs:
        return TaskResult(success=False, message="没有有效的时间段需要删除")

    ctx.log(f"要删除的时间段: {segments_to_csv(segs, duration, use_end_label=True)}")

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        ctx.log(f"处理: {os.path.basename(resolved)}")
        ok_one, outs = _remove_one(runner, resolved, segs, output_dir or None, sync_srt)
        outputs.extend(outs)
        success += int(ok_one)
        failed += int(not ok_one)
    else:
        files = scan_videos(resolved, recursive=False)
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到视频文件: {resolved}")
        ctx.log(f"批量模式：找到 {len(files)} 个视频")

        out_dir = output_dir or None
        if out_dir:
            ensure_dir(out_dir)

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
            ctx.progress(percent=i / len(files) * 100, file=os.path.basename(f))
            # 每个文件的"结尾"不同，需重新解析
            d = get_duration(f)
            file_segs, ws = parse_segments(segments, d)
            for w in ws:
                ctx.warn(w)
            if not file_segs:
                ctx.warn("  跳过：没有有效删除区间")
                failed += 1
                continue
            ctx.log(f"  要删除: {segments_to_csv(file_segs, d, use_end_label=True)}")
            ok_one, outs = _remove_one(runner, f, file_segs, out_dir, sync_srt)
            outputs.extend(outs)
            success += int(ok_one)
            failed += int(not ok_one)

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
        warnings=warnings,
    )
