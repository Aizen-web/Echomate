"""
Calcifer Blob - minimal animated companion orb.

Replaces the facial rig (eyes / mouth / expression shapes) with a single
glowing plasma orb. There is no face: emotion is communicated purely through
colour, and operating state (idle / listening / thinking / speaking) purely
through motion. Colour is driven by the existing emotion protocol
(EMOTION_COLORS lives in ui.py; the CompanionArea maps emotion -> QColor and
hands it to this widget). The colour eases over ~300 ms and then HOLDSTEADY
until a new emotion arrives - it never drifts or fades while idle.

Motion states (distinguishable by movement alone):
  idle      - slow breathing scale + a slowly drifting surface shimmer
  listening - slow inward pull / gentle contraction + ripple toward center
  thinking  - calm orb with a slow internal swirl
  speaking  - rhythmic pulse + expanding ripple rings (no live audio
              amplitude is wired through in this pass, so speech is driven
              by a convincing rhythmic animated pattern)
"""
import math
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget


class CalciferBlob(QWidget):
    STATE_IDLE      = 0
    STATE_LISTENING = 1
    STATE_THINKING  = 2
    STATE_SPEAKING  = 3

    STATE_MAP = {
        "INITIALISING": STATE_IDLE,
        "MUTED":        STATE_IDLE,
        "LISTENING":    STATE_LISTENING,
        "THINKING":     STATE_THINKING,
        "PROCESSING":   STATE_THINKING,
        "SPEAKING":     STATE_SPEAKING,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 340)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._state         = self.STATE_IDLE
        self._color         = QColor("#FFB020")
        self._target_color  = QColor("#FFB020")
        self._ease_progress = 1.0
        self._muted         = False
        self._lite          = False
        self._t0            = time.time() * 1000

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)

    # ------------------------------------------------------------------ API
    def set_target_color(self, color: QColor):
        if QColor(color) == self._color:
            return
        self._target_color = QColor(color)
        self._ease_progress = 0.0
        self.update()

    def set_state(self, state: str):
        self._state = self.STATE_MAP.get(state, self.STATE_IDLE)
        self.update()

    def set_muted(self, muted: bool):
        self._muted = bool(muted)

    def set_lite(self, lite: bool):
        self._lite = bool(lite)
        self._timer.setInterval(60 if lite else 30)

    def current_color(self) -> QColor:
        return QColor(self._color)

    # --------------------------------------------------------------- update
    def _animate(self):
        if self._ease_progress < 1.0:
            self._ease_progress += 0.10
            if self._ease_progress > 1.0:
                self._ease_progress = 1.0
            t = self._ease_progress
            r = int(self._color.red()   * (1 - t) + self._target_color.red()   * t)
            g = int(self._color.green() * (1 - t) + self._target_color.green() * t)
            b = int(self._color.blue()  * (1 - t) + self._target_color.blue()  * t)
            self._color = QColor(r, g, b)
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        if w < 40 or h < 40:
            return
        cx, cy = w / 2.0, h / 2.0
        base_r = min(w, h) * 0.235
        now = time.time() * 1000
        t = now - self._t0

        color = QColor(self._color)
        if self._muted:
            color.setAlpha(120)

        # State-derived motion parameters
        scale   = 1.0
        wob     = 1.0
        glow_ix = 1.0
        speaking = self._state == self.STATE_SPEAKING
        listening = self._state == self.STATE_LISTENING
        thinking = self._state == self.STATE_THINKING

        if self._lite:
            scale = 1.0
            wob = 0.2
            glow_ix = 0.9
        elif speaking:
            scale = 1.0 + 0.06 * math.sin(t * 0.020) + 0.03 * math.sin(t * 0.037)
            wob = 1.8
            glow_ix = 1.22
        elif thinking:
            scale = 1.0 + 0.015 * math.sin(t * 0.0011)
            wob = 0.7
            glow_ix = 1.10
        elif listening:
            scale = 1.0 + 0.020 * math.sin(t * 0.0013)
            wob = 0.6
            glow_ix = 1.0
        else:  # idle
            scale = 1.0 + 0.024 * math.sin(t * 0.0014)
            wob = 1.0
            glow_ix = 0.95

        if self._muted:
            glow_ix *= 0.55

        bob = 0.0
        if not self._lite and speaking:
            bob = base_r * 0.03 * math.sin(t * 0.024)

        cy_eff = cy + bob
        r_eff = base_r * scale

        # -------------------------------------------------- outer glow
        glow_r = r_eff * 2.5
        gg = QRadialGradient(cx, cy_eff, glow_r)
        c0 = QColor(color); c0.setAlpha(int(88 * glow_ix))
        c1 = QColor(color); c1.setAlpha(int(22 * glow_ix))
        c2 = QColor(color); c2.setAlpha(0)
        gg.setColorAt(0.0, c0)
        gg.setColorAt(0.45, c1)
        gg.setColorAt(1.0, c2)
        p.fillRect(QRectF(0, 0, w, h), QBrush(gg))

        # -------------------------------------------------- blob body
        blob = self._blob_path(cx, cy_eff, r_eff, t, wob)
        bg = QRadialGradient(cx, cy_eff - r_eff * 0.28, r_eff * 1.5)
        bg.setColorAt(0.0, QColor(color).lighter(118))
        bg.setColorAt(0.55, QColor(color))
        bg.setColorAt(1.0, QColor(color).darker(150))
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(blob)

        # Rim light (crisp inner edge catching the emotion colour)
        rim = QColor(color).lighter(130); rim.setAlpha(120)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(rim, max(1.0, r_eff * 0.02)))
        p.drawPath(blob)

        # -------------------------------------------------- inner effects
        p.save()
        p.setClipPath(blob)

        # drifting surface shimmer (idle signature)
        if not self._lite:
            shx = cx + math.sin(t * 0.0004) * r_eff * 0.30
            shy = cy_eff - r_eff * 0.34 + math.cos(t * 0.0003) * r_eff * 0.16
            sh = QRadialGradient(shx, shy, r_eff * 0.9)
            sh.setColorAt(0.0, QColor(255, 255, 255, 66))
            sh.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sh))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(shx, shy), r_eff, r_eff)

        if speaking and not self._lite:
            self._draw_ripples(p, cx, cy_eff, r_eff, t, color)
        elif listening and not self._lite:
            self._draw_inward_ripple(p, cx, cy_eff, r_eff, t, color)
        elif thinking and not self._lite:
            self._draw_swirl(p, cx, cy_eff, r_eff, t, color)

        p.restore()

    # ----------------------------------------------------------- helpers
    def _blob_path(self, cx, cy, base_r, t, wob_amp):
        n = 36
        pts = []
        for i in range(n):
            ang = 2.0 * math.pi * i / n
            r = base_r * (1.0 + wob_amp * (
                0.030 * math.sin(3 * ang + t * 0.0009 + 0.7)
                + 0.019 * math.sin(5 * ang - t * 0.0007 + 2.1)
                + 0.012 * math.sin(7 * ang + t * 0.0005 + 4.2)
            ))
            pts.append(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))

        start = QPointF((pts[-1].x() + pts[0].x()) / 2,
                        (pts[-1].y() + pts[0].y()) / 2)
        path = QPainterPath(start)
        for i in range(n):
            pnt = pts[i]
            nxt = pts[(i + 1) % n]
            mid = QPointF((pnt.x() + nxt.x()) / 2, (pnt.y() + nxt.y()) / 2)
            path.quadTo(pnt, mid)
        path.closeSubpath()
        return path

    def _draw_ripples(self, p, cx, cy, r, t, color):
        """Expanding speech ripples radiating from the orb."""
        phase = t * 0.016
        for k in range(2):
            f = (phase + k * 0.5) % 1.0
            rr = r * (1.0 + f * 0.55)
            alpha = int(70 * (1.0 - f))
            ring = QColor(color).lighter(120); ring.setAlpha(alpha)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ring, 3))
            p.drawEllipse(QPointF(cx, cy), rr, rr)

    def _draw_inward_ripple(self, p, cx, cy, r, t, color):
        """Gentle ripple-toward-center, visually distinct from speaking."""
        phase = t * 0.0016
        for k in range(3):
            f = (phase + k / 3.0) % 1.0
            rr = r * (0.95 - f * 0.72)
            alpha = int(46 * (1.0 - f))
            ring = QColor(color).lighter(118); ring.setAlpha(alpha)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ring, 2))
            p.drawEllipse(QPointF(cx, cy), rr, rr)

    def _draw_swirl(self, p, cx, cy, r, t, color):
        """Slow internal swirl for thinking/processing."""
        base_ang = (t * 0.0011) % 360.0
        for i in range(3):
            start_ang = int((base_ang + i * 120) % 360) * 16
            arc = QRectF(cx - r * 0.62, cy - r * 0.62, r * 1.24, r * 1.24)
            sw = QColor(color).lighter(130); sw.setAlpha(150)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(sw, max(2.0, r * 0.13),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(arc, start_ang, 92 * 16)
        # orbiting mote completes the swirl read
        oa = math.radians((t * 0.0016) % 360.0)
        ox = cx + math.cos(oa) * r * 0.38
        oy = cy + math.sin(oa) * r * 0.38
        mote = QColor(255, 255, 255, 160)
        p.setBrush(QBrush(mote))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(ox, oy), max(2.0, r * 0.05), max(2.0, r * 0.05))
