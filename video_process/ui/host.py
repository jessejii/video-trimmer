# -*- coding: utf-8 -*-
"""面板与主窗口之间的窄接口。

面板只依赖这个协议，不直接依赖 QMainWindow，
便于在 offscreen 冒烟测试中注入假 host。
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..core.models import LogLevel, ProgressInfo, Settings, TaskResult
from ..param_spec import ToolDefinition


@runtime_checkable
class PanelHost(Protocol):
    """主窗口向面板暴露的能力。"""

    #: 全局设置（各工具的默认值来源）
    settings: Settings

    def log_message(self, message: str,
                    level: LogLevel = LogLevel.INFO) -> None: ...

    def update_progress(self, info: ProgressInfo) -> None: ...

    def notify(self, message: str, severity: str = "information",
               timeout: int = 5) -> None: ...

    def is_task_cancelled(self) -> bool: ...

    def begin_task(self, title: str) -> bool:
        """进入运行态；已有任务在跑时返回 False。"""
        ...

    def end_task(self, result: Optional[TaskResult] = None) -> None: ...

    def run_task(self, definition: ToolDefinition, values: dict,
                 panel: object = None) -> bool:
        """在后台线程执行工具；启动失败返回 False。

        panel 为发起任务的面板，用于在运行期间切换过导航后
        仍能把结果正确回传给发起面板。
        """
        ...

    def cancel_task(self) -> None: ...

    def fill_remove_segments(self, csv: str) -> None: ...

    def reload_panels(self, keep: object = None) -> None:
        """全局设置变更后重建面板（参数默认值在面板创建时快照）。

        keep: 不重建的面板，通常是发起保存的设置面板自身 ——
        否则刚点完「开始执行」的控件会被销毁。
        """
        ...
