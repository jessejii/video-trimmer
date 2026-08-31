#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键打包：生成版本资源，再调用 PyInstaller。

产出 dist/ 下的单个 exe（单文件模式）或 dist/video-process/ 目录（单目录模式）：

    视频处理工具集.exe   图形界面版，双击即用，无控制台黑窗

用法:
    python build.py                 # 单目录（推荐：启动快、升级只换改动的库）+ 内置 ffmpeg
    python build.py --onefile       # 单文件（便于分发，但每次启动都要解压）
    python build.py --clean         # 先清掉上次的构建缓存
    python build.py --no-ffmpeg     # 不打包 ffmpeg，运行时依赖系统 PATH
    python build.py --ffmpeg-dir DIR  # 指定 ffmpeg 所在目录（默认从 PATH 查找）
    python build.py --upx           # 启用 UPX 压缩（需本机已装 upx）

说明:
    图标由自己提供：把 app.ico 放到 assets/ 下即可，没有图标也能正常打包。
    打包机与运行机需要同样的位数（64 位 Python 打出 64 位 exe），
    且建议在干净的虚拟环境中执行，避免把无关依赖一起打进去。
    ffmpeg 默认随程序打包，产出的 exe 可脱离系统环境独立运行。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(ROOT, "bundle", "video_process.spec")
ICON = os.path.join(ROOT, "assets", "app.ico")
DIST = os.path.join(ROOT, "dist")
WORK = os.path.join(ROOT, "build", "pyinstaller")
GEN_DIR = os.path.join(ROOT, "build")

