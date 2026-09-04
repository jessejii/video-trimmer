# -*- coding: utf-8 -*-
"""时间解析与格式化。

原项目在 7 个文件里重复实现了 parse_time()，且语义有微妙差异。
此处统一为一份实现，并额外支持毫秒与"结尾"关键字。

支持格式:
    SS              90          -> 90.0
    SS.mmm          90.5        -> 90.5
    MM:SS           1:30        -> 90.0
    HH:MM:SS        1:30:45     -> 5445.0
    HH:MM:SS.mmm    1:30:45.500 -> 5445.5
    结尾                        -> 视频总时长（需传 duration）

"结尾"的双向处理（参照原 remove_segments.py）:
    解析方向: "结尾" -> 视频总时长（duration），见 parse_time / parse_segments
    展示方向: 秒数 ≈ 视频总时长 -> "结尾"，见 format_seconds(use_end_label=True)
注意：反向展示只用于日志；传给字幕同步等下游的 CSV 必须是纯数值格式。
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

END_KEYWORD = "结尾"
END_ALIASES = (END_KEYWORD, "end")
# 判定"某个时间点是否就是视频末尾"的容差（秒）。
# copy 裁剪会对齐关键帧，实际边界与请求边界有毫秒级偏差，不能直接用 ==。
END_EPSILON = 0.001


class TimeParseError(ValueError):
    """时间格式解析失败。"""


def is_end_keyword(text) -> bool:
    """输入是否为"结尾"关键字（忽略大小写与包裹引号）。"""
    if text is None:
        return False
    s = str(text).strip().strip('"').strip("'").lower()
    return s in END_ALIASES


def is_at_end(seconds: Optional[float], duration: Optional[float]) -> bool:
    """判断某个时间点是否就是视频末尾（带容差，避免浮点/关键帧误差）。"""
    if duration is None or seconds is None:
        return False
    try:
        return abs(float(seconds) - float(duration)) < END_EPSILON
    except (TypeError, ValueError):
        return False


def parse_time(
    time_str,
    duration: Optional[float] = None,
    end_value: Optional[float] = None,
) -> float:
    """解析时间字符串为秒数。

    参数:
        time_str:   时间字符串
        duration:   视频总时长（秒），"结尾"优先解析为它
        end_value:  没有 duration 时"结尾"的替代值（用于无需真实时长的格式校验）

    返回:
        秒数（浮点数）
    """
    if time_str is None:
        return 0.0
    if isinstance(time_str, (int, float)):
        return float(time_str)

    s = str(time_str).strip().strip('"').strip("'")
    if not s:
        return 0.0

    if is_end_keyword(s):
        if duration is not None:
            return float(duration)
        if end_value is not None:
            return float(end_value)
        raise TimeParseError('使用"结尾"时需要提供视频总时长')

    parts = s.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise TimeParseError(f"时间包含无效字符: {time_str}") from exc

    if len(parts) == 1:      # SS / SS.mmm
        return nums[0]
    if len(parts) == 2:      # MM:SS
        return nums[0] * 60 + nums[1]
    if len(parts) == 3:      # HH:MM:SS
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    raise TimeParseError(f"无效的时间格式: {time_str}")


def format_seconds(
    seconds: Optional[float],
    duration: Optional[float] = None,
    use_end_label: bool = False,
) -> str:
    """秒 -> HH:MM:SS.mmm

    参数:
        duration:      视频总时长
        use_end_label: 为 True 且 seconds 处于视频末尾（容差内）时返回"结尾"
    """
    if seconds is None or not math.isfinite(seconds):
        # 无法解析为有限秒数，只可能是未带时长的"结尾"
        return END_KEYWORD
    if use_end_label and is_at_end(seconds, duration):
        return END_KEYWORD
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_seconds_compact(seconds: float) -> str:
    """秒 -> HH.MM.SS.mmm（文件名安全，冒号替换为点）"""
    return format_seconds(seconds).replace(":", ".")


def format_mmss(seconds: float) -> str:
    """秒 -> HH:MM:SS（不足 1 小时则为 MM:SS），用于时间线展示。"""
    total = max(0, int(seconds))
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_srt_time(ms: Optional[float]) -> str:
    """毫秒 -> SRT 时间戳 HH:MM:SS,mmm（SRT 规范用逗号而非点分隔毫秒）。"""
    try:
        total = int(float(ms))
    except (TypeError, ValueError):
        total = 0
    if total < 0:
        total = 0
    hour, rest = divmod(total, 3_600_000)
    minute, rest = divmod(rest, 60_000)
    second, millisecond = divmod(rest, 1000)
    return f"{hour:02d}:{minute:02d}:{second:02d},{millisecond:03d}"


def parse_segments(
    spec: str,
    duration: Optional[float] = None,
) -> Tuple[List[Tuple[float, float]], List[str]]:
    """解析时间段字符串。

    参数:
        spec:     如 "1:00-2:00,5:00-结尾"
        duration: 视频总时长，用于解析"结尾"

    返回:
        (时间段列表, 警告列表)。非法段被跳过并记录警告，而非直接打印。

    没有 duration 时（例如表单输入校验），"结尾"按 +inf 处理，
    使 "5:00-结尾" 这类写法能被判定为合法区间。
    """
    segments: List[Tuple[float, float]] = []
    warnings: List[str] = []

    if not spec or not spec.strip():
        return segments, warnings

    end_value = math.inf if duration is None else None

    for raw in spec.split(","):
        part = raw.strip()
        if not part:
            continue
        if "-" not in part:
            warnings.append(f"跳过无效的时间段格式（缺少 -）: {part}")
            continue
        start_str, end_str = part.split("-", 1)
        try:
            start = parse_time(start_str, duration, end_value)
            end = parse_time(end_str, duration, end_value)
        except TimeParseError as exc:
            warnings.append(f"跳过无法解析的时间段 {part}: {exc}")
            continue
        if start >= end:
            warnings.append(f"跳过无效的时间段（开始时间 >= 结尾时间）: {part}")
            continue
        segments.append((start, end))

    segments.sort(key=lambda x: x[0])
    return segments, warnings


def segments_to_csv(
    segments: List[Tuple[float, float]],
    duration: Optional[float] = None,
    use_end_label: bool = False,
) -> str:
    """时间段列表 -> HH:MM:SS.mmm-HH:MM:SS.mmm,HH:MM:SS.mmm-...

    use_end_label=True 时，处于视频末尾的**结尾时间**显示为"结尾"（开始时间始终为数值）。
    传给字幕同步等下游时必须用默认的数值格式。
    """
    return ",".join(
        f"{format_seconds(s)}-"
        f"{format_seconds(e, duration, use_end_label=use_end_label)}"
        for s, e in segments
    )


def calculate_keep_segments(
    remove_segments: List[Tuple[float, float]],
    duration: float,
) -> List[Tuple[float, float]]:
    """根据要删除的时间段，反算要保留的时间段。"""
    keep: List[Tuple[float, float]] = []
    current = 0.0
    for start, end in remove_segments:
        if current < start:
            keep.append((current, min(start, duration)))
        current = max(current, end)
    if current < duration:
        keep.append((current, duration))
    return [seg for seg in keep if seg[1] - seg[0] > 1e-6]
