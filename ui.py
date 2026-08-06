from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import (
    QMimeData, Qt, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QDragEnterEvent, QDropEvent, QFont, QKeySequence,
    QPainter, QBrush, QPen, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
    QWidget,
)

from calcifer_face import CalciferFace

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR     = _base_dir()
CONFIG_DIR   = BASE_DIR / "config"
API_FILE     = CONFIG_DIR / "api_keys.json"
CONV_FILE    = CONFIG_DIR / "conversations.json"
SETTINGS_FILE= CONFIG_DIR / "settings.json"

_DEFAULT_W, _DEFAULT_H = 1280, 780
_MIN_W,     _MIN_H     = 980, 600
_SIDEBAR_W  = 210
_SIDEBAR_W_MIN = 58
_CHAT_MIN_W = 360

_OS = platform.system()

_LITE = False  # reduced-motion mode (toggled in Settings)

# ---------------------------------------------------------------------------
# Emotion -> colour mapping (drives the companion glow + face tint)
# ---------------------------------------------------------------------------
EMOTION_COLORS = {
    "happy":     "#FFB347",  # Warm gold
    "proud":     "#FFB347",
    "playful":   "#FFB347",
    "excited":   "#FF6B6B",  # Hot orange/pink
    "surprised": "#FF6B6B",
    "thinking":  "#9B7BFF",  # Violet/blue
    "curious":   "#9B7BFF",
    "focused":   "#9B7BFF",
    "calm":      "#6FA8DC",  # Teal/indigo
    "sleepy":    "#6FA8DC",
    "sad":       "#6FA8DC",
    "angry":     "#FF5F57",  # Red
    "annoyed":   "#FF5F57",
    "error":     "#FF5F57",
}

def get_emotion_color(emotion: str) -> QColor:
    return QColor(EMOTION_COLORS.get(emotion.lower(), "#FFB347"))

# ---------------------------------------------------------------------------
# Warm premium chrome palette
# ---------------------------------------------------------------------------
class C:
    BG        = "#0a0a0c"   # deep charcoal, slightly warm
    CHROME    = "#0e0e11"   # sidebar / panels
    PANEL     = "#131316"
    PANEL2    = "#17171b"
    BORDER    = "#232329"
    BORDER_HI = "#33333b"
    TEXT      = "#e9e7e4"
    TEXT_MED  = "#b4b1ac"
    TEXT_DIM  = "#797672"
    ACC       = "#FFB347"   # warm amber accent
    ACC_DIM   = "#7a551f"
    GREEN     = "#63d390"
    RED       = "#ff5f57"
    WHITE     = "#f5f2ee"

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

def _sans(size=10, weight=QFont.Weight.Normal) -> QFont:
    f = QFont("Segoe UI", int(size)); f.setWeight(weight); return f

def _serif(size=20, weight=QFont.Weight.Bold) -> QFont:
    f = QFont("Georgia", int(size)); f.setWeight(weight); return f

# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------
def _route_line(text: str):
    """Map a raw log line to (role, display_text)."""
    tl = text.lower()
    if tl.startswith("you:"):
        return "you", text.split(":", 1)[1].strip()
    if tl.startswith("calcifer:"):
        return "ai", text.split(":", 1)[1].strip()
    if tl.startswith("file:"):
        return "sys", text
    if "err" in tl:
        return "err", text
    return "sys", text

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"

