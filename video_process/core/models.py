# -*- coding: utf-8 -*-
"""数据契约：界面与业务层之间的调用协议。

设计要点：tools 层不出现任何 print() / input()，全部通过 ToolContext 中的
回调上报日志与进度，因此可以在后台线程安全运行并向界面实时回传状态。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


class LogLevel(enum.Enum):
    """日志级别，UI 据此着色。"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


@dataclass
class ProgressInfo:
    """进度上报。

    percent 为 0.0-100.0；无法确定时为 None，UI 应转为 indeterminate 状态。
    """

    percent: Optional[float] = None
    current_file: str = ""
    detail: str = ""

    def clamped(self) -> Optional[float]:
        if self.percent is None:
            return None
        return max(0.0, min(100.0, self.percent))


@dataclass
class TaskResult:
    """任务最终结果。UI 据此弹通知并回传给面板。"""

    success: bool
    message: str = ""
    outputs: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success


@dataclass
class Settings:
    """全局设置，持久化到 ~/.video-process/config.json。"""

    # AMD AMF 编码参数
    amf_quality: str = "balanced"        # balanced / speed / quality
    amf_usage: str = "transcoding"       # transcoding / lowlatency / ultralowlatency
    amf_bitrate: Optional[int] = None    # kbps，None = 自动匹配原视频码率 * 0.9
    amf_cqp: bool = False                # True 使用恒定质量模式
    amf_qp: int = 22                     # CQP 量化参数 0-51

    # 输出策略
    output_dir: str = ""                 # 留空 = 输出到输入同目录

    # 行为开关
    auto_sync_srt: bool = True           # remove_segments 后自动同步同名 SRT
    find_video_root: bool = True         # extract_audio 向上查找 video 目录
    overwrite: bool = False              # 输出已存在时是否覆盖
    recursive_scan: bool = True          # 文件夹模式是否递归子目录

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class ToolContext:
    """传给每个 tools 层函数的上下文，隔离 UI 依赖。"""

    on_log: Callable[[str, LogLevel], None] = lambda msg, lvl: None
    on_progress: Callable[[ProgressInfo], None] = lambda p: None
    is_cancelled: Callable[[], bool] = lambda: False
    settings: Settings = field(default_factory=Settings)

    # ---- 便捷方法 -------------------------------------------------------
    def log(self, msg: str) -> None:
        self.on_log(msg, LogLevel.INFO)

    def success(self, msg: str) -> None:
        self.on_log(msg, LogLevel.SUCCESS)

    def warn(self, msg: str) -> None:
        self.on_log(msg, LogLevel.WARNING)

    def error(self, msg: str) -> None:
        self.on_log(msg, LogLevel.ERROR)

    def progress(self, percent: Optional[float] = None, file: str = "", detail: str = "") -> None:
        self.on_progress(ProgressInfo(percent=percent, current_file=file, detail=detail))

    def check_cancel(self) -> None:
        """若用户请求取消则抛出异常，中断当前任务。"""
        if self.is_cancelled():
            raise CancelledError("任务已被用户取消")


class CancelledError(Exception):
    """任务被用户取消。"""


class ToolError(Exception):
    """工具执行失败（参数错误、文件不存在、ffmpeg 失败等）。"""
