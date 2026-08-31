# -*- coding: utf-8 -*-
"""路径处理：容错解析、视频文件扫描、输出命名、concat 列表生成。

复刻原 bat 的容错行为：去两端引号、相对路径回退到当前工作目录。
"""

from __future__ import annotations

import os
import re
from typing import Callable, Iterable, List, Optional

# 视频扩展名（与原项目保持一致）
VIDEO_EXTENSIONS = (
    ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv",
    ".m4v", ".webm", ".ts", ".mpg", ".mpeg", ".vob",
    ".m2ts", ".mts", ".3gp", ".rmvb",
)

# 字幕扩展名（rename_srt_to_txt.bat 支持这四种）
SUBTITLE_EXTENSIONS = (".srt", ".ass", ".vtt", ".lrc")

# Windows 文件名非法字符
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')


def clean_path(raw: str) -> str:
    """清洗用户输入的路径：去两端引号与空白。

    对应原 bat 的: set input_path=!input_path:"=!
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    # 反复剥离成对的引号（粘贴路径时常见 ""C:\\x"" 这种）
    while len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1].strip()
    return s


def resolve_path(raw: str, must_exist: bool = False) -> str:
    """解析并校验路径。

    先按原样判断；不存在时回退尝试「当前工作目录 + 输入」（原 bat 的相对路径回退）。

    返回:
        解析后的绝对路径。若 must_exist=False 且路径不存在，仍返回清洗后的原值。
    """
    s = clean_path(raw)
    if not s:
        return ""
    if os.path.exists(s):
        return os.path.abspath(s)
    # 相对路径回退
    joined = os.path.join(os.getcwd(), s)
    if os.path.exists(joined):
        return os.path.abspath(joined)
    return s if not must_exist else ""


def validate_path(raw: str, kind: str = "any") -> tuple:
    """校验路径。

    返回: (ok, resolved_path, error_message)
        kind: "any" | "file" | "dir"
    """
    s = clean_path(raw)
    if not s:
        return False, "", "路径不能为空"

    resolved = resolve_path(s)
    if not os.path.exists(resolved):
        return False, resolved, f"路径不存在: {s}"
    if kind == "file" and not os.path.isfile(resolved):
        return False, resolved, f"不是有效的文件: {s}"
    if kind == "dir" and not os.path.isdir(resolved):
        return False, resolved, f"不是有效的文件夹: {s}"
    return True, resolved, ""


def is_video_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def _scan(
    directory: str,
    recursive: bool,
    accept: Callable[[str], bool],
) -> List[str]:
    """按谓词扫描目录，结果按名称排序（视频与字幕扫描共用）。"""
    files: List[str] = []
    if recursive:
        for root, _dirs, names in os.walk(directory):
            for name in names:
                if accept(name):
                    files.append(os.path.join(root, name))
    else:
        for name in os.listdir(directory):
            full = os.path.join(directory, name)
            if os.path.isfile(full) and accept(name):
                files.append(full)
    files.sort()
    return files


def scan_videos(
    directory: str,
    recursive: bool = False,
    exclude_contains: str = "",
) -> List[str]:
    """扫描目录中的视频文件，按名称排序。

    参数:
        directory:         目录路径
        recursive:         是否递归子目录
        exclude_contains:  文件名包含此子串则跳过（compress 用 "_compressed"）
    """
    return _scan(
        directory,
        recursive,
        lambda name: not (exclude_contains and exclude_contains in name)
        and is_video_file(name),
    )


def scan_subtitles(directory: str, recursive: bool = True) -> List[str]:
    """扫描目录中的字幕文件。"""
    return _scan(
        directory,
        recursive,
        lambda name: os.path.splitext(name)[1].lower() in SUBTITLE_EXTENSIONS,
    )


def safe_filename(text: str, fallback: str = "und") -> str:
    """清理字符串中的非法文件名字符。"""
    cleaned = _ILLEGAL_CHARS.sub("", text).strip()
    return cleaned or fallback


def ensure_dir(path: str) -> str:
    """确保目录存在。"""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def sibling_path(input_file: str, suffix: str, ext: Optional[str] = None) -> str:
    """在输入文件同目录生成输出路径：{stem}{suffix}{ext or 原扩展名}。"""
    directory = os.path.dirname(input_file) or "."
    stem, old_ext = os.path.splitext(os.path.basename(input_file))
    return os.path.join(directory, f"{stem}{suffix}{ext if ext is not None else old_ext}")


def find_video_root(path: str) -> Optional[str]:
    """从给定路径向上查找名为 video 的目录（extract_audio 的输出根策略）。"""
    current = path
    if os.path.isfile(current):
        current = os.path.dirname(current)
    current = os.path.abspath(current)
    while True:
        if os.path.basename(current).lower() == "video":
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# ---------------------------------------------------------------------------
# concat 列表
# ---------------------------------------------------------------------------

def escape_concat_path(path: str) -> str:
    """转义 concat demuxer 列表中的路径。

    规则：反斜杠转正斜杠（Windows），单引号转义为 '\\''。
    """
    return os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")


def write_concat_list(files: Iterable[str], list_path: str) -> str:
    """写入 ffmpeg concat demuxer 列表文件，返回路径。"""
    ensure_dir(os.path.dirname(list_path) or ".")
    with open(list_path, "w", encoding="utf-8") as fh:
        for f in files:
            fh.write(f"file '{escape_concat_path(f)}'\n")
    return list_path


def temp_dir_for(base_dir: str, name: str) -> str:
    """创建并返回临时目录路径。"""
    path = os.path.join(base_dir, name)
    ensure_dir(path)
    return path


def cleanup_dir(path: str) -> None:
    """删除目录（仅当为空时），失败静默。"""
    try:
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
    except OSError:
        pass


def remove_files(files: Iterable[str]) -> None:
    """批量删除文件，失败静默。"""
    for f in files:
        try:
            if f and os.path.exists(f):
                os.remove(f)
        except OSError:
            pass


def human_size(num_bytes: float) -> str:
    """字节 -> 人类可读大小。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.2f} TB"
