"""
bloom/security/encryption.py
Password-based encryption/decryption of user data using AES-256-GCM.
Uses pycryptodome (already in requirements.txt).
The database file is encrypted/decrypted when lock is enabled/disabled.
"""

import os
import hashlib
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtGui import QIcon, QFont

try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

from bloom.core.paths import DB_PATH

class SecurityManager:
    def __init__(self):
        self.settings = QSettings("Bloom", "BloomTerminal")

    def is_locked(self) -> bool:
        return self.settings.value("lock_enabled", False, type=bool)

    def verify_password(self, password: str) -> bool:
        stored_hash = self.settings.value("password_hash", "")
        if not stored_hash:
            return False
        # Simple salt-hash verification
        salt = bytes.fromhex(self.settings.value("password_salt", ""))
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return h.hex() == stored_hash

    def enable_lock(self, password: str, db_path: str = DB_PATH) -> bool:
        if not _CRYPTO_OK:
            return False
        try:
            salt = os.urandom(16)
            key = PBKDF2(password.encode(), salt, dkLen=32, count=100000)
            
            if not os.path.exists(db_path):
                return False

            with open(db_path, "rb") as f:
                data = f.read()

            cipher = AES.new(key, AES.MODE_GCM)
            ciphertext, tag = cipher.encrypt_and_digest(data)

            # Write .enc file
            with open(db_path + ".enc", "wb") as f:
                f.write(ciphertext)

            # Write metadata file
            with open(db_path + ".meta", "wb") as f:
                f.write(salt + cipher.nonce + tag)

            # Hash the password for verification check
            h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            self.settings.setValue("password_hash", h.hex())
            self.settings.setValue("password_salt", salt.hex())
            self.settings.setValue("lock_enabled", True)

            # Remove original unencrypted database
            os.remove(db_path)
            return True
        except Exception:
            return False

    def disable_lock(self, password: str, db_path: str = DB_PATH) -> bool:
        if not self.verify_password(password):
            return False
        if not _CRYPTO_OK:
            return False
        try:
            salt = bytes.fromhex(self.settings.value("password_salt", ""))
            key = PBKDF2(password.encode(), salt, dkLen=32, count=100000)

            enc_path = db_path + ".enc"
            meta_path = db_path + ".meta"

            if not os.path.exists(enc_path) or not os.path.exists(meta_path):
                return False

            with open(meta_path, "rb") as f:
                meta = f.read()
            salt_meta = meta[:16] # Matches salt
            nonce = meta[16:32]
            tag = meta[32:]

            with open(enc_path, "rb") as f:
                ciphertext = f.read()

            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            with open(db_path, "wb") as f:
                f.write(plaintext)

            # Remove files
            os.remove(enc_path)
            os.remove(meta_path)

            self.settings.setValue("lock_enabled", False)
            self.settings.remove("password_hash")
            self.settings.remove("password_salt")
            return True
        except Exception:
            return False

    def decrypt_for_access(self, password: str, db_path: str = DB_PATH) -> bool:
        if not self.verify_password(password):
            return False
        if not _CRYPTO_OK:
            return False
        try:
            salt = bytes.fromhex(self.settings.value("password_salt", ""))
            key = PBKDF2(password.encode(), salt, dkLen=32, count=100000)

            enc_path = db_path + ".enc"
            meta_path = db_path + ".meta"

            with open(meta_path, "rb") as f:
                meta = f.read()
            nonce = meta[16:32]
            tag = meta[32:]

            with open(enc_path, "rb") as f:
                ciphertext = f.read()

            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            # Temporarily restore db for this session
            with open(db_path, "wb") as f:
                f.write(plaintext)
            return True
        except Exception:
            return False


class PasswordLockScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #0a0d14; color: #e2e8f8;")
        self.setFixedSize(400, 300)
        self.sec = SecurityManager()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(15)

        title = QLabel("Bloom Lock")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #7c6af7;")
        lay.addWidget(title)

        subtitle = QLabel("Enter password to unlock your data")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #6b7898;")
        lay.addWidget(subtitle)

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setStyleSheet("""
            QLineEdit {
                background-color: #111827;
                border: 1px solid #1e2d4a;
                border-radius: 6px;
                padding: 8px;
                color: #e2e8f8;
            }
        """)
        lay.addWidget(self.pass_edit)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #f87171; font-size: 10px;")
        self.error_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.error_lbl)

        btn = QPushButton("Unlock")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #7c6af7;
                color: white;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6c5ae7;
            }
        """)
        btn.clicked.connect(self.attempt_unlock)
        lay.addWidget(btn)

    def attempt_unlock(self):
        password = self.pass_edit.text()
        if self.sec.decrypt_for_access(password):
            self.accept()
        else:
            self.error_lbl.setText("Incorrect password! Try again.")
            self.pass_edit.clear()
