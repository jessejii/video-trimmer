# -*- coding: utf-8 -*-
"""深色青蓝主题：调色板 + QSS 样式表。

深色工具风配色，用 QSS 在 Fusion 风格上呈现：
最深底 #0B1120、面板底 #111827、边框 #1F2937、强调青蓝 #22D3EE。
"""

from __future__ import annotations

from PyQt6.QtGui import QFont, QPalette
from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# 调色板
# ---------------------------------------------------------------------------
BG_DEEP = "#0B1120"      # 最深背景：日志区
BG_PANEL = "#111827"     # 面板背景
BG_RAISED = "#1F2937"    # 边框与分隔

ACCENT = "#22D3EE"       # 主强调色（青蓝）
ACCENT_DEEP = "#0EA5E9"
ACCENT_DARK = "#0369A1"

TEXT = "#E5E7EB"         # 主文本
TEXT_DIM = "#9CA3AF"     # 次要文本
TEXT_FAINT = "#6B7280"   # 弱化文本

OK = "#34D399"           # 成功
WARN = "#FBBF24"         # 警告
ERR = "#F87171"          # 错误
INFO = "#60A5FA"         # 信息

# 字体：思源黑体优先，逐级回退到系统中文字体
FONT_FAMILY = (
    '"Source Han Sans SC", "Noto Sans CJK SC", "思源黑体", '
    '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'
)

# 字号（对应设计规范的标题 15 / 副标题 13 / 正文 12）
SIZE_HEADING = 15
SIZE_SUBHEADING = 13
SIZE_BODY = 12

RADIUS = 6

