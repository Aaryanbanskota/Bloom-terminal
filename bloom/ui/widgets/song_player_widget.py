"""
bloom/ui/widgets/song_player_widget.py
Song-Player "wingit" — play audio from a local folder or a URL.
Uses QMediaPlayer (PyQt5.QtMultimedia) which ships with most Qt5 builds.
Falls back gracefully if QtMultimedia is unavailable.
"""

import os
import random

from PyQt5.QtCore import Qt, QUrl, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import (QPainter, QColor, QBrush, QPen, QFont,
                          QLinearGradient, QFontDatabase)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFileDialog, QLineEdit,
                              QSlider, QSizePolicy, QFrame, QInputDialog,
                              QMessageBox)

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    MEDIA_OK = True
except ImportError:
    MEDIA_OK = False


# ── colour tokens ──────────────────────────────────────────────────────────
_BG        = "#13182a"
_CARD      = "#1a2035"
_BORDER    = "#2a3350"
_ACCENT    = "#7c6af7"
_ACCENT2   = "#f7866a"
_TEXT      = "#d4daf0"
_SUBTEXT   = "#7a85a8"
_PLAY_BG   = "#232b48"
_PLAY_BG_H = "#7c6af7"

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}


class _RoundedCard(QFrame):
    """A dark rounded-rect container."""
    def __init__(self, radius=18, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(_CARD)))
        p.setPen(QPen(QColor(_BORDER), 1.0))
        p.drawRoundedRect(self.rect(), self._radius, self._radius)
        p.end()


