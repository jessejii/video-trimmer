# -*- coding: utf-8 -*-
"""任务进度控件：当前文件 + 百分比 + 进度条。

percent 为 None 时进入不确定（忙碌）状态，Qt 下把 range 设为 (0, 0)
即可显示脉动动画。
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class TaskProgress(QWidget):
    """进度显示区。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._percent: Optional[float] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._file_label = QLabel("", self)
        self._file_label.setObjectName("progress-file")
        row.addWidget(self._file_label, 1)

        self._pct_label = QLabel("", self)
        self._pct_label.setObjectName("progress-pct")
        self._pct_label.setMinimumWidth(56)
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignRight
                                     | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._pct_label)

        layout.addLayout(row)

        self._bar = QProgressBar(self)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        layout.addWidget(self._bar)

        self.set_idle(True)

    # ------------------------------------------------------------------
    def set_idle(self, idle: bool = True) -> None:
        """空闲时隐藏进度区。"""
        self.setVisible(not idle)
        if idle:
            self._percent = None
            self._file_label.setText("")
            self._pct_label.setText("")
            self._bar.setRange(0, 100)
            self._bar.setValue(0)

    def set_busy(self) -> None:
        """进入运行态：显示进度区并重置为不确定进度。"""
        self.setVisible(True)
        self._percent = None
        self._file_label.setText("准备中…")
        self._pct_label.setText("")
        self._bar.setRange(0, 0)  # 不确定进度：脉动动画

    def update_progress(
        self,
        percent: Optional[float] = None,
        current_file: str = "",
        detail: str = "",
    ) -> None:
        if current_file:
            self._file_label.setText(current_file)

        if percent is None:
            # 不确定进度：保持脉动
            if self._bar.maximum() != 0:
                self._bar.setRange(0, 0)
            self._pct_label.setText(detail[:8] if detail else "")
            return

        percent = max(0.0, min(100.0, percent))
        # 防止进度回退（批量任务中每个文件会重新从 0 开始）
        if self._percent is not None and percent < self._percent:
            percent = self._percent
        self._percent = percent

        if self._bar.maximum() == 0:
            self._bar.setRange(0, 100)
        self._bar.setValue(int(percent))
        self._pct_label.setText(f"{percent:.0f}%")

    # ------------------------------------------------------------------
    @property
    def percent(self) -> Optional[float]:
        return self._percent
