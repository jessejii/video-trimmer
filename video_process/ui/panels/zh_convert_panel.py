# -*- coding: utf-8 -*-
"""文本繁简转换面板。

纯计算，不进后台线程；转换结果直接回填输入框（可 Ctrl+Z 撤销）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from ...core.models import TaskResult, ToolContext
from ...param_spec import ToolDefinition
from ..host import PanelHost
from .base import ToolPanel


class ZhConvertPanel(ToolPanel):
    """一个输入框：粘贴原文 → 执行 → 得到转换后的文本。"""

    def __init__(
        self,
        definition: ToolDefinition,
        host: PanelHost,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(definition, host, parent)

    # ==================================================================
    # 输入框加大一点，默认的多行高度只够放五六行
    # ==================================================================
    def build_extra(self, content: QWidget, layout: QVBoxLayout) -> None:
        row = self.row("text")
        if row is not None and isinstance(row.editor, QPlainTextEdit):
            row.editor.setFixedHeight(260)

    # ==================================================================
    # 执行：同步完成，不走后台线程
    # ==================================================================
    def start_task(self, values: Dict[str, Any]) -> None:
        self.set_running(True)
        if not self.host.begin_task(self.definition.title):
            self.set_running(False)
            return

        ctx = ToolContext(
            on_log=lambda msg, lvl: self.host.log_message(msg, lvl),
            on_progress=lambda info: self.host.update_progress(info),
            is_cancelled=lambda: self.host.is_task_cancelled(),
        )
        runner = self.definition.resolve_runner()
        try:
            result = runner(
                values.get("text", ""), values.get("conversion", ""), ctx=ctx
            )
        except Exception as exc:  # noqa: BLE001 - 兜底，避免界面静默崩溃
            result = TaskResult(success=False, message=f"执行异常: {exc}")

        self.host.end_task(result)
        self.on_result(result)

    # ==================================================================
    # 结果回填
    # ==================================================================
    def on_result(self, result: TaskResult) -> None:
        self.set_running(False)
        if not result.success:
            return

        row = self.row("text")
        if row is not None and isinstance(row.editor, QPlainTextEdit):
            row.editor.setPlainText(
                result.outputs[0] if result.outputs else ""
            )
