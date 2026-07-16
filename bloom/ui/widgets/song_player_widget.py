"""
bloom/ui/widgets/song_player_widget.py

Song-Player widget — play audio from a local folder or a URL.

Threading model
───────────────
  Main thread   → emits _pick_trigger signal
  Worker thread ← receives it, runs zenity/kdialog subprocess (blocks worker, not UI)
  Worker thread → emits folder_picked signal
  Main thread   ← receives it, emits _scan_trigger signal
  Worker thread ← receives it, runs os.walk (blocks worker, not UI)
  Worker thread → emits songs_ready signal
  Main thread   ← receives it, updates UI

Rule: NOTHING blocking ever runs on the Qt main thread.
"""

import os
import random
import subprocess
import shutil

from PyQt5.QtCore import (Qt, QUrl, QTimer, pyqtSignal, pyqtSlot,
                           QThread, QObject)
from PyQt5.QtGui  import (QPainter, QColor, QBrush, QPen, QFont,
                           QLinearGradient)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QFrame,
                              QInputDialog, QMessageBox)

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    MEDIA_OK = True
except ImportError:
    MEDIA_OK = False


# ── colour tokens ─────────────────────────────────────────────────────────────
_CARD    = "#1a2035"
_BORDER  = "#2a3350"
_ACCENT  = "#7c6af7"
_ACCENT2 = "#f7866a"
_TEXT    = "#d4daf0"
_PLAY_BG = "#232b48"

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}

