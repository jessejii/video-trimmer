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
import math
import os
from typing import Any, Dict, List, Optional

from ..core.models import TaskResult, ToolContext
from ..core.paths import safe_filename, validate_path
from ..core.textio import read_text

#: 剪映草稿文件名，按优先级排列
DRAFT_FILE_NAMES = ("draft_info.json", "draft_content.json")

#: 导出格式下拉项
FORMAT_CHOICES = [
    ("SRT 字幕（含时间轴）", "srt"),
    ("纯文本 TXT（仅台词）", "txt"),
    ("两种都导出", "both"),
]

#: 时间单位下拉项
TIME_UNIT_CHOICES = [
    ("自动（按微秒解析，适用现行剪映）", "auto"),
    ("微秒（Windows 剪映 / 现行版本）", "us"),
    ("毫秒（旧版 Mac 剪映）", "ms"),
]

#: SRT 规范要求 CRLF 换行（对应 JS 的 RN = "\r\n"）
NEWLINE = "\r\n"


# ---------------------------------------------------------------------------
# 核心转换（与 HTML 中的 JS 函数一一对应）
# ---------------------------------------------------------------------------
def format_digit(digit: Any, length: int) -> str:
    """左补零到指定长度（对应 JS formatDigit）。"""
    try:
        text = str(int(digit))
    except (TypeError, ValueError):
        text = "0"
    return text.rjust(length, "0")


def get_srt_time_text(time: Any, micro: bool = True) -> str:
    """剪映时间 -> SRT 时间文本 HH:MM:SS,mmm（对应 JS getSrtTimeText）。

    参数:
        time:  剪映时间值
        micro: True 表示 time 为微秒，需先除以 1000 转为毫秒
    """
    value = math.floor(float(time))
    if micro:
        value = math.floor(value / 1000)

    millisecond = value % 1000
    value = math.floor(value / 1000)
    second = value % 60
    value = math.floor(value / 60)
    minute = value % 60
    value = math.floor(value / 60)
    hour = value

    return (
        f"{format_digit(hour, 2)}:{format_digit(minute, 2)}:"
        f"{format_digit(second, 2)},{format_digit(millisecond, 3)}"
    )


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
                f"{get_srt_time_text(start, micro)} --> "
                f"{get_srt_time_text(start + duration, micro)}{newline}"
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
def load_draft(path: str) -> Dict[str, Any]:
    """读取剪映草稿 JSON（utf-8-sig 优先，失败回退 gbk）。"""
    return json.loads(read_text(path))


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


def draft_stem(draft_path: str) -> str:
    """导出文件主名：draft_info.json 时改用草稿目录名，避免同名覆盖。"""
    stem = os.path.splitext(os.path.basename(draft_path))[0]
    if stem.lower() in ("draft_info", "draft_content"):
        parent = os.path.basename(os.path.dirname(os.path.abspath(draft_path)))
        stem = parent or stem
    return safe_filename(stem, fallback="draft")


def _unique_path(path: str, overwrite: bool) -> str:
    if overwrite or not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}_{n}{ext}"):
        n += 1
    return f"{stem}_{n}{ext}"


def _target_path(draft_path: str, filename: str, output_dir: str) -> str:
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)
    return os.path.join(os.path.dirname(draft_path) or ".", filename)


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
    overwrite = bool(ctx.settings.overwrite)

    outputs: List[str] = []
    warnings: List[str] = []
    success = 0
    failed = 0
    total = len(drafts)

    ctx.log(f"找到 {total} 个草稿文件")

    for i, draft_path in enumerate(drafts, 1):
        ctx.check_cancel()
        folder = os.path.basename(os.path.dirname(draft_path))
        ctx.log(f"[{i}/{total}] {folder}")
        ctx.progress(percent=i / total * 100, file=folder)

        try:
            draft = load_draft(draft_path)
        except (OSError, ValueError) as exc:
            ctx.error(f"  解析失败: {exc}")
            failed += 1
            continue

        produced = 0
        for fmt in targets:
            tracks = convert_draft_to_subtitles(draft, micro=micro, fmt=fmt)
            if not tracks:
                warnings.append(f"{folder}：没有可导出的文本轨道（{fmt.upper()}）")
                continue

            stem = draft_stem(draft_path)
            multi = len(tracks) > 1
            for n, (_track_id, body) in enumerate(tracks.items(), 1):
                filename = f"{stem}_track{n}.{fmt}" if multi else f"{stem}.{fmt}"
                out_path = _unique_path(
                    _target_path(draft_path, filename, output_dir), overwrite
                )
                try:
                    with open(out_path, "w", encoding="utf-8", newline="") as fh:
                        fh.write(body)
                except OSError as exc:
                    ctx.error(f"  写入失败: {exc}")
                    continue
                outputs.append(out_path)
                produced += 1
                ctx.success(f"  -> {os.path.basename(out_path)}")

        if produced:
            success += 1
        else:
            failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个草稿，失败 {failed} 个，共导出 {len(outputs)} 个文件",
        outputs=outputs,
        warnings=warnings,
    )