# ---------------------------------------------------------------------------
# Chat transcript view
# ---------------------------------------------------------------------------
class ChatView(QScrollArea):
    file_dropped = pyqtSignal(str)
    MAX_RENDERED = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical { background: transparent; width: 8px; border: none; }
            QScrollBar::handle:vertical { background: #2a2a30; border-radius: 4px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #3a3a42; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(20, 20, 20, 16)
        self._lay.setSpacing(10)
        self._lay.addStretch(1)
        self.setWidget(self._container)

        self._empty = self._build_empty()
        self._lay.insertWidget(0, self._empty, 1)

        self._bubbles: list[QWidget] = []
        self._near_bottom = True
        self.verticalScrollBar().valueChanged.connect(self._track_scroll)

    def _build_empty(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addStretch(1)
        title = QLabel("Calcifer")
        title.setFont(_serif(36))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        sub = QLabel("Your fiery companion is ready when you are.")
        sub.setFont(_sans(11))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        v.addWidget(title)
        v.addSpacing(10)
        v.addWidget(sub)
        v.addStretch(1)
        return w

    def _track_scroll(self, value: int):
        sb = self.verticalScrollBar()
        self._near_bottom = (sb.maximum() - value) < 60

    def clear(self):
        # Keep the empty-state widget (index 0) and the trailing stretch.
        # Remove and destroy only the message bubbles.
        while self._lay.count() > 2:
            item = self._lay.takeAt(1)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._bubbles = []
        self._empty.show()

    def set_messages(self, messages):
        self.clear()
        for m in messages:
            self._append_bubble(m.get("role", "sys"),
                                m.get("text", ""),
                                m.get("time", ""))
        self._scroll_to_bottom()

    def append_message(self, role: str, text: str, ts: str):
        self._append_bubble(role, text, ts)
        self._scroll_to_bottom()

    def _append_bubble(self, role: str, text: str, ts: str):
        if not self._bubbles and self._empty.isVisible():
            self._empty.hide()
        bubble = self._make_bubble(role, text, ts)
        idx = self._lay.count() - 1  # before trailing stretch
        self._lay.insertWidget(idx, bubble)
        self._bubbles.append(bubble)
        if len(self._bubbles) > self.MAX_RENDERED:
            old = self._bubbles.pop(0)
            self._lay.removeWidget(old)
            old.deleteLater()

    def _scroll_to_bottom(self):
        if not self._near_bottom:
            return
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()))

    def _make_bubble(self, role: str, text: str, ts: str) -> QWidget:
        outer = QWidget()
        h = QHBoxLayout(outer)
        h.setContentsMargins(0, 0, 0, 0)

        if role == "sys":
            lbl = QLabel(text)
            lbl.setFont(_sans(9))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lbl.setMaximumWidth(600)
            h.addStretch(1)
            h.addWidget(lbl)
            h.addStretch(1)
            return outer

        bubble = QFrame()
        bubble.setMaximumWidth(560)
        if role == "you":
            bubble.setStyleSheet(
                "QFrame { background: rgba(255,179,71,0.10);"
                " border: 1px solid rgba(255,179,71,0.30); border-radius: 14px; }")
        elif role == "err":
            bubble.setStyleSheet(
                "QFrame { background: rgba(255,95,87,0.08);"
                " border: 1px solid rgba(255,95,87,0.38); border-radius: 14px; }")
        else:
            bubble.setStyleSheet(
                "QFrame { background: #17171b;"
                " border: 1px solid #24242a; border-radius: 14px; }")

        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 10, 14, 8)
        inner.setSpacing(3)

        lbl = QLabel(text)
        lbl.setFont(_sans(10.5))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        color = {"you": C.WHITE, "err": C.RED, "ai": C.TEXT}.get(role, C.TEXT)
        lbl.setStyleSheet(f"color: {color}; background: transparent;")
        inner.addWidget(lbl)

        if ts:
            t = QLabel(ts)
            t.setFont(_sans(7.5))
            t.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            align = (Qt.AlignmentFlag.AlignRight if role == "you"
                     else Qt.AlignmentFlag.AlignLeft)
            inner.addWidget(t, alignment=align)

        if role == "you":
            h.addStretch(1)
            h.addWidget(bubble)
        else:
            h.addWidget(bubble)
            h.addStretch(1)
        return outer

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self.file_dropped.emit(path)

