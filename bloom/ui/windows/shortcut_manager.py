"""
bloom-shortcut  — custom command shortcut manager window.

Design matches /docs/screenshots/shortcut.png:
  - Title: BLOOM-shortcut (BLOOM in coral/red, -shortcut in white)
  - Cmd-Name input (short, left-aligned)
  - Cmd input (wide, full-row)
  - Output preview box: shows  bloom --"<name>"  live as user types
  - Submit button
  - Recent commands grid (3 cards, newest first)
  - "See More" button → opens full history window

Storage: JSON file at data/shortcuts.json (one file, no new dep).
Reserved names: built-in bloom commands that cannot be overridden.

ponytail: single-file, JSON storage (ceiling: migrate to sqlite if >1k shortcuts needed).
"""

import json
import os
import time

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bloom.core.paths import DATA_DIR

SHORTCUTS_FILE = os.path.join(DATA_DIR, "shortcuts.json")

# Built-in bloom commands that users cannot shadow
_RESERVED = {
    "profile", "lock", "doctor", "intro", "setup", "terminal", "tab",
    "-server", "-share", "-usb", "lockfile", "browser", "help",
    "message", "shortcut",
}


# ── Storage helpers ────────────────────────────────────────────────────────────

def _load() -> list:
    """Return list of shortcut dicts, newest-first order."""
    try:
        if os.path.exists(SHORTCUTS_FILE):
            with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save(shortcuts: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
        json.dump(shortcuts, f, indent=2)


def get_all_shortcuts() -> list:
    return _load()


def find_shortcut(name: str) -> dict | None:
    """Return a shortcut dict for name (case-insensitive) or None."""
    name = name.lower().strip()
    for s in _load():
        if s["name"].lower() == name and s.get("active", True):
            return s
    return None


def add_shortcut(name: str, command: str) -> str | None:
    """Add shortcut. Returns error string on failure, None on success."""
    name = name.strip().lower().replace(" ", "-")
    if not name:
        return "Command name cannot be empty."
    if name in _RESERVED:
        return f"'{name}' is a reserved bloom command name."
    shortcuts = _load()
    for s in shortcuts:
        if s["name"].lower() == name:
            if s.get("active", True):
                return f"'{name}' already exists. Delete or deactivate it first."
            else:
                # Re-use the slot, re-activate
                s["command"] = command
                s["active"] = True
                s["created_at"] = time.time()
                _save(shortcuts)
                return None
    shortcuts.insert(0, {
        "name": name,
        "command": command,
        "active": True,
        "created_at": time.time(),
    })
    _save(shortcuts)
    return None


def delete_shortcut(name: str):
    shortcuts = _load()
    shortcuts = [s for s in shortcuts if s["name"].lower() != name.lower()]
    _save(shortcuts)


def deactivate_shortcut(name: str):
    shortcuts = _load()
    for s in shortcuts:
        if s["name"].lower() == name.lower():
            s["active"] = False
    _save(shortcuts)


# ── Styled helpers ─────────────────────────────────────────────────────────────

_STYLE = """
QWidget {
    background-color: #16181f;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}
QLineEdit {
    background: #1e2130;
    border: 1.5px solid #2e3350;
    border-radius: 8px;
    padding: 8px 14px;
    color: #e2e8f0;
    font-size: 13px;
}
QLineEdit:focus { border-color: #e05252; }
QPushButton {
    background: transparent;
    border: 1.5px solid #e05252;
    border-radius: 10px;
    color: #e05252;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background: #e05252;
    color: #fff;
}
QPushButton:pressed { background: #c03030; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #1a1a2e; width: 6px; border-radius: 3px; }
QScrollBar::handle:vertical { background: #3a3a5a; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: bold; "
                      "letter-spacing: 1px; background: transparent;")
    return lbl


# ── Recent command card ────────────────────────────────────────────────────────

class ShortcutCard(QWidget):
    """Small card showing a shortcut in the 'recent' grid."""
    def __init__(self, shortcut: dict, parent=None):
        super().__init__(parent)
        self._data = shortcut
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        active = shortcut.get("active", True)
        bg = "#1e2130" if active else "#181820"
        border = "#2e3350" if active else "#2a2030"

        self.setStyleSheet(f"""
            ShortcutCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        name_lbl = QLabel(f'bloom --{shortcut["name"]}')
        name_lbl.setStyleSheet(
            "color: #e2e8f0; font-size: 12px; font-weight: bold; background: transparent;"
            if active else
            "color: #6b7280; font-size: 12px; font-weight: bold; background: transparent; text-decoration: line-through;"
        )
        lay.addWidget(name_lbl)

        cmd_lbl = QLabel(shortcut["command"])
        cmd_lbl.setStyleSheet("color: #6b7280; font-size: 11px; background: transparent;")
        cmd_lbl.setWordWrap(True)
        lay.addWidget(cmd_lbl)

        status = QLabel("● active" if active else "○ deactivated")
        status.setStyleSheet(
            "color: #4ade80; font-size: 10px; background: transparent;"
            if active else
            "color: #9ca3af; font-size: 10px; background: transparent;"
        )
        lay.addWidget(status)


# ── Full history window ────────────────────────────────────────────────────────

class ShortcutHistoryWindow(QWidget):
    """All shortcuts with delete / deactivate controls."""
    shortcuts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Bloom Shortcuts — All Commands")
        self.setMinimumSize(680, 500)
        self.setStyleSheet(_STYLE)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # Title
        title = QLabel()
        title.setText('<span style="color:#e05252;font-weight:bold;font-size:18px;">BLOOM</span>'
                      '<span style="color:#e2e8f0;font-size:18px;">-shortcuts  —  All Commands</span>')
        title.setTextFormat(Qt.RichText)
        lay.addWidget(title)

        # Scroll area
        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background: transparent;")
        self._scroll_lay = QVBoxLayout(self._scroll_widget)
        self._scroll_lay.setSpacing(8)
        self._scroll_lay.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._scroll_widget)
        lay.addWidget(scroll, 1)

        self._populate()

    def _populate(self):
        # Clear existing rows
        while self._scroll_lay.count():
            item = self._scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        shortcuts = _load()
        if not shortcuts:
            empty = QLabel("No shortcuts created yet.")
            empty.setStyleSheet("color: #4b5563; font-size: 13px; padding: 20px;")
            self._scroll_lay.addWidget(empty)
            return

        for s in shortcuts:
            row = self._make_row(s)
            self._scroll_lay.addWidget(row)

    def _make_row(self, s: dict) -> QFrame:
        active = s.get("active", True)
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #1e2130;
                border: 1px solid #2e3350;
                border-radius: 10px;
            }
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(3)

        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.get("created_at", 0)))
        name_lbl = QLabel(f'bloom --{s["name"]}')
        name_lbl.setStyleSheet(
            "color: #e2e8f0; font-weight: bold; font-size: 13px; background: transparent;"
            if active else
            "color: #6b7280; font-weight: bold; font-size: 13px; background: transparent; "
            "text-decoration: line-through;"
        )
        info.addWidget(name_lbl)

        cmd_lbl = QLabel(f'→  {s["command"]}')
        cmd_lbl.setStyleSheet("color: #9ca3af; font-size: 12px; background: transparent;")
        info.addWidget(cmd_lbl)

        ts_lbl = QLabel(f"Created: {ts}  |  {'Active' if active else 'Deactivated'}")
        ts_lbl.setStyleSheet("color: #4b5563; font-size: 10px; background: transparent;")
        info.addWidget(ts_lbl)

        lay.addLayout(info, 1)

        # Deactivate / Activate toggle
        toggle_btn = QPushButton("Deactivate" if active else "Activate")
        toggle_btn.setFixedWidth(100)
        toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #4b5563;
                border-radius: 8px;
                color: #9ca3af;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { border-color: #f59e0b; color: #f59e0b; }
        """)
        name = s["name"]
        toggle_btn.clicked.connect(lambda _, n=name, a=active: self._toggle(n, a))
        lay.addWidget(toggle_btn)

        # Delete
        del_btn = QPushButton("Delete")
        del_btn.setFixedWidth(70)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #7f1d1d;
                border-radius: 8px;
                color: #ef4444;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background: #7f1d1d; color: #fff; }
        """)
        del_btn.clicked.connect(lambda _, n=name: self._delete(n))
        lay.addWidget(del_btn)

        return frame

    def _toggle(self, name: str, currently_active: bool):
        if currently_active:
            deactivate_shortcut(name)
        else:
            shortcuts = _load()
            for s in shortcuts:
                if s["name"].lower() == name.lower():
                    s["active"] = True
            _save(shortcuts)
        self._populate()
        self.shortcuts_changed.emit()

    def _delete(self, name: str):
        reply = QMessageBox.question(
            self, "Delete Shortcut",
            f'Permanently delete  bloom --{name}?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_shortcut(name)
            self._populate()
            self.shortcuts_changed.emit()


# ── Main shortcut manager window ───────────────────────────────────────────────

class ShortcutManagerWindow(QWidget):
    """
    Main bloom-shortcut window.
    Layout (top-to-bottom):
      Title bar
      Cmd-Name input  (narrow, left-aligned — like the screenshot)
      Cmd input       (full width)
      Output preview  (read-only box: "bloom --"<name>"")
      Submit button   (centered)
      ── Recent commands (grid of 3 cards) ──
      See More button
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("bloom-shortcut")
        self.setMinimumSize(780, 580)
        self.setStyleSheet(_STYLE)
        self._history_win = None
        self._build()
        self._refresh_recent()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Title bar ──
        title_bar = QWidget()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet("background: #1a1c28; border-bottom: 1px solid #2e3350;")
        tb_lay = QHBoxLayout(title_bar)
        tb_lay.setContentsMargins(24, 0, 24, 0)
        title_lbl = QLabel()
        title_lbl.setText(
            '<span style="color:#e05252;font-weight:bold;font-size:20px;">BLOOM</span>'
            '<span style="color:#e2e8f0;font-size:20px;">-shortcut</span>'
        )
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setAlignment(Qt.AlignCenter)
        tb_lay.addWidget(title_lbl)
        outer.addWidget(title_bar)

        # ── Form area ──
        form_area = QWidget()
        form_area.setStyleSheet("background: #16181f;")
        form_lay = QVBoxLayout(form_area)
        form_lay.setContentsMargins(40, 32, 40, 24)
        form_lay.setSpacing(18)

        # Cmd-Name row
        name_row = QVBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(_section_label("Cmd-Name"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("command name here")
        self._name_input.setFixedWidth(280)
        self._name_input.textChanged.connect(self._update_preview)
        name_row.addWidget(self._name_input)
        form_lay.addLayout(name_row)

        # Cmd row
        cmd_row = QVBoxLayout()
        cmd_row.setSpacing(6)
        cmd_row.addWidget(_section_label("Cmd"))
        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText("command you want to make shortcut")
        self._cmd_input.textChanged.connect(self._update_preview)
        cmd_row.addWidget(self._cmd_input)
        form_lay.addLayout(cmd_row)

        # Output preview row
        out_row = QVBoxLayout()
        out_row.setSpacing(6)
        out_row.addWidget(_section_label("output"))
        self._preview = QLabel('bloom --…')
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet("""
            QLabel {
                background: #1e2130;
                border: 1.5px solid #2e3350;
                border-radius: 10px;
                padding: 12px 16px;
                color: #9ca3af;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)
        self._preview.setMinimumHeight(56)
        out_row.addWidget(self._preview)
        form_lay.addLayout(out_row)

        # Submit button (centered)
        submit_row = QHBoxLayout()
        submit_row.setAlignment(Qt.AlignCenter)
        self._submit_btn = QPushButton("Submit")
        self._submit_btn.setFixedWidth(160)
        self._submit_btn.clicked.connect(self._on_submit)
        submit_row.addWidget(self._submit_btn)
        form_lay.addLayout(submit_row)

        outer.addWidget(form_area)

        # ── Divider ──
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #2e3350; background: #2e3350; max-height: 1px;")
        outer.addWidget(div)

        # ── Recent commands area ──
        recent_area = QWidget()
        recent_area.setStyleSheet("background: #12141c;")
        recent_lay = QVBoxLayout(recent_area)
        recent_lay.setContentsMargins(40, 20, 40, 20)
        recent_lay.setSpacing(14)

        recent_hdr = _section_label("RECENT COMMANDS")
        recent_lay.addWidget(recent_hdr)

        self._grid = QGridLayout()
        self._grid.setSpacing(14)
        recent_lay.addLayout(self._grid)

        # See More
        see_more_row = QHBoxLayout()
        see_more_row.setAlignment(Qt.AlignCenter)
        see_more_btn = QPushButton("See More")
        see_more_btn.setFixedWidth(140)
        see_more_btn.clicked.connect(self._open_history)
        see_more_row.addWidget(see_more_btn)
        recent_lay.addLayout(see_more_row)

        outer.addWidget(recent_area, 1)

    # ── Logic ──────────────────────────────────────────────────────────────────

    def _update_preview(self):
        name = self._name_input.text().strip().lower().replace(" ", "-") or "…"
        self._preview.setText(f'bloom --{name}')
        self._preview.setStyleSheet("""
            QLabel {
                background: #1e2130;
                border: 1.5px solid #2e3350;
                border-radius: 10px;
                padding: 12px 16px;
                color: #c084fc;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """ if name != "…" else """
            QLabel {
                background: #1e2130;
                border: 1.5px solid #2e3350;
                border-radius: 10px;
                padding: 12px 16px;
                color: #9ca3af;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)

    def _on_submit(self):
        name = self._name_input.text().strip()
        command = self._cmd_input.text().strip()
        if not name:
            self._show_error("Please enter a command name.")
            return
        if not command:
            self._show_error("Please enter the command to run.")
            return
        err = add_shortcut(name, command)
        if err:
            self._show_error(err)
            return
        self._name_input.clear()
        self._cmd_input.clear()
        self._update_preview()
        self._refresh_recent()
        # Flash success
        orig = self._submit_btn.text()
        self._submit_btn.setText("✓ Saved!")
        self._submit_btn.setStyleSheet("""
            QPushButton {
                background: #166534;
                border: 1.5px solid #4ade80;
                border-radius: 10px;
                color: #4ade80;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        QTimer.singleShot(1500, lambda: (
            self._submit_btn.setText(orig),
            self._submit_btn.setStyleSheet("")
        ))

    def _show_error(self, msg: str):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Shortcut Error")
        dlg.setText(msg)
        dlg.setStyleSheet("""
            QMessageBox, QWidget { background: #1a1c28; color: #e2e8f0; }
            QLabel { color: #e2e8f0; }
            QPushButton {
                background: #e05252; color: #fff; border-radius: 6px;
                padding: 5px 16px; border: none;
            }
        """)
        dlg.exec_()

    def _refresh_recent(self):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        shortcuts = _load()[:3]  # 3 most recent
        if not shortcuts:
            empty = QLabel("No shortcuts yet — create one above!")
            empty.setStyleSheet("color: #4b5563; font-size: 12px; padding: 10px;")
            self._grid.addWidget(empty, 0, 0, 1, 3)
            return

        for col, s in enumerate(shortcuts):
            card = ShortcutCard(s)
            self._grid.addWidget(card, 0, col)

        # Fill remaining columns if fewer than 3
        for col in range(len(shortcuts), 3):
            placeholder = QFrame()
            placeholder.setStyleSheet(
                "QFrame { background: #1a1c28; border: 1.5px dashed #2e3350; "
                "border-radius: 12px; }"
            )
            placeholder.setFixedHeight(90)
            self._grid.addWidget(placeholder, 0, col)

    def _open_history(self):
        if self._history_win is None or not self._history_win.isVisible():
            self._history_win = ShortcutHistoryWindow()
            self._history_win.shortcuts_changed.connect(self._refresh_recent)
        self._history_win.show()
        self._history_win.raise_()
