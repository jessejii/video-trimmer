# -*- coding: utf-8 -*-
"""PyQt6 主窗口：左侧功能导航 + 右侧参数面板 + 底部日志进度区 + 状态栏。"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from PyQt6.QtCore import (
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPalette,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .._frozen import bundled_ffmpeg_dir, resource_path
from .._io import ensure_utf8_stdio
from ..core.ffmpeg import check_ffmpeg
from ..core.models import LogLevel, ProgressInfo, Settings, TaskResult
from ..core.probe import check_amf_support
from ..defs import NAV_GROUPS, TOOL_DEFS
from ..param_spec import ToolDefinition
from ..settings_store import load_settings
from . import theme
from .panels import create_panel
from .tasks import TaskRunner
from .widgets import LogView, TaskProgress

#: 导航项自定义数据：分组标题标记
ROLE_IS_GROUP = Qt.ItemDataRole.UserRole + 1
#: 导航项自定义数据：工具 id
ROLE_TOOL_ID = Qt.ItemDataRole.UserRole

#: 应用图标（相对项目根 / 打包资源根）。缺失时程序照常运行，
#: 只是任务栏与标题栏用 Qt 默认图标
APP_ICON_REL = os.path.join("assets", "app.ico")


def load_app_icon() -> Optional[QIcon]:
    """加载应用图标，找不到返回 None。

    源码运行与打包运行共用同一份相对路径，由 :func:`resource_path`
    负责在两种布局间切换。
    """
    path = resource_path(APP_ICON_REL)
    if not path:
        return None
    icon = QIcon(path)
    return None if icon.isNull() else icon


class _EnvChecker(QThread):
    """环境自检：check_ffmpeg / check_amf_support 会 spawn 子进程，
    放到后台线程执行以免启动卡顿。"""

    finished = pyqtSignal(bool, str, list)

    def run(self) -> None:  # noqa: D102 - QThread 入口
        try:
            ok, _ffmpeg, _ffprobe, version = check_ffmpeg()
        except Exception:
            ok, version = False, ""
        try:
            amf = check_amf_support()
        except Exception:
            amf = []
        self.finished.emit(bool(ok), str(version or ""), list(amf or []))


class _NavDelegate(QStyledItemDelegate):
    """导航列表绘制：分组标题用小号青蓝字，工具项选中时左侧强调条。"""

    def paint(self, painter, option, index) -> None:  # noqa: D102
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()

        if index.data(ROLE_IS_GROUP) is True:
            # 分组标题：不参与选中与悬停高亮
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.state &= ~QStyle.StateFlag.State_MouseOver
            opt.backgroundBrush = QBrush(QColor(theme.BG_PANEL))
            opt.palette.setColor(
                QPalette.ColorRole.Text, QColor(theme.ACCENT_DEEP)
            )
            font = QFont(opt.font)
            font.setPointSize(9)
            font.setBold(True)
            opt.font = font
        else:
            selected = bool(opt.state & QStyle.StateFlag.State_Selected)
            hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
            if selected:
                opt.backgroundBrush = QBrush(QColor(theme.BG_RAISED))
                opt.palette.setColor(
                    QPalette.ColorRole.Text, QColor(theme.ACCENT)
                )
                font = QFont(opt.font)
                font.setBold(True)
                opt.font = font
            elif hovered:
                opt.backgroundBrush = QBrush(QColor(theme.BG_RAISED))
                opt.palette.setColor(
                    QPalette.ColorRole.Text, QColor(theme.TEXT)
                )

        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget
        )

    def sizeHint(self, option, index) -> QSize:  # noqa: D102
        height = 26 if index.data(ROLE_IS_GROUP) is True else 32
        return QSize(option.rect.width(), height)


class VideoProcessWindow(QMainWindow):
    """视频处理工具集主窗口，同时充当面板的 host。"""

    def __init__(self) -> None:
        super().__init__()
        self.settings: Settings = load_settings()

        self._nav_items: List[Optional[str]] = []
        self._panels: Dict[str, QWidget] = {}
        self._task_title = ""
        self._task_panel: Optional[QWidget] = None

        self._runner = TaskRunner(self)
        self._runner.logRequested.connect(self.log_message)
        self._runner.progressChanged.connect(self.update_progress)
        self._runner.finished.connect(self._on_task_finished)

        self.setWindowTitle(f"视频处理工具集 v{__version__}")
        self.resize(1240, 840)
        self.setMinimumSize(940, 620)

        self._build_ui()
        self._build_status_bar()
        self._build_shortcuts()

        # 界面就绪后再做环境自检
        QTimer.singleShot(60, self._check_environment)

    # ==================================================================
    # 布局
    # ==================================================================
    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("root")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar())

        body = QSplitter(Qt.Orientation.Horizontal, central)
        body.setHandleWidth(1)
        # 先建内容区：导航初始化时会立刻挂载首个面板，需要 _stack 已就绪
        content_pane = self._build_content_pane()
        nav_pane = self._build_nav_pane()
        body.addWidget(nav_pane)
        body.addWidget(content_pane)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([220, 1020])
        body.setCollapsible(0, False)
        body.setCollapsible(1, False)
        root.addWidget(body, 1)

        self.setCentralWidget(central)

    # ------------------------------------------------------------------
    def _build_title_bar(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("title-bar")
        bar.setFixedHeight(48)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        title = QLabel("视频处理工具集", bar)
        title.setObjectName("app-title")
        layout.addWidget(title)

        version = QLabel(f"v{__version__}", bar)
        version.setObjectName("app-version")
        layout.addWidget(version)

        layout.addStretch(1)

        self._env_ffmpeg = QLabel("检测中…", bar)
        self._env_ffmpeg.setProperty("chip", "env")
        self._env_ffmpeg.setProperty("state", "")
        layout.addWidget(self._env_ffmpeg)

        self._env_amf = QLabel("AMF: 检测中…", bar)
        self._env_amf.setProperty("chip", "env")
        self._env_amf.setProperty("state", "")
        layout.addWidget(self._env_amf)

        return bar

    def _build_nav_pane(self) -> QWidget:
        pane = QFrame(self)
        pane.setObjectName("nav-pane")
        pane.setMinimumWidth(180)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(0)

        nav_title = QLabel("功能", pane)
        nav_title.setObjectName("nav-title")
        layout.addWidget(nav_title)

        self._nav_list = QListWidget(pane)
        self._nav_list.setObjectName("nav-list")
        self._nav_list.setItemDelegate(_NavDelegate(self._nav_list))
        layout.addWidget(self._nav_list, 1)

        # 先连接再填充，保证初始选中项也能触发面板挂载
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        self._build_nav()
        return pane

    def _build_content_pane(self) -> QWidget:
        pane = QWidget(self)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget(pane)
        layout.addWidget(self._stack, 1)
        layout.addWidget(self._build_log_pane())
        return pane

    def _build_log_pane(self) -> QWidget:
        pane = QFrame(self)
        pane.setObjectName("log-pane")
        pane.setMinimumHeight(150)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        label = QLabel("日志输出", pane)
        label.setObjectName("log-header-label")
        header.addWidget(label)
        header.addStretch(1)

        clear = QPushButton("清空", pane)
        clear.setProperty("variant", "ghost")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.action_clear_log)
        header.addWidget(clear)
        layout.addLayout(header)

        self._progress = TaskProgress(pane)
        layout.addWidget(self._progress)

        self._log_view = LogView(parent=pane)
        layout.addWidget(self._log_view, 1)
        return pane

    def _build_status_bar(self) -> None:
        bar = QFrame(self)
        bar.setObjectName("status-bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        self._task_state = QLabel("空闲", bar)
        layout.addWidget(self._task_state)
        layout.addStretch(1)

        hint = QLabel(
            "Ctrl+Q 退出 · Ctrl+C 停止任务 · Ctrl+L 清空日志 · F1 快捷键", bar
        )
        hint.setProperty("role", "param-help")
        layout.addWidget(hint)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.setFixedHeight(28)
        status.addWidget(bar, 1)

    # ==================================================================
    # 导航
    # ==================================================================
    def _build_nav(self) -> None:
        for group_name, tool_ids in NAV_GROUPS:
            group_item = QListWidgetItem(group_name)
            group_item.setData(ROLE_IS_GROUP, True)
            group_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._nav_list.addItem(group_item)
            self._nav_items.append(None)

            for tool_id in tool_ids:
                definition = TOOL_DEFS[tool_id]
                item = QListWidgetItem(f"  {definition.title}")
                item.setData(ROLE_TOOL_ID, tool_id)
                item.setToolTip(definition.title)
                self._nav_list.addItem(item)
                self._nav_items.append(tool_id)

        for index, tool_id in enumerate(self._nav_items):
            if tool_id:
                self._nav_list.setCurrentRow(index)
                break

    def _on_nav_changed(self, row: int) -> None:
        if not (0 <= row < len(self._nav_items)):
            return
        tool_id = self._nav_items[row]
        if tool_id is None:
            return
        self.switch_to(tool_id)

    def switch_to(self, tool_id: str) -> None:
        """切换到指定工具面板（面板按需创建并缓存）。"""
        definition = TOOL_DEFS.get(tool_id)
        if definition is None:
            return

        panel = self._panels.get(tool_id)
        if panel is None:
            panel = create_panel(definition, self, self._stack)
            self._panels[tool_id] = panel
            self._stack.addWidget(panel)

        self._stack.setCurrentWidget(panel)

        if self._runner.running and panel is not self._task_panel:
            self.log_message(
                f"（{self._task_title} 仍在后台运行，结果会回传给发起面板）",
                LogLevel.WARNING,
            )

        if tool_id == "settings" and hasattr(panel, "load_from_settings"):
            panel.load_from_settings()

    # ==================================================================
    # 快捷键
    # ==================================================================
    def _build_shortcuts(self) -> None:
        self._add_shortcut("Ctrl+Q", self.close)
        self._add_shortcut("Ctrl+C", self.action_cancel_task)
        self._add_shortcut("Ctrl+L", self.action_clear_log)
        self._add_shortcut("F1", self.action_toggle_help)

    def _add_shortcut(self, sequence: str, slot) -> QAction:
        action = QAction(self)
        action.setShortcut(QKeySequence(sequence))
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    # ==================================================================
    # 环境自检
    # ==================================================================
    def _check_environment(self) -> None:
        self._env_checker = _EnvChecker(self)
        self._env_checker.finished.connect(self._render_env)
        self._env_checker.start()

    def _render_env(self, ok: bool, version: str, amf: List[str]) -> None:
        # 打包版会自带一份 ffmpeg，标明来源便于判断当前用在哪一份
        source = "内置" if bundled_ffmpeg_dir() else "系统"

        if ok:
            short = version.split(" Copyright")[0] if version else "未知版本"
            self._set_env_chip(
                self._env_ffmpeg, f"● ffmpeg（{source}）: {short}", "ok"
            )
            self.log_message(f"ffmpeg 检测通过（{source}）: {short}", LogLevel.SUCCESS)
        else:
            self._set_env_chip(
                self._env_ffmpeg, "● 未检测到 ffmpeg / ffprobe", "error"
            )
            self.log_message(
                "未检测到 ffmpeg/ffprobe，请先安装并加入 PATH", LogLevel.ERROR
            )
            self.notify(
                "未检测到 ffmpeg/ffprobe，所有功能将不可用", "error", timeout=10
            )

        if amf:
            self._set_env_chip(self._env_amf, f"● AMF: {', '.join(amf)}", "ok")
        else:
            self._set_env_chip(
                self._env_amf, "● AMF: 不可用（AMD 相关模式将失败）", "warn"
            )

    @staticmethod
    def _set_env_chip(label: QLabel, text: str, state: str) -> None:
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)
        label.adjustSize()

    # ==================================================================
    # 日志 / 进度 / 通知
    # ==================================================================
    def log_message(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        self._log_view.write_line(message, level)

    def update_progress(self, info: ProgressInfo) -> None:
        self._progress.update_progress(
            info.clamped(), info.current_file, info.detail
        )

    def notify(self, message: str, severity: str = "information",
               timeout: int = 5) -> None:
        """在状态栏左侧短暂提示。"""
        first_line = (message or "").splitlines()
        first_line = first_line[0] if first_line else ""
        if severity == "error":
            self._task_state.setText(f"✖ {first_line}")
        elif severity == "warning":
            self._task_state.setText(f"! {first_line}")
        else:
            self._task_state.setText(first_line)
        QTimer.singleShot(max(1, timeout) * 1000, self._reset_task_state)

    def _reset_task_state(self) -> None:
        if self._runner.running:
            self._task_state.setText(f"运行中：{self._task_title}")
        else:
            self._task_state.setText("空闲")

    def action_clear_log(self) -> None:
        self._log_view.clear_log()

    def action_toggle_help(self) -> None:
        QMessageBox.information(
            self,
            "快捷键",
            "Ctrl+Q  退出\n"
            "Ctrl+C  停止任务\n"
            "Ctrl+L  清空日志\n"
            "F1      显示本帮助\n\n"
            "导航：↑↓ 切换功能，Enter 选中\n"
            "参数：Tab 在控件间移动，路径可直接拖入",
        )

    # ==================================================================
    # 任务调度（PanelHost 实现）
    # ==================================================================
    def is_task_cancelled(self) -> bool:
        return self._runner.is_cancelled()

    def begin_task(self, title: str) -> bool:
        if self._runner.running:
            self.notify("已有任务正在运行", "warning", timeout=3)
            return False
        self._task_title = title
        self.log_message("")
        self.log_message(f"═══ 开始执行：{title} ═══", LogLevel.SUCCESS)
        self._progress.set_busy()
        self._task_state.setText(f"运行中：{title}")
        return True

    def end_task(self, result: Optional[TaskResult] = None) -> None:
        self._progress.set_idle(True)
        self._task_title = ""
        self._reset_task_state()

        if result is None:
            return
        cancelled = "取消" in (result.message or "")
        if result.success:
            self.log_message(f"✔ {result.message}", LogLevel.SUCCESS)
            self.notify(result.message, "information", timeout=6)
        elif cancelled:
            self.log_message(f"■ {result.message}", LogLevel.WARNING)
            self.notify(result.message, "warning", timeout=5)
        else:
            self.log_message(f"✖ {result.message}", LogLevel.ERROR)
            self.notify(result.message, "error", timeout=10)

    def run_task(self, definition: ToolDefinition, values: dict,
                 panel: object = None) -> bool:
        if not self.begin_task(definition.title):
            return False
        self._task_panel = panel
        if not self._runner.start(definition, values, self.settings):
            self._task_panel = None
            self.end_task(None)
            return False
        return True

    def cancel_task(self) -> None:
        if not self._runner.running:
            self.notify("当前没有正在运行的任务", "information", timeout=2)
            return
        self._runner.cancel()
        self.log_message(
            "正在请求停止…（等待当前 ffmpeg 进程退出）", LogLevel.WARNING
        )

    def action_cancel_task(self) -> None:
        self.cancel_task()

    def _on_task_finished(self, result: TaskResult) -> None:
        self.end_task(result)
        # 回传给发起任务的面板：运行期间用户可能已经切换了导航
        panel = self._task_panel or self._stack.currentWidget()
        self._task_panel = None
        if panel is not None and hasattr(panel, "on_result"):
            panel.on_result(result)

    # ==================================================================
    # 供面板调用的跨面板能力
    # ==================================================================
    def fill_remove_segments(self, csv: str) -> None:
        """把广告区间 CSV 填入「片段删除」面板。"""
        for index, tool_id in enumerate(self._nav_items):
            if tool_id == "remove-segments":
                self._nav_list.setCurrentRow(index)
                break

        panel = self._panels.get("remove-segments")
        if panel is None:
            return
        try:
            if hasattr(panel, "fill_value") and panel.fill_value("segments", csv):
                self.notify(f"已填入删除时间段: {csv}", "information", timeout=5)
            else:
                self.notify("填入失败：未找到时间段字段", "error", timeout=5)
        except Exception as exc:
            self.notify(f"填入失败: {exc}", "error", timeout=5)

    # ==================================================================
    # 关闭保护
    # ==================================================================
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._runner.running:
            answer = QMessageBox.question(
                self,
                "任务正在运行",
                "当前任务尚未结束，关闭窗口会中断它。确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._runner.cancel()
            self._runner.wait(3000)
        event.accept()


def create_window() -> VideoProcessWindow:
    """创建主窗口（不进入事件循环，便于测试驱动）。"""
    return VideoProcessWindow()


def run_app(argv: Optional[List[str]] = None) -> int:
    """启动 Qt 图形界面。"""
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(argv or [])

    # 无控制台模式下 sys.stdout 为 None，先补空实现，避免第三方代码 print() 崩溃
    ensure_utf8_stdio()

    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    theme.apply_theme(app)

    window = create_window()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()

    if owns_app:
        return app.exec()
    return 0
