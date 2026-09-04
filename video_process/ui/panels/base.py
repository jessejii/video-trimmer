# -*- coding: utf-8 -*-
"""工具面板基类：由 ToolDefinition 自动生成表单、校验、调度后台任务。

约定：specs 中的 name 必须与业务函数形参名一致，
这样 collect_values() 的结果可以直接 **values 传给业务函数。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dataclasses import replace

from ...core.models import LogLevel, TaskResult
from ...core.paths import validate_path
from ...param_spec import ParamSpec, ToolDefinition
from ..dialogs.confirm import ConfirmDialog, build_summary_lines
from ..host import PanelHost
from ..widgets import PathInput


class _ParamRow(QWidget):
    """单个参数行：标签 + 帮助文本 + 编辑器。

    条件显隐直接对整行 setVisible，不会漏掉帮助文本。
    """

    def __init__(self, spec: ParamSpec, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.spec = spec

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(3)

        if spec.kind == "bool":
            self.editor = QCheckBox(spec.label, self)
            self.editor.setCursor(Qt.CursorShape.PointingHandCursor)
            self.editor.setChecked(bool(spec.default))
            layout.addWidget(self.editor)
            self.label = None
        else:
            self.label = QLabel(spec.label, self)
            self.label.setProperty("role", "param-label")
            layout.addWidget(self.label)

            self.editor = self._make_editor(spec)
            layout.addWidget(self.editor)

        self.help_label: Optional[QLabel] = None
        if spec.help:
            self.help_label = QLabel(spec.help, self)
            self.help_label.setProperty("role", "param-help")
            self.help_label.setWordWrap(True)
            layout.addWidget(self.help_label)

    # ------------------------------------------------------------------
    @staticmethod
    def _make_editor(spec: ParamSpec) -> QWidget:
        if spec.kind == "path":
            return PathInput(
                placeholder="拖入文件或文件夹，或点击右侧浏览…",
                value=str(spec.default or ""),
                select_directory=True,
                file_patterns=spec.file_patterns,
                allow_both=True,
            )
        if spec.kind in ("dir", "outdir"):
            return PathInput(
                placeholder="拖入文件夹，或点击右侧浏览…",
                value=str(spec.default or ""),
                select_directory=True,
            )
        if spec.kind == "file":
            return PathInput(
                placeholder="拖入文件，或点击右侧浏览…",
                value=str(spec.default or ""),
                select_directory=False,
                file_patterns=spec.file_patterns,
            )
        if spec.kind == "choice":
            combo = QComboBox()
            combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            for text, value in spec.choices or []:
                combo.addItem(str(text), userData=value)
            index = combo.findData(spec.default)
            if index >= 0:
                combo.setCurrentIndex(index)
            return combo
        if spec.multiline:
            area = QPlainTextEdit()
            area.setPlainText("" if spec.default is None else str(spec.default))
            area.setFixedHeight(140)
            return area
        from PyQt6.QtWidgets import QLineEdit

        edit = QLineEdit()
        edit.setText("" if spec.default is None else str(spec.default))
        edit.setPlaceholderText(spec.help or spec.label)
        return edit

    # ------------------------------------------------------------------
    def path_input(self) -> Optional[PathInput]:
        return self.editor if isinstance(self.editor, PathInput) else None

    def read_value(self) -> Any:
        """读取控件当前值（未做类型强转）。"""
        editor = self.editor
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QComboBox):
            data = editor.currentData()
            return editor.currentText() if data is None else data
        if isinstance(editor, PathInput):
            return editor.value
        if isinstance(editor, QPlainTextEdit):
            return editor.toPlainText()
        return editor.text()

    def set_value(self, value: Any) -> None:
        editor = self.editor
        if isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif isinstance(editor, QComboBox):
            index = editor.findData(value)
            if index >= 0:
                editor.setCurrentIndex(index)
        elif isinstance(editor, PathInput):
            editor.set_value("" if value is None else str(value))
        elif isinstance(editor, QPlainTextEdit):
            editor.setPlainText("" if value is None else str(value))
        else:
            editor.setText("" if value is None else str(value))

    def set_invalid(self, invalid: bool) -> None:
        path_input = self.path_input()
        if path_input is not None:
            path_input.set_invalid(invalid)
            return
        if not isinstance(self.editor, (QCheckBox, QComboBox, QPlainTextEdit)):
            self.editor.setProperty("invalid", "true" if invalid else "false")
            self.editor.style().unpolish(self.editor)
            self.editor.style().polish(self.editor)


class ToolPanel(QWidget):
    """参数面板基类。"""

    def __init__(
        self,
        definition: ToolDefinition,
        host: PanelHost,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self.host = host
        # 每面板一份 spec 副本：默认值要按当前全局设置覆盖，
        # 而 definition.specs 是模块级共享实例，不能直接改。
        self.specs = [self._apply_setting(s) for s in definition.specs]
        self._rows: Dict[str, _ParamRow] = {}
        self._values: Dict[str, Any] = {
            spec.name: spec.default for spec in self.specs
        }
        self._running = False

        self._build_ui()
        self.refresh_visibility()

    # ==================================================================
    # 默认值来源
    # ==================================================================
    def _apply_setting(self, spec: ParamSpec) -> ParamSpec:
        """spec 声明了 setting 时，用全局设置的值作为本参数的默认值。

        设置值为 None（如「目标码率」留空）时保留 spec 自身的 default，
        这样「留空=自动」这类语义不会被设置里的空值顶掉。
        """
        if not spec.setting:
            return spec
        value = getattr(self.host.settings, spec.setting, None)
        if value is None:
            return spec
        return replace(spec, default=value)

    # ==================================================================
    # UI 构建
    # ==================================================================
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(0)

        title = QLabel(self.definition.title, self)
        title.setProperty("role", "panel-title")
        root.addWidget(title)

        if self.definition.description:
            desc = QLabel(self.definition.description, self)
            desc.setProperty("role", "panel-desc")
            desc.setWordWrap(True)
            root.addWidget(desc)
            root.addSpacing(6)

        scroll = QScrollArea(self)
        scroll.setObjectName("panel-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 8, 12, 8)
        content_layout.setSpacing(0)

        for spec in self.specs:
            row = self._build_row(spec)
            self._rows[spec.name] = row
            content_layout.addWidget(row)

        self.build_extra(content, content_layout)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        root.addLayout(self._build_actions())

    def _build_row(self, spec: ParamSpec) -> _ParamRow:
        row = _ParamRow(spec, self)
        self._connect_row(row, spec)
        return row

    def _connect_row(self, row: _ParamRow, spec: ParamSpec) -> None:
        editor = row.editor
        if isinstance(editor, QCheckBox):
            editor.stateChanged.connect(self._on_value_changed)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(self._on_value_changed)
        elif isinstance(editor, PathInput):
            editor.valueChanged.connect(self._on_value_changed)
            editor.noticeRequested.connect(self._on_path_notice)
        elif isinstance(editor, QPlainTextEdit):
            editor.textChanged.connect(self._on_value_changed)
        else:
            editor.textChanged.connect(self._on_value_changed)

    def build_extra(self, content: QWidget, layout: QVBoxLayout) -> None:
        """子类覆盖：追加自定义控件（如时间线计算器的结果区）。"""
        return None

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 10, 0, 2)
        actions.setSpacing(8)

        self._run_button = QPushButton("开始执行", self)
        self._run_button.setProperty("variant", "primary")
        self._run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_button.clicked.connect(self._on_run_clicked)
        actions.addWidget(self._run_button)

        self._reset_button = QPushButton("重置参数", self)
        self._reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_button.clicked.connect(self.reset_params)
        actions.addWidget(self._reset_button)

        actions.addStretch(1)
        return actions

    # ==================================================================
    # 值收集与校验
    # ==================================================================
    def row(self, name: str) -> Optional[_ParamRow]:
        return self._rows.get(name)

    def _read_widget(self, spec: ParamSpec) -> Any:
        row = self._rows.get(spec.name)
        if row is None:
            return spec.default
        return spec.coerce(row.read_value())

    def collect_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for spec in self.specs:
            values[spec.name] = self._read_widget(spec)
        self._values = dict(values)
        return values

    def validate(self, values: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        for spec in self.specs:
            if spec.visible_when is not None and not spec.should_show(values):
                continue

            value = values.get(spec.name)

            if spec.kind == "dir" and value:
                ok, _r, err = validate_path(str(value), kind="dir")
                if not ok:
                    errors.append(f"{spec.label}：{err}")
                    continue
            elif spec.kind == "file" and value:
                ok, _r, err = validate_path(str(value), kind="file")
                if not ok:
                    errors.append(f"{spec.label}：{err}")
                    continue
            elif spec.kind == "path" and value:
                # 文件或文件夹均可，只校验存在性
                ok, _r, err = validate_path(str(value), kind="any")
                if not ok:
                    errors.append(f"{spec.label}：{err}")
                    continue
            elif spec.kind == "outdir" and value and os.path.isfile(str(value)):
                # 输出文件夹允许不存在（工具会自动创建），但不能是已存在的文件
                errors.append(f"{spec.label}：已存在同名文件，不能作为输出文件夹")
                continue

            if spec.required and spec.kind != "bool" and value in (None, ""):
                errors.append(f"{spec.label}：不能为空")
                continue

            if spec.validator and value not in (None, ""):
                msg = spec.validator(value)
                if msg:
                    errors.append(f"{spec.label}：{msg}")
        return errors

    def mark_errors(self, values: Dict[str, Any]) -> None:
        """把校验失败的参数标红。"""
        for spec in self.specs:
            row = self._rows.get(spec.name)
            if row is None:
                continue
            value = values.get(spec.name)
            if spec.kind in ("dir", "file", "path") and value:
                ok, _r, _err = validate_path(
                    str(value),
                    kind="file" if spec.kind == "file" else (
                        "dir" if spec.kind == "dir" else "any"
                    ),
                )
                row.set_invalid(not ok)
            elif spec.kind == "outdir" and value:
                row.set_invalid(os.path.isfile(str(value)))
            else:
                row.set_invalid(False)

    # ==================================================================
    # 事件
    # ==================================================================
    def _on_value_changed(self, *_args) -> None:
        self.collect_values()
        self.refresh_visibility()

    def _on_path_notice(self, message: str, severity: str) -> None:
        self.host.notify(message, severity, timeout=4)

    def refresh_visibility(self) -> None:
        """根据当前值切换条件字段的显隐。"""
        for spec in self.specs:
            if spec.visible_when is None:
                continue
            row = self._rows.get(spec.name)
            if row is not None:
                row.setVisible(spec.should_show(self._values))

    def reset_params(self) -> None:
        for spec in self.specs:
            row = self._rows.get(spec.name)
            if row is not None:
                row.set_value(spec.default)
        self._values = {s.name: s.default for s in self.specs}
        self.refresh_visibility()

    def fill_value(self, name: str, value: Any) -> bool:
        """外部写入某个参数（如时间线计算器回填「片段删除」）。"""
        row = self._rows.get(name)
        if row is None:
            return False
        row.set_value(value)
        self.collect_values()
        self.refresh_visibility()
        return True

    # ==================================================================
    # 执行流程
    # ==================================================================
    def _on_run_clicked(self) -> None:
        if self._running:
            self.host.cancel_task()
            return
        self.request_run()

    def request_run(self) -> None:
        if self._running:
            return
        values = self.collect_values()
        errors = self.validate(values)
        self.mark_errors(values)
        if errors:
            self.host.notify(
                "参数校验失败:\n" + "\n".join(f"• {e}" for e in errors),
                "error",
                timeout=8,
            )
            for e in errors:
                self.host.log_message(e, LogLevel.ERROR)
            return

        if not self.definition.confirm_before_run:
            self.start_task(values)
            return

        lines = self.build_summary(values)
        if not ConfirmDialog.ask(
            f"确认执行：{self.definition.title}", lines, "开始", self
        ):
            self.host.notify("已取消", "information", timeout=2)
            return
        self.start_task(values)

    def build_summary(self, values: Dict[str, Any]) -> List[str]:
        return build_summary_lines(values, self.definition.labels)

    def start_task(self, values: Dict[str, Any]) -> None:
        """交给主窗口调度后台线程。"""
        self.set_running(True)
        if not self.host.run_task(self.definition, values, panel=self):
            self.set_running(False)

    def set_running(self, running: bool) -> None:
        self._running = running
        self._run_button.setText("停止" if running else "开始执行")
        self._run_button.setProperty(
            "variant", "danger" if running else "primary"
        )
        self._run_button.style().unpolish(self._run_button)
        self._run_button.style().polish(self._run_button)
        self._reset_button.setEnabled(not running)

    @property
    def running(self) -> bool:
        return self._running

    def on_result(self, result: TaskResult) -> None:
        """任务结尾时回调（主线程）。"""
        self.set_running(False)
        if result.outputs:
            self.host.log_message(
                f"输出 {len(result.outputs)} 个文件:", LogLevel.SUCCESS
            )
            for out in result.outputs[:20]:
                self.host.log_message(f"  {out}", LogLevel.INFO)
            if len(result.outputs) > 20:
                self.host.log_message(
                    f"  … 其余 {len(result.outputs) - 20} 个已省略",
                    LogLevel.INFO,
                )
