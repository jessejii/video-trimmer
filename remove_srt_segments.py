import argparse
import os
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


def parse_clock_to_ms(time_str: str) -> int:
    """解析时间为毫秒。

    支持:
    - HH:MM:SS,mmm (SRT 标准)
    - HH:MM:SS
    - MM:SS
    - SS
    """
    s = time_str.strip()

    # HH:MM:SS,mmm
    m = re.fullmatch(r"(\d+):(\d{2}):(\d{2}),(\d{1,3})", s)
    if m:
        h, mi, sec, ms = map(int, m.groups())
        return ((h * 60 + mi) * 60 + sec) * 1000 + int(str(ms).ljust(3, "0"))

    # HH:MM:SS(.mmm)
    m = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?", s)
    if m:
        h, mi, sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return ((int(h) * 60 + int(mi)) * 60 + int(sec)) * 1000 + ms

    # MM:SS(.mmm)
    m = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d{1,3}))?", s)
    if m:
        mi, sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return (int(mi) * 60 + int(sec)) * 1000 + ms

    # SS(.mmm)
    m = re.fullmatch(r"(\d+)(?:\.(\d{1,3}))?", s)
    if m:
        sec, ms = m.groups()
        ms = int(str(ms or "0").ljust(3, "0"))
        return int(sec) * 1000 + ms

    raise ValueError(f"无效时间格式: {time_str}")


def ms_to_srt(ms: int) -> str:
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
    ranges: List[Tuple[int, int]] = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        if "-" not in part:
            raise ValueError(f"无效区间格式(缺少-): {part}")
        a, b = part.split("-", 1)
        start = parse_clock_to_ms(a)
        end = parse_clock_to_ms(b)
        if start >= end:
            raise ValueError(f"无效区间(开始>=结束): {part}")
        ranges.append((start, end))

    if not ranges:
        raise ValueError("未提供有效删除区间")

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
    content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", content.strip())
    cues: List[Cue] = []

    time_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    )

    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln is not None]
        if not lines:
            continue

        time_line_idx = None
        m = None
        for i, line in enumerate(lines[:3]):  # 一般时间轴在前两行
            m = time_pattern.search(line)
            if m:
                time_line_idx = i
                break

        if time_line_idx is None or m is None:
            continue

        start_ms = parse_clock_to_ms(m.group(1))
        end_ms = parse_clock_to_ms(m.group(2))
        if end_ms <= start_ms:
            continue

        text = "\n".join(lines[time_line_idx + 1 :]).rstrip("\n")
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


def subtract_ranges(a: int, b: int, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
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
    out: List[Cue] = []

    # 先按原始时间排序，保证稳定输出
    for cue in sorted(cues, key=lambda c: (c.start_ms, c.end_ms)):
        for ks, ke in subtract_ranges(cue.start_ms, cue.end_ms, ranges):
            ns = ks - removed_before(ks, ranges)
            ne = ke - removed_before(ke, ranges)
            if ne > ns:
                out.append(Cue(start_ms=ns, end_ms=ne, text=cue.text))

    # 再次排序并消除重叠
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
    with open(path, "w", encoding="utf-8") as f:
        for idx, cue in enumerate(cues, start=1):
            f.write(f"{idx}\n")
            f.write(f"{ms_to_srt(cue.start_ms)} --> {ms_to_srt(cue.end_ms)}\n")
            f.write(cue.text.rstrip("\n"))
            f.write("\n\n")


def build_default_output(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    return f"{base}_removed.srt"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="删除 SRT 指定时间段，并将后续字幕时间整体前移。"
    )
    parser.add_argument("input", help="输入 SRT 文件路径")
    parser.add_argument(
        "ranges",
        help='删除时间段，如 "1:00-2:00" 或 "1:00-2:00,5:00-6:00"',
    )
    parser.add_argument("-o", "--output", help="输出 SRT 文件路径")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        return 1

    try:
        remove_ranges = parse_remove_ranges(args.ranges)
    except ValueError as e:
        print(f"错误: {e}")
        return 1

    with open(args.input, "r", encoding="utf-8-sig") as f:
        content = f.read()

    cues = parse_srt(content)
    new_cues = process_cues(cues, remove_ranges)

    output = args.output or build_default_output(args.input)
    write_srt(new_cues, output)

    print(f"处理完成: {args.input}")
    print(f"删除区间: {', '.join(f'{ms_to_srt(s)}-{ms_to_srt(e)}' for s, e in remove_ranges)}")
    print(f"原字幕条数: {len(cues)}")
    print(f"新字幕条数: {len(new_cues)}")
    print(f"输出文件: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
