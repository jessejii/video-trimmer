# -*- coding: utf-8 -*-
"""文本文件读取：字幕与草稿文件多为 UTF-8（常带 BOM），少数是 GBK。"""

from __future__ import annotations


def read_text(path: str) -> str:
    """读取文本文件，utf-8-sig 优先，解码失败回退 gbk。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk") as fh:
            return fh.read()
