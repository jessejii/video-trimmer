# -*- coding: utf-8 -*-
"""视频时间线重新计算器（移植自 video_timeline_calculator.html）。

功能：
    输入带时间戳的时间线文本，自动识别标记为 [广告] 的段落，
    删除广告段后重新计算后续所有时间点。

解析规则:
    - 行格式: `^\\d{1,2}:\\d{2}(?::\\d{2})?\\s+标题$`
    - 广告判定: 标题包含 "[广告]" 或 "广告"（不区分大小写）
    - 广告段结束点 = 下一个非广告条目的时间；若广告直到结尾，则标记为"结尾"

输出三块内容:
    1. 重算后的时间线
    2. 计算方法说明（每个广告段的时长与累计减少时间）
    3. 广告区间 CSV（可直接粘贴给「片段删除」功能使用）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from ..core.models import TaskResult, ToolContext
from ..core.timeparse import format_mmss, parse_time

# 时间线行: "00:00 标题" / "01:33:00 [广告] 广告内容"
LINE_RE = re.compile(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)\s*$")

AD_MARKER = "[广告]"
AD_KEYWORD = "广告"


@dataclass
class TimelineEntry:
    time: float
    time_str: str
    title: str
    is_ad: bool


@dataclass
class AdSegment:
    start: float
    end: float
    start_str: str
    end_str: str
    is_last: bool

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def parse_timeline(text: str) -> List[TimelineEntry]:
    """解析时间线文本为条目列表。"""
    entries: List[TimelineEntry] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = LINE_RE.match(line)
        if not match:
            continue
        time_str, title = match.group(1), match.group(2)
        entries.append(
            TimelineEntry(
                time=parse_time(time_str),
                time_str=time_str,
                title=title,
                is_ad=AD_MARKER in title or AD_KEYWORD in title.lower(),
            )
        )
    return entries


def detect_ad_segments(entries: List[TimelineEntry]) -> List[AdSegment]:
    """检测连续广告条目构成的广告段。"""
    segments: List[AdSegment] = []
    i = 0
    while i < len(entries):
        current = entries[i]
        if not current.is_ad:
            i += 1
            continue

        ad_start = current.time
        ad_start_str = current.time_str

        # 跳过所有连续的广告条目
        j = i
        while j < len(entries) and entries[j].is_ad:
            j += 1

        if j < len(entries):
            end = entries[j].time
            end_str = entries[j].time_str
            is_last = False
        else:
            # 广告直到结尾
            end = ad_start
            end_str = "结尾"
            is_last = True

        segments.append(
            AdSegment(start=ad_start, end=end, start_str=ad_start_str,
                      end_str=end_str, is_last=is_last)
        )
        i = j

    segments.sort(key=lambda s: s.start)
    return segments


def calculate_timeline(
    text: str,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """重算时间线：删除广告段并把后续时间点整体前移。

    参数:
        text: 时间线文本，每行形如 "00:00 开场介绍"

    返回:
        TaskResult，其中 outputs[0] 为重算后的时间线文本，
        warnings 中携带计算方法说明与广告 CSV。
    """
    ctx = ctx or ToolContext()

    if not text or not text.strip():
        return TaskResult(success=False, message="请输入时间线内容")

    entries = parse_timeline(text)
    if not entries:
        return TaskResult(
            success=False,
            message="未解析到有效的时间线行，请检查格式（如：00:00 标题）",
        )

    ad_segments = detect_ad_segments(entries)
    ctx.log(f"解析到 {len(entries)} 条时间线条目")
    ctx.log(f"检测到 {len(ad_segments)} 个广告段")

    if not ad_segments:
        return TaskResult(
            success=False,
            message="未检测到广告时间段。请确保时间线中包含 [广告] 标记。",
        )

    # ---- 计算方法说明 ----
    steps: List[str] = []
    total_reduction = 0.0
    for idx, ad in enumerate(ad_segments):
        duration_str = format_mmss(ad.duration)
        if ad.is_last:
            steps.append(
                f"第 {idx + 1} 个广告段 {ad.start_str} – 结尾（不参与时间前移计算）"
            )
        else:
            total_reduction += ad.duration
            extra = "全部" if idx == 0 else "再额外"
            suffix = (
                f"（总计减去 {format_mmss(total_reduction)}）"
                if idx > 0 else ""
            )
            steps.append(
                f"第 {idx + 1} 个广告段 {ad.start_str} – {ad.end_str}，"
                f"共 {duration_str}，之后的时间{extra}减去 {duration_str}{suffix}"
            )

    # ---- 重算每条非广告条目 ----
    new_lines: List[str] = []
    for line in text.splitlines():
        match = LINE_RE.match(line)
        if not match:
            # 非时间线格式（空行、说明文字）原样保留
            new_lines.append(line)
            continue

        time_str, title = match.group(1), match.group(2)
        is_ad = AD_MARKER in title or AD_KEYWORD in title.lower()

        if is_ad:
            continue  # 删除广告条目

        t = parse_time(time_str)
        reduction = 0.0
        for ad in ad_segments:
            if ad.is_last:
                continue
            if t >= ad.end:
                reduction += ad.duration

        new_time = format_mmss(max(0.0, t - reduction))
        new_lines.append(
            LINE_RE.sub(lambda _m: f"{new_time} {title}", line, count=1)
        )

    ad_csv = ",".join(
        f"{ad.start_str}-{ad.end_str}" for ad in ad_segments
    )

    return TaskResult(
        success=True,
        message=f"计算完成：{len(ad_segments)} 个广告段，"
                f"累计减少 {format_mmss(total_reduction)}",
        outputs=["\n".join(new_lines)],
        warnings=[*steps, f"广告区间 CSV: {ad_csv}"],
    )
