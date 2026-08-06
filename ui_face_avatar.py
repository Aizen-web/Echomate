"""
Calcifer Face Avatar - Procedural Animation Engine
Ported from OmniBot Pixel (nazirlouis/OmniBot)
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QBrush, QPen, QColor, QRadialGradient
import math
import random
import time

class FaceAvatar(QWidget):
    # Emotion modes
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
    
    def __init__(self, face_path: str = None, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)
        
        # Animation state
        self.emotion_mode = self.MODE_SPEAKING
        self.anim_active = False
        self.anim_start_ms = 0
        self.anim_until_ms = 0
        self.frozen_look_x = 0
        self.frozen_look_y = 0
        
        # Idle animation state
        self.look_x = 0
        self.look_y = 0
        self.target_look_x = 0
        self.target_look_y = 0
        self.next_look_change_ms = self._millis() + random.randint(600, 1800)
        
        self.blink_start_ms = 0
        self.blink_duration_ms = 0
        self.next_blink_ms = self._millis() + random.randint(2200, 5200)
        
        # Differential rendering state
        self.prev_eye_ry_l = 66
        self.prev_eye_ry_r = 66
        self.prev_eye_x_offset = 0
        self.prev_eye_y_offset = 0
        self.has_prev_frame = False
        
        # Colors
        self.eye_color = QColor("#00D4FF")  # Cyan
        self.bg_color = QColor("#000000")
        
        # Animation timer (20 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._updateFrame)
        self.timer.start(50)
    
    def _millis(self):
        return int(time.time() * 1000)
    
    def setEmotion(self, emotion: str, duration_ms: int = 2500):
        """Set facial expression from emotion tag"""
        emotion_map = {
            "happy": self.MODE_HAPPY,
            "excited": self.MODE_EXCITED,
            "playful": self.MODE_HAPPY,
            "proud": self.MODE_HAPPY,
            "curious": self.MODE_THINKING,
            "thinking": self.MODE_THINKING,
            "focused": self.MODE_THINKING,
            "calm": self.MODE_SPEAKING,
            "sad": self.MODE_SAD,
            "angry": self.MODE_MAD,
            "annoyed": self.MODE_MAD,
            "surprised": self.MODE_SURPRISED,
            "sleepy": self.MODE_SLEEPY,
            "error": self.MODE_MAD
        }
        
        self.emotion_mode = emotion_map.get(emotion.lower(), self.MODE_SPEAKING)
        self.anim_active = True
        self.anim_start_ms = self._millis()
        self.anim_until_ms = self.anim_start_ms + duration_ms
        
        if self.emotion_mode != 0:
            self.frozen_look_x = self.look_x
            self.frozen_look_y = self.look_y
        
        self.has_prev_frame = False
        self.update()
    
    def _updateFrame(self):
        """Main animation loop - called at 20 FPS"""
        now = self._millis()
        
        # End animation if duration expired
        if self.anim_active and now >= self.anim_until_ms:
            self.anim_active = False
            self.emotion_mode = self.MODE_SPEAKING
            self.has_prev_frame = False
        
        # Update idle state (gaze, blinks)
        self._updateIdleState()
        
        # Trigger Qt repaint
        self.update()
    
    def _updateIdleState(self):
        """Update autonomous gaze shifts and blinks"""
        now = self._millis()
        
        # Gaze shifts
        if now >= self.next_look_change_ms:
            self.target_look_x = random.randint(-10, 10)
            self.target_look_y = random.randint(-5, 5)
            self.next_look_change_ms = now + random.randint(900, 2400)
        
        # Smooth chase
        if self.look_x != self.target_look_x:
            diff = (self.target_look_x - self.look_x) // 3
            self.look_x += diff if diff != 0 else (1 if self.target_look_x > self.look_x else -1)
        
        if self.look_y != self.target_look_y:
            diff = (self.target_look_y - self.look_y) // 3
            self.look_y += diff if diff != 0 else (1 if self.target_look_y > self.look_y else -1)
        
        # Blink scheduling
        if self.blink_start_ms == 0 and now >= self.next_blink_ms:
            self.blink_start_ms = now
            self.blink_duration_ms = random.randint(120, 240)
            self.next_blink_ms = now + random.randint(2500, 7000)
    
    def paintEvent(self, event):
        """Render face with current emotion"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Calculate eye parameters
        eye_ry_l, eye_ry_r = self._calculateEyeHeight()
        
        # Get eye offsets
        if self.emotion_mode != 0 and self.anim_active:
            eye_x = self.frozen_look_x
            eye_y = self.frozen_look_y
        else:
            eye_x = self.look_x
            eye_y = self.look_y
        
        # Render based on emotion
        self._drawEmotion(painter, eye_x, eye_y, eye_ry_l, eye_ry_r)
        
        # Update state for next frame
        self.prev_eye_ry_l = eye_ry_l
        self.prev_eye_ry_r = eye_ry_r
        self.prev_eye_x_offset = eye_x
        self.prev_eye_y_offset = eye_y
        self.has_prev_frame = True
    
    def _calculateEyeHeight(self) -> tuple:
        """Calculate eye radii based on current animation state"""
        base_ry = 66
        
        # Blink cadence
        if self.blink_start_ms > 0:
            elapsed = self._millis() - self.blink_start_ms
            if elapsed < self.blink_duration_ms:
                squint = self._triPulse(elapsed, self.blink_duration_ms, 54)
                base_ry -= squint
            else:
                self.blink_start_ms = 0
        
        # Emotion-specific cadence
        if self.anim_active:
            elapsed = self._millis() - self.anim_start_ms
            
            if self.emotion_mode == self.MODE_SPEAKING:
                cadence = self._triPulse(elapsed % 340, 340, 22)
                cadence += self._triPulse(elapsed % 210, 210, 12)
                base_ry -= cadence
            elif self.emotion_mode == self.MODE_EXCITED:
                cadence = self._triPulse(elapsed % 180, 180, 30)
                base_ry -= cadence
            elif self.emotion_mode == self.MODE_THINKING:
                cadence = self._triPulse(elapsed % 520, 520, 16)
                base_ry -= cadence
            elif self.emotion_mode == self.MODE_SURPRISED:
                base_ry = 74
                cadence = self._triPulse(elapsed % 280, 280, 20)
                base_ry -= cadence
        
        # Clamp
        if base_ry < 10:
            base_ry = 10
        if base_ry > 88:
            base_ry = 88
        
        return (base_ry, base_ry)
    
    def _drawEmotion(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Draw eyes based on current emotion"""
        if self.emotion_mode == self.MODE_HAPPY:
            self._drawHappyEyes(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_MAD:
            self._drawMadEyes(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_SAD:
            self._drawSadEyes(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_SURPRISED:
            self._drawSurprisedEyes(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_SLEEPY:
            self._drawSleepyEyes(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_LOVE:
            self._drawLoveHeart(painter, eye_x, eye_y, ry_l, ry_r)
        elif self.emotion_mode == self.MODE_CONFUSED:
            self._drawConfusedEyes(painter, eye_x, eye_y, ry_l, ry_r)
        else:
            self._drawNormalEyes(painter, eye_x, eye_y, ry_l, ry_r)
    
    def _drawNormalEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Default oval eyes"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        rx = 46
        
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawEllipse(QRectF(cx_l - rx, cy - ry_l, rx * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx, cy - ry_r, rx * 2, ry_r * 2))
    
    def _drawHappyEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Happy upturned eyes"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        rx = 46
        
        # Draw main ellipse
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx_l - rx, cy - ry_l, rx * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx, cy - ry_r, rx * 2, ry_r * 2))
        
        # Carve lower portion for upturned look
        cutoff = ry_l // 2
        painter.setBrush(QBrush(self.bg_color))
        painter.drawEllipse(QRectF(cx_l - rx - 1, cy + cutoff - ry_l, (rx+1) * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx - 1, cy + cutoff - ry_r, (rx+1) * 2, ry_r * 2))
    
    def _drawMadEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Angry angled eyes with furrowed brows"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        
        # Draw angry slits
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Left eye - angled down toward nose
        path_l = QPainterPath()
        path_l.moveTo(cx_l - 40, cy + 10)
        path_l.lineTo(cx_l + 40, cy - 10)
        path_l.lineTo(cx_l + 40, cy)
        path_l.lineTo(cx_l - 40, cy + 20)
        path_l.closeSubpath()
        painter.fillPath(path_l, self.eye_color)
        
        # Right eye - angled down toward nose
        path_r = QPainterPath()
        path_r.moveTo(cx_r - 40, cy - 10)
        path_r.lineTo(cx_r + 40, cy + 10)
        path_r.lineTo(cx_r + 40, cy + 20)
        path_r.lineTo(cx_r - 40, cy)
        path_r.closeSubpath()
        painter.fillPath(path_r, self.eye_color)
        
        # Furrowed brows
        painter.setPen(QPen(QColor("#A80000"), 3))
        painter.drawLine(30 + eye_x, cy - 50, 88 + eye_x, cy - 30)
        painter.drawLine(152 + eye_x, cy - 30, 210 + eye_x, cy - 50)
    
    def _drawSadEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Sad downturned eyes"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        rx = 46
        
        # Draw main ellipse
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx_l - rx, cy - ry_l, rx * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx, cy - ry_r, rx * 2, ry_r * 2))
        
        # Carve upper portion for heavy lids
        cutoff = ry_l // 2
        painter.setBrush(QBrush(self.bg_color))
        painter.drawEllipse(QRectF(cx_l - rx - 1, cy - cutoff - ry_l, (rx+1) * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx - 1, cy - cutoff - ry_r, (rx+1) * 2, ry_r * 2))
    
    def _drawSurprisedEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Wide surprised eyes"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        rx = 52  # Wider
        
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx_l - rx, cy - ry_l, rx * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx, cy - ry_r, rx * 2, ry_r * 2))
    
    def _drawSleepyEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Heavy-lidded sleepy eyes"""
        cx_l = 68 + eye_x
        cx_r = 172 + eye_x
        cy = 112 + eye_y
        
        # Just draw lower slits
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(cx_l - 37, cy + 10, 74, 10)
        painter.drawRect(cx_r - 37, cy + 10, 74, 10)
    
    def _drawLoveHeart(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Heart shape for love emotion"""
        cx = 120 + eye_x
        cy = 106 + eye_y
        beat = ry_l + ry_r  # Use eye params for pulsing
        r = 18 + beat // 10
        if r < 12:
            r = 12
        if r > 30:
            r = 30
        
        painter.setBrush(QBrush(QColor("#F8B2D2")))  # Pink
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Two lobes
        painter.drawEllipse(QPointF(cx - 22, cy - 4), r, r)
        painter.drawEllipse(QPointF(cx + 22, cy - 4), r, r)
        
        # Tapered tip
        tip_h = 26
        for dy in range(tip_h):
            half_w = int(((tip_h - dy) * 28) / tip_h)
            if half_w < 1:
                half_w = 1
            yy = cy + 10 + dy
            painter.drawRect(cx - half_w, yy, 2 * half_w + 1, 1)
    
    def _drawConfusedEyes(self, painter, eye_x, eye_y, ry_l, ry_r):
        """Asymmetric confused eyes"""
        cx_l = (68 + eye_x) - 12  # Offset left
        cx_r = (172 + eye_x) + 12  # Offset right
        cy = 112 + eye_y
        rx = 46
        
        painter.setBrush(QBrush(self.eye_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx_l - rx, cy - ry_l, rx * 2, ry_l * 2))
        painter.drawEllipse(QRectF(cx_r - rx, cy - ry_r, rx * 2, ry_r * 2))
    
    def _triPulse(self, elapsed: int, duration: int, amplitude: int) -> int:
        """Triangular pulse for smooth animation curves"""
        if duration == 0 or elapsed >= duration:
            return 0
        t = elapsed / duration  # 0..1
        tri = 1.0 - abs(2.0 * t - 1.0)  # 0..1..0
        return int(tri * amplitude)
