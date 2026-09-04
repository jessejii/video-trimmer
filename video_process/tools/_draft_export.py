# -*- coding: utf-8 -*-
"""必剪 / 剪映草稿字幕导出的公共部分。

两种草稿格式的结构解析各自独立（见 bcut_subtitle / jianying_subtitle），
但「定位草稿 -> 定导出文件名 -> 写文件 -> 统计」这一段完全一致，抽到这里。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List

from ..core.models import TaskResult, ToolContext
from ..core.paths import safe_filename
from ..core.textio import read_text

#: 导出格式下拉项
FORMAT_CHOICES = [
    ("SRT 字幕（含时间轴）", "srt"),
    ("纯文本 TXT（仅台词）", "txt"),
    ("两种都导出", "both"),
]

#: SRT 规范要求 CRLF 换行
NEWLINE = "\r\n"

#: 无信息量的草稿主名，这类名字改用所属草稿目录名
_GENERIC_NAMES = ("draft", "draft_info", "draft_content")

#: 形如 UUID / 哈希的自动命名（这类文件名不适合做导出主名）
_AUTO_NAME = re.compile(r"^[0-9a-fA-F][0-9a-fA-F\-_]{15,}$")


def load_draft(path: str) -> Dict[str, Any]:
    """读取草稿 JSON（utf-8-sig 优先，失败回退 gbk）。"""
    return json.loads(read_text(path))


def draft_stem(draft_path: str) -> str:
    """导出文件主名：无信息量的草稿名（draft_info / UUID 等）改用草稿目录名。"""
    stem = os.path.splitext(os.path.basename(draft_path))[0]
    if not stem or stem.lower() in _GENERIC_NAMES or _AUTO_NAME.match(stem):
        parent = os.path.basename(os.path.dirname(os.path.abspath(draft_path)))
        stem = parent or stem
    return safe_filename(stem, fallback="draft")


def unique_path(path: str, overwrite: bool) -> str:
    if overwrite or not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}_{n}{ext}"):
        n += 1
    return f"{stem}_{n}{ext}"


def target_path(draft_path: str, filename: str, output_dir: str) -> str:
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)
    return os.path.join(os.path.dirname(draft_path) or ".", filename)


def export_drafts(
    ctx: ToolContext,
    drafts: List[str],
    targets: List[str],
    convert: Callable[[Dict[str, Any], str], Dict[str, str]],
    output_dir: str,
    empty_hint: str,
) -> TaskResult:
    """草稿批量导出的骨架。

    参数:
        targets:    要导出的格式列表，如 ["srt"] 或 ["srt", "txt"]
        convert:    (草稿 dict, 格式) -> {轨道名: 文本}，由各草稿格式提供
        empty_hint: 某格式无轨道时的提示措辞，如「字幕轨道」
    """
    outputs: List[str] = []
    warnings: List[str] = []
    success = 0
    failed = 0
    total = len(drafts)
    overwrite = bool(ctx.settings.overwrite)

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
            tracks = convert(draft, fmt)
            if not tracks:
                warnings.append(f"{folder}：没有可导出的{empty_hint}（{fmt.upper()}）")
                continue

            stem = draft_stem(draft_path)
            multi = len(tracks) > 1
            for n, (_name, body) in enumerate(tracks.items(), 1):
                filename = f"{stem}_track{n}.{fmt}" if multi else f"{stem}.{fmt}"
                out_path = unique_path(
                    target_path(draft_path, filename, output_dir), overwrite
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
        message=(
            f"完成，成功 {success} 个草稿，失败 {failed} 个，"
            f"共导出 {len(outputs)} 个文件"
        ),
        outputs=outputs,
        warnings=warnings,
    )
