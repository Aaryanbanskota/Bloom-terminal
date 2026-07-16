"""
bloom/ui/widgets/setup_widget.py
Premium setup page layout and design configuration.
"""
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QFileDialog, QMessageBox, QHBoxLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from bloom.storage.database import get_user_data, save_user_setup

class SetupWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.selected_dir = ""
        
        existing_name = ""
        if self.parent_app.db_conn:
            data = get_user_data(self.parent_app.db_conn)
            if data:
                existing_name = data[0] or ""
                if data[1] and os.path.isdir(data[1]):
                    self.selected_dir = data[1]

        self.setStyleSheet("background-color: #0a0d14;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Container box
        box = QWidget()
        box.setStyleSheet("""
            QWidget {
                background-color: #161922;
                border: 1px solid #2d3345;
                border-radius: 16px;
            }
        """)
        box.setFixedWidth(500)
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(30, 30, 30, 30)
        box_lay.setSpacing(15)

        # Title
        title = QLabel("🌸  Bloom Terminal Setup")
        title.setFont(QFont("Georgia", 22, QFont.Bold))
        title.setStyleSheet("color: white; border: none;")
        title.setAlignment(Qt.AlignCenter)
        box_lay.addWidget(title)

        sub = QLabel(
            "Tell us your name and choose a sandbox folder.\n"
            "Your workspace directory will be confined here."
        )
        sub.setFont(QFont("Georgia", 11))
        sub.setStyleSheet("color: #7a85a8; border: none;")
        sub.setAlignment(Qt.AlignCenter)
        box_lay.addWidget(sub)

        # Name
        name_lbl = QLabel("Your Name")
        name_lbl.setFont(QFont("Georgia", 11, QFont.Bold))
        name_lbl.setStyleSheet("color: #7c6af7; border: none;")
        box_lay.addWidget(name_lbl)

        self.name_input = QLineEdit()
        self.name_input.setText(existing_name)
        self.name_input.setPlaceholderText("e.g. aaryan")
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                font-size: 14px;
                border-radius: 8px;
                background-color: #0a0d14;
                color: white;
                border: 1.5px solid #2d3345;
            }
            QLineEdit:focus {
                border-color: #7c6af7;
            }
        """)
        box_lay.addWidget(self.name_input)

        # Directory
        dir_lbl = QLabel("Base Directory")
        dir_lbl.setFont(QFont("Georgia", 11, QFont.Bold))
        dir_lbl.setStyleSheet("color: #7c6af7; border: none;")
        box_lay.addWidget(dir_lbl)

        self.dir_label = QLabel()
        self._update_dir_label_style()
        box_lay.addWidget(self.dir_label)

        dir_btn = QPushButton("📂  Choose Directory")
        dir_btn.setCursor(Qt.PointingHandCursor)
        dir_btn.setFont(QFont("Georgia", 11, QFont.Bold))
        dir_btn.setStyleSheet("""
            QPushButton {
                padding: 10px;
                background-color: #1e2740;
                color: #a0b0d0;
                border: 1.5px solid #2d3a55;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2a3a5c;
                color: white;
                border-color: #3b82f6;
            }
        """)
        dir_btn.clicked.connect(self.select_directory)
        box_lay.addWidget(dir_btn)

        # Save Button
        save_btn = QPushButton("✅  Save & Launch")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFont(QFont("Georgia", 12, QFont.Bold))
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 12px;
                background-color: #7c6af7;
                color: white;
                border-radius: 8px;
                border: none;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #6c5ae7;
            }
        """)
        save_btn.clicked.connect(self.save_setup)
        box_lay.addWidget(save_btn)

        layout.addWidget(box, 0, Qt.AlignCenter)

    def _update_dir_label_style(self):
        if self.selected_dir:
            self.dir_label.setText(f"✅  {self.selected_dir}")
            self.dir_label.setStyleSheet("""
                QLabel {
                    color: #4ade80;
                    font-size: 11px;
                    padding: 8px 12px;
                    background: rgba(74,222,128,0.08);
                    border-radius: 6px;
                    border: 1px solid rgba(74,222,128,0.2);
                }
            """)
        else:
            self.dir_label.setText("⚠  No directory selected")
            self.dir_label.setStyleSheet("""
                QLabel {
                    color: #facc15;
                    font-size: 11px;
                    padding: 8px 12px;
                    background: rgba(250,204,21,0.08);
                    border-radius: 6px;
                    border: 1px solid rgba(250,204,21,0.2);
                }
            """)

    def select_directory(self):
        # Fallback helper similar to the song player to avoid crashes on Wayland/X11 systems
        import subprocess, shutil

        folder = ""
        # 1. zenity
        if shutil.which("zenity"):
            try:
                r = subprocess.run(
                    ["zenity", "--file-selection", "--directory", "--title=Choose Base Directory"],
                    capture_output=True, text=True, timeout=300
                )
                if r.returncode == 0:
                    folder = r.stdout.strip()
            except Exception:
                pass

        # 2. kdialog
        if not folder and shutil.which("kdialog"):
            try:
                r = subprocess.run(
                    ["kdialog", "--getexistingdirectory", os.path.expanduser("~"), "--title", "Choose Base Directory"],
                    capture_output=True, text=True, timeout=300
                )
                if r.returncode == 0:
                    folder = r.stdout.strip()
            except Exception:
                pass

        # 3. tkinter
        if not folder:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                folder = filedialog.askdirectory(title="Choose Base Directory")
                root.destroy()
            except Exception:
                pass

        # 4. Qt fallback (only if absolutely no other picker exists)
        if not folder:
            dialog = QFileDialog(self, "Choose Base Directory")
            dialog.setFileMode(QFileDialog.Directory)
            dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            dialog.setStyleSheet("""
                QFileDialog, QWidget { color: white; background-color: #1a202c; }
                QListView, QTreeView, QHeaderView { background: #0f1219; color: white; }
                QPushButton { background: #7c6af7; color: white; border-radius: 4px; padding: 5px 12px; }
            """)
            if dialog.exec_():
                files = dialog.selectedFiles()
                if files and files[0]:
                    folder = files[0]

        if folder:
            self.selected_dir = folder
            self._update_dir_label_style()

    def save_setup(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter your name.")
            return
        if not self.selected_dir:
            QMessageBox.warning(self, "No directory selected", "Please choose a base directory.")
            return

        if self.parent_app.db_conn is None:
            from bloom.storage.database import init_db
            self.parent_app.db_conn = init_db()

        save_user_setup(self.parent_app.db_conn, name, self.selected_dir)
        self.parent_app.load_user_data()
        self.parent_app.show_intro()