class _CircleButton(QPushButton):
    """Round icon button."""
    def __init__(self, symbol, size=36, parent=None):
        super().__init__(symbol, parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._hov = False
        self._active = False
        self.setStyleSheet("background: transparent; border: none;")

    def setActive(self, val: bool):
        self._active = val
        self.update()

    def enterEvent(self, e):
        self._hov = True
        self.update()

    def leaveEvent(self, e):
        self._hov = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = min(self.width(), self.height()) // 2 - 1
        cx, cy = self.width() // 2, self.height() // 2
        if self._active or self._hov:
            p.setBrush(QBrush(QColor(_ACCENT)))
        else:
            p.setBrush(QBrush(QColor(_PLAY_BG)))
        p.setPen(QPen(QColor(_BORDER), 1))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QColor("white" if (self._active or self._hov) else _TEXT))
        font = p.font()
        font.setPointSize(int(self.height() * 0.35))
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _MarqueeLabel(QLabel):
    """Auto-scrolling label for long song names."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start(40)

    def _tick(self):
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text())
        if tw > self.width():
            self._offset = (self._offset + 1) % (tw + 30)
            self.update()
        else:
            self._offset = 0

    def paintEvent(self, event):
        p = QPainter(self)
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text())
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        if tw > self.width():
            p.drawText(-self._offset, fm.ascent() + (self.height() - fm.height()) // 2,
                       self.text())
        else:
            p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _ProgressBar(QWidget):
    """Thin clickable progress/seek bar."""
    seek = pyqtSignal(float)   # emits 0.0–1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self._ratio = 0.0

    def set_ratio(self, r: float):
        self._ratio = max(0.0, min(1.0, r))
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.width() > 0:
            self.seek.emit(e.x() / self.width())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h // 2

        # track
        p.setBrush(QBrush(QColor(_PLAY_BG)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # fill
        fw = int(w * self._ratio)
        if fw > 0:
            grad = QLinearGradient(0, 0, fw, 0)
            grad.setColorAt(0, QColor(_ACCENT))
            grad.setColorAt(1, QColor(_ACCENT2))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, fw, h, r, r)

        # thumb
        tx = max(r, min(fw, w - r))
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(tx - r, 0, h, h)
        p.end()


class SongPlayerWidget(_RoundedCard):
    """
    Bloom Song-Player wingit.
    • Load songs from a local folder (recursive scan).
    • Load a song/stream from a URL.
    • Prev / Play-Pause / Next controls.
    • Seekable progress bar + time display.
    • Shuffle toggle.
    """

    def __init__(self, parent=None):
        super().__init__(radius=20, parent=parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(260)

        self._playlist: list[str] = []      # file paths or URLs
        self._current = -1
        self._playing = False
        self._shuffle = False
        self._duration_ms = 0
        self._position_ms = 0

        if MEDIA_OK:
            self._player = QMediaPlayer()
            self._player.durationChanged.connect(self._on_duration)
            self._player.positionChanged.connect(self._on_position)
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.error.connect(self._on_error)
        else:
            self._player = None

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        # header
        hdr = QLabel("song-player")
        hdr.setFont(QFont("Georgia", 12, QFont.Bold))
        hdr.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(hdr)

        # Song title marquee (visible)
        self._title = _MarqueeLabel()
        self._title.setText("No track loaded")
        self._title.setFont(QFont("Georgia", 9))
        self._title.setStyleSheet("color: #8090b8; background: transparent;")
        self._title.setFixedHeight(18)
        lay.addWidget(self._title)

        # controls row
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 0, 0, 0)
        ctrl.setSpacing(12)
        ctrl.setAlignment(Qt.AlignCenter)

        self._btn_prev = QPushButton("⏮")
        self._btn_prev.setFont(QFont("Segoe UI", 15))
        self._btn_prev.setFixedSize(34, 34)
        self._btn_prev.setCursor(Qt.PointingHandCursor)
        self._btn_prev.setStyleSheet("background: transparent; border: none; color: white;")

        # Play/pause pill button — use stylesheet not setActive()
        self._btn_play = QPushButton("▶")
        self._btn_play.setFont(QFont("Segoe UI", 11))
        self._btn_play.setFixedSize(72, 26)
        self._btn_play.setCursor(Qt.PointingHandCursor)
        self._PLAY_STYLE = """
            QPushButton {
                background-color: #d1d5db;
                color: #0f172a;
                border-radius: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e5e7eb; }
        """
        self._PAUSE_STYLE = """
            QPushButton {
                background-color: #7c6af7;
                color: white;
                border-radius: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6c5ae7; }
        """
        self._btn_play.setStyleSheet(self._PLAY_STYLE)

        self._btn_next = QPushButton("⏭")
        self._btn_next.setFont(QFont("Segoe UI", 15))
        self._btn_next.setFixedSize(34, 34)
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.setStyleSheet("background: transparent; border: none; color: white;")

        self._btn_prev.clicked.connect(self.prev_track)
        self._btn_play.clicked.connect(self.toggle_play)
        self._btn_next.clicked.connect(self.next_track)

        ctrl.addWidget(self._btn_prev)
        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_next)
        lay.addLayout(ctrl)

        # Hidden backend-compatibility labels
        self._source_lbl = QLabel()
        self._source_lbl.setVisible(False)
        self._prog = _ProgressBar()
        self._prog.setVisible(False)
        self._time_cur = QLabel()
        self._time_cur.setVisible(False)
        self._time_tot = QLabel()
        self._time_tot.setVisible(False)
        self._btn_shuf = QPushButton()
        self._btn_shuf.setVisible(False)
        self._track_lbl = QLabel()
        self._track_lbl.setVisible(False)

        # poll timer (fallback position update)
        self._poll = QTimer()
        self._poll.setInterval(300)
        self._poll.timeout.connect(self._poll_position)

    def _small_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {_PLAY_BG};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: {_ACCENT};
                color: white;
                border-color: {_ACCENT};
            }}
        """)
        return b

    # ── public API ─────────────────────────────────────────────────────────

    def load_folder(self):
        dialog = QFileDialog(self, "Select Music Folder")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        if dialog.exec_():
            folder = dialog.selectedFiles()[0]
        else:
            return
        songs = []
        for root, _, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                    songs.append(os.path.join(root, f))
        songs.sort()
        if not songs:
            QMessageBox.information(self, "No Audio", "No supported audio files found in that folder.")
            return
        self._playlist = songs
        self._current = 0
        self._source_lbl.setText(f"📁 {os.path.basename(folder)}  ({len(songs)} tracks)")
        self._track_lbl.setText(f"{len(songs)} tracks")
        self._load_current()

    def load_url(self):
        url, ok = QInputDialog.getText(
            self, "Load from URL", "Enter audio URL (mp3/ogg/stream):",
            QLineEdit.Normal, "https://"
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        self._playlist = [url]
        self._current = 0
        self._source_lbl.setText(f"🔗 {url[:35]}…" if len(url) > 35 else f"🔗 {url}")
        self._track_lbl.setText("stream")
        self._load_current()

    def toggle_play(self):
        if not self._playlist:
            self.load_folder()
            return
        if not MEDIA_OK or self._player is None:
            self._no_media_msg()
            return
        if self._playing:
            self._player.pause()
            self._playing = False
            self._btn_play.setText("▶")
            self._btn_play.setStyleSheet(self._PLAY_STYLE)
            self._poll.stop()
        else:
            self._player.play()
            self._playing = True
            self._btn_play.setText("⏸")
            self._btn_play.setStyleSheet(self._PAUSE_STYLE)
            self._poll.start()

    def prev_track(self):
        if not self._playlist:
            return
        self._current = (self._current - 1) % len(self._playlist)
        self._load_current(autoplay=self._playing)

    def next_track(self):
        if not self._playlist:
            return
        if self._shuffle:
            self._current = random.randint(0, len(self._playlist) - 1)
        else:
            self._current = (self._current + 1) % len(self._playlist)
        self._load_current(autoplay=self._playing)

    # ── internals ──────────────────────────────────────────────────────────

    def _toggle_shuffle(self):
        self._shuffle = not self._shuffle
        self._btn_shuf.setActive(self._shuffle)

    def _load_current(self, autoplay=True):
        if not self._playlist or self._current < 0:
            return
        track = self._playlist[self._current]
        name = os.path.basename(track) if not track.startswith("http") else track
        self._title.setText(name)
        self._prog.set_ratio(0.0)
        self._time_cur.setText("0:00")
        self._time_tot.setText("0:00")

        if not MEDIA_OK or self._player is None:
            return
        if track.startswith("http"):
            content = QMediaContent(QUrl(track))
        else:
            content = QMediaContent(QUrl.fromLocalFile(track))
        self._player.setMedia(content)
        if autoplay:
            self._player.play()
            self._playing = True
            self._btn_play.setText("⏸")
            self._btn_play.setStyleSheet(self._PAUSE_STYLE)
            self._poll.start()

    def _seek(self, ratio: float):
        if MEDIA_OK and self._player and self._duration_ms > 0:
            self._player.setPosition(int(ratio * self._duration_ms))

    def _poll_position(self):
        if MEDIA_OK and self._player:
            self._on_position(self._player.position())

    def _on_duration(self, ms: int):
        self._duration_ms = ms
        self._time_tot.setText(self._fmt(ms))

    def _on_position(self, ms: int):
        self._position_ms = ms
        self._time_cur.setText(self._fmt(ms))
        if self._duration_ms > 0:
            self._prog.set_ratio(ms / self._duration_ms)

    def _on_status(self, status):
        if MEDIA_OK:
            if status == QMediaPlayer.EndOfMedia:
                self.next_track()

    def _on_error(self, error):
        if error != QMediaPlayer.NoError and MEDIA_OK:
            msg = self._player.errorString() if self._player else "Unknown error"
            self._title.setText(f"Error: {msg[:30]}")
            self._playing = False
            self._btn_play.setText("▶")
            self._btn_play.setStyleSheet(self._PLAY_STYLE)

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    def _no_media_msg(self):
        QMessageBox.warning(
            self, "Multimedia Unavailable",
            "PyQt5.QtMultimedia is not installed in this environment.\n"
            "Install it with:  pip install PyQt5-Qt5 PyQt5-sip"
        )