#: 构建产物目录名（与 spec 里的 VP_DIST_NAME 保持一致）
DIST_NAME = "video-process"

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _utf8_console() -> None:
    """Windows 中文控制台默认 GBK，先切 UTF-8 免得打印进度就崩。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def log(message: str = "") -> None:
    print(message, flush=True)


def step(message: str) -> None:
    log(f"\n==> {message}")


# ---------------------------------------------------------------------------
def ensure_pyinstaller() -> bool:
    """PyInstaller 缺失时自动安装。"""
    if importlib.util.find_spec("PyInstaller") is not None:
        return True

    step("未检测到 PyInstaller，正在安装")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"]
    )
    if result.returncode != 0:
        log("    安装失败，请手动执行: python -m pip install pyinstaller")
        return False
    return importlib.util.find_spec("PyInstaller") is not None


def ensure_version_file() -> str:
    """生成 Windows 版本资源文件（非 Windows 平台跳过）。"""
    if sys.platform != "win32":
        return ""

    step("生成 Windows 版本资源 build/version_info.txt")
    from video_process import __version__

    from bundle.version_info import render

    os.makedirs(GEN_DIR, exist_ok=True)
    path = os.path.join(GEN_DIR, "version_info.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(__version__, filename="video-process"))
    log(f"    已生成: {path} (v{__version__})")
    return path


def clean(onefile: bool) -> None:
    """清掉上次构建产物。"""
    step("清理上次构建")
    targets = [WORK, os.path.join(GEN_DIR, "version_info.txt")]
    if onefile:
        targets.append(os.path.join(DIST, "视频处理工具集.exe"))
    else:
        targets.append(os.path.join(DIST, DIST_NAME))

    for item in targets:
        if os.path.isdir(item):
            shutil.rmtree(item, ignore_errors=True)
            log(f"    已删除目录: {item}")
        elif os.path.isfile(item):
            try:
                os.remove(item)
                log(f"    已删除文件: {item}")
            except OSError:
                pass


def report_ffmpeg(directory: Optional[str], enabled: bool) -> bool:
    """构建前告知 ffmpeg 的打包情况，避免产物体积出乎意料。

    返回:
        本次构建是否会附带 ffmpeg
    """
    step("检查 ffmpeg")
    from bundle.ffmpeg_bins import find_ffmpeg, human_size

    info = find_ffmpeg(directory)

    if not enabled:
        log("    已指定 --no-ffmpeg，运行时依赖系统 PATH 中的 ffmpeg / ffprobe")
        return False

    if not info["ok"]:
        log("    未在 PATH 中找到 ffmpeg / ffprobe，本次构建不附带")
        log("    运行机需自行安装并加入 PATH；或用 --ffmpeg-dir 指定目录")
        return False

    files = info["files"]  # type: ignore[assignment]
    exes = [
        f for f in files
        if os.path.basename(f).lower().startswith(("ffmpeg", "ffprobe"))
    ]
    libs = [f for f in files if f not in exes]
    log(f"    目录:   {info['dir']}")
    log(f"    可执行: {', '.join(os.path.basename(f) for f in exes)}")
    if libs:
        log(f"    动态库: {len(libs)} 个（动态链接版 ffmpeg，一并打包）")
    log(f"    合计:   {human_size(info['size'])}")  # type: ignore[arg-type]
    return True


def run_pyinstaller(onefile: bool, upx: bool, with_ffmpeg: bool,
                    ffmpeg_dir: Optional[str]) -> int:
    """调用 PyInstaller 执行 spec。"""
    step(f"开始打包（{'单文件' if onefile else '单目录'}模式，请稍候）")

    env = os.environ.copy()
    env["VP_BUILD_MODE"] = "onefile" if onefile else "onedir"
    env["VP_UPX"] = "1" if upx else "0"
    env["VP_DIST_NAME"] = DIST_NAME
    env["VP_WITH_FFMPEG"] = "1" if with_ffmpeg else "0"
    if ffmpeg_dir:
        env["VP_FFMPEG_DIR"] = ffmpeg_dir
    # PyInstaller 读子进程输出时按本地代码页解码，中文 exe 名在 GBK 控制台
    # 下会抛 UnicodeDecodeError（不影响产物，但日志里很难看），统一切成 UTF-8
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", SPEC,
            "--noconfirm",
            "--distpath", DIST,
            "--workpath", WORK,
        ],
        cwd=ROOT,
        env=env,
    )
    return result.returncode


def report(onefile: bool, code: int, with_ffmpeg: bool = False) -> None:
    """打印构建结果。"""
    log("")
    if code != 0:
        log("打包失败，请检查上面的 PyInstaller 输出")
        return

    if onefile:
        log("打包完成:")
        log(f"    {os.path.join(DIST, '视频处理工具集.exe')}")
    else:
        out = os.path.join(DIST, DIST_NAME)
        log("打包完成:")
        log(f"    {os.path.join(out, '视频处理工具集.exe')}")
        log(f"\n分发时把整个 {DIST_NAME}/ 目录一起拷贝即可")

    if with_ffmpeg:
        log(
            "\n已内置 ffmpeg / ffprobe，运行机无需安装，"
            "可直接拷到没有 ffmpeg 的机器上使用"
        )
        log(
            "临时改用系统 ffmpeg：设置环境变量 "
            "VIDEO_PROCESS_FFMPEG_DIR 指向其所在目录"
        )
    else:
        log("\n提示: 本次未内置 ffmpeg，运行机需自行安装并加入 PATH")


def main() -> int:
    _utf8_console()

    parser = argparse.ArgumentParser(
        description="把视频处理工具集打包为 Windows 可执行程序"
    )
    parser.add_argument(
        "--onefile", action="store_true", help="打包为单个 exe（默认单目录）"
    )
    parser.add_argument(
        "--clean", action="store_true", help="构建前清掉上次的产物与缓存"
    )
    parser.add_argument(
        "--no-ffmpeg", action="store_true",
        help="不打包 ffmpeg，运行时依赖系统 PATH",
    )
    parser.add_argument(
        "--ffmpeg-dir", metavar="DIR", default=None,
        help="指定 ffmpeg 所在目录（默认从 PATH 查找）",
    )
    parser.add_argument(
        "--upx", action="store_true", help="启用 UPX 压缩（需先安装 upx）"
    )
    args = parser.parse_args()

    if not os.path.isfile(SPEC):
        log(f"找不到打包配置: {SPEC}")
        return 1

    if not ensure_pyinstaller():
        return 1

    if args.clean:
        clean(args.onefile)

    if os.path.isfile(ICON):
        log(f"图标: {ICON}")
    else:
        log(f"未找到 {ICON}，本次构建不带图标")

    ensure_version_file()
    with_ffmpeg = report_ffmpeg(args.ffmpeg_dir, not args.no_ffmpeg)

    code = run_pyinstaller(
        args.onefile, args.upx, not args.no_ffmpeg, args.ffmpeg_dir
    )
    report(args.onefile, code, with_ffmpeg and code == 0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