# ---------------------------------------------------------------------------
# QSS
# ---------------------------------------------------------------------------
_STYLESHEET = f"""
/* ---------- 全局 ---------- */
QWidget {{
    background: {BG_DEEP};
    color: {TEXT};
    font-family: {FONT_FAMILY};
    font-size: {SIZE_BODY}px;
}}

QWidget#root, QMainWindow, QMainWindow > QWidget {{
    background: {BG_DEEP};
}}

/* ---------- 标题区 ---------- */
QFrame#title-bar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BG_RAISED};
}}

QLabel#app-title {{
    font-size: {SIZE_HEADING}px;
    font-weight: 600;
    color: {ACCENT};
    background: transparent;
}}

QLabel#app-version {{
    font-size: 11px;
    color: {TEXT_FAINT};
    background: {ACCENT_DARK};
    border-radius: 3px;
    padding: 2px 6px;
}}

QLabel[chip="env"] {{
    background: {BG_RAISED};
    color: {TEXT_DIM};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
}}
QLabel[chip="env"][state="ok"] {{
    background: {ACCENT_DARK};
    color: #FFFFFF;
    font-weight: 600;
}}
QLabel[chip="env"][state="warn"] {{
    background: {BG_RAISED};
    color: {WARN};
    font-weight: 600;
}}
QLabel[chip="env"][state="error"] {{
    background: {BG_RAISED};
    color: {ERR};
    font-weight: 600;
}}

/* ---------- 左侧导航 ---------- */
QFrame#nav-pane {{
    background: {BG_PANEL};
    border-right: 1px solid {BG_RAISED};
}}

QLabel#nav-title {{
    color: {TEXT_FAINT};
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    padding: 6px 10px 2px 10px;
}}

QListWidget#nav-list {{
    background: {BG_PANEL};
    border: none;
    outline: none;
    padding: 0;
}}

/* 导航项的配色与行高由 _NavDelegate 绘制，此处只定框架外观 */
QListWidget#nav-list::item {{
    padding-left: 12px;
    border-left: 3px solid transparent;
}}

QListWidget#nav-list::item:selected {{
    border-left: 3px solid {ACCENT};
}}

/* ---------- 面板 ---------- */
QScrollArea#panel-scroll {{
    background: {BG_DEEP};
    border: none;
}}
QScrollArea#panel-scroll > QWidget > QWidget {{
    background: {BG_DEEP};
}}

QLabel[role="panel-title"] {{
    font-size: {SIZE_HEADING}px;
    font-weight: 600;
    color: {ACCENT};
    background: transparent;
}}

QLabel[role="panel-desc"] {{
    color: {TEXT_DIM};
    background: transparent;
}}

QLabel[role="section"] {{
    font-size: {SIZE_SUBHEADING}px;
    font-weight: 600;
    color: {ACCENT_DEEP};
    background: transparent;
    padding-top: 6px;
}}

QLabel[role="param-label"] {{
    color: {TEXT};
    background: transparent;
}}

QLabel[role="param-help"] {{
    color: {TEXT_FAINT};
    font-size: 11px;
    background: transparent;
}}

QLabel[role="status-ok"] {{ color: {OK}; background: transparent; }}
QLabel[role="status-err"] {{ color: {ERR}; background: transparent; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
    padding: 6px 8px;
    selection-background-color: {ACCENT_DARK};
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit[invalid="true"] {{
    border: 1px solid {ERR};
}}

QComboBox {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
    padding: 6px 8px;
    min-height: 18px;
}}

QComboBox:focus {{ border: 1px solid {ACCENT}; }}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
    border-left: 2px solid {TEXT_DIM};
    border-bottom: 2px solid {TEXT_DIM};
}}

QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BG_RAISED};
    selection-background-color: {ACCENT_DARK};
    selection-color: #FFFFFF;
    outline: none;
}}

QCheckBox {{
    background: transparent;
    color: {TEXT};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BG_RAISED};
    border-radius: 3px;
    background: {BG_PANEL};
}}

QCheckBox::indicator:hover {{ border: 1px solid {ACCENT}; }}

QCheckBox::indicator:checked {{
    background: {ACCENT_DARK};
    border: 1px solid {ACCENT};
    image: none;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
    padding: 6px 14px;
    min-width: 72px;
}}

QPushButton:hover {{
    background: {ACCENT_DARK};
    border: 1px solid {ACCENT_DARK};
    color: #FFFFFF;
}}

QPushButton:pressed {{
    background: {ACCENT};
    color: {BG_DEEP};
}}

QPushButton:disabled {{
    background: {BG_PANEL};
    color: {TEXT_FAINT};
    border: 1px solid {BG_RAISED};
}}

/* ---------- 下拉菜单（浏览按钮的 文件/文件夹 选择） ---------- */
QMenu {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: {ACCENT_DARK};
    color: #FFFFFF;
}}

QPushButton[variant="primary"] {{
    background: {ACCENT_DARK};
    color: #FFFFFF;
    font-weight: 600;
    border: 1px solid {ACCENT_DARK};
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT};
    color: {BG_DEEP};
    border: 1px solid {ACCENT};
}}
QPushButton[variant="primary"]:pressed {{
    background: {ACCENT_DEEP};
    color: #FFFFFF;
}}

QPushButton[variant="danger"] {{
    background: {ACCENT_DARK};
    color: #FFFFFF;
    font-weight: 600;
    border: 1px solid {ACCENT_DARK};
}}
QPushButton[variant="danger"]:hover {{
    background: {ERR};
    border: 1px solid {ERR};
    color: #FFFFFF;
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_FAINT};
    min-width: 48px;
    padding: 4px 10px;
}}
QPushButton[variant="ghost"]:hover {{
    background: {BG_RAISED};
    color: {ERR};
    border: 1px solid {BG_RAISED};
}}

QPushButton#path-browse {{
    min-width: 56px;
    padding: 6px 10px;
}}

/* ---------- 日志与进度 ---------- */
QFrame#log-pane {{
    background: {BG_DEEP};
    border-top: 1px solid {BG_RAISED};
}}

QLabel#log-header-label {{
    color: {TEXT_FAINT};
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}}

LogView {{
    background: {BG_DEEP};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei Mono", monospace;
    font-size: 11px;
}}

QLabel#progress-file {{
    color: {TEXT_DIM};
    background: transparent;
}}

QLabel#progress-pct {{
    color: {ACCENT};
    font-weight: 600;
    background: transparent;
}}

QProgressBar {{
    background: {BG_PANEL};
    border: 1px solid {BG_RAISED};
    border-radius: 3px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {ACCENT_DARK}, stop:1 {ACCENT});
    border-radius: 2px;
}}

/* ---------- 状态栏 ---------- */
QFrame#status-bar {{
    background: {BG_PANEL};
    border-top: 1px solid {BG_RAISED};
}}
QFrame#status-bar QLabel {{
    background: transparent;
    color: {TEXT_DIM};
}}
QFrame#status-bar QLabel[role="param-help"] {{
    color: {TEXT_FAINT};
}}

QStatusBar {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BG_RAISED};
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{
    background: transparent;
    color: {TEXT_DIM};
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle {{
    background: {BG_RAISED};
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{ background: {ACCENT_DARK}; }}
QScrollBar::handle:pressed {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- 分隔条 ---------- */
QSplitter::handle {{
    background: {BG_RAISED};
}}
QSplitter::handle:horizontal {{ height: 1px; }}
QSplitter::handle:vertical {{ width: 1px; }}

/* ---------- 对话框 ---------- */
QDialog {{
    background: {BG_PANEL};
}}
QLabel#confirm-title {{
    font-size: {SIZE_SUBHEADING}px;
    font-weight: 600;
    color: {ACCENT};
    background: transparent;
}}
QFrame#confirm-body {{
    background: {BG_DEEP};
    border: 1px solid {BG_RAISED};
    border-radius: {RADIUS}px;
}}

/* ---------- 提示条 ---------- */
QFrame[toast="true"] {{
    background: {BG_PANEL};
    border: 1px solid {ACCENT_DARK};
    border-radius: {RADIUS}px;
}}
QFrame[toast="true"][level="success"] {{ border: 1px solid {OK}; }}
QFrame[toast="true"][level="warning"] {{ border: 1px solid {WARN}; }}
QFrame[toast="true"][level="error"]   {{ border: 1px solid {ERR}; }}
QLabel[toast="true"][level="success"] {{ color: {OK}; background: transparent; }}
QLabel[toast="true"][level="warning"] {{ color: {WARN}; background: transparent; }}
QLabel[toast="true"][level="error"]   {{ color: {ERR}; background: transparent; }}
QLabel[toast="true"]                  {{ color: {TEXT}; background: transparent; }}
"""