_MSG_STYLE = """
    QMessageBox        { background: #13182a; }
    QMessageBox QLabel { color: white; font-size: 13px; }
    QMessageBox QPushButton {
        background: #2a3350; color: white;
        border: 1px solid #7c6af7; border-radius: 6px;
        padding: 4px 14px;
    }
    QMessageBox QPushButton:hover { background: #7c6af7; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Worker — lives on a QThread, never touches any Qt widget
# ─────────────────────────────────────────────────────────────────────────────
class _FolderWorker(QObject):
    folder_picked = pyqtSignal(str)   # '' = cancelled
    songs_ready   = pyqtSignal(list)
    error         = pyqtSignal(str)

    @pyqtSlot()
    def pick_folder(self):
        """Slot — called on the worker thread via signal."""
        try:
            path = self._pick_native()
            self.folder_picked.emit(path)
        except Exception as exc:
            self.error.emit(str(exc))

    def _pick_native(self) -> str:
        # ── 1. zenity (GNOME / GTK) ──────────────────────────────────────────
        if shutil.which("zenity"):
            try:
                r = subprocess.run(
                    ["zenity", "--file-selection", "--directory",
                     "--title=Select Music Folder"],
                    capture_output=True, text=True, timeout=300
                )
                return r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                pass

        # ── 2. kdialog (KDE / Plasma) ─────────────────────────────────────────
        if shutil.which("kdialog"):
            try:
                r = subprocess.run(
                    ["kdialog", "--getexistingdirectory",
                     os.path.expanduser("~"),
                     "--title", "Select Music Folder"],
                    capture_output=True, text=True, timeout=300
                )
                return r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                pass

        # ── 3. tkinter fallback (completely separate GUI toolkit) ─────────────
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title="Select Music Folder")
            root.destroy()
            return folder or ""
        except Exception:
            pass

        return ""

    @pyqtSlot(str)
    def scan_folder(self, folder: str):
        """Slot — called on the worker thread via signal."""
        try:
            songs = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                        songs.append(os.path.join(root, f))
            songs.sort()
            self.songs_ready.emit(songs)
        except Exception as exc:
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Visual helpers
# ─────────────────────────────────────────────────────────────────────────────
class _RoundedCard(QFrame):
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


class _MarqueeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start(40)

    def _tick(self):
        tw = self.fontMetrics().horizontalAdvance(self.text())
        if tw > self.width():
            self._offset = (self._offset + 1) % (tw + 30)
            self.update()
        else:
            self._offset = 0

    def paintEvent(self, event):
        p  = QPainter(self)
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text())
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        if tw > self.width():
            p.drawText(-self._offset,
                       fm.ascent() + (self.height() - fm.height()) // 2,
                       self.text())
        else:
            p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _ProgressBar(QWidget):
    seek = pyqtSignal(float)

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
        p.setBrush(QBrush(QColor(_PLAY_BG)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)
        fw = int(w * self._ratio)
        if fw > 0:
            grad = QLinearGradient(0, 0, fw, 0)
            grad.setColorAt(0, QColor(_ACCENT))
            grad.setColorAt(1, QColor(_ACCENT2))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, fw, h, r, r)
        tx = max(r, min(fw, w - r))
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(tx - r, 0, h, h)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Main widget
# ─────────────────────────────────────────────────────────────────────────────
class SongPlayerWidget(_RoundedCard):
    """
    Bloom Song-Player.
    All blocking I/O (folder picker, directory scan) runs on a QThread.
    The Qt main thread / event loop is never blocked.
    """

    # These signals cross the thread boundary to the worker
    _pick_trigger = pyqtSignal()       # → worker.pick_folder()
    _scan_trigger = pyqtSignal(str)    # → worker.scan_folder(path)

    def __init__(self, parent=None):
        super().__init__(radius=20, parent=parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(260)

        self._playlist: list = []
        self._current        = -1
        self._playing        = False
        self._shuffle        = False
        self._duration_ms    = 0
        self._position_ms    = 0
        self._pending_folder = ""

        # ── Worker thread setup ───────────────────────────────────────────────
        self._thread = QThread(self)
        self._worker = _FolderWorker()
        self._worker.moveToThread(self._thread)

        # worker → main  (auto QueuedConnection across threads)
        self._worker.folder_picked.connect(self._on_folder_picked)
        self._worker.songs_ready.connect(self._on_songs_ready)
        self._worker.error.connect(self._on_worker_error)

        # main → worker  (QueuedConnection: slot runs on worker thread)
        self._pick_trigger.connect(self._worker.pick_folder,
                                   Qt.QueuedConnection)
        self._scan_trigger.connect(self._worker.scan_folder,
                                   Qt.QueuedConnection)

        self._thread.start()

        # ── Media player ──────────────────────────────────────────────────────
        if MEDIA_OK:
            self._player = QMediaPlayer()
            self._player.durationChanged.connect(self._on_duration)
            self._player.positionChanged.connect(self._on_position)
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.error.connect(self._on_error)
        else:
            self._player = None

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        hdr = QLabel("song-player")
        hdr.setFont(QFont("Georgia", 12, QFont.Bold))
        hdr.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(hdr)

        self._title = _MarqueeLabel()
        self._title.setText("No track loaded")
        self._title.setFont(QFont("Georgia", 9))
        self._title.setStyleSheet("color: #8090b8; background: transparent;")
        self._title.setFixedHeight(18)
        lay.addWidget(self._title)

        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 0, 0, 0)
        ctrl.setSpacing(12)
        ctrl.setAlignment(Qt.AlignCenter)

        self._btn_prev = QPushButton("⏮")
        self._btn_prev.setFont(QFont("Segoe UI", 15))
        self._btn_prev.setFixedSize(34, 34)
        self._btn_prev.setCursor(Qt.PointingHandCursor)
        self._btn_prev.setStyleSheet(
            "background: transparent; border: none; color: white;")

        self._btn_play = QPushButton("▶")
        self._btn_play.setFont(QFont("Segoe UI", 11))
        self._btn_play.setFixedSize(72, 26)
        self._btn_play.setCursor(Qt.PointingHandCursor)

        self._PLAY_STYLE = """
            QPushButton {
                background-color: #d1d5db; color: #0f172a;
                border-radius: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #e5e7eb; }
        """
        self._PAUSE_STYLE = """
            QPushButton {
                background-color: #7c6af7; color: white;
                border-radius: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #6c5ae7; }
        """
        self._LOADING_STYLE = """
            QPushButton {
                background-color: #2a3350; color: #7a85a8;
                border-radius: 13px; font-weight: bold;
            }
        """
        self._btn_play.setStyleSheet(self._PLAY_STYLE)

        self._btn_next = QPushButton("⏭")
        self._btn_next.setFont(QFont("Segoe UI", 15))
        self._btn_next.setFixedSize(34, 34)
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.setStyleSheet(
            "background: transparent; border: none; color: white;")

        self._btn_prev.clicked.connect(self.prev_track)
        self._btn_play.clicked.connect(self.toggle_play)
        self._btn_next.clicked.connect(self.next_track)

        ctrl.addWidget(self._btn_prev)
        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_next)
        lay.addLayout(ctrl)

        # Hidden compat labels
        self._source_lbl = QLabel(); self._source_lbl.setVisible(False)
        self._prog       = _ProgressBar(); self._prog.setVisible(False)
        self._time_cur   = QLabel(); self._time_cur.setVisible(False)
        self._time_tot   = QLabel(); self._time_tot.setVisible(False)
        self._btn_shuf   = QPushButton(); self._btn_shuf.setVisible(False)
        self._track_lbl  = QLabel(); self._track_lbl.setVisible(False)

        self._poll = QTimer()
        self._poll.setInterval(300)
        self._poll.timeout.connect(self._poll_position)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_folder(self):
        """Non-blocking: tells the worker thread to open the folder picker."""
        self._title.setText("📂 Picking folder…")
        self._btn_play.setText("…")
        self._btn_play.setStyleSheet(self._LOADING_STYLE)
        self._btn_play.setEnabled(False)
        # Signal crosses to worker thread → worker.pick_folder() runs there
        self._pick_trigger.emit()

    def load_url(self):
        url, ok = QInputDialog.getText(
            self, "Load from URL", "Enter audio URL (mp3/ogg/stream):",
            QLineEdit.Normal, "https://"
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        self._playlist = [url]
        self._current  = 0
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
        self._current = (
            random.randint(0, len(self._playlist) - 1) if self._shuffle
            else (self._current + 1) % len(self._playlist)
        )
        self._load_current(autoplay=self._playing)

    # ── Worker signal handlers (run on main thread) ───────────────────────────

    @pyqtSlot(str)
    def _on_folder_picked(self, folder: str):
        if not folder:
            self._reset_btn()
            return
        self._pending_folder = folder
        self._title.setText("🔍 Scanning…")
        # Signal crosses to worker thread → worker.scan_folder(folder) runs there
        self._scan_trigger.emit(folder)

    @pyqtSlot(list)
    def _on_songs_ready(self, songs: list):
        self._btn_play.setEnabled(True)
        if not songs:
            self._reset_btn()
            msg = QMessageBox(self)
            msg.setWindowTitle("No Audio Found")
            msg.setText("No supported audio files found in that folder.")
            msg.setStyleSheet(_MSG_STYLE)
            msg.exec_()
            return
        self._playlist = songs
        self._current  = 0
        name = os.path.basename(self._pending_folder)
        self._source_lbl.setText(f"📁 {name}  ({len(songs)} tracks)")
        self._track_lbl.setText(f"{len(songs)} tracks")
        self._reset_btn()
        self._load_current()

    @pyqtSlot(str)
    def _on_worker_error(self, msg_text: str):
        self._reset_btn()
        msg = QMessageBox(self)
        msg.setWindowTitle("Music Folder Error")
        msg.setText(f"Could not load music folder:\n{msg_text}")
        msg.setStyleSheet(_MSG_STYLE)
        msg.exec_()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _reset_btn(self):
        self._btn_play.setEnabled(True)
        self._btn_play.setText("▶")
        self._btn_play.setStyleSheet(self._PLAY_STYLE)
        if not self._playlist:
            self._title.setText("No track loaded")

    def _load_current(self, autoplay=True):
        if not self._playlist or self._current < 0:
            return
        track = self._playlist[self._current]
        name  = os.path.basename(track) if not track.startswith("http") else track
        self._title.setText(name)
        self._prog.set_ratio(0.0)
        self._time_cur.setText("0:00")
        self._time_tot.setText("0:00")
        if not MEDIA_OK or self._player is None:
            return
        content = (QMediaContent(QUrl(track))
                   if track.startswith("http")
                   else QMediaContent(QUrl.fromLocalFile(track)))
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
        if MEDIA_OK and status == QMediaPlayer.EndOfMedia:
            self.next_track()

    def _on_error(self, error):
        if error != QMediaPlayer.NoError and MEDIA_OK:
            txt = self._player.errorString() if self._player else "Unknown error"
            self._title.setText(f"Error: {txt[:30]}")
            self._playing = False
            self._reset_btn()

    def _no_media_msg(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Multimedia Unavailable")
        msg.setText(
            "PyQt5.QtMultimedia is not installed.\n"
            "Install:  pip install PyQt5-Qt5 PyQt5-sip"
        )
        msg.setStyleSheet(_MSG_STYLE)
        msg.exec_()

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    def closeEvent(self, event):
        self._thread.quit()
        self._thread.wait(3000)
        super().closeEvent(event)
