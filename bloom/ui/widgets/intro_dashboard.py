"""
bloom/ui/widgets/intro_dashboard.py
Premium Intro Dashboard for Bloom Terminal.
Real-time widgets: weather, running programs, song player, battery+CPU gauges.
"""

import os
import sys
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QSize, QRectF, QRect, QPoint, pyqtSignal, QSettings
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPixmap, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QFileDialog, QScrollArea,
)

from bloom.core.constants import BG_DARK
from bloom.core.paths import BLOOM_DIR

try:
    from bloom.ui.widgets.weather_widget import WeatherWidget
    _HAS_WEATHER = True
except ImportError:
    _HAS_WEATHER = False

try:
    from bloom.ui.widgets.song_player_widget import SongPlayerWidget
    _HAS_PLAYER = True
except ImportError:
    _HAS_PLAYER = False

try:
    from bloom.ui.widgets.system_stats_widget import BatteryCpuWidget
    _HAS_STATS = True
except ImportError:
    _HAS_STATS = False

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_BG     = "#0a0d14"
_CARD   = "#161922"
_BORDER = "#2d3345"
_TEXT   = "#e2e8f8"

# ── Circular Avatar Widget ────────────────────────────────────────────────
class CircleAvatar(QWidget):
    def __init__(self, size=180, border_color="#ef4444", border_width=2.5, parent=None):
        super().__init__(parent)
        self._size = size
        self.border_color = QColor(border_color)
        self.border_width = border_width
        self.setFixedSize(size, size)
        self.pixmap = None

    def set_image(self, path):
        default_avatar = os.path.join(BLOOM_DIR, "assets", "avatars", "sketch-guy.jpg")
        target_path = path if (path and os.path.exists(path)) else default_avatar
        if target_path and os.path.exists(target_path):
            self.pixmap = QPixmap(target_path)
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self._size, self._size)
        path = QPainterPath()
        path.addEllipse(rect)
        p.save()
        p.setClipPath(path)
        if self.pixmap and not self.pixmap.isNull():
            # Scale to completely fill the circle (KeepAspectRatioByExpanding)
            scaled = self.pixmap.scaled(self._size, self._size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            # Center the scaled image in the crop circle
            x = (self._size - scaled.width()) // 2
            y = (self._size - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.setBrush(QBrush(QColor("#111827")))
            p.setPen(Qt.NoPen)
            p.drawEllipse(rect)
        p.restore()
        pen = QPen(self.border_color, self.border_width)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        off = self.border_width / 2.0
        p.drawEllipse(rect.adjusted(off, off, -off, -off))
        p.end()

# ── Profile Widget ────────────────────────────────────────────────────────
class ProfileWidget(QWidget):
    def __init__(self, user_name="", xp=0, level=1, parent_dashboard=None, parent=None):
        super().__init__(parent)
        self.parent_dashboard = parent_dashboard
        self.setStyleSheet("background: transparent;")
        self._build_ui(user_name, xp, level)

    def _build_ui(self, user_name, xp, level):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(14)

        # Flower on left
        flower_lbl = QLabel()
        flower_path = os.path.join(BLOOM_DIR, "assets", "bloom-flower.png")
        if os.path.exists(flower_path):
            pix = QPixmap(flower_path)
            flower_lbl.setPixmap(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        flower_lbl.setFixedSize(60, 60)
        flower_lbl.setStyleSheet("background: transparent;")

        # Stats on right
        txt = QVBoxLayout()
        txt.setSpacing(3)

        # Display user data safely from cache if locked
        settings = QSettings("Bloom", "BloomTerminal")
        cached_name = settings.value("cached_user_name", "User")
        cached_xp = settings.value("cached_xp", 0, type=int)

        display_name = user_name if user_name else cached_name
        display_xp = xp if xp else cached_xp

        self.name_lbl = QLabel(f"User: {display_name}")
        self.name_lbl.setFont(QFont("Georgia", 10, QFont.Bold))
        self.name_lbl.setStyleSheet("color: white; background: transparent;")

        self.xp_lbl = QLabel(f"xp: {display_xp}")
        self.xp_lbl.setFont(QFont("Georgia", 10, QFont.Bold))
        self.xp_lbl.setStyleSheet("color: white; background: transparent;")

        self.batt_lbl = QLabel("Batt: --%")
        self.batt_lbl.setFont(QFont("Georgia", 10, QFont.Bold))
        self.batt_lbl.setStyleSheet("color: white; background: transparent;")
        self._refresh_batt()

        # Refresh battery every 3 seconds
        self._batt_timer = QTimer(self)
        self._batt_timer.timeout.connect(self._refresh_batt)
        self._batt_timer.start(3000)

        txt.addWidget(self.name_lbl)
        txt.addWidget(self.xp_lbl)
        txt.addWidget(self.batt_lbl)

        # Colour dots
        dots = QHBoxLayout()
        dots.setSpacing(5)
        for c in ["#f87171", "#60a5fa", "#4ade80", "#22d3ee", "#e2e8f0"]:
            d = QLabel()
            d.setFixedSize(12, 12)
            d.setStyleSheet(f"background:{c}; border-radius:6px;")
            dots.addWidget(d)
        dots.addStretch()
        txt.addLayout(dots)

        lay.addWidget(flower_lbl, 0, Qt.AlignVCenter)
        lay.addLayout(txt, 1)

    def _refresh_batt(self):
        pct = "--"
        if _HAS_PSUTIL:
            try:
                bat = psutil.sensors_battery()
                if bat:
                    pct = int(bat.percent)
            except Exception:
                pass
        self.batt_lbl.setText(f"Batt: {pct}%")

    def refresh(self, name, xp, level):
        self.name_lbl.setText(f"User: {name}")
        self.xp_lbl.setText(f"xp: {xp}  ·  lvl: {level}")

# ── Running Programs Widget ───────────────────────────────────────────────
class RunningProgramsWidget(QWidget):
    """Shows real running processes with the circular logo representing the user's avatar."""

    def __init__(self, parent_dashboard=None, parent=None):
        super().__init__(parent)
        self.parent_dashboard = parent_dashboard
        self.setStyleSheet("background: transparent;")
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_programs)
        self._refresh_timer.start(3000)
        self._refresh_programs()

    def _build_ui(self):
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 12, 12, 12)
        self._lay.setSpacing(8)

        hdr = QLabel("Running Programs")
        hdr.setFont(QFont("Georgia", 12, QFont.Bold))
        hdr.setStyleSheet("color: #e2e8f8; background: transparent;")
        self._lay.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1a2035; width: 5px; border-radius: 2px; }
            QScrollBar::handle:vertical { background: #3b4a6b; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._proc_container = QWidget()
        self._proc_container.setStyleSheet("background: transparent;")
        self._proc_lay = QVBoxLayout(self._proc_container)
        self._proc_lay.setContentsMargins(0, 0, 0, 0)
        self._proc_lay.setSpacing(6)
        self._scroll.setWidget(self._proc_container)
        self._lay.addWidget(self._scroll, 1)

    def _refresh_programs(self):
        while self._proc_lay.count():
            item = self._proc_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not _HAS_PSUTIL:
            lbl = QLabel("psutil not installed")
            lbl.setStyleSheet("color: #6b7898; font-size: 10px;")
            self._proc_lay.addWidget(lbl)
            return

        procs = []
        try:
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "status"]):
                try:
                    if p.info["status"] == psutil.STATUS_RUNNING:
                        procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
        shown = procs[:4] if procs else []

        if not shown:
            try:
                for p in list(psutil.process_iter(["pid", "name"]))[:4]:
                    try:
                        shown.append(p.info)
                    except Exception:
                        pass
            except Exception:
                pass

        for info in shown:
            row = self._make_proc_row(
                name=info.get("name", "unknown"),
                cpu=info.get("cpu_percent", 0),
            )
            self._proc_lay.addWidget(row)

        self._proc_lay.addStretch()

    def _make_proc_row(self, name: str, cpu: float) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Micro circular avatar instead of plain red dot
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(22, 22)
        
        avatar_path = ""
        if self.parent_dashboard:
            avatar_path = self.parent_dashboard._avatar_path
            if not avatar_path:
                hacker = os.path.join(BLOOM_DIR, "assets", "avatars", "hacker.png")
                if os.path.exists(hacker):
                    avatar_path = hacker

        if avatar_path and os.path.exists(avatar_path):
            pix = QPixmap(avatar_path)
            logo_lbl.setPixmap(pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_lbl.setStyleSheet("border-radius: 11px; border: 1px solid #ef4444; background: #111827;")
        else:
            logo_lbl.setStyleSheet("background-color: #ef4444; border-radius: 11px;")

        lay.addWidget(logo_lbl, 0, Qt.AlignVCenter)

        short = name[:16] + "…" if len(name) > 16 else name
        name_lbl = QLabel(short)
        name_lbl.setFont(QFont("Georgia", 9))
        name_lbl.setStyleSheet("color: #c8d4e8; background: transparent;")
        lay.addWidget(name_lbl, 1)

        cpu_lbl = QLabel(f"{cpu:.0f}%")
        cpu_lbl.setFont(QFont("Georgia", 9, QFont.Bold))
        cpu_lbl.setStyleSheet("color: #7a85a8; background: transparent;")
        cpu_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(cpu_lbl)

        return row

# ── Song Player Card (with folder button) ────────────────────────────────
class _SongCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        if _HAS_PLAYER:
            self._player = SongPlayerWidget()
            lay.addWidget(self._player)

            folder_btn = QPushButton("📂  Open Music Folder")
            folder_btn.setCursor(Qt.PointingHandCursor)
            folder_btn.setFont(QFont("Georgia", 9))
            folder_btn.setStyleSheet("""
                QPushButton {
                    background: #1e2740;
                    color: #a0b0d0;
                    border: 1px solid #2d3a55;
                    border-radius: 8px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background: #2a3a5c;
                    color: white;
                    border-color: #3b82f6;
                }
            """)
            folder_btn.clicked.connect(self._player.load_folder)
            lay.addWidget(folder_btn)
        else:
            lbl = QLabel("song-player\n(QtMultimedia unavailable)")
            lbl.setStyleSheet("color: #6b7898; font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(lbl)

    def get_player(self):
        return getattr(self, "_player", None)

# ── Gear / Settings Button ────────────────────────────────────────────────
class _GearButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("⚙", parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: #1a2035;
                color: #c8d4e8;
                border: 1px solid #2d3345;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #253050;
                color: white;
                border-color: #3b82f6;
            }
        """)

# ── IntroDashboard ────────────────────────────────────────────────────────
class IntroDashboard(QWidget):
    clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, user_name="", xp=0, level=1, avatar_path="",
                 on_click=None, on_resetup=None, on_settings=None, parent_app=None):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self._user_name = user_name
        self._xp = xp
        self._level = level
        self._avatar_path = avatar_path
        self._on_click = on_click
        self._on_resetup = on_resetup
        self._on_settings = on_settings

        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet(f"background-color: {_BG};")

        self._build_ui()

        if on_click:
            self.clicked.connect(on_click)
        if on_settings:
            self.settings_clicked.connect(on_settings)

    def _build_ui(self):
        self.master_layout = QHBoxLayout(self)
        self.master_layout.setContentsMargins(24, 24, 24, 24)
        self.master_layout.setSpacing(20)

        # ────────────────────────────────── LEFT COLUMN
        self._left_col = QWidget()
        self._left_col.setFixedWidth(250)
        left_lay = QVBoxLayout(self._left_col)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(16)

        # Weather card
        self._weather_card = self._make_card(250, 130)
        wl = QVBoxLayout(self._weather_card)
        wl.setContentsMargins(0, 0, 0, 0)
        if _HAS_WEATHER:
            wl.addWidget(WeatherWidget())
        else:
            wl.addWidget(QLabel("Weather unavailable"))

        # Profile card
        self._profile_card = self._make_card(250, 145)
        pl = QVBoxLayout(self._profile_card)
        pl.setContentsMargins(0, 0, 0, 0)
        self.prof_widget = ProfileWidget(self._user_name, self._xp, self._level, self)
        pl.addWidget(self.prof_widget)

        # Song player card
        self._player_card = self._make_card(250, 160)
        ppl = QVBoxLayout(self._player_card)
        ppl.setContentsMargins(8, 8, 8, 8)
        ppl.setSpacing(6)
        self._song_card = _SongCard()
        ppl.addWidget(self._song_card)

        left_lay.addWidget(self._weather_card)
        left_lay.addWidget(self._profile_card)
        left_lay.addWidget(self._player_card)
        left_lay.addStretch()

        # ────────────────────────────────── CENTER COLUMN
        self._center_col = QWidget()
        cent_lay = QVBoxLayout(self._center_col)
        cent_lay.setContentsMargins(0, 0, 0, 0)
        cent_lay.setSpacing(20)
        cent_lay.setAlignment(Qt.AlignCenter)

        # ── Clock (proportional sizes, higher placement) ──
        self.clock_widget = QWidget()
        self.clock_widget.setStyleSheet("background: transparent;")
        clock_lay = QHBoxLayout(self.clock_widget)
        clock_lay.setContentsMargins(0, 0, 0, 0)
        clock_lay.setSpacing(0)
        clock_lay.setAlignment(Qt.AlignCenter)

        self.hours_lbl = QLabel("10")
        self.hours_lbl.setFont(QFont("Georgia", 96, QFont.Bold))
        self.hours_lbl.setStyleSheet("color: #eca8a9; background: transparent;")
        self.hours_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        right_clock = QWidget()
        right_clock.setStyleSheet("background: transparent;")
        right_lay = QVBoxLayout(right_clock)
        right_lay.setContentsMargins(6, 12, 0, 0)
        right_lay.setSpacing(4)
        right_lay.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.minutes_lbl = QLabel("45")
        self.minutes_lbl.setFont(QFont("Georgia", 64, QFont.Bold))
        self.minutes_lbl.setStyleSheet("color: white; background: transparent;")
        self.minutes_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.ampm_container = QWidget()
        self.ampm_container.setFixedSize(50, 24)
        self.ampm_container.setStyleSheet("background-color: #2b303c; border-radius: 6px;")
        ampm_lay = QVBoxLayout(self.ampm_container)
        ampm_lay.setContentsMargins(0, 0, 0, 0)
        self.ampm_lbl = QLabel("PM")
        self.ampm_lbl.setAlignment(Qt.AlignCenter)
        self.ampm_lbl.setFont(QFont("Georgia", 11, QFont.Bold))
        self.ampm_lbl.setStyleSheet("color: #e2e8f8; background: transparent;")
        ampm_lay.addWidget(self.ampm_lbl)

        right_lay.addWidget(self.minutes_lbl)
        right_lay.addWidget(self.ampm_container)

        clock_lay.addWidget(self.hours_lbl)
        clock_lay.addWidget(right_clock)

        cent_lay.addWidget(self.clock_widget, 0, Qt.AlignCenter)

        # ── Avatar ──
        self.avatar_widget = CircleAvatar(size=180, border_color="#ef4444", border_width=2.5)
        default_path = os.path.join(BLOOM_DIR, "assets", "avatars", "sketch-guy.jpg")
        if self._avatar_path and os.path.exists(self._avatar_path):
            self.avatar_widget.set_image(self._avatar_path)
        else:
            self.avatar_widget.set_image(default_path)
        cent_lay.addWidget(self.avatar_widget, 0, Qt.AlignCenter)

        # ── Password / unlock field ──
        from bloom.security.encryption import SecurityManager
        self.sec = SecurityManager()
        self.is_locked = self.sec.is_locked()

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setAlignment(Qt.AlignCenter)
        self.pass_edit.setPlaceholderText("- - - -")
        self.pass_edit.setMaximumWidth(220)
        self.pass_edit.setStyleSheet("""
            QLineEdit {
                background-color: #111827;
                border: 1.5px solid #4a5568;
                border-radius: 18px;
                padding: 8px 18px;
                color: white;
                font-family: 'Georgia', serif;
                font-size: 17px;
                letter-spacing: 6px;
            }
            QLineEdit:focus { border-color: #ef4444; }
        """)
        self.pass_edit.returnPressed.connect(self.attempt_unlock)
        cent_lay.addWidget(self.pass_edit, 0, Qt.AlignCenter)

        self.pulsing_lbl = QLabel("Click anywhere to enter →")
        self.pulsing_lbl.setStyleSheet("color: #6b7898; font-size: 13px;")
        self.pulsing_lbl.setAlignment(Qt.AlignCenter)
        cent_lay.addWidget(self.pulsing_lbl)

        if self.is_locked:
            self.pulsing_lbl.setVisible(False)
            self.pass_edit.setVisible(True)
            QTimer.singleShot(100, self.pass_edit.setFocus)
        else:
            self.pass_edit.setVisible(False)
            self.pulsing_lbl.setVisible(True)

        # ────────────────────────────────── RIGHT COLUMN
        self._right_col = QWidget()
        self._right_col.setFixedWidth(250)
        right_col_lay = QVBoxLayout(self._right_col)
        right_col_lay.setContentsMargins(0, 0, 0, 0)
        right_col_lay.setSpacing(16)

        # Battery + CPU stats card (Real real-time stats)
        self._stats_card = self._make_card(250, 155)
        sl = QVBoxLayout(self._stats_card)
        sl.setContentsMargins(0, 0, 0, 0)
        if _HAS_STATS:
            sl.addWidget(BatteryCpuWidget())

        # Running programs card (circular logo rows)
        self._running_card = self._make_card(250, 185)
        rl = QVBoxLayout(self._running_card)
        rl.setContentsMargins(0, 0, 0, 0)
        self.running_widget = RunningProgramsWidget(self)
        rl.addWidget(self.running_widget)

        right_col_lay.addWidget(self._stats_card)
        right_col_lay.addWidget(self._running_card)
        right_col_lay.addStretch()

        # Assemble master layout
        self.master_layout.addWidget(self._left_col, 0)
        self.master_layout.addWidget(self._center_col, 1)
        self.master_layout.addWidget(self._right_col, 0)

        # Gear button
        self.settings_btn = _GearButton(self)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)

        # Clock timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    @staticmethod
    def _make_card(w: int, h: int) -> QWidget:
        card = QWidget()
        card.setFixedSize(w, h)
        card.setStyleSheet(f"background: {_CARD}; border-radius: 18px;")
        return card

    def attempt_unlock(self):
        password = self.pass_edit.text()
        if self.sec.decrypt_for_access(password):
            self.is_locked = False
            self.pass_edit.setVisible(False)
            self.pulsing_lbl.setVisible(True)
            self.pulsing_lbl.setText("✅  Unlocked! Click anywhere to enter →")
            if self.parent_app and hasattr(self.parent_app, "on_database_unlocked"):
                self.parent_app.on_database_unlocked()
        else:
            self.pass_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #111827;
                    border: 2px solid #ef4444;
                    border-radius: 18px;
                    padding: 8px 18px;
                    color: white;
                    font-family: 'Georgia', serif;
                    font-size: 17px;
                    letter-spacing: 6px;
                }
            """)
            self.pass_edit.clear()

    def _update_clock(self):
        now = datetime.now()
        self.hours_lbl.setText(now.strftime("%I").lstrip("0") or "12")
        self.minutes_lbl.setText(now.strftime("%M"))
        self.ampm_lbl.setText(now.strftime("%p"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.settings_btn.move(self.width() - 52, 14)
        if self.width() < 720:
            self._left_col.setVisible(False)
            self._right_col.setVisible(False)
        elif self.width() < 1024:
            self._left_col.setVisible(True)
            self._right_col.setVisible(False)
        else:
            self._left_col.setVisible(True)
            self._right_col.setVisible(True)

    def refresh_user(self, name, xp, level, avatar_path):
        self._user_name = name
        self._xp = xp
        self._level = level
        self._avatar_path = avatar_path
        self.prof_widget.refresh(name, xp, level)
        default_path = os.path.join(BLOOM_DIR, "assets", "avatars", "sketch-guy.jpg")
        if avatar_path and os.path.exists(avatar_path):
            self.avatar_widget.set_image(avatar_path)
        else:
            self.avatar_widget.set_image(default_path)
        self.running_widget._refresh_programs()

    def mousePressEvent(self, event):
        if self.is_locked:
            return
        if self.settings_btn.geometry().contains(event.pos()):
            return
        self.clicked.emit()