def apply_theme(app: QApplication) -> None:
    """应用 Fusion 风格 + 深色青蓝 QSS。"""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, _color(BG_DEEP))
    palette.setColor(QPalette.ColorRole.WindowText, _color(TEXT))
    palette.setColor(QPalette.ColorRole.Base, _color(BG_PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, _color(BG_RAISED))
    palette.setColor(QPalette.ColorRole.ToolTipBase, _color(BG_PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, _color(TEXT))
    palette.setColor(QPalette.ColorRole.Text, _color(TEXT))
    palette.setColor(QPalette.ColorRole.Button, _color(BG_RAISED))
    palette.setColor(QPalette.ColorRole.ButtonText, _color(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, _color(ACCENT))
    palette.setColor(QPalette.ColorRole.Link, _color(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, _color(ACCENT_DARK))
    palette.setColor(QPalette.ColorRole.HighlightedText, _color("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, _color(TEXT_FAINT))
    app.setPalette(palette)

    app.setStyleSheet(_STYLESHEET)

    # 高 DPI 下让字号与位图缩放更锐利
    font = QFont()
    font.setFamilies([
        "Source Han Sans SC", "Noto Sans CJK SC", "思源黑体",
        "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
    ])
    font.setPointSize(SIZE_BODY)
    app.setFont(font)


def _color(hex_value: str):
    from PyQt6.QtGui import QColor

    return QColor(hex_value)
