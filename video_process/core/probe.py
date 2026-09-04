# -*- coding: utf-8 -*-
"""ffprobe 探测封装，带内存缓存。

合并原项目中散落各处的 get_video_duration / get_video_codec /
get_video_bitrate / get_audio_streams / get_keyframes / check_amf_support。

缓存必要性：remove_segments 会对同一文件逐段重复读时长；
AMF 编码器列表每次调用都要跑一遍 `ffmpeg -encoders`，开销明显。
"""

from __future__ import annotations

import json
import os
from typing import Callable, Dict, List, Optional, Tuple

from .ffmpeg import run_quiet

# 缓存：(path, kind) -> value
_CACHE: Dict[Tuple[str, str], object] = {}

# AMF 编码器列表：进程级只探测一次
_AMF_CACHE: Optional[List[str]] = None


def clear_cache() -> None:
    """清空探测缓存。"""
    global _AMF_CACHE
    _CACHE.clear()
    _AMF_CACHE = None


# 哨兵：用于区分「未缓存」与「已缓存但值为 None」。
# 直接用 .get(key) 返回 None 判断未命中的话，探测失败的结果永远缓存不住，
# 导致每次调用都重新 fork 一次 ffprobe —— 而失败恰恰是最昂贵的路径。
_MISS = object()


def _cached(path: str, kind: str):
    return _CACHE.get((os.path.abspath(path), kind), _MISS)


def _store(path: str, kind: str, value) -> None:
    _CACHE[(os.path.abspath(path), kind)] = value


def _probe(args: List[str]) -> Optional[str]:
    """执行 ffprobe 并返回 stdout，失败返回 None。"""
    result = run_quiet(["ffprobe", *args])
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    return out or None


def _cached_probe(path: str, kind: str, args: List[str],
                  parse: Callable[[Optional[str]], object]):
    """统一的「查缓存 → 探测 → 解析 → 写缓存」流程。

    parse 必须能接收 None（探测失败），这样失败结果同样会被缓存，
    避免最昂贵的路径被反复执行。
    """
    cached = _cached(path, kind)
    if cached is not _MISS:
        return cached
    value = parse(_probe(args))
    _store(path, kind, value)
    return value


def _parse_duration(out: Optional[str]) -> Optional[float]:
    if not out:
        return None
    try:
        return float(out.splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


def _parse_codec(out: Optional[str]) -> Optional[str]:
    return (out or "").strip().lower() or None


def _parse_bitrate(out: Optional[str]) -> Optional[int]:
    text = (out or "").strip()
    if not text or text == "N/A":
        return None
    try:
        return int(text) // 1000  # bps -> kbps
    except ValueError:
        return None


def _parse_audio_streams(out: Optional[str]) -> List[dict]:
    streams: List[dict] = []
    if not out:
        return streams
    try:
        data = json.loads(out)
        for s in data.get("streams", []):
            tags = s.get("tags", {}) or {}
            streams.append({
                "index": s.get("index"),
                "codec_name": (s.get("codec_name") or "").lower(),
                "channels": s.get("channels"),
                "language": tags.get("language", ""),
                "title": tags.get("title", ""),
            })
    except (ValueError, KeyError, TypeError):
        streams = []
    return streams


def _parse_keyframes(out: Optional[str]) -> List[float]:
    frames: List[float] = []
    if not out:
        return frames
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        first = line.split(",")[0].strip()
        try:
            t = float(first)
        except ValueError:
            continue
        if t >= 0:
            frames.append(t)
    return sorted(set(frames))


#: 各探测项对应的 ffprobe 参数与解析函数
_PROBES = {
    "duration": (
        ["-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1"],
        _parse_duration,
    ),
    "codec": (
        ["-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name",
         "-of", "default=noprint_wrappers=1:nokey=1"],
        _parse_codec,
    ),
    "bitrate": (
        ["-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=bit_rate",
         "-of", "default=noprint_wrappers=1:nokey=1"],
        _parse_bitrate,
    ),
    "audio": (
        ["-v", "error", "-select_streams", "a",
         "-show_entries",
         "stream=index,codec_name,channels:stream_tags=language,title",
         "-of", "json"],
        _parse_audio_streams,
    ),
    "keyframes": (
        ["-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_frames",
         "-show_entries", "frame=best_effort_timestamp_time,pkt_pts_time",
         "-of", "csv=p=0"],
        _parse_keyframes,
    ),
}


def get_duration(path: str) -> Optional[float]:
    """视频总时长（秒）。"""
    args, parse = _PROBES["duration"]
    return _cached_probe(path, "duration", [*args, path], parse)  # type: ignore[return-value]


def get_codec(path: str) -> Optional[str]:
    """视频编码名称（小写），无视频流返回 None。"""
    args, parse = _PROBES["codec"]
    return _cached_probe(path, "codec", [*args, path], parse)  # type: ignore[return-value]


def get_bitrate(path: str) -> Optional[int]:
    """视频码率（kbps），无法检测返回 None。"""
    args, parse = _PROBES["bitrate"]
    return _cached_probe(path, "bitrate", [*args, path], parse)  # type: ignore[return-value]


def get_audio_streams(path: str) -> List[dict]:
    """获取所有音轨信息。

    返回元素: {"index", "codec_name", "channels", "language", "title"}
    """
    args, parse = _PROBES["audio"]
    return _cached_probe(path, "audio", [*args, path], parse)  # type: ignore[return-value]


def get_keyframes(path: str) -> List[float]:
    """获取视频关键帧时间点（秒），用于 split_video 的关键帧对齐。"""
    args, parse = _PROBES["keyframes"]
    return _cached_probe(path, "keyframes", [*args, path], parse)  # type: ignore[return-value]


def check_amf_support(force: bool = False) -> List[str]:
    """返回可用的 AMF 编码器列表（h264_amf / hevc_amf / av1_amf）。"""
    global _AMF_CACHE
    if _AMF_CACHE is not None and not force:
        return _AMF_CACHE

    supported: List[str] = []
    try:
        result = run_quiet(["ffmpeg", "-hide_banner", "-encoders"])
        output = result.stdout or ""
        for enc in ("h264_amf", "hevc_amf", "av1_amf"):
            if enc in output:
                supported.append(enc)
    except Exception:
        supported = []

    _AMF_CACHE = supported
    return supported
