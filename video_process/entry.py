# -*- coding: utf-8 -*-
"""启动入口。

源码运行（`python main.py`）与打包后的 exe（`bundle/entry_gui.py`）
共用这一份初始化逻辑，保证两种运行方式行为一致。

这里的准备工作必须在加载任何业务模块之前完成：
业务代码用裸文件名调用 ffmpeg/ffprobe，因此要先把随程序分发的副本
挂到 PATH 前面，后续 ``shutil.which`` 才能命中。
"""

from __future__ import annotations

from ._frozen import prepare_ffmpeg_path
from ._io import ensure_utf8_stdio


def run() -> int:
    """启动图形界面，返回进程退出码。"""
    # Windows 中文控制台默认 GBK，先切到 UTF-8；无控制台时补空实现
    ensure_utf8_stdio()

    prepare_ffmpeg_path()

    # 延迟导入，保持本模块尽量轻量
    from .ui.app import run_app

    return run_app()