# ---------------------------------------------------------------------------
# Chat input bar
# ---------------------------------------------------------------------------
class ChatInputBar(QWidget):
    send_requested      = pyqtSignal(str)
    attach_requested    = pyqtSignal()
    clear_file_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 6, 20, 18)
        lay.setSpacing(8)

        self._attach = QPushButton("＋")
        self._attach.setFixedSize(40, 40)
        self._attach.setToolTip("Attach a file")
        self._attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach.setFont(_sans(15, QFont.Weight.Bold))
        self._attach.setStyleSheet(self._ghost_btn())
        self._attach.clicked.connect(self.attach_requested.emit)
        lay.addWidget(self._attach)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Calcifer…")
        self._input.setFont(_sans(10.5))
        self._input.setFixedHeight(40)
        self._input.setStyleSheet("""
            QLineEdit {
                background: #101013; color: #e9e7e4;
                border: 1px solid #26262c; border-radius: 20px;
                padding: 0 16px; selection-background-color: #3a2c18;
            }
            QLineEdit:focus { border: 1px solid #7a551f; }
        """)
        self._input.textChanged.connect(self._sync_send)
        self._input.returnPressed.connect(self._emit_send)
        lay.addWidget(self._input, 1)

        self._send = QPushButton("Send")
        self._send.setFixedSize(72, 40)
        self._send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send.setFont(_sans(10, QFont.Weight.Bold))
        self._send.clicked.connect(self._emit_send)
        lay.addWidget(self._send)
        self._sync_send("")

    @staticmethod
    def _ghost_btn():
        return """
            QPushButton {
                background: #131316; color: #b4b1ac;
                border: 1px solid #26262c; border-radius: 20px;
            }
            QPushButton:hover {
                color: #FFB347; border: 1px solid #7a551f; background: #171711;
            }
            QPushButton:pressed { background: #1c1c12; }
        """

    def _sync_send(self, text: str):
        self._send.setEnabled(bool(text.strip()))
        if text.strip():
            self._send.setStyleSheet("""
                QPushButton {
                    background: #FFB347; color: #1a1206;
                    border: none; border-radius: 20px; font-weight: bold;
                }
                QPushButton:hover { background: #ffc36b; }
                QPushButton:pressed { background: #e39a2e; }
            """)
        else:
            self._send.setStyleSheet("""
                QPushButton {
                    background: #18181d; color: #55524e;
                    border: none; border-radius: 20px; font-weight: bold;
                }
            """)

    def _emit_send(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.send_requested.emit(txt)

    def clear(self):
        self._input.clear()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
class _ConvRow(QWidget):
    delete_clicked = pyqtSignal()

    def __init__(self, title: str, meta: str, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(54)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(6)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._title = QLabel(title)
        self._title.setFont(_sans(10, QFont.Weight.DemiBold))
        self._title.setStyleSheet("color: #e9e7e4; background: transparent;")
        col.addWidget(self._title)
        self._meta = QLabel(meta)
        self._meta.setFont(_sans(8))
        self._meta.setStyleSheet("color: #797672; background: transparent;")
        col.addWidget(self._meta)
        lay.addLayout(col, 1)

        self._x = QPushButton("×")
        self._x.setFixedSize(20, 20)
        self._x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._x.setStyleSheet("""
            QPushButton { background: transparent; color: #797672; border: none; }
            QPushButton:hover { color: #ff5f57; }
        """)
        self._x.clicked.connect(self.delete_clicked.emit)
        self._x.hide()
        lay.addWidget(self._x)

    def set_title(self, title: str):
        self._title.setText(title)

    def enterEvent(self, e):
        self._x.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._x.hide()
        super().leaveEvent(e)


class Sidebar(QWidget):
    new_chat_requested     = pyqtSignal()
    conversation_selected  = pyqtSignal(str)
    rename_requested       = pyqtSignal(str, str)
    delete_requested       = pyqtSignal(str)
    settings_requested     = pyqtSignal()
    collapse_requested     = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(_SIDEBAR_W)
        self.setStyleSheet(f"background: {C.CHROME}; border-right: 1px solid {C.BORDER};")
        self._expanded = True
        self._id_to_item: dict[str, QListWidgetItem] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 16, 10, 12)
        lay.setSpacing(8)

        # Identity
        self._identity = QLabel("Calcifer")
        self._identity.setFont(_serif(20))
        self._identity.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        self._identity.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._identity)

        self._tagline = QLabel("Fire companion")
        self._tagline.setFont(_sans(8.5))
        self._tagline.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._tagline)
        lay.addSpacing(6)

        # New chat
        self._new_btn = QPushButton("＋  New chat")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setFixedHeight(36)
        self._new_btn.setFont(_sans(10, QFont.Weight.Bold))
        self._new_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,179,71,0.12); color: #FFB347;
                border: 1px solid rgba(255,179,71,0.35); border-radius: 10px;
            }
            QPushButton:hover { background: rgba(255,179,71,0.20); }
            QPushButton:pressed { background: rgba(255,179,71,0.28); }
        """)
        self._new_btn.clicked.connect(self.new_chat_requested.emit)
        lay.addWidget(self._new_btn)
        lay.addSpacing(6)

        # Conversation list
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: 0; }
            QListWidget::item {
                background: transparent; border: none; border-radius: 8px;
                padding: 2px;
            }
            QListWidget::item:hover { background: rgba(255,255,255,0.04); }
            QListWidget::item:selected {
                background: rgba(255,179,71,0.12);
                border-left: 2px solid #FFB347;
            }
            QScrollBar:vertical { background: transparent; width: 6px; border: none; }
            QScrollBar::handle:vertical { background: #2a2a30; border-radius: 3px; min-height: 20px; }
        """)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        lay.addWidget(self._list, 1)

        # Clock + bottom controls
        self._clock = QLabel("")
        self._clock.setFont(_sans(8.5, QFont.Weight.DemiBold))
        self._clock.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._clock)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setFixedHeight(32)
        self._settings_btn.setFont(_sans(9.5))
        self._settings_btn.setStyleSheet(self._bottom_btn_style())
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        lay.addWidget(self._settings_btn)

        self._collapse_btn = QPushButton("‹")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setFixedHeight(28)
        self._collapse_btn.setFont(_sans(12))
        self._collapse_btn.setStyleSheet(self._bottom_btn_style())
        self._collapse_btn.clicked.connect(self.collapse_requested.emit)
        lay.addWidget(self._collapse_btn)

    @staticmethod
    def _bottom_btn_style():
        return """
            QPushButton {
                background: #131316; color: #b4b1ac;
                border: 1px solid #232329; border-radius: 8px;
            }
            QPushButton:hover { color: #FFB347; border: 1px solid #7a551f; }
        """

    def set_conversations(self, convs, active_id: str | None):
        self._list.blockSignals(True)
        self._list.clear()
        self._id_to_item.clear()
        for c in convs:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            self._list.addItem(item)
            row = _ConvRow(self._truncate(c.get("title", "New chat"), 26), c.get("meta", ""))
            row.delete_clicked.connect(lambda cid=c["id"]: self.delete_requested.emit(cid))
            self._list.setItemWidget(item, row)
            self._id_to_item[c["id"]] = item
        if active_id and active_id in self._id_to_item:
            self._list.setCurrentItem(self._id_to_item[active_id])
        self._list.blockSignals(False)

    @staticmethod
    def _truncate(title: str, n: int) -> str:
        return title if len(title) <= n else title[: n - 1] + "…"

    def set_clock(self, text: str):
        self._clock.setText(text)

    def set_collapsed(self, collapsed: bool):
        self._expanded = not collapsed
        self.setFixedWidth(_SIDEBAR_W_MIN if collapsed else _SIDEBAR_W)
        self._identity.setVisible(not collapsed)
        self._tagline.setVisible(not collapsed)
        self._list.setVisible(not collapsed)
        self._clock.setVisible(not collapsed)
        self._new_btn.setText("＋" if collapsed else "＋  New chat")
        self._settings_btn.setText("⋮" if collapsed else "Settings")
        self._collapse_btn.setText("›" if collapsed else "‹")

    def _item_id(self, item: QListWidgetItem | None) -> str | None:
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_current_changed(self, current, _previous):
        cid = self._item_id(current)
        if cid:
            self.conversation_selected.emit(cid)

    def _on_double_clicked(self, item):
        cid = self._item_id(item)
        if cid:
            row = self._list.itemWidget(item)
            old = row._title.text() if row else ""
            self.rename_requested.emit(cid, old)

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return
        cid = self._item_id(item)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #17171b; color: #e9e7e4; border: 1px solid #232329;"
            " border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 6px 18px; border-radius: 6px; }"
            "QMenu::item:selected { background: rgba(255,179,71,0.15); }")
        act_rename = menu.addAction("Rename")
        act_delete = menu.addAction("Delete")
        chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        if chosen == act_rename and cid:
            self.rename_requested.emit(cid, "")
        elif chosen == act_delete and cid:
            self.delete_requested.emit(cid)

