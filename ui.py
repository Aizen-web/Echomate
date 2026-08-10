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
    QMimeData, QPointF, QRectF, Qt, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QDragEnterEvent, QDropEvent, QFont, QKeySequence,
    QLinearGradient, QPainter, QPen, QBrush, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
    QWidget,
)

from calcifer_blob import CalciferBlob

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
_MIN_W,     _MIN_H     = 680, 560
_SIDEBAR_W  = 210
_SIDEBAR_W_MIN = 58
_CHAT_MIN_W = 300
_CHAT_RAIL_W = 44
_CHAT_AUTO_COLLAPSE_W = 860

_OS = platform.system()

_LITE = False  # reduced-motion mode (toggled in Settings)

# ---------------------------------------------------------------------------
# Emotion -> colour mapping (drives the companion glow + face tint)
# ---------------------------------------------------------------------------
EMOTION_COLORS = {
    "happy":     "#FFB020",  # Deep warm gold
    "proud":     "#FFB020",
    "playful":   "#FFB020",
    "love":      "#FF8FB3",  # Warm rose
    "excited":   "#FF5E6E",  # Vivid coral / hot pink
    "surprised": "#FF5E6E",
    "thinking":  "#8B7CFF",  # Rich violet
    "curious":   "#8B7CFF",
    "focused":   "#8B7CFF",
    "calm":      "#4FC6E8",  # Jewel teal
    "sleepy":    "#4FC6E8",
    "sad":       "#4FC6E8",
    "angry":     "#FF4B5C",  # Ember red
    "annoyed":   "#FF4B5C",
    "error":     "#FF4B5C",
}

def get_emotion_color(emotion: str) -> QColor:
    return QColor(EMOTION_COLORS.get(emotion.lower(), "#FFB020"))

# ---------------------------------------------------------------------------
# Deep glass chrome palette
# ---------------------------------------------------------------------------
class C:
    BG         = "#0a0a0d"   # deep charcoal
    CHROME     = "#101014"
    PANEL      = "#15141a"
    PANEL2     = "#1b1a21"
    BORDER     = "#26252c"
    BORDER_HI  = "#3a3942"
    TEXT       = "#f2efe9"
    TEXT_MED   = "#c3c0b9"
    TEXT_DIM   = "#8f8b84"
    ACC        = "#FFB020"
    ACC_HI     = "#FFC554"
    ACC_DIM    = "#8A5A14"
    GREEN      = "#5BE3A6"
    RED        = "#FF4B5C"
    WHITE      = "#f8f5f0"

    # glass material tokens
    GLASS        = "rgba(255,255,255,0.04)"
    GLASS_HI     = "rgba(255,255,255,0.07)"
    GLASS_BORDER = "rgba(255,255,255,0.10)"
    EDGE         = "rgba(255,255,255,0.18)"

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

def _sans(size=10, weight=QFont.Weight.Normal) -> QFont:
    f = QFont("Segoe UI", int(size)); f.setWeight(weight); return f

def _serif(size=20, weight=QFont.Weight.Bold) -> QFont:
    f = QFont("Georgia", int(size)); f.setWeight(weight); return f

