import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
from bloom.storage.database import get_user_data, save_user_setup

class SetupWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.selected_dir = ""
        
        # Pre-populate from existing DB data if it exists
        data = get_user_data(self.parent_app.db_conn)
        existing_name = ""
        if data:
            existing_name = data[0] or ""
            if data[1] and os.path.isdir(data[1]):
                self.selected_dir = data[1]

        self.setStyleSheet("background-color: #0f1219;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        # ── Title ──────────────────────────────────────────────
        title = QLabel("🌸  Bloom Terminal Setup")
        title.setStyleSheet(
            "color: white; font-size: 26px; font-weight: bold; margin-bottom: 10px;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel(
            "Tell us your name and choose a folder.\n"
            "The terminal will be sandboxed to that folder and its subfolders."
        )
        sub.setStyleSheet("color: #a0aec0; font-size: 13px;")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        # ── Name ───────────────────────────────────────────────
        name_lbl = QLabel("Your name")
        name_lbl.setStyleSheet("color: #73d936; font-size: 13px; font-weight: bold;")
        layout.addWidget(name_lbl)

        self.name_input = QLineEdit()
        self.name_input.setText(existing_name)
        self.name_input.setPlaceholderText("e.g.  aaryan")
        self.name_input.setStyleSheet(
            "padding: 10px; font-size: 15px; border-radius: 6px;"
            "background: #1a202c; color: white; border: 1px solid #2d3748;"
        )
        layout.addWidget(self.name_input)

        # ── Directory ──────────────────────────────────────────
        dir_lbl = QLabel("Base directory  (your terminal sandbox)")
        dir_lbl.setStyleSheet("color: #73d936; font-size: 13px; font-weight: bold;")
        layout.addWidget(dir_lbl)

        if self.selected_dir:
            self.dir_label = QLabel(f"✅  {self.selected_dir}")
            self.dir_label.setStyleSheet(
                "color: #73d936; font-size: 12px; padding: 6px 10px;"
                "background: rgba(115,217,54,0.08); border-radius: 5px;"
            )
        else:
            self.dir_label = QLabel("⚠  No directory selected — please choose one")
            self.dir_label.setStyleSheet(
                "color: #fbd38d; font-size: 12px; padding: 6px 10px;"
                "background: rgba(251,211,141,0.08); border-radius: 5px;"
            )
        layout.addWidget(self.dir_label)

        dir_btn = QPushButton("📂  Choose Base Directory")
        dir_btn.setStyleSheet(
            "padding: 10px; font-size: 14px; background-color: #3b8eea;"
            "color: white; border-radius: 6px; border: none;"
        )
        dir_btn.clicked.connect(self.select_directory)
        layout.addWidget(dir_btn)

        # ── Save ───────────────────────────────────────────────
        save_btn = QPushButton("✅  Save & Continue")
        save_btn.setStyleSheet(
            "padding: 12px; font-size: 15px; font-weight: bold;"
            "background-color: #38a169; color: white; border-radius: 6px;"
            "border: none; margin-top: 10px;"
        )
        save_btn.clicked.connect(self.save_setup)
        layout.addWidget(save_btn)

    # ── Slot: pick directory ───────────────────────────────────
    def select_directory(self):
        dialog = QFileDialog(self, "Choose Base Directory")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(
            "QFileDialog, QWidget { color: white; background-color: #1a202c; }"
            "QListView, QTreeView, QHeaderView { background: #0f1219; color: white; }"
            "QListView::item:hover, QTreeView::item:hover { background-color: #2d3748; }"
            "QListView::item:selected, QTreeView::item:selected { background-color: #3b8eea; color: white; }"
            "QLineEdit { background: #2d3748; color: white; border: 1px solid #4a5568; }"
            "QPushButton { background: #3b8eea; color: white; border-radius: 4px; padding: 5px 12px; }"
            "QComboBox { background: #2d3748; color: white; }"
        )
        if dialog.exec_():
            files = dialog.selectedFiles()
            if files and files[0]:
                self.selected_dir = files[0]
                self.dir_label.setText(f"✅  {self.selected_dir}")
                self.dir_label.setStyleSheet(
                    "color: #73d936; font-size: 12px; padding: 6px 10px;"
                    "background: rgba(115,217,54,0.08); border-radius: 5px;"
                )

    # ── Slot: save ────────────────────────────────────────────
    def save_setup(self):
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing name",
                                "Please enter your name before continuing.")
            return

        if not self.selected_dir:
            QMessageBox.warning(self, "No directory selected",
                                "Please choose a base directory.\n"
                                "The terminal will be sandboxed to that folder.")
            return

        save_user_setup(self.parent_app.db_conn, name, self.selected_dir)
        self.parent_app.load_user_data()
        self.parent_app.show_intro()