# ---------------------------------------------------------------------------
# Companion area: face on soft ambient glow
# ---------------------------------------------------------------------------
class CompanionArea(QWidget):
    mute_requested = pyqtSignal()

    STATE_TEXT = {
        "INITIALISING": ("Initialising…",   C.TEXT_DIM),
        "LISTENING":    ("Listening…",      C.GREEN),
        "THINKING":     ("Thinking…",       C.ACC),
        "PROCESSING":   ("Processing…",     C.ACC),
        "SPEAKING":     ("Speaking…",       C.ACC),
        "MUTED":        ("Muted",           C.RED),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 420)
        self._glow_color   = QColor("#FFB347")
        self._target_color = QColor("#FFB347")
        self._anim_progress = 1.0
        self._state = "INITIALISING"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 30, 24, 26)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addStretch(2)
        self.face = CalciferFace()
        lay.addWidget(self.face, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(14)

        self._status = QLabel("Initialising…")
        self._status.setFont(_sans(11, QFont.Weight.DemiBold))
        self._status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._status)
        lay.addSpacing(10)

        self._mute_btn = QPushButton("MIC ON")
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setFixedHeight(28)
        self._mute_btn.setFont(_sans(8.5, QFont.Weight.DemiBold))
        self._mute_btn.clicked.connect(self.mute_requested.emit)
        lay.addWidget(self._mute_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(3)

        self._muted = False
        self._style_mute(False)

        self._color_timer = QTimer(self)
        self._color_timer.timeout.connect(self._update_glow)
        self._color_timer.start(30)

    def set_emotion(self, emotion: str):
        self._target_color = get_emotion_color(emotion)
        self._anim_progress = 0.0
        self.face.setEmotion(emotion)

    def set_state(self, state: str):
        self._state = state
        text, color = self.STATE_TEXT.get(state, (f"{state}…", C.TEXT_MED))
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color}; background: transparent;")

    def set_muted(self, muted: bool):
        self._muted = muted
        self._style_mute(muted)

    def _style_mute(self, muted: bool):
        if muted:
            self._mute_btn.setText("MUTED")
            self._mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,95,87,0.10); color: #ff5f57;
                    border: 1px solid rgba(255,95,87,0.40); border-radius: 14px;
                }
                QPushButton:hover { background: rgba(255,95,87,0.20); }
            """)
        else:
            self._mute_btn.setText("MIC ON")
            self._mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(99,211,144,0.10); color: #63d390;
                    border: 1px solid rgba(99,211,144,0.35); border-radius: 14px;
                }
                QPushButton:hover { background: rgba(99,211,144,0.20); }
            """)

    def set_lite(self, lite: bool):
        self._color_timer.setInterval(60 if lite else 30)

    def _update_glow(self):
        if self._anim_progress < 1.0:
            self._anim_progress += 0.05
            if self._anim_progress > 1.0:
                self._anim_progress = 1.0
            t = self._anim_progress
            r = int(self._glow_color.red()   * (1 - t) + self._target_color.red()   * t)
            g = int(self._glow_color.green() * (1 - t) + self._target_color.green() * t)
            b = int(self._glow_color.blue()  * (1 - t) + self._target_color.blue()  * t)
            self._glow_color = QColor(r, g, b)
            self.face.setColor(self._glow_color)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        cx, cy = self.width() / 2, self.height() / 2
        radius = min(self.width(), self.height()) * 0.62

        pulse = 1.25 if self._state == "SPEAKING" else (
                1.10 if self._state in ("THINKING", "PROCESSING") else 1.0)
        if self._muted:
            pulse *= 0.55

        g = QRadialGradient(cx, cy, radius)
        c = QColor(self._glow_color)
        a0 = min(160, int(90 * pulse))
        c.setAlpha(a0)
        g.setColorAt(0.0, c)
        c.setAlpha(int(40 * pulse))
        g.setColorAt(0.55, c)
        c.setAlpha(0)
        g.setColorAt(1.0, c)
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(self.rect())

# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, lite: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(360)
        self.setStyleSheet(f"""
            QDialog {{ background: {C.PANEL}; border: 1px solid {C.BORDER}; }}
            QLabel {{ color: {C.TEXT}; background: transparent; }}
        """)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(10)

        title = QLabel("Emotion palette")
        title.setFont(_sans(11, QFont.Weight.Bold))
        v.addWidget(title)

        groups = [
            ("Happy · Proud · Playful", "#FFB347"),
            ("Excited · Surprised",     "#FF6B6B"),
            ("Thinking · Curious · Focused", "#9B7BFF"),
            ("Calm · Sleepy · Sad",     "#6FA8DC"),
            ("Angry · Annoyed · Error", "#FF5F57"),
        ]
        for label, col in groups:
            row = QHBoxLayout()
            swatch = QFrame()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                f"background: {col}; border-radius: 8px; border: none;")
            row.addWidget(swatch)
            lbl = QLabel(label)
            lbl.setFont(_sans(9.5))
            row.addWidget(lbl)
            row.addStretch(1)
            v.addLayout(row)

        v.addSpacing(8)
        self._lite = QCheckBox("Reduced motion (lite mode)")
        self._lite.setFont(_sans(10))
        self._lite.setChecked(lite)
        self._lite.setStyleSheet(
            "QCheckBox { color: #e9e7e4; }"
            "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;"
            " border: 1px solid #33333b; background: #131316; }"
            "QCheckBox::indicator:checked { background: #FFB347; border: 1px solid #FFB347; }")
        v.addWidget(self._lite)

        v.addSpacing(10)
        btn = QPushButton("Done")
        btn.setFixedHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #FFB347; color: #1a1206; border: none; border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ffc36b; }
        """)
        btn.clicked.connect(self.accept)
        v.addWidget(btn)

    def lite(self) -> bool:
        return self._lite.isChecked()

# ---------------------------------------------------------------------------
# Setup overlay (first run)
# ---------------------------------------------------------------------------
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(12, 12, 15, 245);
                border: 1px solid {C.BORDER_HI};
                border-radius: 12px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(8)

        def _lbl(txt, font, color=C.TEXT, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(font)
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        lay.addWidget(_lbl("Calcifer", _serif(24), C.ACC))
        lay.addWidget(_lbl("Configure your companion before first boot.", _sans(9), C.TEXT_DIM))
        lay.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        lay.addWidget(sep)
        lay.addSpacing(4)

        lay.addWidget(_lbl("GEMINI API KEY", _sans(8, QFont.Weight.Bold), C.TEXT_DIM,
                           Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(_sans(10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(self._input_style("#FFB347"))
        lay.addWidget(self._key_input)
        lay.addSpacing(8)

        lay.addWidget(_lbl("OPENROUTER API KEY", _sans(8, QFont.Weight.Bold), C.TEXT_DIM,
                           Qt.AlignmentFlag.AlignLeft))
        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-…")
        self._or_input.setFont(_sans(10))
        self._or_input.setFixedHeight(32)
        self._or_input.setStyleSheet(self._input_style("#FFB347"))
        lay.addWidget(self._or_input)

        lay.addSpacing(12)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};")
        lay.addWidget(sep2)
        lay.addSpacing(4)

        lay.addWidget(_lbl("OPERATING SYSTEM", _sans(8, QFont.Weight.Bold), C.TEXT_DIM,
                           Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        lay.addWidget(_lbl(f"Auto-detected: {det_name}", _sans(8), C.ACC,
                           Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux")]:
            btn = QPushButton(label)
            btn.setFont(_sans(9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        lay.addLayout(os_row)
        self._sel(detected)
        lay.addSpacing(12)

        init_btn = QPushButton("Initialise Systems")
        init_btn.setFont(_sans(10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet("""
            QPushButton {
                background: #FFB347; color: #1a1206;
                border: none; border-radius: 10px; font-weight: bold;
            }
            QPushButton:hover { background: #ffc36b; }
        """)
        init_btn.clicked.connect(self._submit)
        lay.addWidget(init_btn)

    @staticmethod
    def _input_style(accent: str):
        return f"""
            QLineEdit {{
                background: #0d0d10; color: #e9e7e4;
                border: 1px solid {C.BORDER}; border-radius: 8px; padding: 4px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
        """

    def _sel(self, key: str):
        self._sel_os = key
        colors = {"windows": "#FFB347", "mac": "#63d390", "linux": "#63d390"}
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {colors[k]}; color: #141006;
                        border: none; border-radius: 8px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #101013; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER}; border-radius: 8px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_HI}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        or_key = self._or_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._input_style("#ff5f57") +
                " QLineEdit { border: 1px solid #ff5f57; }")
            return
        if not or_key:
            self._or_input.setStyleSheet(
                self._input_style("#ff5f57") +
                " QLineEdit { border: 1px solid #ff5f57; }")
            return
        self.done.emit(key, or_key, self._sel_os)

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    _log_sig     = pyqtSignal(str)
    _state_sig   = pyqtSignal(str)
    _emotion_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("Calcifer")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command = None
        self._muted = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        self.chat_panel = self._build_chat_panel()
        root.addWidget(self.chat_panel, stretch=4)

        self.companion = CompanionArea()
        self.companion.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        root.addWidget(self.companion, stretch=5)

        # --- conversations ---
        self._conversations: list[dict] = []
        self._active_id: str | None = None
        self._load_conversations()
        if not self._conversations:
            self._new_chat(select=True, save=False)
        self._render_active()
        self._refresh_sidebar()

        # --- wiring ---
        self.sidebar.new_chat_requested.connect(self._new_chat)
        self.sidebar.conversation_selected.connect(self._switch_conversation)
        self.sidebar.rename_requested.connect(self._rename_conversation)
        self.sidebar.delete_requested.connect(self._delete_conversation)
        self.sidebar.settings_requested.connect(self._open_settings)
        self.sidebar.collapse_requested.connect(self._toggle_sidebar)
        self.chat_bar.send_requested.connect(self._send)
        self.chat_bar.attach_requested.connect(self._attach_file)
        self.chat_bar.clear_file_requested.connect(self._clear_file)
        self.chat_view.file_dropped.connect(self._set_current_file)
        self.companion.mute_requested.connect(self._toggle_mute)

        self._log_sig.connect(self._append_log)
        self._state_sig.connect(self._apply_state)
        self._emotion_sig.connect(self._apply_emotion)

        # timers
        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # settings
        self._lite = False
        self._load_settings()

        # shortcuts
        QShortcut(QKeySequence("F4"), self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

    # ---------------------------------------------------------- conversation
    def _load_conversations(self):
        try:
            if CONV_FILE.exists():
                data = json.loads(CONV_FILE.read_text(encoding="utf-8"))
                self._conversations = data.get("conversations", [])
                self._active_id = data.get("active_id")
        except Exception:
            self._conversations = []
            self._active_id = None

    def _save_conversations(self):
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
            CONV_FILE.write_text(json.dumps({
                "conversations": self._conversations,
                "active_id": self._active_id,
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _active_conv(self) -> dict | None:
        for c in self._conversations:
            if c["id"] == self._active_id:
                return c
        return None

    def _new_chat(self, select=True, save=True):
        conv = {
            "id": str(uuid.uuid4()),
            "title": "New chat",
            "created": time.time(),
            "updated": time.time(),
            "messages": [],
        }
        self._conversations.append(conv)
        if select:
            self._active_id = conv["id"]
        if save:
            self._save_conversations()
        self._render_active()
        self._refresh_sidebar()

    def _switch_conversation(self, cid: str):
        self._active_id = cid
        self._save_conversations()
        self._render_active()

    def _rename_conversation(self, cid: str, old_title: str):
        old = old_title or "New chat"
        title, ok = QInputDialog.getText(self, "Rename chat", "Title:", text=old)
        if ok and title.strip():
            for c in self._conversations:
                if c["id"] == cid:
                    c["title"] = title.strip()[:40]
                    break
            self._save_conversations()
            self._refresh_sidebar()

    def _delete_conversation(self, cid: str):
        self._conversations = [c for c in self._conversations if c["id"] != cid]
        if self._active_id == cid:
            self._active_id = self._conversations[0]["id"] if self._conversations else None
        if not self._conversations:
            self._new_chat(select=True, save=False)
        self._save_conversations()
        self._render_active()
        self._refresh_sidebar()

    def _maybe_title(self, conv: dict, role: str, body: str):
        if role == "you" and conv["title"] == "New chat" and body:
            conv["title"] = body[:28]

    def _append_log(self, text: str):
        conv = self._active_conv()
        if conv is None:
            return
        role, body = _route_line(text)
        conv["messages"].append({
            "role": role, "text": body, "time": time.strftime("%H:%M"),
        })
        if len(conv["messages"]) > 200:
            conv["messages"] = conv["messages"][-200:]
        conv["updated"] = time.time()
        self._maybe_title(conv, role, body)
        self._save_conversations()
        self._render_active()
        self._refresh_sidebar()

    def _render_active(self):
        conv = self._active_conv()
        self.chat_view.clear()
        if conv:
            self.chat_view.set_messages(conv.get("messages", []))

    def _refresh_sidebar(self):
        convs = []
        for c in self._conversations:
            n = len(c.get("messages", []))
            meta = f"{time.strftime('%H:%M', time.localtime(c.get('updated', 0)))} · {n} msg"
            convs.append({"id": c["id"], "title": c.get("title", "New chat"), "meta": meta})
        self.sidebar.set_conversations(convs, self._active_id)

    # ---------------------------------------------------------------- chat
    def _build_chat_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(_CHAT_MIN_W)
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.chat_view = ChatView()
        lay.addWidget(self.chat_view, 1)

        self.chat_bar = ChatInputBar()
        lay.addWidget(self.chat_bar)

        # file chip
        self._chip = QFrame()
        self._chip.setStyleSheet(
            "QFrame { background: #131316; border: 1px solid #232329;"
            " border-radius: 10px; }")
        chip_lay = QHBoxLayout(self._chip)
        chip_lay.setContentsMargins(14, 4, 6, 4)
        chip_lay.setSpacing(8)
        self._chip_label = QLabel("")
        self._chip_label.setFont(_sans(9))
        self._chip_label.setStyleSheet(
            f"color: {C.TEXT_MED}; background: transparent; border: none;")
        chip_lay.addWidget(self._chip_label, 1)
        clear_btn = QPushButton("×")
        clear_btn.setFixedSize(22, 22)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #797672; border: none; }"
            "QPushButton:hover { color: #ff5f57; }")
        clear_btn.clicked.connect(self.chat_bar.clear_file_requested)
        chip_lay.addWidget(clear_btn)
        self._chip.hide()
        lay.addWidget(self._chip)
        return w

    def _send(self, txt: str):
        txt = txt.strip()
        if not txt:
            return
        self._append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for Calcifer", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_current_file(path)

    def _set_current_file(self, path: str):
        try:
            p = Path(path)
            size = _fmt_size(p.stat().st_size)
            self._current_file = path
            self._chip_label.setText(f"File: {p.name}  ·  {size}")
            self._chip.show()
            self._append_log(f"FILE: {p.name} ({size}) loaded")
            if self.on_text_command:
                msg = (
                    f"[FILE_UPLOADED] path={path} | name={p.name} | "
                    f"type={p.suffix.lstrip('.')} | size={size} | "
                    f"Briefly tell the user you can see the file '{p.name}' "
                    f"({size}) has been uploaded and ask what they'd like to do with it."
                )
                threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()
        except Exception:
            pass

    def _clear_file(self):
        self._current_file = None
        self._chip.hide()

    # ----------------------------------------------------------- companion
    def _apply_state(self, state: str):
        self.companion.set_state(state)

    def _apply_emotion(self, emotion: str):
        self.companion.set_emotion(emotion)

    def _toggle_mute(self):
        self._muted = not self._muted
        self.companion.set_muted(self._muted)
        if self._muted:
            self._apply_state("MUTED")
            self._append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._append_log("SYS: Microphone active.")

    # ------------------------------------------------------------ sidebar
    def _toggle_sidebar(self):
        collapsed = self.sidebar.width() == _SIDEBAR_W_MIN
        self.sidebar.set_collapsed(not collapsed)

    def _tick_clock(self):
        now = time.strftime("%H:%M")
        self.sidebar.set_clock(now)

    # ------------------------------------------------------------ settings
    def _load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self._lite = bool(data.get("lite", False))
        except Exception:
            self._lite = False
        self.companion.set_lite(self._lite)

    def _save_settings(self):
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps({"lite": self._lite}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _open_settings(self):
        dlg = SettingsDialog(self._lite, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._lite = dlg.lite()
            self._save_settings()
            self.companion.set_lite(self._lite)

    # ------------------------------------------------------------ window
    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ------------------------------------------------------------ setup
    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (bool(d.get("gemini_api_key")) and
                    bool(d.get("openrouter_api_key")) and
                    bool(d.get("os_system")))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        ow, oh = 440, 470
        cw = self.centralWidget()
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 440, 470
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({
                "gemini_api_key":     key,
                "openrouter_api_key": or_key,
                "os_system":          os_name,
            }, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._append_log("SYS: Initialised. OS=%s. Calcifer online." % os_name.upper())

# ---------------------------------------------------------------------------
# Public backend-facing API (must stay compatible with main.py)
# ---------------------------------------------------------------------------
class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_emotion(self, emotion: str):
        self._win._emotion_sig.emit(emotion)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
