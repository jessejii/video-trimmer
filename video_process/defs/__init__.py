# -*- coding: utf-8 -*-
"""工具定义层：界面渲染的唯一事实来源（不依赖任何 UI 框架）。

每个工具由一份 ToolDefinition 描述：参数规格（ParamSpec）+ 业务函数。
界面据此渲染表单，并在后台线程调用业务函数。

新增一个工具只需：在对应分组模块里加一个 ToolDefinition 并注册进 DEFS。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..param_spec import ParamSpec, ToolDefinition
from . import media, misc, subtitle, video

#: 导航分组顺序即界面显示顺序
NAV_GROUPS: List[Tuple[str, List[str]]] = [
    (video.GROUP, [d.id for d in video.DEFS]),
    (media.GROUP, [d.id for d in media.DEFS]),
    (subtitle.GROUP, [d.id for d in subtitle.DEFS]),
    (misc.GROUP, [d.id for d in misc.DEFS]),
]

#: 工具 id -> 定义。id 为 kebab 形式
TOOL_DEFS: Dict[str, ToolDefinition] = {
    d.id: d
    for module in (video, media, subtitle, misc)
    for d in module.DEFS
}


def get_def(tool_id: str) -> Optional[ToolDefinition]:
    """按 id 取工具定义。"""
    return TOOL_DEFS.get(tool_id)


def all_tools() -> List[Tuple[str, ToolDefinition]]:
    """返回 [(tool_id, 定义), ...]，顺序与导航一致。"""
    return [
        (tool_id, TOOL_DEFS[tool_id])
        for _group, ids in NAV_GROUPS
        for tool_id in ids
    ]


__all__ = [
    "NAV_GROUPS",
    "TOOL_DEFS",
    "ToolDefinition",
    "ParamSpec",
    "get_def",
    "all_tools",
]
