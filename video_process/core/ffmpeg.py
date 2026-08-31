# -*- coding: utf-8 -*-
"""ffmpeg 执行器：流式日志、真实进度、可取消、Windows 友好。

相比原项目中散落各处的 subprocess.run(cmd, capture_output=True)，本模块提供：
  - 流式 stderr 日志（逐行回调，长任务不再黑屏干等）
  - 基于 -progress pipe:1 的百分比进度
  - 取消支持（Windows 下用 taskkill 杀进程树，ffmpeg 会派生子进程）
  - 统一 utf-8 编码，避免中文路径乱码
  - Windows 下隐藏控制台窗口闪烁
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import IO, List, Optional, Sequence

from .models import (
    CancelledError,
    LogLevel,
    ProgressInfo,
    ToolContext,
    ToolError,
)

IS_WINDOWS = sys.platform == "win32"

# 进度节流间隔（秒）——避免高频刷新拖慢终端渲染
_PROGRESS_THROTTLE = 0.2

# ffmpeg 输出的噪音行（配置回显等），不值得展示给用户
_NOISE_RE = re.compile(
    r"^\s*(configuration:|lib\w+|built with|\s*$)",
    re.IGNORECASE,
)


@dataclass
class RunResult:
    """命令执行结果。"""

    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _startupinfo():
    """Windows 下隐藏子进程控制台窗口。"""
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """终止进程树。Windows 下 plain terminate() 杀不掉 ffmpeg 派生的子进程。"""
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                startupinfo=_startupinfo(),
                timeout=10,
            )
        else:
            proc.terminate()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _find_executable(name: str) -> Optional[str]:
    return shutil.which(name)


def check_ffmpeg() -> tuple:
    """检测 ffmpeg / ffprobe 是否可用，返回 (ok, ffmpeg_path, ffprobe_path, version_line)。"""
    ffmpeg = _find_executable("ffmpeg")
    ffprobe = _find_executable("ffprobe")
    if not ffmpeg or not ffprobe:
        return False, ffmpeg, ffprobe, ""
    try:
        proc = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
            timeout=15,
        )
        first_line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        return True, ffmpeg, ffprobe, first_line.strip()
    except Exception:
        return False, ffmpeg, ffprobe, ""


class FFmpegRunner:
    """执行 ffmpeg/ffprobe 并流式上报日志与进度。"""

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self._last_progress_ts = 0.0
        self._stderr_chunks: List[str] = []

    # ------------------------------------------------------------------
    # 对外主入口
    # ------------------------------------------------------------------
    def run(
        self,
        args: Sequence[str],
        duration: Optional[float] = None,
        description: str = "",
        capture_stderr: bool = True,
        check: bool = True,
    ) -> RunResult:
        """执行一条 ffmpeg/ffprobe 命令。

        参数:
            args:           完整命令行（含程序名）
            duration:       输入媒体总时长（秒），用于把 out_time 换算成百分比
            description:    展示给用户的步骤描述
            capture_stderr: 是否把 stderr 逐行回调到 UI
            check:          返回码非 0 时是否抛出 ToolError
        """
        self.ctx.check_cancel()
        if description:
            self.ctx.log(description)

        cmd = list(args)
        self._stderr_chunks = []

        popen_args = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
        )

        try:
            proc = subprocess.Popen(cmd, **popen_args)
        except FileNotFoundError as exc:
            raise ToolError(f"未找到可执行文件: {cmd[0]}（请确保已安装并加入 PATH）") from exc

        # 读取 stderr 与 stdout 的线程
        stderr_thread = threading.Thread(
            target=self._pump_stream,
            args=(proc.stderr, capture_stderr),
            daemon=True,
        )
        stdout_thread = threading.Thread(
            target=self._pump_progress,
            args=(proc.stdout, duration),
            daemon=True,
        )
        stderr_thread.start()
        stdout_thread.start()

        # 轮询取消
        try:
            while proc.poll() is None:
                if self.ctx.is_cancelled():
                    _kill_process_tree(proc)
                    self.ctx.warn("已发送终止信号，正在取消...")
                    break
                time.sleep(0.1)
            proc.wait()
        finally:
            stderr_thread.join(timeout=5)
            stdout_thread.join(timeout=5)

        if self.ctx.is_cancelled():
            raise CancelledError("任务已被用户取消")

        result = RunResult(
            returncode=proc.returncode or 0,
            stderr="".join(self._stderr_chunks),
        )

        if check and result.returncode != 0:
            raise ToolError(
                f"命令执行失败 (返回码 {result.returncode}): {' '.join(cmd[:6])}...\n"
                + self._tail(result.stderr)
            )
        return result

    # ------------------------------------------------------------------
    # 内部：流泵
    # ------------------------------------------------------------------
    def _pump_stream(self, stream: Optional[IO[str]], report: bool) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                line = line.rstrip("\n").rstrip("\r")
                if not line:
                    continue
                self._stderr_chunks.append(line + "\n")
                if not report:
                    continue
                if _NOISE_RE.match(line):
                    continue
                # 分级着色：ffmpeg 常见关键字
                lowered = line.lower()
                if "error" in lowered or "invalid" in lowered or "failed" in lowered:
                    self.ctx.on_log(line, LogLevel.ERROR)
                elif "warning" in lowered or "deprecated" in lowered:
                    self.ctx.on_log(line, LogLevel.WARNING)
                else:
                    self.ctx.on_log(line, LogLevel.INFO)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _pump_progress(self, stream: Optional[IO[str]], duration: Optional[float]) -> None:
        """解析 ffmpeg -progress 输出的 out_time_ms / out_time 字段。"""
        if stream is None:
            return
        total_us = duration * 1_000_000 if duration and duration > 0 else None
        try:
            for line in iter(stream.readline, ""):
                line = line.strip()
                if not line:
                    continue
                if total_us is None:
                    continue
                # -progress 输出为 key=value 形式
                if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                    try:
                        raw = line.split("=", 1)[1].strip()
                        if raw in ("N/A", ""):
                            continue
                        us = int(raw)
                        if line.startswith("out_time_ms="):
                            us *= 1000
                        percent = (us / total_us) * 100.0
                        self._emit_progress(percent)
                    except (ValueError, ZeroDivisionError):
                        continue
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _emit_progress(self, percent: float) -> None:
        """节流上报，避免每帧都刷新 UI。"""
        now = time.monotonic()
        if now - self._last_progress_ts < _PROGRESS_THROTTLE:
            return
        self._last_progress_ts = now
        self.ctx.on_progress(ProgressInfo(percent=max(0.0, min(100.0, percent))))

    @staticmethod
    def _tail(text: str, limit: int = 25) -> str:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) <= limit:
            return "\n".join(lines)
        return "\n".join(lines[-limit:])


def build_progress_args() -> List[str]:
    """返回启用机器可读进度输出的参数（需插在输出文件之前）。"""
    return ["-progress", "pipe:1", "-nostats"]


def run_quiet(args: Sequence[str]) -> RunResult:
    """无 UI 上下文的静默执行（ffprobe 探测等短命令用）。"""
    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
            timeout=60,
        )
        return RunResult(proc.returncode, proc.stdout or "", proc.stderr or "")
    except FileNotFoundError as exc:
        raise ToolError(f"未找到可执行文件: {args[0]}") from exc
    except subprocess.TimeoutExpired:
        return RunResult(-1, "", "命令执行超时")
