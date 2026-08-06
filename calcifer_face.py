"""
Calcifer Face Engine - Eilik-grade glass redesign
Procedural glass character face: glossy eyes, per-emotion expressive shapes,
animated mouth, glass housing with rim light, ambient bloom, crossfade
transitions between expressions, and refined eased idle motion.
"""
import math
import random
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget


DESIGN_W, DESIGN_H = 340, 400


def tri_pulse(elapsed_ms: int, duration_ms: int, amplitude: int) -> int:
    """Triangular pulse: ramps 0→1→0 over duration."""
    if duration_ms <= 0 or elapsed_ms >= duration_ms:
        return 0
    t = elapsed_ms / duration_ms
    return int((1.0 - abs(2.0 * t - 1.0)) * amplitude)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class CalciferFace(QWidget):
    """
    Procedural glass face.
    Modes: 0=speaking, 1=happy, 2=mad, 3=sad, 4=surprised, 5=sleepy,
           6=thinking, 7=confused, 8=excited, 9=love
    """
    MODE_SPEAKING = 0
    MODE_HAPPY = 1
    MODE_MAD = 2
    MODE_SAD = 3
    MODE_SURPRISED = 4
    MODE_SLEEPY = 5
    MODE_THINKING = 6
    MODE_CONFUSED = 7
    MODE_EXCITED = 8
    MODE_LOVE = 9

    EMOTION_MAP = {
        "speaking": 0, "happy": 1, "mad": 2, "sad": 3, "surprised": 4,
        "sleepy": 5, "thinking": 6, "confused": 7, "excited": 8, "love": 9,
        "playful": 1, "proud": 1, "angry": 2, "annoyed": 2, "calm": 5,
        "curious": 6, "focused": 6, "error": 2,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 380)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Expression state
        self.emotion_mode = 0
        self.emotion_start_ms = 0
        self.frozen_look_x = 0
        self.frozen_look_y = 0

        # Crossfade state
        self._out_mode = 0
        self._out_look_x = 0
        self._out_look_y = 0
        self._out_elapsed = 0
        self._xfade_active = False
        self._xfade_start_ms = 0
        self._xfade_dur = 230

        # Idle gaze
        self.look_x = 0
        self.look_y = 0
        self.target_look_x = 0
        self.target_look_y = 0
        self.next_look_change_ms = 0

        # Blink
        self.blink_start_ms = 0
        self.blink_duration_ms = 0
        self.next_blink_ms = 0

        # Warm accent colour (emotion-synced by the UI)
        self._face_color = QColor("#FFB020")
        self.bob_y = 0.0
        self.lite = False

        self.reset_idle_state()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(45)  # ~22 FPS

    def setColor(self, color: QColor):
        """Recolour the face to match the current emotion glow."""
        self._face_color = QColor(color)
        self.update()

    def set_lite(self, lite: bool):
        self.lite = bool(lite)
        self._xfade_dur = 120 if lite else 230

    def reset_idle_state(self):
        now = time.time() * 1000
        self.look_x = 0
        self.look_y = 0
        self.target_look_x = 0
        self.target_look_y = 0
        self.next_look_change_ms = now + random.randint(600, 1800)
        self.blink_start_ms = 0
        self.blink_duration_ms = 0
        self.next_blink_ms = now + random.randint(2200, 5200)

    def setEmotion(self, emotion: str, duration_ms: int = 2500):
        """Change facial expression (with crossfade from the previous one)."""
        mode = self.EMOTION_MAP.get(emotion.lower(), 0)
        now = time.time() * 1000

        if mode != self.emotion_mode:
            self._xfade_active = True
            self._out_mode = self.emotion_mode
            self._out_start_ms = now
            self._out_elapsed = int(now - self.emotion_start_ms)
            self._out_look_x = self.look_x
            self._out_look_y = self.look_y

        if mode != 0:
            self.frozen_look_x = self.look_x
            self.frozen_look_y = self.look_y
            if mode == self.MODE_THINKING:
                self.frozen_look_y = _clamp(self.look_y - 8, -16, -2)

        self.emotion_mode = mode
        self.emotion_start_ms = now
        self.update()

    def _animate(self):
        now = time.time() * 1000

        if self.emotion_mode == self.MODE_SPEAKING:
            # Idle gaze chase (eased)
            if now >= self.next_look_change_ms:
                self.target_look_x = random.randint(-10, 11)
                self.target_look_y = random.randint(-5, 6)
                self.next_look_change_ms = now + random.randint(900, 2400)
            self.look_x += int(round((self.target_look_x - self.look_x) * 0.18))
            self.look_y += int(round((self.target_look_y - self.look_y) * 0.18))

            # Blink
            if self.blink_start_ms == 0 and now >= self.next_blink_ms:
                self.blink_start_ms = now
                self.blink_duration_ms = random.randint(120, 240)
                self.next_blink_ms = now + random.randint(2500, 7000)

            # Gentle organic breathing bob
            self.bob_y = (math.sin(now * 0.0016) * 3.2) if not self.lite else 0.0
        elif not self.lite and self.emotion_mode == self.MODE_EXCITED:
            self.bob_y = math.sin(now * 0.004) * 2.0
        else:
            self.bob_y = 0.0

        self.update()

    def _look_eff(self):
        if self.emotion_mode != self.MODE_SPEAKING:
            return self.frozen_look_x, self.frozen_look_y
        return self.look_x, self.look_y + int(self.bob_y)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = min(self.width() / DESIGN_W, self.height() / DESIGN_H)
        if s <= 0:
            return
        ox = (self.width() - DESIGN_W * s) / 2
        oy = (self.height() - DESIGN_H * s) / 2
        painter.translate(ox, oy)
        painter.scale(s, s)

        now = time.time() * 1000
        self._draw_bloom(painter, now)
        self._draw_housing(painter)

        lx, ly = self._look_eff()

        if self._xfade_active:
            t = (now - self._xfade_start_ms) / self._xfade_dur
            if t >= 1.0:
                self._xfade_active = False
            else:
                self._paint_features(painter, self._out_mode,
                                     self._out_look_x, self._out_look_y,
                                     self._out_elapsed, 1.0 - t)
                self._paint_features(painter, self.emotion_mode, lx, ly,
                                     int(now - self.emotion_start_ms), t)
                return

        self._paint_features(painter, self.emotion_mode, lx, ly,
                             int(now - self.emotion_start_ms), 1.0)

    # ---------------------------------------------------------------- layers
    def _draw_bloom(self, painter: QPainter, now: float):
        """Soft ambient light bloom behind the housing, echoing the emotion."""
        rc = self._face_color
        pulse = 1.0
        if self.lite:
            pulse = 0.9
        elif self.emotion_mode == self.MODE_SPEAKING:
            pulse = 1.15 + 0.10 * math.sin(now * 0.010)
        elif self.emotion_mode == self.MODE_EXCITED:
            pulse = 1.30 + 0.15 * math.sin(now * 0.020)

        cx, cy = DESIGN_W / 2, DESIGN_H * 0.46
        rad = DESIGN_W * 0.62 * pulse
        g = QRadialGradient(cx, cy, rad)
        c = QColor(rc); c.setAlpha(48); g.setColorAt(0.0, c)
        c = QColor(rc); c.setAlpha(16); g.setColorAt(0.55, c)
        c = QColor(rc); c.setAlpha(0);  g.setColorAt(1.0, c)
        painter.setBrush(QBrush(g))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(0, 0, DESIGN_W, DESIGN_H))

    def _draw_housing(self, painter: QPainter):
        """Glass bezel/frame around the face with rim light + inner sheen."""
        rect = QRectF(30, 24, 280, 352)
        rad = 42
        rc = self._face_color

        # Outer rim glow ring (echoes emotion colour)
        rim_out = QColor(rc); rim_out.setAlpha(26)
        painter.setPen(QPen(rim_out, 8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(-6, -6, 6, 6), rad + 6, rad + 6)

        # Translucent glass fill so the bloom/background shows through
        g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        g.setColorAt(0.0, QColor(30, 27, 30, 120))
        g.setColorAt(0.5, QColor(22, 20, 24, 110))
        g.setColorAt(1.0, QColor(13, 12, 15, 120))
        painter.setBrush(QBrush(g))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, rad, rad)

        # Rim light (top + sides catch the accent colour)
        rim = QColor(rc); rim.setAlpha(170)
        painter.setPen(QPen(rim, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)

        # Inner top sheen (glass catching light)
        sheen = QRectF(rect.left() + 5, rect.top() + 5,
                       rect.width() - 10, rect.height() * 0.42)
        sg = QLinearGradient(0, sheen.top(), 0, sheen.bottom())
        sg.setColorAt(0.0, QColor(255, 255, 255, 30))
        sg.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(sg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(sheen, rad - 4, rad - 4)

        # Subtle futuristic corner notches
        notch = QColor(rc); notch.setAlpha(90)
        painter.setPen(QPen(notch, 2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        inset = 10
        top = rect.top() + 12
        bot = rect.bottom() - 12
        left = rect.left() + 12
        right = rect.right() - 12
        painter.drawLine(QPointF(left - inset + 4, top - 2),
                         QPointF(left + inset, top - 2))
        painter.drawLine(QPointF(right - inset, top - 2),
                         QPointF(right + inset - 4, top - 2))
        painter.drawLine(QPointF(left - inset + 4, bot + 2),
                         QPointF(left + inset, bot + 2))
        painter.drawLine(QPointF(right - inset, bot + 2),
                         QPointF(right + inset - 4, bot + 2))

    # -------------------------------------------------------------- features
    def _paint_features(self, painter, mode, lx, ly, elapsed, opacity):
        painter.setOpacity(opacity)

        base_y = 158
        eye_l = (112 + lx, base_y + ly)
        eye_r = (228 + lx, base_y + ly)

        ry_l, ry_r = 44, 44
        cadence = 0
        rx = 40

        if mode == self.MODE_SPEAKING:
            cadence = tri_pulse(elapsed % 340, 340, 20)
            cadence += tri_pulse(elapsed % 210, 210, 10)
            rx += int(math.sin(elapsed * 0.012) * 2.0)
        elif mode == self.MODE_EXCITED:
            cadence = tri_pulse(elapsed % 180, 180, 28)
        elif mode == self.MODE_THINKING:
            cadence = tri_pulse(elapsed % 520, 520, 12)
        elif mode == self.MODE_SURPRISED:
            ry_l = ry_r = 54
            rx = 45
            cadence = tri_pulse(elapsed % 280, 280, 16)
        elif mode == self.MODE_CONFUSED:
            ry_l, ry_r = 42, 30
        else:
            cadence = tri_pulse(elapsed % 340, 340, 22)

        ry_l -= cadence
        ry_r -= cadence

        # Blink (speaking mode only)
        if mode == self.MODE_SPEAKING and self.blink_start_ms != 0:
            be = int(time.time() * 1000 - self.blink_start_ms)
            if be >= self.blink_duration_ms:
                self.blink_start_ms = 0
            else:
                sq = tri_pulse(be, self.blink_duration_ms, 44)
                ry_l -= sq
                ry_r -= sq

        ry_l = _clamp(ry_l, 6, 72)
        ry_r = _clamp(ry_r, 6, 72)

        color = QColor(self._face_color)

        if mode == self.MODE_HAPPY:
            self._eyes_happy(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], color)
        elif mode == self.MODE_MAD:
            self._eyes_mad(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], color)
        elif mode == self.MODE_SAD:
            self._eyes_sad(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], color)
        elif mode == self.MODE_SURPRISED:
            self._eyes_surprised(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], rx, ry_l, color)
        elif mode == self.MODE_SLEEPY:
            self._eyes_sleepy(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], color)
        elif mode == self.MODE_THINKING:
            self._eyes_thinking(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], rx, ry_l, color)
        elif mode == self.MODE_CONFUSED:
            self._eyes_confused(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], rx, ry_l, ry_r, color)
        elif mode == self.MODE_EXCITED:
            self._eyes_excited(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], rx, ry_l, color)
        elif mode == self.MODE_LOVE:
            self._eyes_love(painter, eye_l[0], eye_l[1], eye_r[0], eye_r[1], color)
        else:
            self._glossy_eye(painter, eye_l[0], eye_l[1], rx, ry_l, color)
            self._glossy_eye(painter, eye_r[0], eye_r[1], rx, ry_r, color)

        mouth_y = 252 + ly
        self._draw_mouth(painter, mode, 170 + lx, mouth_y, elapsed, color)

        painter.setOpacity(1.0)

    # ----------------------------------------------------------------- eyes
    def _glossy_eye(self, painter, cx, cy, rx, ry, color, pupil=True,
                    gloss=True, squish=1.0):
        if rx <= 1 or ry <= 1:
            return
        # Squashed-to-a-line state (blink / sleepy)
        if ry < 8:
            painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(cx - rx, cy), QPointF(cx + rx, cy))
            return

        g = QLinearGradient(0, cy - ry, 0, cy + ry)
        g.setColorAt(0.0, QColor(color).lighter(116))
        g.setColorAt(1.0, QColor(color).darker(138))
        painter.setBrush(QBrush(g))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), rx, ry * squish)

        if pupil:
            pc = QColor(color).darker(230)
            painter.setBrush(QBrush(pc))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx + rx * 0.05, cy + ry * 0.20),
                                rx * 0.26, ry * 0.34 * squish)

        if gloss:
            gg = QRadialGradient(cx - rx * 0.35, cy - ry * 0.42, rx * 0.5)
            gg.setColorAt(0.0, QColor(255, 255, 255, 215))
            gg.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(gg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - rx * 0.72, cy - ry * 0.78,
                                       rx * 0.75, ry * 0.75))

    def _eyes_happy(self, painter, lx, ly, rx_, ry_, color):
        pen = QPen(color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Upward crescent (∩)
        painter.drawArc(QRectF(lx - 40, ly - 30, 80, 60), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(rx_ - 40, ry_ - 30, 80, 60), 180 * 16, 180 * 16)

    def _eyes_mad(self, painter, lx, ly, rx_, ry_, color):
        brow = QColor(color).darker(150)
        painter.setPen(QPen(brow, 6, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(lx - 52, ly - 34), QPointF(lx + 4, ly - 16))
        painter.drawLine(QPointF(rx_ + 52, ry_ - 34), QPointF(rx_ - 4, ry_ - 16))
        # Slanted almond eyes
        painter.save()
        painter.translate(lx, ly)
        painter.rotate(14)
        self._glossy_eye(painter, 0, 0, 40, 34, color)
        painter.restore()
        painter.save()
        painter.translate(rx_, ry_)
        painter.rotate(-14)
        self._glossy_eye(painter, 0, 0, 40, 34, color)
        painter.restore()

    def _eyes_sad(self, painter, lx, ly, rx_, ry_, color):
        pen = QPen(color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Downturned crescent (∪)
        painter.drawArc(QRectF(lx - 38, ly - 26, 76, 52), 0 * 16, 180 * 16)
        painter.drawArc(QRectF(rx_ - 38, ry_ - 26, 76, 52), 0 * 16, 180 * 16)

    def _eyes_surprised(self, painter, lx, ly, rx_, ry_, rx, ry, color):
        self._glossy_eye(painter, lx, ly, rx, ry, color, pupil=True, gloss=True)
        self._glossy_eye(painter, rx_, ry_, rx, ry, color, pupil=True, gloss=True)

    def _eyes_sleepy(self, painter, lx, ly, rx_, ry_, color):
        # Half-lidded slits with a lid line
        lid = QColor(color).darker(150)
        for cx in (lx, rx_):
            self._glossy_eye(painter, cx, ly + 4, 40, 11, color,
                             pupil=False, gloss=False)
            painter.setPen(QPen(lid, 4, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 38, ly - 6), QPointF(cx + 38, ly - 6))

    def _eyes_thinking(self, painter, lx, ly, rx_, ry_, rx, ry, color):
        self._glossy_eye(painter, lx, ly, rx, int(ry * 0.92), color)
        self._glossy_eye(painter, rx_, ry_, rx, int(ry * 0.92), color)
        # Thought dots
        d = QColor(color); d.setAlpha(170)
        painter.setPen(QPen(d, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for dx in (-8, 0, 8):
            painter.drawPoint(QPointF(rx_ + dx, ly - 66))

    def _eyes_confused(self, painter, lx, ly, rx_, ry_, rx, ry_l, ry_r, color):
        self._glossy_eye(painter, lx, ly, rx, ry_l, color)
        self._glossy_eye(painter, rx_, ry_ + 6, int(rx * 0.72), ry_r, color)
        # One raised brow
        brow = QColor(color).darker(150)
        painter.setPen(QPen(brow, 5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(rx_ - 30, ry_ - 40), QPointF(rx_ + 26, ry_ - 48))

    def _eyes_excited(self, painter, lx, ly, rx_, ry_, rx, ry, color):
        self._glossy_eye(painter, lx, ly, int(rx * 1.1), ry, color)
        self._glossy_eye(painter, rx_, ry_, int(rx * 1.1), ry, color)
        # Sparkle accents
        sp = QColor(255, 255, 255, 210)
        painter.setPen(QPen(sp, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for cx, cy_ in ((lx - rx, ly - ry), (rx_ + rx, ry_ - ry)):
            painter.drawPoint(QPointF(cx, cy_ - 6))
            painter.drawPoint(QPointF(cx - 6, cy_))
            painter.drawPoint(QPointF(cx + 6, cy_))

    def _heart_path(self, cx, cy, s):
        path = QPainterPath()
        path.addEllipse(QPointF(cx - s * 0.45, cy - s * 0.50), s * 0.55, s * 0.55)
        path.addEllipse(QPointF(cx + s * 0.45, cy - s * 0.50), s * 0.55, s * 0.55)
        path.moveTo(cx - s * 0.95, cy - s * 0.08)
        path.lineTo(cx + s * 0.95, cy - s * 0.08)
        path.lineTo(cx, cy + s * 0.88)
        path.closeSubpath()
        return path

    def _eyes_love(self, painter, lx, ly, rx_, ry_, color):
        for cx, cy_ in ((lx, ly), (rx_, ry_)):
            s = 27
            path = self._heart_path(cx, cy_, s)
            g = QLinearGradient(cx, cy_ - s, cx, cy_ + s)
            g.setColorAt(0.0, QColor(color).lighter(114))
            g.setColorAt(1.0, QColor(color).darker(126))
            painter.setBrush(QBrush(g))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            gg = QRadialGradient(cx - s * 0.3, cy_ - s * 0.45, s * 0.5)
            gg.setColorAt(0.0, QColor(255, 255, 255, 190))
            gg.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(gg))
            painter.drawEllipse(QRectF(cx - s * 0.6, cy_ - s * 0.85,
                                       s * 0.5, s * 0.5))

    # ---------------------------------------------------------------- mouth
    def _draw_mouth(self, painter, mode, cx, cy, elapsed, color):
        dark = QColor(color).darker(165)
        if mode == self.MODE_SPEAKING:
            op = tri_pulse(elapsed % 300, 300, 12)
            h = 6 + op
            w = 54 - op // 2
            r = QRectF(cx - w / 2, cy - h / 2, w, h)
            g = QLinearGradient(0, r.top(), 0, r.bottom())
            g.setColorAt(0.0, QColor(color).lighter(112))
            g.setColorAt(1.0, dark)
            painter.setBrush(QBrush(g))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(r)
        elif mode == self.MODE_HAPPY:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawChord(QRectF(cx - 34, cy - 18, 68, 36), 0 * 16, 180 * 16)
        elif mode == self.MODE_EXCITED:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawChord(QRectF(cx - 40, cy - 26, 80, 52), 0 * 16, 180 * 16)
            # tongue
            tg = QLinearGradient(0, cy, 0, cy + 30)
            tg.setColorAt(0.0, QColor(color).lighter(130))
            tg.setColorAt(1.0, dark)
            painter.setBrush(QBrush(tg))
            painter.drawEllipse(QPointF(cx, cy + 20), 12, 9)
        elif mode == self.MODE_LOVE:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawChord(QRectF(cx - 24, cy - 12, 48, 24), 0 * 16, 180 * 16)
        elif mode == self.MODE_MAD:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawChord(QRectF(cx - 26, cy - 14, 52, 28), 180 * 16, 180 * 16)
            painter.setPen(QPen(dark, 3))
            painter.drawLine(QPointF(cx - 12, cy), QPointF(cx + 12, cy))
        elif mode == self.MODE_SAD:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawChord(QRectF(cx - 20, cy - 12, 40, 24), 180 * 16, 180 * 16)
        elif mode == self.MODE_SURPRISED:
            g = QLinearGradient(0, cy - 15, 0, cy + 15)
            g.setColorAt(0.0, QColor(color).lighter(112))
            g.setColorAt(1.0, dark)
            painter.setBrush(QBrush(g))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 13, 16)
        elif mode == self.MODE_SLEEPY:
            painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 14, cy), QPointF(cx + 14, cy))
        elif mode == self.MODE_THINKING:
            painter.setBrush(QBrush(dark))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 11, 8)
        elif mode == self.MODE_CONFUSED:
            path = QPainterPath(QPointF(cx - 22, cy))
            path.quadTo(cx - 11, cy - 8, cx, cy)
            path.quadTo(cx + 11, cy + 8, cx + 22, cy)
            painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        else:
            painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 12, cy), QPointF(cx + 12, cy))
