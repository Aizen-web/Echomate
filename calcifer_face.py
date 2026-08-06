"""
Calcifer Face Engine - Ported from OmniBot Pixel C++ implementation
Procedural face rendering with eyes + mouth, transparent background
"""
import math
import random
import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import QWidget


def tri_pulse(elapsed_ms: int, duration_ms: int, amplitude: int) -> int:
    """Triangular pulse: ramps 0→1→0 over duration"""
    if duration_ms == 0 or elapsed_ms >= duration_ms:
        return 0
    t = elapsed_ms / duration_ms  # 0..1
    tri = 1.0 - abs(2.0 * t - 1.0)  # 0..1..0
    return int(tri * amplitude)


class CalciferFace(QWidget):
    """
    Procedural face with differential rendering
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Animation state
        self.emotion_mode = 0
        self.emotion_start_ms = 0
        self.frozen_look_x = 0
        self.frozen_look_y = 0
        
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
        
        # Warm accent colour (default amber). Emotion changes can override.
        self._face_color = QColor("#FFB347")
        self.bob_y = 0.0
        
        # Start animation
        self.reset_idle_state()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(45)  # ~22 FPS

    def setColor(self, color: QColor):
        """Recolour the face to match the current emotion glow (kept in sync by the UI)."""
        self._face_color = QColor(color)
        self.update()
    
    def reset_idle_state(self):
        """Reset to neutral idle pose"""
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
        """Change facial expression"""
        emotion_map = {
            "speaking": 0, "happy": 1, "mad": 2, "sad": 3, "surprised": 4,
            "sleepy": 5, "thinking": 6, "confused": 7, "excited": 8, "love": 9,
            "playful": 1, "proud": 1, "angry": 2, "annoyed": 2, "calm": 5,
            "curious": 6, "focused": 6, "error": 2
        }
        mode = emotion_map.get(emotion.lower(), 0)
        
        if mode != 0:
            self.frozen_look_x = self.look_x
            self.frozen_look_y = self.look_y
            if mode == 6:  # thinking - look up slightly
                self.frozen_look_y = max(-14, min(-2, self.look_y - 8))
        
        self.emotion_mode = mode
        self.emotion_start_ms = time.time() * 1000
        self.update()
    
    def _animate(self):
        """Update animation state"""
        now = time.time() * 1000
        
        # Idle gaze (only for speaking mode)
        if self.emotion_mode == 0:
            if now >= self.next_look_change_ms:
                self.target_look_x = random.randint(-10, 11)
                self.target_look_y = random.randint(-5, 6)
                self.next_look_change_ms = now + random.randint(900, 2400)
            
            # Smooth chase (eased, not integer stepping)
            self.look_x += int(round((self.target_look_x - self.look_x) * 0.22))
            self.look_y += int(round((self.target_look_y - self.look_y) * 0.22))
            
            # Blink
            if self.blink_start_ms == 0 and now >= self.next_blink_ms:
                self.blink_start_ms = now
                self.blink_duration_ms = random.randint(120, 240)
                self.next_blink_ms = now + random.randint(2500, 7000)
            
            # Gentle idle bob so the character breathes
            self.bob_y = math.sin(now * 0.0016) * 3.5
        
        self.update()
    
    def paintEvent(self, event):
        """Draw face with cyan eyes + mouth"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        now = time.time() * 1000
        elapsed = int(now - self.emotion_start_ms)
        
        # Determine eye offset
        if self.emotion_mode != 0:
            eye_x_offset = self.frozen_look_x
            eye_y_offset = self.frozen_look_y
        else:
            eye_x_offset = self.look_x
            eye_y_offset = self.look_y + int(self.bob_y)
        
        # Calculate eye radii with cadence
        eye_ry_l = 66
        eye_ry_r = 66
        cadence = 0
        
        if self.emotion_mode == 0:  # speaking
            cadence = tri_pulse(elapsed % 340, 340, 22)
            cadence += tri_pulse(elapsed % 210, 210, 12)
            eye_x_offset += int(math.sin(elapsed * 0.012) * 4.0)
        elif self.emotion_mode == 8:  # excited
            cadence = tri_pulse(elapsed % 180, 180, 30)
        elif self.emotion_mode == 6:  # thinking
            cadence = tri_pulse(elapsed % 520, 520, 16)
        elif self.emotion_mode == 4:  # surprised
            eye_ry_l = 74
            eye_ry_r = 74
            cadence = tri_pulse(elapsed % 280, 280, 20)
        elif self.emotion_mode == 7:  # confused
            eye_ry_l = 40
            eye_ry_r = 80
            cadence = tri_pulse(elapsed % 340, 340, 18)
        else:
            cadence = tri_pulse(elapsed % 340, 340, 24)
        
        # Apply cadence
        eye_ry_l -= cadence
        eye_ry_r -= cadence
        
        # Blink overlay (speaking mode only)
        if self.emotion_mode == 0 and self.blink_start_ms != 0:
            blink_elapsed = int(now - self.blink_start_ms)
            if blink_elapsed >= self.blink_duration_ms:
                self.blink_start_ms = 0
            else:
                sq = tri_pulse(blink_elapsed, self.blink_duration_ms, 54)
                eye_ry_l -= sq
                eye_ry_r -= sq
        
        # Clamp
        eye_ry_l = max(10, min(88, eye_ry_l))
        eye_ry_r = max(10, min(88, eye_ry_r))
        
        # Draw eyes based on mode
        color = QColor(self._face_color)  # Warm accent, synced with emotion glow
        
        if self.emotion_mode == 1:  # happy
            self._draw_happy_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        elif self.emotion_mode == 2:  # mad
            self._draw_mad_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        elif self.emotion_mode == 3:  # sad
            self._draw_sad_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        elif self.emotion_mode == 5:  # sleepy
            self._draw_sleepy_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        elif self.emotion_mode == 7:  # confused
            self._draw_confused_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        elif self.emotion_mode == 9:  # love
            self._draw_love_heart(painter, eye_x_offset, eye_y_offset, eye_ry_l + eye_ry_r)
        else:  # speaking, surprised, thinking, excited use normal ovals
            self._draw_normal_eyes(painter, eye_x_offset, eye_y_offset, eye_ry_l, eye_ry_r, color)
        
        # Draw mouth (only for speaking mode)
        if self.emotion_mode == 0:
            self._draw_mouth(painter, eye_x_offset, eye_y_offset, elapsed)
    
    def _fill_oval(self, painter: QPainter, cx: int, cy: int, rx: int, ry: int, color: QColor):
        """Fill an ellipse"""
        if rx <= 0 or ry <= 0:
            return
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - rx, cy - ry, rx * 2, ry * 2)
    
    def _draw_normal_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw standard oval eyes"""
        base_y = 160  # Centered in 340x400 widget
        rx = 46
        cx_l = 85 + look_x
        cx_r = 255 + look_x
        yc = base_y + look_y
        
        self._fill_oval(painter, cx_l, yc, rx, ry_l, color)
        self._fill_oval(painter, cx_r, yc, rx, ry_r, color)
    
    def _draw_happy_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw upturned crescent eyes"""
        base_y = 160
        rx = 46
        cx_l = 85 + look_x
        cx_r = 255 + look_x
        yc = base_y + look_y
        
        painter.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(cx_l - rx, yc - ry_l, rx * 2, ry_l * 2, 0 * 16, 180 * 16)
        painter.drawArc(cx_r - rx, yc - ry_r, rx * 2, ry_r * 2, 0 * 16, 180 * 16)
    
    def _draw_mad_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw angry slanted eyes"""
        base_y = 160
        rx = 46
        yc = base_y + look_y
        
        # Angry brows
        brow_color = QColor(self._face_color).darker(160)
        painter.setPen(QPen(brow_color, 3))
        painter.drawLine(40 + look_x, yc - 50, 85 + look_x, yc - 30)
        painter.drawLine(300 + look_x, yc - 50, 255 + look_x, yc - 30)
        
        # Slanted eyes
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        cx_l = 85 + look_x
        cx_r = 255 + look_x
        painter.drawEllipse(cx_l - rx, yc - ry_l // 2, rx * 2, ry_l)
        painter.drawEllipse(cx_r - rx, yc - ry_r // 2, rx * 2, ry_r)
    
    def _draw_sad_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw downturned eyes"""
        base_y = 160
        rx = 46
        cx_l = 85 + look_x
        cx_r = 255 + look_x
        yc = base_y + look_y
        
        painter.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(cx_l - rx, yc - ry_l, rx * 2, ry_l * 2, 180 * 16, 180 * 16)
        painter.drawArc(cx_r - rx, yc - ry_r, rx * 2, ry_r * 2, 180 * 16, 180 * 16)
    
    def _draw_sleepy_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw narrow slits"""
        base_y = 160
        eye_w = 74
        eye_h = 10
        left_x = (85 + look_x) - eye_w // 2
        right_x = (255 + look_x) - eye_w // 2
        y = (base_y + look_y) - eye_h // 2
        
        painter.fillRect(left_x, y, eye_w, eye_h, color)
        painter.fillRect(right_x, y, eye_w, eye_h, color)
    
    def _draw_confused_eyes(self, painter: QPainter, look_x: int, look_y: int, ry_l: int, ry_r: int, color: QColor):
        """Draw asymmetric eyes"""
        base_y = 160
        rx = 46
        cx_l = (85 + look_x) - 12
        cx_r = (255 + look_x) + 12
        yc = base_y + look_y
        
        self._fill_oval(painter, cx_l, yc, rx, ry_l, color)
        self._fill_oval(painter, cx_r, yc, rx, ry_r, color)
    
    def _draw_love_heart(self, painter: QPainter, look_x: int, look_y: int, beat: int):
        """Draw pink heart"""
        cx = 170 + look_x
        cy = 150 + look_y
        r = 18 + beat // 10
        r = max(12, min(30, r))
        
        love_pink = QColor("#F8B2F8")
        painter.setBrush(QBrush(love_pink))
        painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawEllipse(cx - 22 - r, cy - 4 - r, r * 2, r * 2)
        painter.drawEllipse(cx + 22 - r, cy - 4 - r, r * 2, r * 2)
        
        # Triangle tip
        tip_h = 26
        for dy in range(tip_h):
            half_w = ((tip_h - dy) * 28) // tip_h
            yy = cy + 10 + dy
            painter.fillRect(cx - half_w, yy, half_w * 2 + 1, 1, love_pink)
    
    def _draw_mouth(self, painter: QPainter, look_x: int, look_y: int, elapsed: int):
        """Draw animated mouth"""
        mouth_y_base = 240
        mouth_y = mouth_y_base + look_y
        
        mouth_open = tri_pulse(elapsed % 280, 280, 12)
        mouth_h = 4 + mouth_open
        mouth_w = 60 - mouth_open // 2
        
        mouth_x = 170 + look_x - mouth_w // 2
        
        mouth_color = QColor(self._face_color)
        painter.setBrush(QBrush(mouth_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(mouth_x, mouth_y - mouth_h // 2, mouth_w, mouth_h)