def _acc_gradient():
    return ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #FFC554, stop:1 #F0A020)")

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
# Top strip: full-width wordmark + status readout
# ---------------------------------------------------------------------------
class TopStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 2, 16, 2)
        lay.setSpacing(8)

        mark = QLabel("◆ CALCIFER")
        mark.setFont(_serif(13))
        mark.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(mark)

        tag = QLabel("LIVE COMPANION")
        tag.setFont(_sans(8, QFont.Weight.DemiBold))
        tag.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(tag)

        lay.addStretch(1)

        self._led = QLabel("●")
        self._led.setFont(_sans(11))
        self._led.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._led)

        self._status = QLabel("Initialising…")
        self._status.setFont(_sans(9, QFont.Weight.DemiBold))
        self._status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._status)

    def set_status(self, text: str, color: str):
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color}; background: transparent;")
        self._led.setStyleSheet(f"color: {color}; background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(30, 28, 32, 120))
        g.setColorAt(1.0, QColor(20, 19, 22, 150))
        p.fillRect(r, QBrush(g))

        # bottom divider with a subtle amber glow
        d = QLinearGradient(r.left(), 0, r.right(), 0)
        c0 = QColor(C.ACC); c0.setAlpha(16)
        c1 = QColor(C.ACC); c1.setAlpha(70)
        c2 = QColor(C.ACC); c2.setAlpha(16)
        d.setColorAt(0.0, c0); d.setColorAt(0.5, c1); d.setColorAt(1.0, c2)
        p.fillRect(QRectF(0, r.height() - 2, r.width(), 2), d)

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
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; border: none; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.14); border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.24); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._container = QWidget()
        self._container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._container.setStyleSheet("background: transparent;")
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(16, 18, 16, 14)
        self._lay.setSpacing(8)
        self._lay.addStretch(1)
        self.setWidget(self._container)

        self._empty = self._build_empty()
        self._lay.insertWidget(0, self._empty, 1)

        self._bubbles: list[QWidget] = []
        self._near_bottom = True
        self.verticalScrollBar().valueChanged.connect(self._track_scroll)

    def _build_empty(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        v = QVBoxLayout(w)
        v.addStretch(1)

        glow = QFrame()
        glow.setFixedSize(64, 64)
        glow.setStyleSheet(
            "background: qradialgradient(cx:0.5, cy:0.5, radius:0.6,"
            " stop:0 rgba(255,176,32,0.30), stop:1 rgba(255,176,32,0.0));"
            " border: none; border-radius: 32px;")
        v.addWidget(glow, alignment=Qt.AlignmentFlag.AlignCenter)
        v.addSpacing(6)

        title = QLabel("Calcifer")
        title.setFont(_serif(34))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        v.addWidget(title)

        sub = QLabel("Your fiery companion is ready when you are.")
        sub.setFont(_sans(10.5))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        v.addWidget(sub)
        v.addSpacing(4)

        hint = QLabel("Speak, type, or drop a file to begin.")
        hint.setFont(_sans(8.5))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        v.addWidget(hint)

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
        outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        h = QHBoxLayout(outer)
        h.setContentsMargins(0, 0, 0, 0)

        if role == "sys":
            lbl = QLabel(text)
            lbl.setFont(_sans(8.5))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lbl.setMaximumWidth(460)
            h.addStretch(1)
            h.addWidget(lbl)
            h.addStretch(1)
            return outer

        bubble = QFrame()
        bubble.setMaximumWidth(480)
        if role == "you":
            bubble.setStyleSheet(
                "QFrame { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                " stop:0 rgba(255,176,32,0.20), stop:1 rgba(255,176,32,0.09));"
                " border: 1px solid rgba(255,176,32,0.40); border-radius: 12px; }")
        elif role == "err":
            bubble.setStyleSheet(
                "QFrame { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                " stop:0 rgba(255,75,92,0.16), stop:1 rgba(255,75,92,0.07));"
                " border: 1px solid rgba(255,75,92,0.45); border-radius: 12px; }")
        else:
            bubble.setStyleSheet(
                "QFrame { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                " stop:0 rgba(255,255,255,0.07), stop:1 rgba(255,255,255,0.03));"
                " border: 1px solid rgba(255,255,255,0.11); border-radius: 12px; }")

        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(12, 8, 12, 7)
        inner.setSpacing(2)

        lbl = QLabel(text)
        lbl.setFont(_sans(10))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        color = {"you": C.WHITE, "err": C.RED, "ai": C.TEXT}.get(role, C.TEXT)
        lbl.setStyleSheet(f"color: {color}; background: transparent;")
        inner.addWidget(lbl)

        if ts:
            t = QLabel(ts)
            t.setFont(_sans(7))
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 14)
        lay.setSpacing(8)

        self._attach = QPushButton("＋")
        self._attach.setFixedSize(38, 38)
        self._attach.setToolTip("Attach a file")
        self._attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach.setFont(_sans(15, QFont.Weight.Bold))
        self._attach.setStyleSheet(self._ghost_btn())
        self._attach.clicked.connect(self.attach_requested.emit)
        lay.addWidget(self._attach)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Calcifer…")
        self._input.setFont(_sans(10))
        self._input.setFixedHeight(38)
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05); color: #f2efe9;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 19px;
                padding: 0 14px; selection-background-color: rgba(255,176,32,0.35);
            }
            QLineEdit:focus { border: 1px solid rgba(255,176,32,0.65); }
        """)
        self._input.textChanged.connect(self._sync_send)
        self._input.returnPressed.connect(self._emit_send)
        lay.addWidget(self._input, 1)

        self._send = QPushButton("Send")
        self._send.setFixedSize(66, 38)
        self._send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send.setFont(_sans(9.5, QFont.Weight.Bold))
        self._send.clicked.connect(self._emit_send)
        self._send_glow = QGraphicsDropShadowEffect(self._send)
        self._send_glow.setBlurRadius(18)
        self._send_glow.setOffset(0, 0)
        self._send_glow.setColor(QColor(255, 176, 32, 150))
        self._send.setGraphicsEffect(self._send_glow)
        lay.addWidget(self._send)
        self._sync_send("")

    @staticmethod
    def _ghost_btn():
        return """
            QPushButton {
                background: rgba(255,255,255,0.05); color: #c3c0b9;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 19px;
            }
            QPushButton:hover {
                color: #FFB020; border: 1px solid rgba(255,176,32,0.55);
                background: rgba(255,176,32,0.10);
            }
            QPushButton:pressed { background: rgba(255,176,32,0.18); }
        """

    def _sync_send(self, text: str):
        self._send.setEnabled(bool(text.strip()))
        self._send_glow.setEnabled(bool(text.strip()))
        if text.strip():
            self._send.setStyleSheet(f"""
                QPushButton {{
                    background: {_acc_gradient()}; color: #1c1205;
                    border: none; border-radius: 19px; font-weight: bold;
                }}
                QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #FFD27A, stop:1 #F0A020); }}
                QPushButton:pressed {{ background: #E09418; }}
            """)
        else:
            self._send.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.05); color: #6d6a66;
                    border: none; border-radius: 19px; font-weight: bold;
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumHeight(50)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 5, 10, 5)
        lay.setSpacing(6)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._title = QLabel(title)
        self._title.setFont(_sans(10, QFont.Weight.DemiBold))
        self._title.setStyleSheet("color: #f2efe9; background: transparent;")
        col.addWidget(self._title)
        self._meta = QLabel(meta)
        self._meta.setFont(_sans(7.5))
        self._meta.setStyleSheet("color: #8f8b84; background: transparent;")
        col.addWidget(self._meta)
        lay.addLayout(col, 1)

        self._x = QPushButton("×")
        self._x.setFixedSize(20, 20)
        self._x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._x.setStyleSheet("""
            QPushButton { background: transparent; color: #8f8b84; border: none; }
            QPushButton:hover { color: #FF4B5C; }
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
    task_toggle_requested  = pyqtSignal()

    _TASK_STATUS_COLOR = {
        "pending":   C.TEXT_DIM,
        "running":   C.ACC,
        "completed": C.GREEN,
        "failed":    C.RED,
        "cancelled": C.TEXT_DIM,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(_SIDEBAR_W)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._expanded = True
        self._tasks_open = False
        self._id_to_item: dict[str, QListWidgetItem] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
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
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,176,32,0.22), stop:1 rgba(255,176,32,0.10));
                color: #FFB020;
                border: 1px solid rgba(255,176,32,0.45); border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,176,32,0.32), stop:1 rgba(255,176,32,0.16));
            }
            QPushButton:pressed { background: rgba(255,176,32,0.24); }
        """)
        self._new_btn.clicked.connect(self.new_chat_requested.emit)
        lay.addWidget(self._new_btn)
        lay.addSpacing(6)

        # Conversation list
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: 0; }
            QListWidget::item {
                background: transparent; border: none; border-radius: 10px;
                padding: 1px;
            }
            QListWidget::item:hover {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.06);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(255,176,32,0.26), stop:1 rgba(255,176,32,0.06));
                border: 1px solid rgba(255,176,32,0.45);
                border-left: 3px solid #FFB020;
            }
            QScrollBar:vertical { background: transparent; width: 6px; border: none; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.14); border-radius: 3px; min-height: 20px; }
        """)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        lay.addWidget(self._list, 1)

        # --- Background task activity feed (collapsed by default) ---
        self._tasks_btn = QPushButton("▤  Tasks")
        self._tasks_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tasks_btn.setFixedHeight(32)
        self._tasks_btn.setFont(_sans(9.5))
        self._tasks_btn.setStyleSheet(self._bottom_btn_style())
        self._tasks_btn.clicked.connect(self.task_toggle_requested.emit)
        lay.addWidget(self._tasks_btn)

        self._tasks_box = QFrame()
        self._tasks_box.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.04);"
            " border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }")
        self._tasks_lay = QVBoxLayout(self._tasks_box)
        self._tasks_lay.setContentsMargins(10, 8, 10, 8)
        self._tasks_lay.setSpacing(5)
        self._tasks_box.hide()
        lay.addWidget(self._tasks_box)

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
                background: rgba(255,255,255,0.05); color: #c3c0b9;
                border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;
            }
            QPushButton:hover {
                color: #FFB020; border: 1px solid rgba(255,176,32,0.55);
                background: rgba(255,176,32,0.10);
            }
        """

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # Translucent glass fill
        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(28, 26, 30, 150))
        g.setColorAt(1.0, QColor(17, 16, 19, 160))
        p.fillRect(r, QBrush(g))

        # Top edge highlight (light catching the rim)
        hi = QLinearGradient(r.left(), 0, r.right(), 0)
        hi.setColorAt(0.0, QColor(255, 255, 255, 0))
        hi.setColorAt(0.5, QColor(255, 255, 255, 42))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, r.width(), 1), hi)

        # Right glowing divider
        d = QLinearGradient(0, r.top(), 0, r.bottom())
        c0 = QColor(C.ACC); c0.setAlpha(18)
        c1 = QColor(C.ACC); c1.setAlpha(95)
        c2 = QColor(C.ACC); c2.setAlpha(18)
        d.setColorAt(0.0, c0); d.setColorAt(0.5, c1); d.setColorAt(1.0, c2)
        p.fillRect(QRectF(r.width() - 2, 0, 2, r.height()), d)

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

    def set_tasks(self, tasks: list[dict]):
        """Refresh the background-task activity feed (sidebar section)."""
        running = sum(1 for t in tasks if t.get("status") == "running")
        total = len(tasks)
        if running:
            label = f"▤  Tasks ({running} running)"
        elif total:
            label = f"▤  Tasks ({total})"
        else:
            label = "▤  Tasks"
        self._tasks_btn.setText(label)

        # Rebuild the task list lazily.
        while self._tasks_lay.count():
            item = self._tasks_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not tasks:
            empty = QLabel("No background tasks yet.")
            empty.setFont(_sans(8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            self._tasks_lay.addWidget(empty)
        else:
            for t in tasks[-6:][::-1]:
                row = self._make_task_row(t)
                self._tasks_lay.addWidget(row)

    @staticmethod
    def _make_task_row(t: dict) -> QLabel:
        status = t.get("status", "pending")
        color = Sidebar._TASK_STATUS_COLOR.get(status, C.TEXT_DIM)
        goal = t.get("goal", "")
        if len(goal) > 34:
            goal = goal[:33] + "…"
        lbl = QLabel(f"● {goal}")
        lbl.setFont(_sans(7.5))
        lbl.setWordWrap(True)
        lbl.setToolTip(status)
        lbl.setStyleSheet(f"color: {color}; background: transparent;")
        return lbl

    def toggle_tasks(self):
        self._tasks_open = not self._tasks_open
        self._tasks_box.setVisible(self._tasks_open)
        self._tasks_btn.setText(
            "▤  Tasks" if not self._tasks_open else "▤  Tasks (hide)")

    def set_collapsed(self, collapsed: bool):
        self._expanded = not collapsed
        self.setFixedWidth(_SIDEBAR_W_MIN if collapsed else _SIDEBAR_W)
        self._identity.setVisible(not collapsed)
        self._tagline.setVisible(not collapsed)
        self._list.setVisible(not collapsed)
        self._clock.setVisible(not collapsed)
        self._tasks_btn.setVisible(not collapsed)
        self._tasks_box.setVisible(not collapsed and self._tasks_open)
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
            "QMenu { background: rgba(24,23,27,235); color: #f2efe9;"
            " border: 1px solid rgba(255,255,255,0.12); border-radius: 10px;"
            " padding: 4px; }"
            "QMenu::item { padding: 6px 18px; border-radius: 6px; }"
            "QMenu::item:selected { background: rgba(255,176,32,0.18); }")
        act_rename = menu.addAction("Rename")
        act_delete = menu.addAction("Delete")
        chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        if chosen == act_rename and cid:
            self.rename_requested.emit(cid, "")
        elif chosen == act_delete and cid:
            self.delete_requested.emit(cid)

# ---------------------------------------------------------------------------
# Companion stage (center): layered glow + ambient rings behind the face
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
        self.setMinimumSize(380, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._state = "INITIALISING"
        self._muted = False
        self._lite  = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Minimal glass clock, tucked into the top corner of the stage.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        self._clock = QLabel("--:--")
        self._clock.setFont(_sans(9, QFont.Weight.DemiBold))
        self._clock.setStyleSheet(
            "QLabel { color: rgba(255,255,255,0.55);"
            " background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 9px;"
            " padding: 3px 10px; }")
        top.addWidget(self._clock)
        lay.addLayout(top)

        lay.addStretch(1)

        self.blob = CalciferBlob()
        self.blob.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
        lay.addWidget(self.blob, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(12)

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
        lay.addStretch(2)

        self._style_mute(False)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    def _tick_clock(self):
        self._clock.setText(time.strftime("%H:%M:%S"))

    def set_emotion(self, emotion: str):
        self.blob.set_target_color(get_emotion_color(emotion))

    def set_state(self, state: str):
        self._state = state
        text, color = self.STATE_TEXT.get(state, (f"{state}…", C.TEXT_MED))
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color}; background: transparent;")
        self.blob.set_state(state)

    def set_muted(self, muted: bool):
        self._muted = muted
        self._style_mute(muted)
        self.blob.set_muted(muted)

    def set_lite(self, lite: bool):
        self._lite = lite
        self.blob.set_lite(lite)

    def _style_mute(self, muted: bool):
        if muted:
            self._mute_btn.setText("MUTED")
            self._mute_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(255,75,92,0.22), stop:1 rgba(255,75,92,0.10));
                    color: #FF4B5C;
                    border: 1px solid rgba(255,75,92,0.50); border-radius: 14px;
                }
                QPushButton:hover { background: rgba(255,75,92,0.22); }
            """)
        else:
            self._mute_btn.setText("MIC ON")
            self._mute_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(91,227,166,0.18), stop:1 rgba(91,227,166,0.08));
                    color: #5BE3A6;
                    border: 1px solid rgba(91,227,166,0.45); border-radius: 14px;
                }
                QPushButton:hover { background: rgba(91,227,166,0.20); }
            """)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # Stage base: slightly lighter, warm-centred gradient (reads distinct
        # from the sidebar/chat glass at a glance).
        base = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        base.setColorAt(0.0, QColor(18, 17, 20, 235))
        base.setColorAt(0.5, QColor(21, 18, 20, 235))
        base.setColorAt(1.0, QColor(14, 13, 16, 235))
        p.fillRect(r, QBrush(base))

        # The blob paints its own emotion-synced glow, so the stage itself
        # only adds a faint, colour-synced ambient ring so the whole region
        # reads as one light source without fighting the blob.
        rc = self.blob.current_color()
        cx, cy = r.width() / 2, r.height() / 2
        radius = min(r.width(), r.height()) * 0.52
        pulse = 1.0
        if self._state == "SPEAKING" and not self._lite:
            pulse = 1.12
        if self._muted:
            pulse *= 0.6

        g = QRadialGradient(cx, cy, radius * pulse)
        c = QColor(rc); c.setAlpha(int(34 * pulse))
        g.setColorAt(0.0, c)
        c = QColor(rc); c.setAlpha(0)
        g.setColorAt(1.0, c)
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(r)

        # Rim light along the stage edges
        edge = QColor(rc); edge.setAlpha(26)
        p.setPen(QPen(edge, 2))
        p.drawLine(0, 0, r.width(), 0)
        p.drawLine(0, r.height() - 1, r.width(), r.height() - 1)

# ---------------------------------------------------------------------------
# Settings dialog (glass)
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, lite: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(380, 380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(10)

        title = QLabel("Emotion palette")
        title.setFont(_sans(11, QFont.Weight.Bold))
        title.setStyleSheet("color: #f2efe9; background: transparent;")
        v.addWidget(title)

        groups = [
            ("Happy · Proud · Playful", "#FFB020"),
            ("Excited · Surprised",     "#FF5E6E"),
            ("Thinking · Curious · Focused", "#8B7CFF"),
            ("Calm · Sleepy · Sad",     "#4FC6E8"),
            ("Angry · Annoyed · Error", "#FF4B5C"),
            ("Love",                    "#FF8FB3"),
        ]
        for label, col in groups:
            row = QHBoxLayout()
            swatch = QFrame()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                f"background: qradialgradient(cx:0.5, cy:0.5, radius:0.6,"
                f" stop:0 {col}, stop:1 {QColor(col).darker(150).name()});"
                f" border-radius: 8px; border: none;")
            row.addWidget(swatch)
            lbl = QLabel(label)
            lbl.setFont(_sans(9.5))
            lbl.setStyleSheet("color: #c3c0b9; background: transparent;")
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
            " border: 1px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.05); }"
            "QCheckBox::indicator:checked { background: #FFB020; border: 1px solid #FFB020; }")
        v.addWidget(self._lite)

        v.addStretch(1)

        btn = QPushButton("Done")
        btn.setFixedHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_acc_gradient()}; color: #1c1205;
                border: none; border-radius: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #FFD27A, stop:1 #F0A020); }}
        """)
        btn.clicked.connect(self.accept)
        v.addWidget(btn)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(34, 32, 37, 245))
        g.setColorAt(1.0, QColor(20, 19, 23, 245))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 176, 32, 70), 1.5))
        p.drawRoundedRect(r, 16, 16)
        # top sheen
        sh = QRectF(r.left() + 6, r.top() + 6, r.width() - 12, 26)
        sg = QLinearGradient(0, sh.top(), 0, sh.bottom())
        sg.setColorAt(0.0, QColor(255, 255, 255, 26))
        sg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(sg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(sh, 12, 12)

    def lite(self) -> bool:
        return self._lite.isChecked()

# ---------------------------------------------------------------------------
# Setup overlay (glass, first run)
# ---------------------------------------------------------------------------
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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
        sep.setStyleSheet("color: rgba(255,255,255,0.10);")
        lay.addWidget(sep)
        lay.addSpacing(4)

        lay.addWidget(_lbl("GEMINI API KEY", _sans(8, QFont.Weight.Bold), C.TEXT_DIM,
                           Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(_sans(10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(self._input_style("#FFB020"))
        lay.addWidget(self._key_input)
        lay.addSpacing(8)

        lay.addWidget(_lbl("OPENROUTER API KEY", _sans(8, QFont.Weight.Bold), C.TEXT_DIM,
                           Qt.AlignmentFlag.AlignLeft))
        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-…")
        self._or_input.setFont(_sans(10))
        self._or_input.setFixedHeight(32)
        self._or_input.setStyleSheet(self._input_style("#FFB020"))
        lay.addWidget(self._or_input)

        lay.addSpacing(12)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.10);")
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
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_acc_gradient()}; color: #1c1205;
                border: none; border-radius: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #FFD27A, stop:1 #F0A020); }}
        """)
        init_btn.clicked.connect(self._submit)
        lay.addWidget(init_btn)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(30, 28, 33, 244))
        g.setColorAt(1.0, QColor(16, 15, 19, 244))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 176, 32, 80), 1.5))
        p.drawRoundedRect(r, 16, 16)

    @staticmethod
    def _input_style(accent: str):
        return f"""
            QLineEdit {{
                background: rgba(255,255,255,0.05); color: #f2efe9;
                border: 1px solid rgba(255,255,255,0.14); border-radius: 8px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
        """

    def _sel(self, key: str):
        self._sel_os = key
        colors = {"windows": "#FFB020", "mac": "#5BE3A6", "linux": "#5BE3A6"}
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
                        background: rgba(255,255,255,0.05); color: #c3c0b9;
                        border: 1px solid rgba(255,255,255,0.12); border-radius: 8px;
                    }}
                    QPushButton:hover {{
                        color: #f2efe9; border: 1px solid rgba(255,255,255,0.24);
                    }}
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
# Base pane: rich gradient background behind everything
# ---------------------------------------------------------------------------
class _BasePane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # Deep charcoal base with subtle colour movement
        g = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
        g.setColorAt(0.00, QColor("#121116"))
        g.setColorAt(0.55, QColor("#0b0a0d"))
        g.setColorAt(1.00, QColor("#070709"))
        p.fillRect(r, QBrush(g))

        # Warm ember tone bleeding in from the bottom-left
        ember = QRadialGradient(r.left(), r.bottom(), max(r.width(), r.height()) * 0.75)
        c = QColor("#3a1c08"); c.setAlpha(72)
        ember.setColorAt(0.0, c)
        c = QColor("#3a1c08"); c.setAlpha(0)
        ember.setColorAt(1.0, c)
        p.fillRect(r, ember)

        # Cool near-black from the top-right
        cool = QRadialGradient(r.right(), r.top(), max(r.width(), r.height()) * 0.85)
        c = QColor("#101a2e"); c.setAlpha(64)
        cool.setColorAt(0.0, c)
        c = QColor("#101a2e"); c.setAlpha(0)
        cool.setColorAt(1.0, c)
        p.fillRect(r, cool)

# ---------------------------------------------------------------------------
# Glass chat panel (right side)
# ---------------------------------------------------------------------------
class _GlassPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(22, 21, 25, 160))
        g.setColorAt(1.0, QColor(13, 12, 15, 170))
        p.fillRect(r, QBrush(g))

        # Top edge highlight
        hi = QLinearGradient(r.left(), 0, r.right(), 0)
        hi.setColorAt(0.0, QColor(255, 255, 255, 0))
        hi.setColorAt(0.5, QColor(255, 255, 255, 40))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, r.width(), 1), hi)

        # Left glowing divider
        d = QLinearGradient(0, r.top(), 0, r.bottom())
        c0 = QColor(C.ACC); c0.setAlpha(18)
        c1 = QColor(C.ACC); c1.setAlpha(90)
        c2 = QColor(C.ACC); c2.setAlpha(18)
        d.setColorAt(0.0, c0); d.setColorAt(0.5, c1); d.setColorAt(1.0, c2)
        p.fillRect(QRectF(0, 0, 2, r.height()), d)

# ---------------------------------------------------------------------------
# Quick-command palette (Ctrl+K): keyboard-triggerable launcher for common
# tools. Selecting an item either runs it immediately or prompts for the one
# missing argument, then sends it down the normal chat pipeline.
# ---------------------------------------------------------------------------
class CommandPalette(QWidget):
    command_chosen  = pyqtSignal(str)
    action_triggered = pyqtSignal(str)

    # (label, chat template, argument hint, or None, and an optional local action id)
    COMMANDS = [
        ("Open an application",     "Open {arg}",   "Type an app name, e.g. Chrome",   None),
        ("Search the web",          "Search the web for {arg}", "Type a search query",  None),
        ("Check the weather",       "Check the weather in {arg}", "Type a city name",    None),
        ("Set a reminder",          "Set a reminder: {arg}", "Describe the reminder",   None),
        ("Play a YouTube video",    "Play the YouTube video {arg}", "Type a video title", None),
        ("Send a message",          "Send a message to {arg}", "Type a contact name",    None),
        ("Take a screenshot",       "Take a screenshot and analyze it", None,             None),
        ("Manage files",            "Help me manage files: {arg}", "Describe the file task", None),
        ("New chat",                None, None, "new_chat"),
        ("Mute / unmute mic",       None, None, "toggle_mute"),
        ("Open settings",           None, None, "settings"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(460, 420)
        self.hide()

        self._arg_mode = False
        self._pending = ""
        self._input = QLineEdit()
        self._input.setPlaceholderText("What do you want Calcifer to do?")
        self._input.setFont(_sans(10.5))
        self._input.setFixedHeight(38)
        self._input.setStyleSheet("""
            QLineEdit { background: rgba(255,255,255,0.06); color: #f2efe9;
                border: 1px solid rgba(255,176,32,0.45); border-radius: 10px;
                padding: 0 12px; selection-background-color: rgba(255,176,32,0.35); }
        """)
        self._input.textChanged.connect(self._filter)

        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: 0; }
            QListWidget::item { padding: 8px 10px; border-radius: 8px; color: #c3c0b9; }
            QListWidget::item:selected { background: rgba(255,176,32,0.18); color: #FFC554; }
        """)
        self._list.itemClicked.connect(lambda item: self._run_index(
            item.data(Qt.ItemDataRole.UserRole)))

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)
        title = QLabel("QUICK COMMANDS")
        title.setFont(_sans(8, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        v.addWidget(title)
        v.addWidget(self._input)
        v.addWidget(self._list, 1)
        self._hint = QLabel("Esc to close")
        self._hint.setFont(_sans(8))
        self._hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        v.addWidget(self._hint)

        self._refresh()
        self.installEventFilter(self)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(30, 28, 33, 248))
        g.setColorAt(1.0, QColor(17, 16, 20, 248))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 176, 32, 70), 1.5))
        p.drawRoundedRect(r, 16, 16)
        sh = QRectF(r.left() + 6, r.top() + 6, r.width() - 12, 26)
        sg = QLinearGradient(0, sh.top(), 0, sh.bottom())
        sg.setColorAt(0.0, QColor(255, 255, 255, 22))
        sg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(sg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(sh, 12, 12)

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self._arg_mode = False
            self._input.clear()
            self._input.setPlaceholderText("What do you want Calcifer to do?")
            self._hint.setText("Esc to close")
            self._refresh()
            self.show()
            self.raise_()
            self._input.setFocus()

    def _refresh(self):
        self._list.blockSignals(True)
        self._list.clear()
        for i, (label, _tpl, _hint, _act) in enumerate(self.COMMANDS):
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(it)
        self._list.blockSignals(False)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _filter(self, text: str):
        if self._arg_mode:
            return
        q = text.strip().lower()
        self._list.blockSignals(True)
        self._list.clear()
        for i, (label, _tpl, _hint, _act) in enumerate(self.COMMANDS):
            if q and q not in label.lower():
                continue
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(it)
        self._list.blockSignals(False)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _run_index(self, index: int):
        if index is None or index < 0 or index >= len(self.COMMANDS):
            return
        label, template, hint, action = self.COMMANDS[index]
        if action:
            self.action_triggered.emit(action)
            self.hide()
            return
        if template and "{arg}" in template:
            self._arg_mode = True
            self._pending = template
            self._input.setText("")
            self._input.setPlaceholderText(hint or "Type a value…")
            self._hint.setText("Enter to run · Esc to cancel")
            self._list.clear()
            self._input.setFocus()
            return
        self.command_chosen.emit(template)
        self.hide()

    def _commit(self):
        if self._arg_mode:
            arg = self._input.text().strip()
            if not arg:
                return
            self.command_chosen.emit(self._pending.format(arg=arg))
            self.hide()
            return
        it = self._list.currentItem()
        if it is None and self._list.count():
            self._list.setCurrentRow(0)
            it = self._list.currentItem()
        if it is not None:
            self._run_index(it.data(Qt.ItemDataRole.UserRole))

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit()
                return True
            if key == Qt.Key.Key_Down and self._list.count():
                row = self._list.currentRow()
                self._list.setCurrentRow((row + 1) % self._list.count())
                return True
            if key == Qt.Key.Key_Up and self._list.count():
                row = self._list.currentRow()
                self._list.setCurrentRow((row - 1) % self._list.count())
                return True
        return super().eventFilter(obj, event)


# ---------------------------------------------------------------------------
# Glass notification toast: small, auto-dismissing, non-blocking.
# ---------------------------------------------------------------------------
class _Toast(QWidget):
    def __init__(self, text: str, color: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(40)
        self._label = QLabel(text, self)
        self._label.setFont(_sans(9.5, QFont.Weight.DemiBold))
        self._label.setStyleSheet(f"color: {color}; background: transparent;")
        self._label.adjustSize()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        g.setColorAt(0.0, QColor(34, 32, 37, 242))
        g.setColorAt(1.0, QColor(20, 19, 23, 242))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRoundedRect(r, 20, 20)


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
        self._chat_collapsed = False

        central = _BasePane()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top strip: wordmark + live status (helps separate the three regions)
        self._top = TopStrip()
        outer.addWidget(self._top)

        regions = QHBoxLayout()
        regions.setContentsMargins(0, 0, 0, 0)
        regions.setSpacing(0)

        self.sidebar = Sidebar()
        regions.addWidget(self.sidebar)

        # Companion stage = center, primary focal point, largest region
        self.companion = CompanionArea()
        self.companion.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        regions.addWidget(self.companion, stretch=5)

        # Chat panel = right, narrower supporting panel
        self.chat_panel = self._build_chat_panel()
        regions.addWidget(self.chat_panel, stretch=3)

        outer.addLayout(regions, 1)

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
        self.sidebar.task_toggle_requested.connect(self._toggle_tasks)
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
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._toggle_palette)

        # quick-command palette overlay
        self._palette = CommandPalette(self.centralWidget())
        self._palette.command_chosen.connect(self._send)
        self._palette.action_triggered.connect(self._palette_action)

        # background-task monitoring (activity feed + toasts)
        self._task_timer = QTimer(self)
        self._task_timer.timeout.connect(self._poll_tasks)
        self._task_timer.start(1000)
        self._known_task_status: dict[str, str] = {}
        self._toasts: list[_Toast] = []
        self.sidebar.set_tasks([])

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
        w = _GlassPanel()
        w.setMinimumWidth(_CHAT_MIN_W)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Header: label + collapse toggle
        header = QWidget()
        header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        header.setFixedHeight(42)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 8, 0)
        hl.setSpacing(8)
        title = QLabel("CONVERSATION")
        title.setFont(_sans(8.5, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hl.addWidget(title)
        hl.addStretch(1)
        self._chat_collapse_btn = QPushButton("›")
        self._chat_collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_collapse_btn.setFixedSize(26, 26)
        self._chat_collapse_btn.setFont(_sans(11))
        self._chat_collapse_btn.setToolTip("Collapse chat")
        self._chat_collapse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05); color: #c3c0b9;
                border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;
            }
            QPushButton:hover {
                color: #FFB020; border: 1px solid rgba(255,176,32,0.55);
            }
        """)
        self._chat_collapse_btn.clicked.connect(self._toggle_chat)
        hl.addWidget(self._chat_collapse_btn)
        v.addWidget(header)

        # Body (collapsed away by the toggle)
        body = QWidget()
        body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        self.chat_view = ChatView()
        bl.addWidget(self.chat_view, 1)

        self.chat_bar = ChatInputBar()
        bl.addWidget(self.chat_bar)

        # file chip
        self._chip = QFrame()
        self._chip.setStyleSheet("""
            QFrame { background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,176,32,0.35); border-radius: 10px; }
        """)
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
            "QPushButton { background: transparent; color: #8f8b84; border: none; }"
            "QPushButton:hover { color: #FF4B5C; }")
        clear_btn.clicked.connect(self.chat_bar.clear_file_requested)
        chip_lay.addWidget(clear_btn)
        self._chip.hide()
        bl.addWidget(self._chip)

        v.addWidget(body, 1)
        self._chat_body = body
        return w

    def _toggle_chat(self):
        self._chat_collapsed = not self._chat_collapsed
        if self._chat_collapsed:
            self.chat_panel.setMinimumWidth(_CHAT_RAIL_W)
            self.chat_panel.setMaximumWidth(_CHAT_RAIL_W)
            self._chat_body.hide()
            self._chat_collapse_btn.setText("‹")
            self._chat_collapse_btn.setToolTip("Expand chat")
        else:
            self.chat_panel.setMinimumWidth(_CHAT_MIN_W)
            self.chat_panel.setMaximumWidth(16777215)
            self._chat_body.show()
            self._chat_collapse_btn.setText("›")
            self._chat_collapse_btn.setToolTip("Collapse chat")

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
        text, color = CompanionArea.STATE_TEXT.get(state, (f"{state}…", C.TEXT_MED))
        self.companion.set_state(state)
        self._top.set_status(text, color)

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

    # ---------------------------------------------------------- quick cmds
    def _toggle_palette(self):
        self._palette.toggle()
        if self._palette.isVisible():
            cw = self.centralWidget()
            self._palette.move(
                (cw.width()  - self._palette.width()) // 2,
                (cw.height() - self._palette.height()) // 2,
            )

    def _palette_action(self, action: str):
        if action == "new_chat":
            self._new_chat()
        elif action == "toggle_mute":
            self._toggle_mute()
        elif action == "settings":
            self._open_settings()

    # -------------------------------------------------------------- tasks
    def _toggle_tasks(self):
        self.sidebar.toggle_tasks()

    def _poll_tasks(self):
        try:
            from agent.task_queue import get_queue
            tasks = get_queue().get_all_statuses()
        except Exception:
            tasks = []

        for t in tasks:
            tid = t.get("task_id")
            status = t.get("status", "pending")
            prev = self._known_task_status.get(tid)
            if status in ("completed", "failed", "cancelled"):
                if prev not in ("completed", "failed", "cancelled"):
                    self._toast_task(t)
            self._known_task_status[tid] = status

        self.sidebar.set_tasks(tasks)

    def _toast_task(self, t: dict):
        status = t.get("status", "")
        goal = t.get("goal", "")
        color = C.GREEN
        text = "Finished:"
        if status == "failed":
            color = C.RED
            text = "Failed:"
        elif status == "cancelled":
            color = C.TEXT_DIM
            text = "Cancelled:"
        msg = f"{text} {goal[:48]}"
        self._show_toast(msg, color)

    def _show_toast(self, text: str, color: str):
        try:
            toast = _Toast(text, color, self.centralWidget())
            w = toast._label.width() + 40
            cw = self.centralWidget()
            toast.setFixedWidth(min(max(w, 220), 420))
            toast._label.move(24, (toast.height() - toast._label.height()) // 2)
            y = 44 + len(self._toasts) * 46
            toast.move(cw.width() - toast.width() - 16, y)
            toast.show()
            self._toasts.append(toast)
            QTimer.singleShot(3200, lambda: self._dismiss_toast(toast))
        except Exception:
            pass

    def _dismiss_toast(self, toast: _Toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.deleteLater()

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
        ow, oh = 440, 480
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
            ow, oh = 440, 480
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        # Responsive: chat panel is the first thing to collapse when narrow.
        if self.width() < _CHAT_AUTO_COLLAPSE_W and not self._chat_collapsed:
            self._toggle_chat()

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
