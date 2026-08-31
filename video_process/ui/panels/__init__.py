# -*- coding: utf-8 -*-
"""功能面板：由工具定义（ToolDefinition）驱动生成。"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QWidget

from ...param_spec import ToolDefinition
from ..host import PanelHost
from .base import ToolPanel
from .settings_panel import SettingsPanel
from .timeline_panel import TimelinePanel

#: 定制面板注册表：ToolDefinition.panel_class -> 面板类
_CUSTOM_PANELS = {
    "timeline": TimelinePanel,
    "settings": SettingsPanel,
}

__all__ = ["ToolPanel", "TimelinePanel", "SettingsPanel", "create_panel"]


def create_panel(
    definition: ToolDefinition,
    host: PanelHost,
    parent: Optional[QWidget] = None,
) -> ToolPanel:
    """按工具定义创建面板；未声明 panel_class 时使用通用表单面板。"""
    panel_cls = _CUSTOM_PANELS.get(definition.panel_class or "", ToolPanel)
    return panel_cls(definition, host, parent)
