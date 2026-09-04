# -*- coding: utf-8 -*-
"""剪映草稿字幕导出：draft_info.json -> SRT / TXT。

由「字幕导出-剪映.html」中的 JavaScript 实现移植，算法保持一致：

    · materials.texts 以 id 建索引，得到 {material_id: content}
    · 遍历 tracks，用 segment.material_id 取回文本
    · 时间取自 segment.target_timerange，剪映以微秒存储，SRT 需要毫秒
    · 每条文本轨道导出为一个独立文件
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..core.models import TaskResult, ToolContext
from ..core.paths import validate_path
from ..core.timeparse import format_srt_time
from ._draft_export import FORMAT_CHOICES, NEWLINE, export_drafts, load_draft

#: 剪映草稿文件名，按优先级排列
DRAFT_FILE_NAMES = ("draft_info.json", "draft_content.json")

#: 时间单位下拉项
TIME_UNIT_CHOICES = [
    ("自动（按微秒解析，适用现行剪映）", "auto"),
    ("微秒（Windows 剪映 / 现行版本）", "us"),
    ("毫秒（旧版 Mac 剪映）", "ms"),
]


# ---------------------------------------------------------------------------
# 核心转换（对应 HTML 中的 JS 函数）
# ---------------------------------------------------------------------------
def extract_text(content: Any) -> str:
    """取出文本材料的纯文本（对应 JS JSON.parse(content).text）。

    content 通常是形如 '{"styles":[...],"text":"大家好"}' 的 JSON 串；
    部分版本已是 dict，个别情况下直接就是纯文本，这里全部兼容。
    """
    if isinstance(content, dict):
        text = content.get("text", "")
    elif isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
            except ValueError:
                obj = None
            text = obj.get("text", "") if isinstance(obj, dict) else content
        else:
            text = content
    else:
        text = "" if content is None else str(content)
    return "" if text is None else str(text)


def _segment_start(segment: Dict[str, Any]) -> int:
    """安全读取片段开始时间，用于排序。"""
    trange = segment.get("target_timerange") or {}
    try:
        return int(trange.get("start") or 0)
    except (TypeError, ValueError):
        return 0


def convert_track_to_subtitles(
    track: Dict[str, Any],
    texts: Dict[str, Any],
    micro: bool = True,
    fmt: str = "srt",
    newline: str = NEWLINE,
) -> str:
    """把一条轨道转换为 SRT / TXT 文本（对应 JS convertTrack2Srt）。"""
    segments = [
        s for s in (track.get("segments") or []) if isinstance(s, dict)
    ]
    # 按开始时间稳定排序，保证 SRT 时间严格递增
    segments.sort(key=_segment_start)
    # 剪映以微秒存储（旧版 Mac 为毫秒），SRT 需要毫秒
    scale = 1000 if micro else 1

    pieces: List[str] = []
    index = 0

    for segment in segments:
        text = extract_text(texts.get(segment.get("material_id")))
        if not text.strip():
            continue                       # JS: if (!srt.content) continue

        trange = segment.get("target_timerange") or {}
        start = _segment_start(segment)
        duration = int(trange.get("duration") or 0)

        if fmt == "srt":
            index += 1
            pieces.append(
                f"{index}{newline}"
                f"{format_srt_time(start // scale)} --> "
                f"{format_srt_time((start + duration) // scale)}{newline}"
                f"{text}{newline}{newline}"
            )
        else:
            pieces.append(f"{text}{newline}{newline}")

    return "".join(pieces)


def convert_draft_to_subtitles(
    draft: Dict[str, Any],
    micro: bool = True,
    fmt: str = "srt",
) -> Dict[str, str]:
    """{track_id: 字幕文本}，空轨道不产出（对应 JS convertJSON2SRT）。"""
    texts: Dict[str, Any] = {}
    materials = draft.get("materials") or {}
    for material in materials.get("texts") or []:
        if isinstance(material, dict) and material.get("id"):
            texts[material["id"]] = material.get("content")

    results: Dict[str, str] = {}
    for track in draft.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        body = convert_track_to_subtitles(track, texts, micro=micro, fmt=fmt)
        if not body:
            continue                       # JS: 空轨道不生成文件
        results[str(track.get("id") or f"track{len(results) + 1}")] = body
    return results


# ---------------------------------------------------------------------------
# 文件发现与输出命名
# ---------------------------------------------------------------------------
def _draft_file_in(directory: str) -> Optional[str]:
    for name in DRAFT_FILE_NAMES:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def collect_draft_files(root: str, recursive: bool = True) -> List[str]:
    """定位草稿 JSON：支持单个文件、草稿目录、草稿库根目录。"""
    if os.path.isfile(root):
        return [root] if root.lower().endswith(".json") else []

    found: List[str] = []

    # 情况一：目录本身即草稿目录
    direct = _draft_file_in(root)
    if direct:
        return [direct]

    # 情况二：草稿库根目录，向下查找
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            lowered = {name.lower(): name for name in filenames}
            for want in DRAFT_FILE_NAMES:
                if want in lowered:
                    found.append(os.path.join(dirpath, lowered[want]))
                    break
    else:
        for name in sorted(os.listdir(root)):
            sub = os.path.join(root, name)
            if not os.path.isdir(sub):
                continue
            hit = _draft_file_in(sub)
            if hit:
                found.append(hit)

    return sorted(found)



# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------
def export_jianying_subtitles(
    input_path: str,
    export_format: str = "srt",
    time_unit: str = "auto",
    recursive: bool = True,
    output_dir: str = "",
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """导出剪映草稿中的字幕为 SRT / TXT。

    参数:
        input_path:    draft_info.json、单个草稿目录或草稿库根目录
        export_format: srt / txt / both
        time_unit:     auto / us / ms，控制 target_timerange 的解析单位
        recursive:     文件夹模式是否递归子目录
        output_dir:    输出目录，留空输出到草稿文件同目录
    """
    ctx = ctx or ToolContext()

    if export_format not in ("srt", "txt", "both"):
        return TaskResult(success=False, message=f"不支持的导出格式: {export_format}")
    if time_unit not in ("auto", "us", "ms"):
        return TaskResult(success=False, message=f"不支持的时间单位: {time_unit}")

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    drafts = collect_draft_files(resolved, recursive=recursive)
    if not drafts:
        return TaskResult(
            success=False,
            message=f"没有找到剪映草稿文件（{' / '.join(DRAFT_FILE_NAMES)}）: {resolved}",
        )

    targets = [f for f in ("srt", "txt") if export_format in (f, "both")]
    # auto 与 us 都按微秒解析；仅旧版 Mac 草稿需按毫秒
    micro = time_unit != "ms"

    return export_drafts(
        ctx,
        drafts,
        targets,
        convert=lambda draft, fmt: convert_draft_to_subtitles(
            draft, micro=micro, fmt=fmt
        ),
        output_dir=output_dir,
        empty_hint="文本轨道",
    )
