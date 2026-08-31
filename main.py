#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频处理工具集 - 源码模式的启动入口。

启动 PyQt6 图形界面。

用法:
    python main.py      # 启动图形界面（会弹出控制台窗口）
    run.bat             # 用 pythonw 启动，不弹控制台黑窗

打包后的可执行文件不走这里，而是用 bundle/entry_gui.py，
但它与下面调用的是同一份初始化逻辑（video_process.entry.run）。
"""

from video_process.entry import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
