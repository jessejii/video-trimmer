# -*- coding: utf-8 -*-
"""路径输入控件：输入框 + 浏览按钮，支持原生文件拖放。

Qt 下拖放是原生事件（dragEnterEvent / dropEvent），不必再像终端时代那样
靠粘贴文本兜底；但粘贴进来的带引号路径仍需清洗，故保留清洗逻辑。
浏览按钮调用系统原生对话框（目录模式 / 按扩展名过滤的文件模式 /
二者皆可时弹出 选择文件·选择文件夹 菜单）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import unquote, urlparse

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QGuiApplication,
    QKeyEvent,
)
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QWidget,
)

# Windows 盘符路径 / UNC / POSIX 绝对路径 / 家目录
_ABSOLUTE_RE = re.compile(r"^(\\\\[^\\/]+|[A-Za-z]:[\\/]|/|~)")


def _strip_quotes(s: str) -> str:
    """剥离成对的首尾引号（可多次，兼容 '"a"' 与 '''a'''）。"""
    s = (s or "").strip()
    while len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1].strip()
    return s


def _path_from_file_url(s: str) -> Optional[str]:
    """把 file:///D:/a/b.mp4 之类的 URL 还原为本地路径。"""
    if not s.lower().startswith("file:"):
        return None
    try:
        parsed = urlparse(s)
        raw = unquote(parsed.path or "")
        if not raw:
            return None
        # file:///D:/a/b -> /D:/a/b
        raw = raw.lstrip("/")
        if re.match(r"^[A-Za-z]:[\\/]?", raw):
            return raw.replace("/", "\\")
        return "/" + raw
    except Exception:
        return None


def _clean_candidate(chunk: str) -> str:
    """清洗单个路径片段。"""
    s = (chunk or "").replace("\x00", "").strip()
    if not s:
        return ""
    s = _strip_quotes(s)
    # 中文引号（部分终端/资源管理器会给出）
    s = s.strip("“”‘’")
    url_path = _path_from_file_url(s)
    if url_path:
        s = url_path
    else:
        # POSIX 风格的转义空格：/home/a/my\ file.mp4
        s = s.replace("\\ ", " ")
    s = s.strip()
    if not s:
        return ""
    try:
        s = os.path.expanduser(s)
    except Exception:
        pass
    return s


def _split_quoted(text: str) -> List[str]:
    """按空格切分，但保留引号内部的空格（多文件拖入的常见形式）。"""
    return re.findall(r'"[^"]*"|\'[^\']*\'|[^\s]+', text)


def looks_like_path(candidate: str) -> bool:
    """判断一段文本是否足以被当作路径处理。"""
    if not candidate:
        return False
    try:
        if os.path.exists(candidate):
            return True
    except OSError:
        return False
    return bool(_ABSOLUTE_RE.match(candidate))


def parse_dropped_paths(text: str) -> List[str]:
    """把拖入 / 粘贴的文本解析为路径列表（已去重、已清洗）。"""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return []

    # 整体优先：含空格且未加引号的路径也应当被识别
    whole = _clean_candidate(raw)
    if whole and os.path.exists(whole):
        return [whole]

    chunks = raw.splitlines() if "\n" in raw else _split_quoted(raw)

    result: List[str] = []
    for chunk in chunks:
        item = _clean_candidate(chunk)
        if item and item not in result:
            result.append(item)
    return result


