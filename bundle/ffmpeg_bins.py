# -*- coding: utf-8 -*-
"""定位并把 ffmpeg / ffprobe 收进打包产物。

Windows 的 ffmpeg 发行版有两种形态：

- **静态链接**（gyan.dev / BtbN 的 full build）：bin 目录里只有 exe，
  直接打包即可，开箱即用
- **动态链接**（部分 Linux 发行版、conda 等）：exe 旁边摆着
  ``avcodec-*.dll`` 等一批运行库，漏了就起不来

因此这里按「exe + 同目录所有 dll」收集。同目录的 dll 一定是 ffmpeg
自带的——Windows 加载 DLL 时优先搜索 exe 所在目录，发行方必然把依赖
摆在那里；反过来，系统目录里的 dll 不需要打包，也就顺带避开了
PyInstaller 依赖分析常把 ``api-ms-win-crt-*.dll`` 误收进来的问题。

``ffplay.exe`` 用不到，不收。
"""

from __future__ import annotations

import os
import shutil
from typing import Dict, List, Optional, Tuple

#: 需要打包的可执行文件（不含扩展名）
EXECUTABLES = ("ffmpeg", "ffprobe")

#: 与 exe 同目录、需要一并打包的动态库扩展名
LIB_SUFFIXES = (".dll",)


def _exe_names(name: str) -> Tuple[str, ...]:
    """按平台给出候选文件名：Windows 带 .exe，其它平台用原名。"""
    if os.name == "nt":
        return (f"{name}.exe", name)
    return (name,)


def _locate(name: str, directory: Optional[str]) -> str:
    """在指定目录（或系统 PATH）中定位可执行文件。"""
    if directory:
        for candidate in _exe_names(name):
            path = os.path.join(directory, candidate)
            if os.path.isfile(path):
                return path
        return ""
    # 不带 path 时 shutil.which 走系统 PATH
    return shutil.which(name) or ""


def find_ffmpeg(directory: Optional[str] = None) -> Dict[str, object]:
    """定位 ffmpeg / ffprobe 及其随附动态库。

    参数:
        directory: 限定在该目录内查找；None 表示从系统 PATH 查找

    返回:
        ``{"ok", "dir", "files", "size", "missing"}``
        files 为绝对路径列表，size 为总字节数，missing 为没找到的可执行文件名
    """
    found: List[str] = []
    missing: List[str] = []
    resolved_dir = ""

    for name in EXECUTABLES:
        path = _locate(name, directory)
        if path:
            path = os.path.abspath(path)
            found.append(path)
            resolved_dir = resolved_dir or os.path.dirname(path)
        else:
            missing.append(name)

    if not found:
        return {
            "ok": False, "dir": "", "files": [], "size": 0, "missing": missing,
        }

    # 同目录的动态库（静态链接的构建里通常一个都没有）
    if resolved_dir and os.path.isdir(resolved_dir):
        for entry in sorted(os.listdir(resolved_dir)):
            if entry.lower().endswith(LIB_SUFFIXES):
                found.append(os.path.join(resolved_dir, entry))

    total = 0
    for path in found:
        try:
            total += os.path.getsize(path)
        except OSError:
            pass

    return {
        "ok": True,
        "dir": resolved_dir,
        "files": found,
        "size": total,
        "missing": missing,
    }


def collect(directory: Optional[str] = None) -> List[Tuple[str, str]]:
    """生成可直接交给 Analysis(``binaries=...``) 的条目列表。

    注意这里的元组是「hook 风格」的 ``(源路径, 目标目录)``，与
    ``Analysis.binaries`` 属性那种 ``(目标文件, 源文件, 类型)`` 的
    TOC 三元组顺序相反，别混用。

    目标目录用 ``os.curdir``（即 ``.``）表示产物根目录：单目录模式落在
    ``_internal/``，单文件模式落在 ``sys._MEIPASS``，正好对上
    :func:`video_process._frozen.bundle_dir` 的查找位置。
    """
    info = find_ffmpeg(directory)
    if not info["ok"]:
        return []
    return [(path, os.curdir) for path in info["files"]]  # type: ignore[union-attr]


def human_size(num_bytes: float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} GB"
