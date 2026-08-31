# -*- coding: utf-8 -*-
"""全局设置面板。

沉淀原 bat 中反复出现的选项，避免每次重填。持久化到 ~/.video-process/config.json。
"""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...core.models import LogLevel, Settings
from ...settings_store import save_settings
from ..host import PanelHost
from ...param_spec import ToolDefinition
from .base import ToolPanel


class SettingsPanel(ToolPanel):
    """全局设置：从 host.settings 回填，保存时写回配置文件。"""

    def __init__(
        self,
        definition: ToolDefinition,
        host: PanelHost,
        parent: QWidget | None = None,
    ) -> None:
        self._status_label: QLabel | None = None
        super().__init__(definition, host, parent)
        self.load_from_settings()

    # ==================================================================
    def build_extra(self, content: QWidget, layout: QVBoxLayout) -> None:
        self._status_label = QLabel("", content)
        self._status_label.setProperty("role", "param-help")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def load_from_settings(self) -> None:
        """用当前全局设置填充控件值。"""
        settings = self.host.settings
        for spec in self.definition.specs:
            if not hasattr(settings, spec.name):
                continue
            row = self.row(spec.name)
            if row is None:
                continue
            value = getattr(settings, spec.name)
            row.set_value(spec.default if value is None else value)
        self.collect_values()
        self.refresh_visibility()

    # ==================================================================
    def start_task(self, values: Dict[str, Any]) -> None:
        """保存设置，不走后台线程。"""
        self.set_running(True)
        try:
            merged = {**self.host.settings.to_dict(), **values}
            settings = Settings.from_dict(merged)
            self.host.settings = settings
            ok = save_settings(settings)
        finally:
            self.set_running(False)

        if ok:
            self._set_status("设置已保存", ok=True)
            self.host.notify("设置已保存", "information", timeout=3)
            self.host.log_message("全局设置已保存", LogLevel.SUCCESS)
        else:
            self._set_status("保存失败，请检查配置文件权限", ok=False)
            self.host.notify("设置保存失败", "error", timeout=5)

    def build_summary(self, values: Dict[str, Any]) -> List[str]:
        return []

    # ==================================================================
    def _set_status(self, text: str, ok: bool) -> None:
        if self._status_label is None:
            return
        self._status_label.setText(text)
        self._status_label.setProperty(
            "role", "status-ok" if ok else "status-err"
        )
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def reset_params(self) -> None:
        """重置为内置默认值（Spec 中的 default），不写盘。"""
        super().reset_params()
        self._set_status("已重置为默认值，点击「开始执行」保存", ok=True)
