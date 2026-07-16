"""
bloom/ui/dialogs/settings_dialog.py
Premium Settings Dialog with custom design, resetup buttons and lock screen logic.
"""
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QWidget, QPushButton, QLineEdit, QStackedWidget)
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush

from bloom.security.encryption import SecurityManager

_BG = '#0a0d14'
_CARD = '#161922'
_CARD2 = '#1c2331'
_BORDER = '#2d3345'
_ACCENT = '#7c6af7'
_TEXT = '#e2e8f8'

class _ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 26)
        self._state = False
        self._thumb_pos = 3
        self.setStyleSheet("background: transparent;")

    def setChecked(self, checked: bool):
        if self._state != checked:
            self._state = checked
            self._thumb_pos = 27 if checked else 3
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._state = not self._state
            self._thumb_pos = 27 if self._state else 3
            self.toggled.emit(self._state)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg_col = QColor(_ACCENT if self._state else _BORDER)
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 13, 13)

        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(self._thumb_pos, 3, 20, 20)
        p.end()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(650, 420)
        self.setStyleSheet(f"background-color: {_BG}; color: {_TEXT};")
        self.sec = SecurityManager()
        self.settings = QSettings("Bloom", "BloomTerminal")
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(24, 24, 24, 24)
        main_lay.setSpacing(20)

        # Header Row
        hdr = QHBoxLayout()
        title = QLabel("Settings")
        title.setFont(QFont("Georgia", 16, QFont.Bold))
        title.setStyleSheet("color: white;")
        hdr.addWidget(title)
        hdr.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("background: transparent; border: none; font-size: 18px; color: white;")
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        main_lay.addLayout(hdr)

        # Content area
        body = QHBoxLayout()
        body.setSpacing(20)

        # Left panel (options)
        left_p = QWidget()
        left_p.setStyleSheet(f"background-color: {_CARD}; border-radius: 12px; border: 1px solid {_BORDER};")
        left_lay = QVBoxLayout(left_p)
        left_lay.setContentsMargins(18, 18, 18, 18)
        left_lay.setSpacing(16)

        # Lock screen switch
        lock_row = QHBoxLayout()
        lbl_lock = QLabel("Lock Screen")
        lbl_lock.setFont(QFont("Georgia", 11))
        lock_row.addWidget(lbl_lock)
        self.lock_switch = _ToggleSwitch()
        self.lock_switch.toggled.connect(self._lock_toggled)
        lock_row.addWidget(self.lock_switch)
        left_lay.addLayout(lock_row)

        # Wingits switch
        wing_row = QHBoxLayout()
        lbl_wing = QLabel("Show Widgets")
        lbl_wing.setFont(QFont("Georgia", 11))
        wing_row.addWidget(lbl_wing)
        self.wing_switch = _ToggleSwitch()
        self.wing_switch.toggled.connect(self._wingits_toggled)
        wing_row.addWidget(self.wing_switch)
        left_lay.addLayout(wing_row)

        # Resetup Button in Middle of Left Panel
        left_lay.addSpacing(20)
        resetup_btn = QPushButton("🔄  Run Setup Wizard")
        resetup_btn.setCursor(Qt.PointingHandCursor)
        resetup_btn.setFont(QFont("Georgia", 11, QFont.Bold))
        resetup_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2740;
                color: #a0b0d0;
                border: 1px solid #2d3a55;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #2a3a5c;
                color: white;
                border-color: #3b82f6;
            }
        """)
        resetup_btn.clicked.connect(self._trigger_resetup)
        left_lay.addWidget(resetup_btn)

        left_lay.addStretch()
        body.addWidget(left_p, 1)

        # Right panel (Preview/Config area)
        self.right_p = QStackedWidget()
        self.right_p.setStyleSheet(f"background-color: {_CARD2}; border-radius: 12px; border: 1px solid {_BORDER};")

        # Page 1: Default placeholder
        self.p1 = QWidget()
        p1_lay = QVBoxLayout(self.p1)
        p1_lay.setContentsMargins(20, 20, 20, 20)
        p1_lay.setAlignment(Qt.AlignCenter)
        lbl_p1 = QLabel("Configure settings and options on the left pane.")
        lbl_p1.setFont(QFont("Georgia", 10))
        lbl_p1.setStyleSheet("color: #7a85a8;")
        lbl_p1.setAlignment(Qt.AlignCenter)
        p1_lay.addWidget(lbl_p1)
        self.right_p.addWidget(self.p1)

        # Page 2: Lock Setup Page
        self.p2 = QWidget()
        p2_lay = QVBoxLayout(self.p2)
        p2_lay.setSpacing(12)
        p2_lay.setContentsMargins(20, 20, 20, 20)

        lbl_sec = QLabel("Security Manager")
        lbl_sec.setFont(QFont("Georgia", 12, QFont.Bold))
        p2_lay.addWidget(lbl_sec)

        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("New Password")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setStyleSheet(f"background-color: {_BG}; border: 1px solid {_BORDER}; padding: 8px; border-radius: 6px; color: {_TEXT};")
        p2_lay.addWidget(self.pass_edit)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setPlaceholderText("Confirm Password")
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit.setStyleSheet(f"background-color: {_BG}; border: 1px solid {_BORDER}; padding: 8px; border-radius: 6px; color: {_TEXT};")
        p2_lay.addWidget(self.confirm_edit)

        self.lock_btn = QPushButton("Enable Lock & Encrypt")
        self.lock_btn.setCursor(Qt.PointingHandCursor)
        self.lock_btn.setStyleSheet(f"background-color: {_ACCENT}; padding: 10px; border-radius: 6px; font-weight: bold; color: white; border: none;")
        self.lock_btn.clicked.connect(self._save_lock)
        p2_lay.addWidget(self.lock_btn)

        self.lock_status = QLabel("")
        self.lock_status.setFont(QFont("Georgia", 10))
        self.lock_status.setStyleSheet("color: #facc15;")
        self.lock_status.setAlignment(Qt.AlignCenter)
        p2_lay.addWidget(self.lock_status)
        p2_lay.addStretch()

        self.right_p.addWidget(self.p2)
        body.addWidget(self.right_p, 1)

        main_lay.addLayout(body, 1)

    def _load_settings(self):
        lock_active = self.sec.is_locked()
        self.lock_switch.setChecked(lock_active)
        self.wing_switch.setChecked(self.settings.value("show_wingits", True, type=bool))

    def _lock_toggled(self, state):
        if state:
            self.right_p.setCurrentIndex(1)
        else:
            from PyQt5.QtWidgets import QInputDialog
            pwd, ok = QInputDialog.getText(self, "Disable Lock", "Enter your password to unlock data:", QLineEdit.Password)
            if ok and self.sec.disable_lock(pwd):
                self.lock_status.setText("Lock disabled successfully.")
                self.lock_switch.setChecked(False)
                self.right_p.setCurrentIndex(0)
            else:
                self.lock_status.setText("Incorrect password or error.")
                self.lock_switch.setChecked(True)

    def _save_lock(self):
        pwd = self.pass_edit.text()
        conf = self.confirm_edit.text()
        if not pwd:
            self.lock_status.setText("Password cannot be empty!")
            return
        if pwd != conf:
            self.lock_status.setText("Passwords do not match!")
            return
        if self.sec.enable_lock(pwd):
            self.lock_status.setText("Lock enabled!")
            self.pass_edit.clear()
            self.confirm_edit.clear()
            self.lock_switch.setChecked(True)
        else:
            self.lock_status.setText("Failed to encrypt data.")

    def _wingits_toggled(self, state):
        self.settings.setValue("show_wingits", state)

    def _trigger_resetup(self):
        self.close()
        # Access parent app via parent widget hierarchy and go to setup screen
        parent = self.parent()
        if parent and hasattr(parent, "go_to_setup"):
            parent.go_to_setup()
