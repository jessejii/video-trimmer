# -*- coding: utf-8 -*-
"""声明式参数表单规格（与 UI 框架无关）。

每个工具只声明一份 specs 列表，工具定义层（defs）持有它，
界面据此生成对应控件（条件显隐、类型强转、校验）。

新增一个工具只需：一份 spec 列表 + 一个业务函数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ParamSpec:
    """单个参数的规格。"""

    name: str                                  # 参数名（字段名）
    label: str                                 # UI 显示标签
    kind: str                                  # dir|file|path|text|int|float|choice|bool
    default: Any = None
    choices: Optional[List[Tuple[str, Any]]] = None   # (显示文本, 实际值)
    help: str = ""
    required: bool = True
    # 条件显隐：(依赖字段名, 触发显示的值)。值为 None 时表示"非空即显示"
    visible_when: Optional[Tuple[str, Any]] = None
    # 路径参数的浏览模式
    select_directory: bool = True
    file_patterns: Optional[List[str]] = None
    # 校验函数：返回错误信息或 None
    validator: Optional[Callable[[Any], Optional[str]]] = None
    # 多行文本输入（如时间线计算器的时间线内容）
    multiline: bool = False

    # --------------------------------------------------------------
    def should_show(self, values: Dict[str, Any]) -> bool:
        if self.visible_when is None:
            return True
        dep_name, trigger = self.visible_when
        current = values.get(dep_name)
        if trigger is None:
            return bool(current)
        if isinstance(trigger, (list, tuple, set)):
            return current in trigger
        return current == trigger

    def coerce(self, raw: Any) -> Any:
        """把控件返回值转换为目标类型。"""
        if self.kind == "int":
            if raw in (None, ""):
                return self.default
            try:
                return int(str(raw).strip())
            except (TypeError, ValueError):
                return self.default
        if self.kind == "float":
            if raw in (None, ""):
                return self.default
            try:
                return float(str(raw).strip())
            except (TypeError, ValueError):
                return self.default
        if self.kind == "bool":
            return bool(raw)
        if raw is None:
            return self.default
        return raw


@dataclass
class ToolDefinition:
    """一个工具的完整定义：参数规格 + 业务逻辑 + 分组信息。

    与任何 UI 框架无关，界面层据此渲染表单。
    """

    id: str                                     # kebab id，界面与业务逻辑共用
    title: str
    group: str                                  # 导航分组
    description: str = ""
    specs: List[ParamSpec] = field(default_factory=list)
    runner: Optional[Callable[..., Any]] = None  # 业务函数
    # 面板自定义渲染钩子：None → 通用表单面板；"timeline"/"settings" → 定制面板
    panel_class: Optional[str] = None
    # 是否在执行前弹出确认框（纯计算类工具可关掉）
    confirm_before_run: bool = True

    # --------------------------------------------------------------
    @property
    def labels(self) -> Dict[str, str]:
        return {s.name: s.label for s in self.specs}

    def resolve_runner(self) -> Optional[Callable[..., Any]]:
        """取得可直接调用的业务函数。

        兼容 runner = staticmethod(func) 的写法：Python 3.10 起静态方法对象
        本身可调用，3.9 及更早需取 __func__，此处统一解包以保证跨版本可用。
        """
        runner = self.runner
        if isinstance(runner, staticmethod):
            return runner.__func__
        return runner


def validate_segments(text: str) -> Optional[str]:
    """时间段格式校验：至少包含一个 开始-结束 区间。"""
    from .core.timeparse import parse_segments

    if not text or not text.strip():
        return "时间段不能为空"
    segs, warnings = parse_segments(text, None)
    if not segs:
        return f"没有有效的时间段（格式: 1:00-2:00,5:00-6:00）" + (
            f"；{warnings[0]}" if warnings else ""
        )
    return None


def validate_time_points(text: str) -> Optional[str]:
    """分割时间点校验。"""
    from .core.timeparse import parse_time

    if not text or not text.strip():
        return "分割时间点不能为空"
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            t = parse_time(part)
        except Exception:
            return f"无效的时间格式: {part}"
        if t <= 0:
            return f"分割时间必须大于 0: {part}"
    return None


def validate_positive_int(value: Any) -> Optional[str]:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "必须是整数"
    if n <= 0:
        return "必须大于 0"
    return None
