# -*- coding: utf-8 -*-
"""字幕文件后缀重命名：为字幕文件追加 .txt 后缀，方便文本编辑。

替代原 rename_srt_to_txt.bat 的纯批处理实现。

    1.srt -> 1.srt.txt

支持 .srt / .ass / .vtt / .lrc，文件夹模式递归子目录。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.models import TaskResult, ToolContext
from ..core.paths import SUBTITLE_EXTENSIONS, scan_subtitles, validate_path


def rename_subtitles(
    input_path: str,
    recursive: bool = True,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """为字幕文件追加 .txt 后缀。

    参数:
        input_path: 输入字幕文件或文件夹
        recursive:  文件夹模式是否递归子目录
    """
    ctx = ctx or ToolContext()

    ok, resolved, err = validate_path(input_path)
    if not ok:
        return TaskResult(success=False, message=err)

    outputs: List[str] = []
    success = 0
    failed = 0

    if os.path.isfile(resolved):
        targets = [resolved]
    else:
        targets = scan_subtitles(resolved, recursive=recursive)

    if not targets:
        return TaskResult(
            success=False,
            message=f"没有找到字幕文件（{', '.join(SUBTITLE_EXTENSIONS)}）: {resolved}",
        )

    ctx.log(f"找到 {len(targets)} 个字幕文件")

    for i, path in enumerate(targets, 1):
        ctx.check_cancel()
        name = os.path.basename(path)
        new_path = path + ".txt"

        if os.path.exists(new_path):
            ctx.warn(f"  跳过（目标已存在）: {name}")
            failed += 1
            continue

        ctx.log(f"[{i}/{len(targets)}] {name} -> {name}.txt")
        try:
            os.rename(path, new_path)
            outputs.append(new_path)
            success += 1
        except OSError as exc:
            ctx.error(f"  重命名失败: {exc}")
            failed += 1

    return TaskResult(
        success=failed == 0 and success > 0,
        message=f"完成，成功 {success} 个，失败 {failed} 个",
        outputs=outputs,
    )
