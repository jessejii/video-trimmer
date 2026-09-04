# -*- coding: utf-8 -*-
"""必剪（Bcut）草稿字幕导出：*.bjson -> SRT / TXT。

由 bcut-subtitle-workshop 的 bcut_core.py 移植，字幕定位逻辑保持一致：

    · 新版草稿: timelineWidget.timeline.captionTracks[].captions[]
    · 旧版草稿: timelineWidget.tracks[] 中 type 为 subtitle/text 的 segments[]
    · 时间为毫秒（inPoint / outPoint），文本取 captionText

相比原实现，这里补齐了多字幕轨道、按时间排序、跳过空字幕与批量导出。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import TaskResult, ToolContext
from ..core.paths import validate_path
from ..core.timeparse import format_srt_time
from ._draft_export import FORMAT_CHOICES, NEWLINE, export_drafts, load_draft

#: 必剪草稿文件扩展名
DRAFT_EXT = ".bjson"

#: 旧版轨道类型
_SUBTITLE_TRACK_TYPES = ("subtitle", "text", "caption")


# ---------------------------------------------------------------------------
# 核心转换
# ---------------------------------------------------------------------------
def _caption_text(caption: Dict[str, Any]) -> str:
    """取出一条字幕的文本，兼容新旧字段。"""
    for key in ("captionText", "text"):
        value = caption.get(key)
        if isinstance(value, str) and value.strip():
            return value
    asset = caption.get("assetInfo")
    if isinstance(asset, dict):
        for key in ("content", "displayName"):
            value = asset.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _caption_start(caption: Dict[str, Any]) -> int:
    """读取字幕起点（毫秒），用于排序。"""
    for key in ("inPoint", "start"):
        value = caption.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _caption_end(caption: Dict[str, Any], start: int) -> int:
    """读取字幕终点（毫秒），缺失时用 duration 推导。"""
    for key in ("outPoint", "end"):
        value = caption.get(key)
        if isinstance(value, (int, float)):
            end = int(value)
            return end if end >= start else start
    duration = caption.get("duration")
    if isinstance(duration, (int, float)):
        return start + max(int(duration), 0)
    asset = caption.get("assetInfo")
    if isinstance(asset, dict) and isinstance(asset.get("duration"), (int, float)):
        return start + max(int(asset["duration"]), 0)
    return start


def find_caption_tracks(data: Dict[str, Any]) -> List[Tuple[str, List[dict]]]:
    """定位草稿中的字幕轨道，返回 [(轨道名, 字幕列表), ...]。"""
    tracks: List[Tuple[str, List[dict]]] = []

    widget = data.get("timelineWidget") or {}

    # 新版：timelineWidget.timeline.captionTracks[].captions
    timeline = widget.get("timeline") or {}
    for i, track in enumerate(timeline.get("captionTracks") or [], 1):
        if not isinstance(track, dict):
            continue
        captions = [c for c in (track.get("captions") or []) if isinstance(c, dict)]
        if captions:
            tracks.append((str(track.get("name") or f"track{i}"), captions))

    # 旧版：timelineWidget.tracks[] 中字幕/文本轨道的 segments
    if not tracks:
        for i, track in enumerate(widget.get("tracks") or [], 1):
            if not isinstance(track, dict):
                continue
            if str(track.get("type") or "").lower() not in _SUBTITLE_TRACK_TYPES:
                continue
            captions = [c for c in (track.get("segments") or []) if isinstance(c, dict)]
            if captions:
                tracks.append((str(track.get("name") or f"track{i}"), captions))

    return tracks


def convert_track_to_subtitles(
    captions: List[dict],
    fmt: str = "srt",
    newline: str = NEWLINE,
) -> str:
    """把一条字幕轨道转换为 SRT / TXT 文本。"""
    items = [_Caption(c) for c in captions]
    # 按起点稳定排序，保证 SRT 时间严格递增
    items.sort(key=lambda item: item.start)

    pieces: List[str] = []
    index = 0
    for item in items:
        if not item.text.strip():
            continue
        if fmt == "srt":
            index += 1
            pieces.append(
                f"{index}{newline}"
                f"{format_srt_time(item.start)} --> "
                f"{format_srt_time(item.end)}{newline}"
                f"{item.text}{newline}{newline}"
            )
        else:
            pieces.append(f"{item.text}{newline}{newline}")

    return "".join(pieces)


class _Caption:
    """单条字幕的归一化视图。"""

    __slots__ = ("start", "end", "text")

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.start = _caption_start(raw)
        self.end = _caption_end(raw, self.start)
        self.text = _caption_text(raw)


def convert_draft_to_subtitles(
    draft: Dict[str, Any],
    fmt: str = "srt",
) -> Dict[str, str]:
    """{轨道名: 字幕文本}，空轨道不产出。"""
    results: Dict[str, str] = {}
    for name, captions in find_caption_tracks(draft):
        body = convert_track_to_subtitles(captions, fmt=fmt)
        if not body:
            continue
        key = name or f"track{len(results) + 1}"
        if key in results:
            key = f"{key}_{len(results) + 1}"
        results[key] = body
    return results


# ---------------------------------------------------------------------------
# 文件发现与输出命名
# ---------------------------------------------------------------------------
def _latest_bjson_in(directory: str) -> Optional[str]:
    """取目录中修改时间最新的 .bjson（与原实现的 find_latest_bjson 一致）。"""
    try:
        names = [
            n for n in os.listdir(directory) if n.lower().endswith(DRAFT_EXT)
        ]
    except OSError:
        return None
    if not names:
        return None
    paths = [os.path.join(directory, n) for n in names]
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[0]


def collect_draft_files(root: str, recursive: bool = True) -> List[str]:
    """定位草稿 bjson：支持单个文件、草稿目录、草稿库根目录。"""
    if os.path.isfile(root):
        return [root] if root.lower().endswith(DRAFT_EXT) else []

    # 目录本身即草稿目录
    direct = _latest_bjson_in(root)
    if direct:
        return [direct]

    found: List[str] = []
    if recursive:
        for dirpath, _dirnames, _filenames in os.walk(root):
            hit = _latest_bjson_in(dirpath)
            if hit:
                found.append(hit)
    else:
        try:
            subdirs = sorted(os.listdir(root))
        except OSError:
            subdirs = []
        for name in subdirs:
            sub = os.path.join(root, name)
            if not os.path.isdir(sub):
                continue
            hit = _latest_bjson_in(sub)
            if hit:
                found.append(hit)

    return sorted(found)



# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------
def export_bcut_subtitles(
    input_path: str,
    export_format: str = "srt",
    recursive: bool = True,
    output_dir: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """导出必剪草稿中的字幕为 SRT / TXT。

    参数:
        input_path:    .bjson 草稿文件、草稿目录或草稿库根目录
        export_format: srt / txt / both
        recursive:     文件夹模式是否递归子目录
        output_dir:    输出目录，留空输出到草稿文件同目录
    """
    ctx = ctx or ToolContext()

    if export_format not in ("srt", "txt", "both"):
        return TaskResult(success=False, message=f"不支持的导出格式: {export_format}")

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    drafts = collect_draft_files(resolved, recursive=recursive)
    if not drafts:
        return TaskResult(
            success=False,
            message=f"没有找到必剪草稿文件（*{DRAFT_EXT}）: {resolved}",
        )

    targets = [f for f in ("srt", "txt") if export_format in (f, "both")]

    return export_drafts(
        ctx,
        drafts,
        targets,
        convert=lambda draft, fmt: convert_draft_to_subtitles(draft, fmt=fmt),
        output_dir=output_dir,
        empty_hint="字幕轨道",
    )
