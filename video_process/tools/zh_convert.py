# -*- coding: utf-8 -*-
"""文本繁简转换（OpenCC）。

支持台湾正体：s2twp 把简体字转成台湾用字与用语
（软件→軟體、鼠标→滑鼠），反向用 tw2sp / t2s。

转换结果放在 TaskResult.outputs[0]，由界面回填到输入框。

依赖: pip install opencc-python-reimplemented
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Tuple

from ..core.models import TaskResult, ToolContext

try:
    import opencc
except ImportError:      # 依赖缺失时给可操作提示，而不是导入即崩溃
    opencc = None        # type: ignore[assignment]

DEFAULT_CONVERSION = "s2twp"

#: (界面显示, OpenCC 配置名)
CONVERSION_CHOICES: List[Tuple[str, str]] = [
    ("简体 → 台湾正体（含习惯用语）", "s2twp"),
    ("简体 → 台湾正体", "s2tw"),
    ("简体 → 繁体（标准）", "s2t"),
    ("繁体 → 简体", "t2s"),
    ("台湾正体 → 简体（含习惯用语）", "tw2sp"),
    ("台湾正体 → 简体", "tw2s"),
]


@lru_cache(maxsize=None)
def _converter(config: str):
    """按配置名缓存 OpenCC 实例（词典载入较慢，别每次转换都重载）。"""
    if opencc is None:
        raise RuntimeError(
            "缺少 opencc 库，请执行: pip install opencc-python-reimplemented"
        )
    return opencc.OpenCC(config)


def convert_text(
    text: str,
    conversion: str = DEFAULT_CONVERSION,
    ctx: Optional[ToolContext] = None,
) -> TaskResult:
    """转换文本的简体与繁体。

    参数:
        text:       待转换文本
        conversion: OpenCC 配置名，见 CONVERSION_CHOICES
    """
    ctx = ctx or ToolContext()

    if not text or not text.strip():
        return TaskResult(success=False, message="请输入要转换的文本")

    try:
        converter = _converter(conversion)
    except RuntimeError as exc:
        return TaskResult(success=False, message=str(exc))
    except OSError as exc:
        return TaskResult(
            success=False, message=f"无效的转换配置 {conversion}: {exc}"
        )

    ctx.log(f"转换方向: {conversion}，共 {len(text)} 字")

    return TaskResult(
        success=True,
        message=f"转换完成（{conversion}）",
        outputs=[converter.convert(text)],
    )
