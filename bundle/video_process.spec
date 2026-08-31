# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

产出单个可执行文件：

    视频处理工具集.exe   图形界面版（--windowed，不弹控制台黑窗）

ffmpeg / ffprobe 默认一并打包（能从 PATH 找到的话），
产物因此可以脱离 Python 与 ffmpeg 环境独立运行，
代价是体积增加约 300 MB 起。

通常不需要手动执行本文件，交给 build.py / build.bat 即可：

    pyinstaller bundle/video_process.spec
    VP_BUILD_MODE=onefile pyinstaller bundle/video_process.spec

可用环境变量：
    VP_BUILD_MODE   onedir（默认）| onefile
    VP_UPX          1 启用 UPX 压缩（需本机已装 upx）
    VP_GUI_NAME     exe 名
    VP_DIST_NAME    dist 下的输出目录名
    VP_WITH_FFMPEG  auto（默认）| 1 | 0 —— 是否附带 ffmpeg
    VP_FFMPEG_DIR   指定 ffmpeg 所在目录（默认从 PATH 查找）
"""

import inspect
import os
import sys

# Analysis / PYZ / EXE / COLLECT / SPECPATH 由 PyInstaller 在执行
# spec 前注入到全局命名空间，不要 import——不同版本所在的模块不一样。

# ---------------------------------------------------------------------------
# 路径与基本配置
# ---------------------------------------------------------------------------
# SPECPATH 由 PyInstaller 注入；直接 exec 本文件时退回脚本自身所在目录
SPECDIR = os.path.abspath(
    globals().get("SPECPATH") or os.path.dirname(os.path.abspath(__file__))
)
ROOT = os.path.dirname(SPECDIR)
sys.path.insert(0, ROOT)

from bundle.ffmpeg_bins import collect as collect_ffmpeg  # noqa: E402
from bundle.ffmpeg_bins import find_ffmpeg, human_size  # noqa: E402
from video_process import __version__ as APP_VERSION  # noqa: E402


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_flag(name, default=False):
    return _env(name, "1" if default else "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


GUI_NAME = _env("VP_GUI_NAME", "视频处理工具集")
DIST_NAME = _env("VP_DIST_NAME", "video-process")
ONEFILE = _env("VP_BUILD_MODE", "onedir").strip().lower() == "onefile"
UPX = _env_flag("VP_UPX", False)

ICON_PATH = os.path.join(ROOT, "assets", "app.ico")
HAS_ICON = os.path.isfile(ICON_PATH)
# 图标与版本资源只在 Windows 上有意义，其它平台传了反而会报错
ICON = ICON_PATH if (HAS_ICON and sys.platform == "win32") else None
VERSION_FILE = os.path.join(ROOT, "build", "version_info.txt")
VERSION = VERSION_FILE if (
    sys.platform == "win32" and os.path.isfile(VERSION_FILE)
) else None

DATAS = [(ICON_PATH, "assets")] if HAS_ICON else []

# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------
# auto：PATH 里能找到就打包，找不到就退回依赖系统 ffmpeg（构建不会失败）
WITH_FFMPEG = _env("VP_WITH_FFMPEG", "auto").strip().lower()
FFMPEG_DIR = _env("VP_FFMPEG_DIR", "").strip() or None

FFMPEG_BINARIES = []
FFMPEG_ENABLED = WITH_FFMPEG in ("auto", "1", "true", "yes", "on")
if FFMPEG_ENABLED:
    _info = find_ffmpeg(FFMPEG_DIR)
    if _info["ok"]:
        FFMPEG_BINARIES = collect_ffmpeg(FFMPEG_DIR)
        print(
            "[spec] 附带 ffmpeg: "
            f"{len(_info['files'])} 个文件 / {human_size(_info['size'])} "
            f"（{_info['dir']}）"
        )
    elif WITH_FFMPEG != "auto":
        raise SystemExit(
            "[spec] 错误: 指定打包 ffmpeg 但未找到可执行文件，"
            f"缺失 {', '.join(_info['missing'])}"
        )
    else:
        print("[spec] 未找到 ffmpeg/ffprobe，本次不附带（运行时依赖系统 PATH）")
else:
    print("[spec] 已关闭 ffmpeg 打包（VP_WITH_FFMPEG=0）")

print(
    f"[spec] 视频处理工具集 v{APP_VERSION} · "
    f"{'单文件' if ONEFILE else '单目录'}模式"
)
if ONEFILE and FFMPEG_BINARIES:
    print(
        "[spec] 提示: 单文件模式 + 内置 ffmpeg，每次启动都要解压数百 MB，"
        "\n[spec]       冷启动明显变慢，改用单目录模式可避免"
    )

# ---------------------------------------------------------------------------
# 依赖裁剪
# ---------------------------------------------------------------------------
# defs/tools 都是静态 import，PyInstaller 能自动追踪；
# 这里显式声明的是 Qt 绑定，避免 hook 漏收。
HIDDEN_IMPORTS = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
]

# 明确用不到的重量级模块。PyInstaller 默认也会排除一部分，这里只是再收紧
EXCLUDES = [
    "tkinter",
    "unittest",
    "doctest",
    "pydoc",
    "lib2to3",
    "numpy",
    "PIL",
    "matplotlib",
    "pandas",
    "scipy",
    "IPython",
    "notebook",
    "PySide6",
    "PyQt5",
    "pytest",
    "setuptools",
    "pip",
]


def _supported(func, kwargs):
    """按当前 PyInstaller 版本的签名过滤参数（5.x / 6.x 差异较大）。"""
    params = inspect.signature(func).parameters
    return {key: value for key, value in kwargs.items() if key in params}


def _toc(analysis, name):
    """取 Analysis 上的某个 TOC 列表，缺失时返回空 TOC。"""
    value = getattr(analysis, name, None)
    if value is None:
        return type(analysis.binaries)()
    return value


# ---------------------------------------------------------------------------
# 依赖分析
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(SPECDIR, "entry_gui.py")],
    **_supported(Analysis, dict(
        pathex=[ROOT],
        binaries=FFMPEG_BINARIES,
        datas=DATAS,
        hiddenimports=HIDDEN_IMPORTS,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=EXCLUDES,
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=None,
        noarchive=False,
    )),
)

# PYZ 的签名在 5.x / 6.x 之间变了：
#   5.x  PYZ(pure, zipped_data=..., cipher=...)
#   6.x  PYZ(*tocs)  —— 位置参数，zipped_data 与 cipher 都被移除
# 因此这里只能按位置传，并用 hasattr 判断要不要带 zipped_data
_pyz_tocs = [a.pure]
if hasattr(a, "zipped_data"):
    _pyz_tocs.append(_toc(a, "zipped_data"))

pyz = PYZ(*_pyz_tocs)

# ---------------------------------------------------------------------------
# 可执行文件
# ---------------------------------------------------------------------------
EXE_KW = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=UPX,
    upx_exclude=[],
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version=VERSION,
)

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name=GUI_NAME, console=False, **EXE_KW,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        name=GUI_NAME, console=False, exclude_binaries=True, **EXE_KW,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=UPX, upx_exclude=[], name=DIST_NAME,
    )
