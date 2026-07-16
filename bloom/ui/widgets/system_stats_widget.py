"""
bloom/ui/widgets/system_stats_widget.py
Battery percentage + CPU usage widgets with wave animation for Bloom intro dashboard.
Uses psutil for live readings; falls back to placeholders if unavailable.
"""

import math
import os
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

# ── colour tokens ──────────────────────────────────────────────────────────
_BG_CARD  = "#1a2035"
_BORDER   = "#2a3350"
_TEXT     = "#d4daf0"
_SUBTEXT  = "#7a85a8"
_GREEN    = "#4ade80"
_YELLOW   = "#facc15"
_RED      = "#f87171"
_BLUE     = "#60a5fa"


class WaveGauge(QWidget):
    """Animated wave gauge container."""
    def __init__(self, color_hex, is_circle=False, parent=None):
        super().__init__(parent)
        self.color = QColor(color_hex)
        self.is_circle = is_circle
        self.value = 50.0  # 0 to 100
        self.setFixedSize(64, 64)
        self.wave_offset = 0.0
        self.setStyleSheet("background: transparent;")

        # Animation timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(50)

    def _animate(self):
        self.wave_offset += 0.1
        self.update()

    def set_value(self, val):
        self.value = max(0.0, min(100.0, val))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        rect = QRectF(2, 2, w-4, h-4)

        # Clip path
        clip_path = QPainterPath()
        if self.is_circle:
            clip_path.addEllipse(rect)
        else:
            # Rounded rect with custom corner radius
            clip_path.addRoundedRect(rect, 14, 14)

        p.save()
        p.setClipPath(clip_path)

        # Draw container background (slightly lighter dark grey)
        p.setBrush(QBrush(QColor("#2d3345")))
        p.setPen(Qt.NoPen)
        if self.is_circle:
            p.drawEllipse(rect)
        else:
            p.drawRoundedRect(rect, 14, 14)

        # Draw fluid wave
        level = rect.bottom() - (rect.height() * (self.value / 100.0))
        wave_path = QPainterPath()
        wave_path.moveTo(rect.left(), rect.bottom())

        steps = int(rect.width())
        for x_pos in range(steps + 1):
            y_offset = 3.5 * math.sin(x_pos * 0.15 + self.wave_offset)
            y_pos = level + y_offset
            wave_path.lineTo(rect.left() + x_pos, y_pos)

        wave_path.lineTo(rect.right(), rect.bottom())
        wave_path.closeSubpath()

        p.setBrush(QBrush(self.color))
        p.drawPath(wave_path)
        p.restore()

        # Draw border outline
        pen = QPen(QColor("#3f485c"), 1.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if self.is_circle:
            p.drawEllipse(rect)
        else:
            p.drawRoundedRect(rect, 14, 14)

        p.end()


class BatteryCpuWidget(QWidget):
    """
    Combined battery + CPU usage widget showing two wave gauges side by side,
    matching the screenshot style exactly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

        # live-update timer (every 3 s)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)
        self._refresh()   # immediate first read

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(24)

        # ── battery ──
        batt_col = QVBoxLayout()
        batt_col.setSpacing(8)
        batt_col.setAlignment(Qt.AlignCenter)

        # Battery in screenshot is a rounded cup/block, red color
        self._batt_gauge = WaveGauge("#e11d48", is_circle=False)
        self._batt_lbl = QLabel("48% batt")
        self._batt_lbl.setAlignment(Qt.AlignCenter)
        self._batt_lbl.setFont(QFont("Georgia", 11, QFont.Bold))
        self._batt_lbl.setStyleSheet("color: white; background: transparent;")

        batt_col.addWidget(self._batt_gauge, 0, Qt.AlignCenter)
        batt_col.addWidget(self._batt_lbl)
        lay.addLayout(batt_col)

        # ── cpu ──
        cpu_col = QVBoxLayout()
        cpu_col.setSpacing(8)
        cpu_col.setAlignment(Qt.AlignCenter)

        # CPU in screenshot is a circle shape, brown/earth color
        self._cpu_gauge = WaveGauge("#8d5b4c", is_circle=True)
        self._cpu_lbl = QLabel("50% cpu-used")
        self._cpu_lbl.setAlignment(Qt.AlignCenter)
        self._cpu_lbl.setFont(QFont("Georgia", 11, QFont.Bold))
        self._cpu_lbl.setStyleSheet("color: white; background: transparent;")

        cpu_col.addWidget(self._cpu_gauge, 0, Qt.AlignCenter)
        cpu_col.addWidget(self._cpu_lbl)
        lay.addLayout(cpu_col)

    def _refresh(self):
        if not PSUTIL_OK:
            self._batt_gauge.set_value(48)
            self._batt_lbl.setText("48% batt")
            self._cpu_gauge.set_value(50)
            self._cpu_lbl.setText("50% cpu-used")
            return

        # battery
        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = bat.percent
                self._batt_gauge.set_value(pct)
                self._batt_lbl.setText(f"{int(pct)}% batt")
            else:
                self._batt_gauge.set_value(48)
                self._batt_lbl.setText("48% batt")
        except Exception:
            self._batt_gauge.set_value(48)
            self._batt_lbl.setText("48% batt")

        # cpu
        try:
            cpu = psutil.cpu_percent(interval=None)
            self._cpu_gauge.set_value(cpu)
            self._cpu_lbl.setText(f"{int(cpu)}% cpu-used")
        except Exception:
            self._cpu_gauge.set_value(50)
            self._cpu_lbl.setText("50% cpu-used")