class _PasteFilter(QObject):
    """拦截路径输入框的粘贴，清洗剪贴板中的路径文本。

    资源管理器「复制文件地址」得到的是带引号的路径，浏览器复制的可能是
    file:/// 链接，直接粘贴会带着这些噪音进入 ffmpeg 命令行。
    仅当文本确实像一条路径时才接管，否则放行给 Qt 默认粘贴，不影响正常输入。

    注意：PyQt6 不允许重写 QLineEdit.insertFromMimeData（该虚函数未暴露），
    故用事件过滤器实现。
    """

    def __init__(self, edit: QLineEdit) -> None:
        super().__init__(edit)
        self._edit = edit

    def eventFilter(self, obj, event) -> bool:  # noqa: D102 - Qt 回调
        if not self._is_paste(event):
            return super().eventFilter(obj, event)

        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        if mime is None:
            return super().eventFilter(obj, event)

        if mime.hasUrls():
            local = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if local:
                self._edit.insert(_clean_candidate(local[0]))
                return True

        if mime.hasText():
            paths = parse_dropped_paths(mime.text())
            if paths and looks_like_path(paths[0]):
                self._edit.insert(paths[0])
                return True

        return super().eventFilter(obj, event)

    @staticmethod
    def _is_paste(event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        key: QKeyEvent = event  # type: ignore[assignment]
        ctrl = key.modifiers() & Qt.KeyboardModifier.ControlModifier
        shift = key.modifiers() & Qt.KeyboardModifier.ShiftModifier
        if ctrl and key.key() == Qt.Key.Key_V:
            return True
        return bool(shift and key.key() == Qt.Key.Key_Insert)


class PathInput(QWidget):
    """带浏览按钮的路径输入，支持原生拖放。"""

    #: 路径变化（手动输入、粘贴或拖入）
    valueChanged = pyqtSignal(str)
    #: 需要向用户提示一条消息（文本, 级别）
    noticeRequested = pyqtSignal(str, str)

    def __init__(
        self,
        placeholder: str = "拖入文件/文件夹、粘贴路径，或点击右侧浏览…",
        value: str = "",
        select_directory: bool = True,
        file_patterns: Optional[Iterable[str]] = None,
        parent: Optional[QWidget] = None,
        allow_both: bool = False,
    ) -> None:
        """allow_both 为 True 时，文件与文件夹都接受（拖入文件不再折算为父目录）。"""
        super().__init__(parent)
        self.select_directory = select_directory
        self.allow_both = allow_both
        self.file_patterns: Optional[List[str]] = (
            list(file_patterns) if file_patterns else None
        )

        self.setAcceptDrops(True)
        self.setAutoFillBackground(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setText(value or "")
        self._edit.textChanged.connect(self.valueChanged)
        self._edit.setDragEnabled(True)
        self._edit.installEventFilter(_PasteFilter(self._edit))
        layout.addWidget(self._edit, 1)

        self._browse = QPushButton("浏览", self)
        self._browse.setObjectName("path-browse")
        self._browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse.clicked.connect(self._open_picker)
        layout.addWidget(self._browse)

    # ------------------------------------------------------------------
    # 值
    # ------------------------------------------------------------------
    @property
    def value(self) -> str:
        """返回清洗后的路径（剥离引号与首尾空白）。"""
        return _strip_quotes(self._edit.text())

    def set_value(self, value: str) -> None:
        text = str(value or "")
        if self._edit.text() != text:
            self._edit.setText(text)
        else:
            self.valueChanged.emit(text)

    def set_invalid(self, invalid: bool) -> None:
        self._edit.setProperty("invalid", "true" if invalid else "false")
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)

    # ------------------------------------------------------------------
    # 拖放
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.apply_dropped_paths(
            [u.toLocalFile() for u in urls if u.isLocalFile()]
        )

    def apply_dropped_paths(self, candidates: List[str]) -> bool:
        """把拖入的路径列表填入本控件，成功返回 True。"""
        candidates = [c for c in (candidates or []) if c]
        if not candidates:
            return False

        path = _clean_candidate(candidates[0])
        if not looks_like_path(path):
            return False

        # 目录模式下拖入的是文件，则取其所在目录（与浏览弹窗行为一致）；
        # 文件/文件夹皆可的模式（allow_both）保留文件本身
        if self.select_directory and not self.allow_both and os.path.isfile(path):
            path = os.path.dirname(path) or path

        self.set_value(path)
        self._edit.setFocus()

        extra = len(candidates) - 1
        if not os.path.exists(path):
            self.noticeRequested.emit(f"路径不存在：{path}", "warning")
        elif extra > 0:
            self.noticeRequested.emit(
                f"已填入 {path}（另有 {extra} 个被忽略）", "information"
            )
        else:
            self.noticeRequested.emit(f"已填入 {path}", "information")
        return True

    # ------------------------------------------------------------------
    # 浏览
    # ------------------------------------------------------------------
    def _start_dir(self) -> str:
        current = self.value
        if current and os.path.isdir(current):
            return current
        if current and os.path.isfile(current):
            return os.path.dirname(current) or current
        return str(Path.home())

    def _open_picker(self) -> None:
        if self.select_directory and self.allow_both:
            self._open_picker_menu()
        elif self.select_directory:
            self._pick_dir()
        else:
            self._pick_file()

    def _pick_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "选择文件夹", self._start_dir(),
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.set_value(selected)

    def _pick_file(self) -> None:
        selected, _ok = QFileDialog.getOpenFileName(
            self, "选择文件", self._start_dir(), self._build_name_filter()
        )
        if selected:
            self.set_value(selected)

    def _open_picker_menu(self) -> None:
        """文件与文件夹皆可时，先让用户选择浏览哪一种。"""
        menu = QMenu(self)
        act_file = menu.addAction("选择文件…")
        act_file.setData("file")
        act_dir = menu.addAction("选择文件夹…")
        act_dir.setData("dir")

        chosen = menu.exec(
            self._browse.mapToGlobal(self._browse.rect().bottomLeft())
        )
        if chosen is None:
            return

        # 等菜单关闭后再弹原生对话框，避免嵌套模态
        pick = self._pick_file if chosen.data() == "file" else self._pick_dir
        QTimer.singleShot(0, pick)

    def _build_name_filter(self) -> str:
        if not self.file_patterns:
            return "所有文件 (*)"
        exts = " ".join(f"*{e}" for e in self.file_patterns)
        return f"目标文件 ({exts});;所有文件 (*)"
