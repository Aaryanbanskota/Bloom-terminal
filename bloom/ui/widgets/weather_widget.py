"""
bloom/ui/widgets/weather_widget.py
Weather widget for the Bloom intro dashboard.
Fetches weather from weatherapi.com (if key is set in bloom/api/config.py) or falls back to wttr.in.
"""

import json
import threading
import urllib.request
import urllib.parse
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout

try:
    from bloom.api.config import WEATHER_API_KEY
except ImportError:
    WEATHER_API_KEY = ""

class _Fetcher(QObject):
    done = pyqtSignal(dict)

    def fetch(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        # 1. Try weatherapi.com if API key is provided
        if WEATHER_API_KEY and WEATHER_API_KEY.strip():
            try:
                # Default query is London, but we try auto ip locate if possible
                key = WEATHER_API_KEY.strip()
                url = f"http://api.weatherapi.com/v1/current.json?key={key}&q=auto:ip"
                req = urllib.request.Request(url, headers={"User-Agent": "Bloom-Terminal/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode())
                
                # Normalize structure to match our UI expectations
                normalized = {
                    "temp_c": int(data["current"]["temp_c"]),
                    "feels_c": int(data["current"]["feelslike_c"]),
                    "desc": data["current"]["condition"]["text"]
                }
                self.done.emit(normalized)
                return
            except Exception:
                pass  # Fallback to wttr.in if WeatherAPI fails or key is invalid

        # 2. wttr.in Fallback
        try:
            url = "https://wttr.in/?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "Bloom-Terminal/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                raw_data = json.loads(r.read().decode())
            
            cur = raw_data["current_condition"][0]
            normalized = {
                "temp_c": int(cur.get("temp_C", 34)),
                "feels_c": int(cur.get("FeelsLikeC", 69)),
                "desc": cur.get("weatherDesc", [{}])[0].get("value", "Unknown")
            }
            self.done.emit(normalized)
        except Exception:
            self.done.emit({})


class WeatherIconWidget(QWidget):
    """Custom painted white-outline cloud with a yellow lightning bolt."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setStyleSheet("background: transparent;")
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor("white"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        
        # Draw cloud outline
        p.drawArc(3, 13, 13, 13, 0 * 16, 180 * 16)
        p.drawArc(9, 6, 16, 16, -30 * 16, 210 * 16)
        p.drawArc(19, 11, 11, 11, -60 * 16, 190 * 16)
        p.drawLine(6, 23, 23, 23)
        
        # Draw lightning bolt path
        path = QPainterPath()
        path.moveTo(17, 23)
        path.lineTo(12, 29)
        path.lineTo(19, 29)
        path.lineTo(14, 34)
        
        p.setPen(QPen(QColor("#ef4444"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.end()


class WeatherWidget(QWidget):
    """Shows weather condition, temperature, and feels-like."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

        self._fetcher = _Fetcher()
        self._fetcher.done.connect(self._apply)
        self._cache = {}
        self._last_fetch_time = None

        # Refresh every 15 minutes
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fetch)
        self._timer.start(15 * 60 * 1000)
        self._fetch()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self._cond_lbl = QLabel("Fetching weather...")
        self._cond_lbl.setFont(QFont("Georgia", 14, QFont.Bold))
        self._cond_lbl.setStyleSheet("color: white; background: transparent;")

        temp_row = QHBoxLayout()
        temp_row.setSpacing(10)
        
        self._temp_lbl = QLabel("--° C")
        self._temp_lbl.setFont(QFont("Georgia", 32, QFont.Bold))
        self._temp_lbl.setStyleSheet("color: white; background: transparent;")
        
        self._icon = WeatherIconWidget()
        
        temp_row.addWidget(self._temp_lbl)
        temp_row.addWidget(self._icon, 0, Qt.AlignVCenter)
        temp_row.addStretch()

        self._feels_lbl = QLabel("feels like --c")
        self._feels_lbl.setFont(QFont("Georgia", 12))
        self._feels_lbl.setStyleSheet("color: white; background: transparent;")

        lay.addWidget(self._cond_lbl)
        lay.addLayout(temp_row)
        lay.addWidget(self._feels_lbl)

    def _fetch(self):
        from datetime import datetime
        now = datetime.now()
        if self._last_fetch_time and (now - self._last_fetch_time).total_seconds() < 900:
            if self._cache:
                self._apply(self._cache)
                return
        self._fetcher.fetch()

    def _apply(self, data: dict):
        if not data:
            if self._cache:
                data = self._cache
            else:
                self._cond_lbl.setText("Offline")
                self._temp_lbl.setText("--° C")
                self._feels_lbl.setText("feels like --c")
                return
        else:
            self._cache = data
            from datetime import datetime
            self._last_fetch_time = datetime.now()
        
        self._cond_lbl.setText(data.get("desc", "Clear"))
        self._temp_lbl.setText(f"{data.get('temp_c', '--')}° C")
        self._feels_lbl.setText(f"feels like {data.get('feels_c', '--')}c")
