# -*- coding: utf-8 -*-
"""Windows 控制台 I/O 编码兜底。

Windows 中文环境默认代码页为 GBK，输出 ✔ / ═══ 等符号会抛
UnicodeEncodeError。此处统一把标准流切换为 UTF-8，
并对无法编码的字符降级为替换符而非崩溃。
"""

from __future__ import annotations

import sys


class NullStream:
    """空实现的文本流，用于替代不存在的标准流。

    打包成无控制台程序（PyInstaller --windowed / pythonw）后
    sys.stdout、sys.stderr 都是 None，任何 print() 都会抛
    AttributeError。补一个空实现，让调用方无需到处判空。
    """

    encoding = "utf-8"
    errors = "replace"

    def write(self, *args, **kwargs) -> int:
        return 0

    def writelines(self, *args, **kwargs) -> None:
        return None

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def reconfigure(self, **kwargs) -> None:
        return None


def ensure_utf8_stdio() -> None:
    """把 stdout / stderr 切换为 UTF-8（幂等，失败静默）。

    标准流缺失时（无控制台的打包程序）替换为空实现。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            setattr(sys, stream_name, NullStream())
            continue
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 某些运行环境（如被重定向的管道）不支持 reconfigure
            pass
