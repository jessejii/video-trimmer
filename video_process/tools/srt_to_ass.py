# -*- coding: utf-8 -*-
"""SRT 字幕转 ASS 格式。

默认样式针对中文字体优化：文泉驿正黑、48 号字、描边 3、阴影 3、底部对齐，
适合视频压制。

时间转换: SRT `00:00:20,000` -> ASS `0:00:20.00`（毫秒保留两位）
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

from ..core.models import TaskResult, ToolContext
from ..core.paths import scan_subtitles, validate_path

ASS_HEADER = """[Script Info]
Title: Converted from SRT
ScriptType: v4.00+
WrapStyle: 1
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,文泉驿正黑,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,3,2,30,30,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# SRT 时间行: 00:00:20,000 --> 00:00:22,000
_TIME_LINE = re.compile(
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
)


class AssStyle:
    """ASS 默认样式参数，便于 UI 暴露可调项。"""

    def __init__(
        self,
        fontname: str = "文泉驿正黑",
        fontsize: int = 48,
        primary_colour: str = "&H00FFFFFF",
        outline: int = 3,
        shadow: int = 3,
        margin_v: int = 30,
    ) -> None:
        self.fontname = fontname
        self.fontsize = fontsize
        self.primary_colour = primary_colour
        self.outline = outline
        self.shadow = shadow
        self.margin_v = margin_v

    def header(self) -> str:
        style_line = (
            f"Style: Default,{self.fontname},{self.fontsize},"
            f"{self.primary_colour},&H000000FF,&H00000000,&H80000000,"
            f"0,0,0,0,100,100,0,0,1,{self.outline},{self.shadow},2,"
            f"30,30,{self.margin_v},1"
        )
        return ASS_HEADER.replace(
            "Style: Default,文泉驿正黑,48,&H00FFFFFF,&H000000FF,&H00000000,"
            "&H80000000,0,0,0,0,100,100,0,0,1,3,3,2,30,30,30,1",
            style_line,
        )


def parse_srt_time(time_str: str) -> str:
    """SRT 时间 -> ASS 时间。00:00:20,000 -> 0:00:20.00"""
    s = time_str.replace(",", ".")
    parts = s.split(":")
    if len(parts) != 3:
        return s
    hours, minutes, seconds = parts
    # seconds 形如 "20.000"，保留两位小数
    return f"{int(hours)}:{minutes}:{seconds[:-1]}"


def _read_text(path: str) -> str:
    """读取字幕文件，utf-8-sig 优先，失败回退 gbk。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk") as fh:
            return fh.read()


def convert_srt_to_ass(
    srt_file: str,
    ass_file: Optional[str] = None,
    style: Optional[AssStyle] = None,
) -> tuple:
    """转换单个 SRT 文件。返回 (成功, 输出路径, 字幕条数, 错误信息)。"""
    try:
        content = _read_text(srt_file)
    except OSError as exc:
        return False, "", 0, f"读取失败: {exc}"

    out = ass_file or (os.path.splitext(srt_file)[0] + ".ass")
    blocks = re.split(r"\n\s*\n", content.strip())
    dialogues: List[str] = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        match = None
        for line in lines[:3]:
            match = _TIME_LINE.search(line)
            if match:
                break
        if not match:
            continue

        # 字幕文本为时间行之后的所有行
        time_idx = next(
            (i for i, ln in enumerate(lines) if _TIME_LINE.search(ln)), -1
        )
        if time_idx < 0:
            continue
        text = "\\N".join(lines[time_idx + 1:])

        start = parse_srt_time(match.group(1))
        end = parse_srt_time(match.group(2))
        dialogues.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    header = (style or AssStyle()).header()
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(header)
            fh.write("\n".join(dialogues))
    except OSError as exc:
        return False, out, 0, f"写入失败: {exc}"

    return True, out, len(dialogues), ""


def srt_to_ass(
    input_path: str,
    output_dir: str = "",
    fontname: str = "文泉驿正黑",
    fontsize: int = 48,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """SRT 转 ASS。

    参数:
        input_path: 输入 .srt 文件或文件夹
        output_dir: 输出目录，空表示输入同目录
        fontname:    ASS 字体名
        fontsize:    字号
    """
    ctx = ctx or ToolContext()

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    style = AssStyle(fontname=fontname, fontsize=fontsize)

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        if not resolved.lower().endswith(".srt"):
            return TaskResult(success=False, message="请提供 SRT 格式的字幕文件")
        out = _target_path(resolved, output_dir)
        ctx.log(f"处理: {os.path.basename(resolved)}")
        ok_one, out_path, count, err_msg = convert_srt_to_ass(resolved, out, style)
        if ok_one:
            outputs.append(out_path)
            success += 1
            ctx.success(f"  转换成功，{count} 条字幕 -> {os.path.basename(out_path)}")
        else:
            failed += 1
            ctx.error(f"  失败: {err_msg}")
    else:
        files = [f for f in scan_subtitles(resolved, recursive=False)
                 if f.lower().endswith(".srt")]
        if not files:
            return TaskResult(success=False, message=f"文件夹中没有找到 .srt 文件: {resolved}")
        ctx.log(f"批量模式：找到 {len(files)} 个 SRT 文件")

        for i, f in enumerate(files, 1):
            ctx.check_cancel()
            out = _target_path(f, output_dir)
            ctx.log(f"[{i}/{len(files)}] {os.path.basename(f)}")
            ctx.progress(percent=i / len(files) * 100, file=os.path.basename(f))
            ok_one, out_path, count, err_msg = convert_srt_to_ass(f, out, style)
            if ok_one:
                outputs.append(out_path)
                success += 1
                ctx.success(f"  {count} 条字幕 -> {os.path.basename(out_path)}")
            else:
                failed += 1
                ctx.error(f"  失败: {err_msg}")

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )


def _target_path(srt_file: str, output_dir: str) -> str:
    if not output_dir:
        return os.path.splitext(srt_file)[0] + ".ass"
    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(srt_file))[0]
    return os.path.join(output_dir, f"{stem}.ass")
