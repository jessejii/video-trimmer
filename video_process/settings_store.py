# -*- coding: utf-8 -*-
"""全局设置的持久化（与 UI 框架无关）。

配置文件位于 ~/.video-process/config.json。
"""

from __future__ import annotations

import json
import os

from .core.models import Settings

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".video-process", "config.json"
)


def load_settings() -> Settings:
    """读取持久化设置，不存在或损坏时返回默认值。"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return Settings.from_dict(json.load(fh))
    except Exception:
        pass
    return Settings()


def save_settings(settings: Settings) -> bool:
    """保存设置。"""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
