# -*- coding: utf-8 -*-
"""日志输出区：分级着色、限行数、自动滚动。

ffmpeg 在长任务中可能瞬间产生数千行输出。若逐行 appendHtml，
主线程会被高频信号淹没而卡死，因此这里用 100 ms 定时器把期间到达的
行合并成一次批量写入；同时用 maximumBlockCount 限制保留行数。
"""

from __future__ import annotations

import html
from typing import List, Tuple

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit

from ...core.models import LogLevel

# 各级别配色（对应设计规范的青蓝/青绿/琥珀/绯红）
_LEVEL_COLOR = {
    LogLevel.INFO: "#E5E7EB",
    LogLevel.SUCCESS: "#34D399",
    LogLevel.WARNING: "#FBBF24",
    LogLevel.ERROR: "#F87171",
    LogLevel.DEBUG: "#6B7280",
}

_LEVEL_MARK = {
    LogLevel.SUCCESS: "✔ ",
    LogLevel.WARNING: "! ",
    LogLevel.ERROR: "✖ ",
}

_FLUSH_INTERVAL_MS = 100


class LogView(QPlainTextEdit):
    """带级别着色的日志视图。"""

    def __init__(self, max_lines: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self._max_lines = max_lines
        self._pending: List[Tuple[str, LogLevel]] = []

        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(max_lines)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        self._timer = QTimer(self)
        self._timer.setInterval(_FLUSH_INTERVAL_MS)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    # ------------------------------------------------------------------
    def write_line(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """排队写入一行日志（实际写入由定时器批量完成）。"""
        self._pending.append((message, level))
        # 缓冲区过大时立即落盘，避免内存无界增长
        if len(self._pending) >= 500:
            self._flush()

    def clear_log(self) -> None:
        self._pending.clear()
        self.clear()

    # ------------------------------------------------------------------
    def _flush(self) -> None:
        if not self._pending:
            return
        batch, self._pending = self._pending, []

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for message, level in batch:
            color = _LEVEL_COLOR.get(level, "#E5E7EB")
            mark = _LEVEL_MARK.get(level, "")
            cursor.insertHtml(
                f'<span style="color:{color};">'
                f"{html.escape(mark + message)}</span><br>"
            )
        self.setTextCursor(cursor)
        self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
