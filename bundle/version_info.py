# -*- coding: utf-8 -*-
"""生成 Windows 可执行文件的版本资源（供 PyInstaller 的 --version-file 使用）。

exe 的资源管理器「详细信息」页就是从这里读的：产品名、版本号、公司等。
内容由 PyInstaller 以受限命名空间 eval 执行，因此写成字面量形式。
"""

from __future__ import annotations

from typing import Tuple

_TEMPLATE = """\
# -*- coding: utf-8 -*-
# 由 build.py 自动生成，请勿手动修改
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers={filevers},
        prodvers={prodvers},
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable(
                "080404b0",
                [
                    StringStruct("CompanyName", "{company}"),
                    StringStruct("FileDescription", "{description}"),
                    StringStruct("FileVersion", "{version}"),
                    StringStruct("InternalName", "{filename}"),
                    StringStruct("LegalCopyright", "{copyright}"),
                    StringStruct("OriginalFilename", "{filename}.exe"),
                    StringStruct("ProductName", "{product}"),
                    StringStruct("ProductVersion", "{version}"),
                ],
            )
        ]),
        VarFileInfo([VarStruct("Translation", [2052, 1200])]),
    ],
)
"""

#: 语言 ID：2052 = 简体中文，1200 = Unicode
LANG_ID = 2052
CHARSET_ID = 1200


def parse_version(version: str) -> Tuple[int, int, int, int]:
    """``"1.1.0"`` -> ``(1, 1, 0, 0)``；无法解析的段一律按 0 处理。"""
    parts = []
    for chunk in str(version).split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    parts += [0] * (4 - len(parts))
    return tuple(parts[:4])  # type: ignore[return-value]


def render(
    version: str,
    product: str = "视频处理工具集",
    description: str = "视频 / 字幕处理工具集",
    company: str = "video-process",
    copyright_text: str = "",
    filename: str = "video-process",
) -> str:
    """渲染版本资源脚本文本。"""
    filevers = parse_version(version)
    return _TEMPLATE.format(
        filevers=filevers,
        prodvers=filevers,
        version=version,
        product=product,
        description=description,
        company=company,
        copyright=copyright_text,
        filename=filename,
    )
