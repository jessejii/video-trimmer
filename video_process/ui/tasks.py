# -*- coding: utf-8 -*-
"""后台任务执行器。

业务函数运行在 QThread 中，其内部通过 ToolContext 回调上报日志与进度。
这些回调发生在工作线程里，绝不能直接操作 QWidget，因此一律转成信号，
由主线程（自动 QueuedConnection）的槽函数去更新界面。
"""

from __future__ import annotations

import threading
import traceback
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ..core.models import (
    CancelledError,
    LogLevel,
    ProgressInfo,
    Settings,
    TaskResult,
    ToolContext,
    ToolError,
)
from ..core.probe import clear_cache
from ..param_spec import ToolDefinition


class ToolTask(QObject):
    """在后台线程执行一个工具的业务函数。

    用法：由 :class:`TaskRunner` 创建并移入 QThread，通过信号回传结果。
    """

    #: (message, LogLevel) —— 工作线程发射，主线程接收
    logRequested = pyqtSignal(str, object)
    #: ProgressInfo
    progressChanged = pyqtSignal(object)
    #: TaskResult
    finished = pyqtSignal(object)

    def __init__(self, definition: ToolDefinition, values: Dict[str, Any],
                 settings: Settings, cancel_event: threading.Event) -> None:
        super().__init__()
        self._definition = definition
        self._values = values
        self._settings = settings
        self._cancel_event = cancel_event

    # ------------------------------------------------------------------
    def run(self) -> None:
        """在工作线程内执行（由 TaskRunner 触发）。"""
        ctx = ToolContext(
            on_log=lambda msg, lvl: self.logRequested.emit(str(msg), lvl),
            on_progress=lambda info: self.progressChanged.emit(info),
            is_cancelled=lambda: self._cancel_event.is_set(),
            settings=self._settings,
        )
        try:
            result = self._invoke(ctx)
        except CancelledError as exc:
            result = TaskResult(success=False, message=str(exc))
        except ToolError as exc:
            result = TaskResult(success=False, message=str(exc))
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默崩溃
            self.logRequested.emit(traceback.format_exc(), LogLevel.ERROR)
            result = TaskResult(success=False, message=f"执行异常: {exc}")
        finally:
            # 探测缓存（时长/码率/关键帧）无上限，且源文件可能已被本任务改掉，
            # 任务结束即清空，避免跨任务读到脏数据
            clear_cache()
        self.finished.emit(result)

    def _invoke(self, ctx: ToolContext) -> TaskResult:
        runner = self._definition.resolve_runner()
        if runner is None:
            return TaskResult(success=False, message="该工具尚未接入业务逻辑")
        return runner(ctx=ctx, **self._values)


class TaskRunner(QObject):
    """管理单个后台任务的生命周期（exclusive：同时只允许一个任务）。"""

    #: (message, LogLevel)
    logRequested = pyqtSignal(str, object)
    #: ProgressInfo
    progressChanged = pyqtSignal(object)
    #: TaskResult
    finished = pyqtSignal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._task: Optional[ToolTask] = None
        self._cancel_event = threading.Event()
        self.running = False

    # ------------------------------------------------------------------
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """请求取消（业务函数通过 is_cancelled 回调感知）。"""
        self._cancel_event.set()

    def start(self, definition: ToolDefinition, values: Dict[str, Any],
              settings: Settings) -> bool:
        """启动后台任务，已在运行则返回 False。"""
        if self.running:
            return False

        self._cancel_event = threading.Event()
        self.running = True

        self._thread = QThread(self)
        self._task = ToolTask(definition, values, settings, self._cancel_event)
        self._task.moveToThread(self._thread)

        self._task.logRequested.connect(self.logRequested)
        self._task.progressChanged.connect(self.progressChanged)
        self._task.finished.connect(self._on_finished)

        self._thread.started.connect(self._task.run)
        self._task.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        return True

    # ------------------------------------------------------------------
    def _on_finished(self, result: TaskResult) -> None:
        self.running = False
        self._cancel_event.clear()
        self.finished.emit(result)

    def _cleanup(self) -> None:
        if self._task is not None:
            self._task.deleteLater()
            self._task = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def wait(self, msecs: int = 3000) -> None:
        """等待线程退出（关闭窗口前调用，避免留下 ffmpeg 孤儿进程）。"""
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(msecs)
