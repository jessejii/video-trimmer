# -*- coding: utf-8 -*-
"""打包（frozen）运行环境适配。

PyInstaller 会把随包数据文件解压/放置在 ``sys._MEIPASS`` 指向的目录
（单文件模式为临时目录，单目录模式为 exe 旁的 ``_internal``）。
源码运行时同一批数据文件位于项目根目录，这里统一按相对路径解析，
让两种模式的行为完全一致。

同时负责把随程序分发的 ffmpeg / ffprobe 接入 PATH：
业务代码里到处都是 ``ffmpeg`` / ``ffprobe`` 这样的裸可执行文件名，
与其逐个改成绝对路径，不如在启动时把目录挂到 PATH 前面，
``shutil.which`` 与 ``subprocess`` 都能自动命中。

只依赖标准库，界面可以安全引用。
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import List, Optional

#: 是否运行在打包后的可执行文件中
IS_FROZEN = bool(getattr(sys, "frozen", False))

#: 需要随程序分发的可执行文件名（不含扩展名，兼容 Windows 的 .exe）
FFMPEG_NAMES = ("ffmpeg", "ffprobe")

#: 用户自定义 ffmpeg 目录的环境变量，优先级高于内置副本
FFMPEG_DIR_ENV = "VIDEO_PROCESS_FFMPEG_DIR"

#: 上一次 prepare_ffmpeg_path 实际加入 PATH 的目录（供界面展示来源）
_FFMPEG_ADDED: List[str] = []
_path_prepared = False


def bundle_dir() -> Optional[str]:
    """打包后的资源根目录；未打包时返回 None。"""
    return getattr(sys, "_MEIPASS", None)


def app_dir() -> str:
    """可执行文件所在目录（未打包时为项目根目录）。"""
    if IS_FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative: str) -> str:
    """按相对路径定位随包数据文件，找不到时返回空串（调用方需自行降级）。

    参数:
        relative: 相对项目根的路径，如 ``assets/app.ico``
    """
    rel = relative.replace("/", os.sep)
    candidates = []
    bundle = bundle_dir()
    if bundle:
        candidates.append(os.path.join(bundle, rel))
    candidates.append(os.path.join(app_dir(), rel))
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


# ---------------------------------------------------------------------------
# ffmpeg 查找
# ---------------------------------------------------------------------------
def _has_ffmpeg(directory: str) -> bool:
    """目录里是否有可直接调用的 ffmpeg。

    用 which 而不是拼 .exe 后缀，这样 Linux / macOS 打包时同样可用。
    """
    return any(
        shutil.which(name, path=directory) for name in FFMPEG_NAMES
    )


def _existing(directory: Optional[str]) -> Optional[str]:
    if directory and os.path.isdir(directory):
        return os.path.abspath(directory)
    return None


def ffmpeg_dirs() -> List[str]:
    """随程序分发的 ffmpeg 候选目录，优先级从高到低。

    1. ``VIDEO_PROCESS_FFMPEG_DIR`` 环境变量指向的目录（用户覆盖）
    2. 打包进程序的内置目录（单目录模式的 ``_internal`` / 单文件模式的临时目录）
    3. exe 同目录（用户自己丢一个 ffmpeg.exe 进去也能用）
    """
    candidates = [
        os.environ.get(FFMPEG_DIR_ENV, ""),
        bundle_dir(),
        # 单目录模式下 exe 与 _internal 平级，用户放在 exe 旁边更直观
        app_dir() if IS_FROZEN else None,
    ]

    found: List[str] = []
    for candidate in candidates:
        directory = _existing(candidate)
        if directory and directory not in found and _has_ffmpeg(directory):
            found.append(directory)
    return found


def prepare_ffmpeg_path() -> List[str]:
    """把随程序分发的 ffmpeg 目录挂到 PATH 最前面。

    幂等：只有首次调用会改动 PATH，之后返回同一份结果。
    业务代码无需关心 ffmpeg 从哪来，照旧用文件名调用即可。

    返回:
        实际加入 PATH 的目录列表（已按优先级排序）。
    """
    global _path_prepared
    if _path_prepared:
        return list(_FFMPEG_ADDED)
    _path_prepared = True

    found = ffmpeg_dirs()
    if not found:
        _FFMPEG_ADDED = []
        return []

    # 倒序插入，保证 found[0] 最终排在最前（PATH 越靠前优先级越高）
    for directory in reversed(found):
        current = os.environ.get("PATH", "")
        parts = [p for p in current.split(os.pathsep) if p]
        if directory in parts:
            parts.remove(directory)
        parts.insert(0, directory)
        os.environ["PATH"] = os.pathsep.join(parts)

    _FFMPEG_ADDED = found
    return found


def bundled_ffmpeg_dir() -> Optional[str]:
    """内置（随程序打包）的 ffmpeg 目录；没有则返回 None。

    与 ``ffmpeg_dirs()`` 的区别：这里只看打包目录，不含环境变量与 exe 同目录，
    界面用它判断该显示「内置」还是「系统」。
    """
    directory = _existing(bundle_dir())
    if directory and _has_ffmpeg(directory):
        return directory
    return None
