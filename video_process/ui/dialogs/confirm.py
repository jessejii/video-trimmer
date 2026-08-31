# -*- coding: utf-8 -*-
"""任务确认对话框：执行前汇总展示所有参数。"""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def build_summary_lines(values: Dict[str, object],
                        labels: Dict[str, str]) -> List[str]:
    """把参数字典渲染为确认文本行。"""
    lines: List[str] = []
    for key, value in values.items():
        label = labels.get(key, key)
        if isinstance(value, bool):
            shown = "是" if value else "否"
        elif value in (None, ""):
            shown = "（默认）"
        else:
            shown = str(value)
        lines.append(f"  {label}: {shown}")
    return lines or ["  （无参数）"]


class ConfirmDialog(QDialog):
    """确认对话框。"""

    def __init__(
        self,
        title: str = "确认执行",
        lines: Optional[List[str]] = None,
        confirm_label: str = "开始",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_label = QLabel(title, self)
        title_label.setObjectName("confirm-title")
        layout.addWidget(title_label)

        body = QFrame(self)
        body.setObjectName("confirm-body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 10, 12, 10)
        body_label = QLabel("\n".join(lines or []), body)
        body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body_label.setWordWrap(True)
        body_layout.addWidget(body_label)
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addStretch(1)

        ok = QPushButton(confirm_label, self)
        ok.setProperty("variant", "primary")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        actions.addWidget(ok)

        cancel = QPushButton("取消", self)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)

        layout.addLayout(actions)

    # ------------------------------------------------------------------
    @staticmethod
    def ask(
        title: str,
        lines: Optional[List[str]],
        confirm_label: str = "开始",
        parent: Optional[QWidget] = None,
    ) -> bool:
        dialog = ConfirmDialog(title, lines, confirm_label, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted
