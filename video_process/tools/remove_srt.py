# -*- coding: utf-8 -*-
"""SRT 字幕时间段删除与时间前移（纯 Python，不依赖 ffmpeg）。

移植自 remove_srt_segments.py，核心算法：
    1. parse_remove_ranges: 解析并合并重叠/相邻区间
    2. removed_before:      某时间点之前累计被删除的毫秒数
    3. subtract_ranges:     从 [a,b) 中扣掉删除区间，返回保留子区间
    4. process_cues:        逐条字幕切分 -> 时间前移 -> 消除重叠

支持输入 .srt 与 .srt.txt，默认输出 {base}_removed.srt。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.models import TaskResult, ToolContext
from ..core.paths import validate_path

# SRT 标准时间戳: 00:00:20,000 --> 00:00:22,000
_TIME_PATTERN = re.compile(
    r"(\d{1,3}:\d{1,2}:\d{1,2}[,.]\d{1,3})\s*-->\s*(\d{1,3}:\d{1,2}:\d{1,2}[,.]\d{1,3})"
)


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


class SrtError(ValueError):
    """SRT 解析或处理失败。"""


def parse_clock_to_ms(time_str: str) -> int:
    """解析时间为毫秒。

    支持: HH:MM:SS,mmm / HH:MM:SS(.mmm) / MM:SS(.mmm) / SS(.mmm)
    """
    s = time_str.strip().replace(",", ".")

    m = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?", s)
    if m:
        h, mi, sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return ((int(h) * 60 + int(mi)) * 60 + int(sec)) * 1000 + ms

    m = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d{1,3}))?", s)
    if m:
        mi, sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return (int(mi) * 60 + int(sec)) * 1000 + ms

    m = re.fullmatch(r"(\d+)(?:\.(\d{1,3}))?", s)
    if m:
        sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return int(sec) * 1000 + ms

    raise SrtError(f"无效时间格式: {time_str}")


def ms_to_srt(ms: int) -> str:
    """毫秒 -> HH:MM:SS,mmm"""
    if ms < 0:
        ms = 0
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_remove_ranges(spec: str) -> List[Tuple[int, int]]:
    """解析删除区间字符串，返回合并后的毫秒区间列表。"""
    ranges: List[Tuple[int, int]] = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        if "-" not in part:
            raise SrtError(f"无效区间格式（缺少 -）: {part}")
        a, b = part.split("-", 1)
        start = parse_clock_to_ms(a)
        end = parse_clock_to_ms(b)
        if start >= end:
            raise SrtError(f"无效区间（开始 >= 结束）: {part}")
        ranges.append((start, end))

    if not ranges:
        raise SrtError("未提供有效删除区间")

    ranges.sort(key=lambda x: x[0])

    # 合并重叠/相邻区间
    merged: List[Tuple[int, int]] = []
    for s, e in ranges:
        if not merged or s > merged[-1][1]:
            merged.append((s, e))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    return merged


def parse_srt(content: str) -> List[Cue]:
    """解析 SRT 文本为字幕条目列表。"""
    content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", content.strip())
    cues: List[Cue] = []

    for block in blocks:
        lines = block.split("\n")
        if not lines:
            continue

        time_line_idx = None
        match = None
        for i, line in enumerate(lines[:3]):  # 时间轴一般在前两行
            match = _TIME_PATTERN.search(line)
            if match:
                time_line_idx = i
                break

        if time_line_idx is None or match is None:
            continue

        start_ms = parse_clock_to_ms(match.group(1))
        end_ms = parse_clock_to_ms(match.group(2))
        if end_ms <= start_ms:
            continue

        text = "\n".join(lines[time_line_idx + 1:]).rstrip("\n")
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=text))

    return cues


def removed_before(t: int, ranges: List[Tuple[int, int]]) -> int:
    """原时间点 t 之前累计删除的毫秒数。"""
    total = 0
    for s, e in ranges:
        if t <= s:
            break
        total += max(0, min(t, e) - s)
    return total


def subtract_ranges(
    a: int, b: int, ranges: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """从区间 [a,b) 中扣掉删除区间，返回保留子区间列表。"""
    keep: List[Tuple[int, int]] = []
    cur = a
    for s, e in ranges:
        if e <= cur:
            continue
        if s >= b:
            break
        if s > cur:
            keep.append((cur, min(s, b)))
        cur = max(cur, e)
        if cur >= b:
            break
    if cur < b:
        keep.append((cur, b))
    return [(x, y) for x, y in keep if y > x]


def process_cues(cues: List[Cue], ranges: List[Tuple[int, int]]) -> List[Cue]:
    """按删除区间切分并前移字幕时间，消除重叠。"""
    out: List[Cue] = []

    for cue in sorted(cues, key=lambda c: (c.start_ms, c.end_ms)):
        for ks, ke in subtract_ranges(cue.start_ms, cue.end_ms, ranges):
            ns = ks - removed_before(ks, ranges)
            ne = ke - removed_before(ke, ranges)
            if ne > ns:
                out.append(Cue(start_ms=ns, end_ms=ne, text=cue.text))

    out.sort(key=lambda c: (c.start_ms, c.end_ms))

    fixed: List[Cue] = []
    prev_end = 0
    for cue in out:
        s = max(cue.start_ms, prev_end)
        e = cue.end_ms
        if e <= s:
            continue
        fixed.append(Cue(start_ms=s, end_ms=e, text=cue.text))
        prev_end = e

    return fixed


def write_srt(cues: List[Cue], path: str) -> None:
    """写入 SRT 文件。"""
    with open(path, "w", encoding="utf-8") as fh:
        for idx, cue in enumerate(cues, start=1):
            fh.write(f"{idx}\n")
            fh.write(f"{ms_to_srt(cue.start_ms)} --> {ms_to_srt(cue.end_ms)}\n")
            fh.write(cue.text.rstrip("\n"))
            fh.write("\n\n")


def default_output_path(input_path: str) -> str:
    """.srt.txt 输入先去掉 .txt，再输出 {base}_removed.srt"""
    normalized = input_path
    if input_path.lower().endswith(".srt.txt"):
        normalized = input_path[:-4]
    base, _ = os.path.splitext(normalized)
    return f"{base}_removed.srt"


def remove_srt_segments(
    input_file: str,
    ranges_spec: str,
    output_file: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """删除 SRT 指定时间段并前移后续字幕。

    参数:
        input_file:  输入 .srt / .srt.txt 文件路径
        ranges_spec: 删除区间，如 "1:00-2:00" 或 "1:00-2:00,5:00-6:00"
        output_file: 输出路径，空表示自动生成
    """
    ctx = ctx or ToolContext()

    ok, resolved, err = validate_path(input_file, kind="file")
    if not ok:
        return TaskResult(success=False, message=err)

    try:
        ranges = parse_remove_ranges(ranges_spec)
    except SrtError as exc:
        return TaskResult(success=False, message=str(exc))

    try:
        with open(resolved, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
    except UnicodeDecodeError:
        with open(resolved, "r", encoding="gbk") as fh:
            content = fh.read()

    cues = parse_srt(content)
    if not cues:
        return TaskResult(success=False, message="未解析到任何字幕条目，请检查文件格式")

    new_cues = process_cues(cues, ranges)
    out = output_file or default_output_path(resolved)

    try:
        write_srt(new_cues, out)
    except OSError as exc:
        return TaskResult(success=False, message=f"写入失败: {exc}")

    ctx.log(f"删除区间: {', '.join(f'{ms_to_srt(s)}-{ms_to_srt(e)}' for s, e in ranges)}")
    ctx.success(f"原字幕 {len(cues)} 条 -> 新字幕 {len(new_cues)} 条")
    ctx.success(f"输出文件: {out}")

    return TaskResult(
        success=True,
        message=f"字幕处理完成：{len(cues)} -> {len(new_cues)} 条",
        outputs=[out],
    )
