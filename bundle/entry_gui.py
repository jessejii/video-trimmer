# -*- coding: utf-8 -*-
"""打包后的图形界面入口（对应「视频处理工具集.exe」，无控制台窗口）。"""

from __future__ import annotations

import sys

from video_process.entry import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
