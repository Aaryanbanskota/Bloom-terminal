import os
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
                             QScrollArea, QWidget, QFrame, QSlider, QGridLayout,
                             QFileDialog, QMessageBox)
from PyQt5.QtGui import QPixmap, QColor, QPainter, QPainterPath, QPen, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QSize

from bloom.core.paths import AVATARS_DIR
from bloom.ui.widgets.avatar_cropper import AvatarCropper
from bloom.storage.database import update_user_stats

# ────────────────────────────────────────────────────────────────
#  Profile Edit Dialog
# ────────────────────────────────────────────────────────────────
class ProfileEditDialog(QDialog):
    updated = pyqtSignal(str)   # emits saved image path

    def __init__(self, current_avatar):
        super().__init__()
        self.setWindowTitle("Edit Profile Avatar")
        self.setFixedSize(760, 500)
        self.setStyleSheet("""
            QDialog, QWidget { 
                background-color: #0f1219; 
                color: white;
            }
            QLabel  { color: white; }
            QPushButton {
                background-color: #2d3748;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover { background-color: #3b8eea; }
            QListView, QTreeView, QLineEdit {
                background-color: #1a202c;
                color: white;
                border: 1px solid #2d3748;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #2d3748;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3b8eea;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #3b8eea; border-radius: 2px; }
            QScrollArea { border: none; background: transparent; }
        """)

        self._saved_path = current_avatar
        main = QHBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(20)

        # ── Left panel ──────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(12)

        title = QLabel("Avatar Editor")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #73d936;")
        left.addWidget(title)

        self.cropper = AvatarCropper()
        left.addWidget(self.cropper, alignment=Qt.AlignHCenter)

        # Zoom slider
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("🔍"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(0, 300)
        self.zoom_slider.setValue(0)
        self.zoom_slider.setFixedWidth(200)
        self.zoom_slider.valueChanged.connect(self.cropper.set_scale)
        zoom_row.addWidget(self.zoom_slider)
        left.addLayout(zoom_row)

        # Buttons row
        btn_row = QHBoxLayout()
        upload_btn = QPushButton("📂  Upload Image")
        upload_btn.clicked.connect(self.upload_image)
        save_btn = QPushButton("✅  Save Avatar")
        save_btn.setStyleSheet("background-color: #38a169; color: white; border-radius: 6px; padding: 8px 14px;")
        save_btn.clicked.connect(self.save_avatar)
        btn_row.addWidget(upload_btn)
        btn_row.addWidget(save_btn)
        left.addLayout(btn_row)

        left.addStretch()
        main.addLayout(left)

        # ── Divider ─────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("background-color: #2d3748; max-width: 1px;")
        main.addWidget(div)

        # ── Right panel — Avatar gallery ─────────────────────────
        right = QVBoxLayout()
        right.setSpacing(10)
        gallery_title = QLabel("Choose Preset Avatar")
        gallery_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #a0aec0;")
        right.addWidget(gallery_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)

        os.makedirs(AVATARS_DIR, exist_ok=True)
        images = [
            f for f in sorted(os.listdir(AVATARS_DIR))
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and f != "saved_avatar.png"
        ]

        for i, fname in enumerate(images):
            path = os.path.join(AVATARS_DIR, fname)
            btn = self._make_avatar_btn(path)
            grid.addWidget(btn, i // 2, i % 2)

        # Empty placeholders if fewer than 4 images
        for i in range(len(images), max(4, len(images))):
            ph = QLabel()
            ph.setFixedSize(110, 110)
            ph.setStyleSheet("background: #1a202c; border: 1px dashed #2d3748; border-radius: 10px;")
            grid.addWidget(ph, i // 2, i % 2)

        scroll.setWidget(grid_widget)
        right.addWidget(scroll)
        main.addLayout(right)

        # Pre-load current avatar
        if current_avatar and os.path.exists(current_avatar):
            self._load_to_cropper(current_avatar)

    def _make_avatar_btn(self, path):
        btn = QPushButton()
        btn.setFixedSize(110, 110)
        thumb = QPixmap(path).scaled(110, 110, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        icon = QIcon(thumb)
        btn.setIcon(icon)
        btn.setIconSize(QSize(110, 110))
        btn.setStyleSheet("""
            QPushButton {
                border-radius: 10px;
                border: 2px solid #2d3748;
                background-color: #1a202c;
            }
            QPushButton:hover { border: 2px solid #3b8eea; }
        """)
        btn.clicked.connect(lambda _, p=path: self._load_to_cropper(p))
        return btn

    def _load_to_cropper(self, path):
        self._saved_path = path
        self.zoom_slider.setValue(0)
        self.cropper.load_pixmap(QPixmap(path))

    def upload_image(self):
        dialog = QFileDialog(self, "Select Image")
        dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.webp)")
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
            if files:
                self._load_to_cropper(files[0])

    def save_avatar(self):
        cropped = self.cropper.get_cropped_image()
        save_path = os.path.join(AVATARS_DIR, "saved_avatar.png")
        cropped.save(save_path)
        self._saved_path = save_path
        self.updated.emit(save_path)
        self.accept()


# ────────────────────────────────────────────────────────────────
#  Animated circular avatar label helper
# ────────────────────────────────────────────────────────────────
def make_circle_pixmap(path, size=120) -> QPixmap:
    src = QPixmap(path).scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, size, size))
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.setClipping(False)
    painter.setPen(QPen(QColor("#e53e3e"), 4))
    painter.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    painter.end()
    return result


# ────────────────────────────────────────────────────────────────
#  Profile View Dialog
# ────────────────────────────────────────────────────────────────
class ProfileDialog(QDialog):
    def __init__(self, user_data, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.name, self.base_dir, self.xp, self.level, self.succ, self.fail, self.avatar = user_data

        self.setWindowTitle("Bloom Profile")
        self.setFixedSize(700, 560)
        self.setStyleSheet("""
            QDialog, QWidget { 
                background-color: #0f1219; 
                color: white;
            }
            QLabel  { color: white; }
            QPushButton {
                background-color: #2d3748;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3b8eea; }
            QScrollArea { border: none; background: transparent; }
            QListView, QTreeView, QLineEdit {
                background-color: #1a202c;
                color: white;
                border: 1px solid #2d3748;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        self.avatar_lbl = QLabel()
        self.avatar_lbl.setFixedSize(120, 120)
        self._refresh_avatar()
        header.addWidget(self.avatar_lbl)

        info = QVBoxLayout()
        info.setSpacing(4)
        tier = self._tier()
        name_lbl = QLabel(f"<span style='font-size:22px; font-weight:bold; color:#73d936;'>{self.name}</span>")
        tier_lbl  = QLabel(f"<span style='font-size:14px; color:#3b8eea;'>{tier}</span>")
        level_lbl = QLabel(f"<span style='font-size:13px;'>Level <b>{self.level}</b> &nbsp;|&nbsp; XP: <b>{self.xp}</b></span>")
        stats_lbl = QLabel(
            f"<span style='font-size:13px;'>"
            f"✅ Success: <b style='color:#73d936;'>{self.succ}</b>&nbsp;&nbsp;"
            f"❌ Failed: <b style='color:#e53e3e;'>{self.fail}</b></span>"
        )
        for w in (name_lbl, tier_lbl, level_lbl, stats_lbl):
            info.addWidget(w)
        info.addStretch()
        header.addLayout(info)
        header.addStretch()

        edit_btn = QPushButton("✏️  Edit Profile")
        edit_btn.clicked.connect(self._open_edit)
        header.addWidget(edit_btn, alignment=Qt.AlignTop)
        layout.addLayout(header)

        # ── XP Progress bar ──────────────────────────────────────
        xp_needed = self._xp_for_next_level()
        xp_current = self.xp - self._xp_for_level(self.level)
        pct = min(1.0, xp_current / max(1, xp_needed))

        bar_bg = QWidget()
        bar_bg.setFixedHeight(10)
        bar_bg.setStyleSheet("background: #2d3748; border-radius: 5px;")
        bar_fill = QWidget(bar_bg)
        bar_fill.setFixedHeight(10)
        bar_fill.setFixedWidth(int(pct * 652))
        bar_fill.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                               "stop:0 #3b8eea, stop:1 #73d936); border-radius: 5px;")
        layout.addWidget(bar_bg)
        xp_lbl = QLabel(f"XP to next level: {xp_current} / {xp_needed}")
        xp_lbl.setStyleSheet("color: #a0aec0; font-size: 11px;")
        layout.addWidget(xp_lbl)

        # ── Perks ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #2d3748;")
        layout.addWidget(sep)

        perks_title = QLabel("🏆  Unlocked Perks")
        perks_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(perks_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        perk_widget = QWidget()
        perk_widget.setStyleSheet("background: transparent;")
        perk_layout = QVBoxLayout(perk_widget)
        perk_layout.setSpacing(6)

        for perk in self._unlocked_perks():
            row = QLabel(f"<span style='color:#73d936;'>✔</span>  {perk}")
            row.setStyleSheet(
                "font-size:13px; padding: 6px 10px;"
                "background: rgba(59,142,234,0.08);"
                "border-radius: 6px;"
            )
            perk_layout.addWidget(row)

        perk_layout.addStretch()
        scroll.setWidget(perk_widget)
        layout.addWidget(scroll)

    def _refresh_avatar(self):
        if self.avatar and os.path.exists(self.avatar):
            self.avatar_lbl.setPixmap(make_circle_pixmap(self.avatar, 120))
        else:
            ph = QPixmap(120, 120)
            ph.fill(QColor("#1a202c"))
            self.avatar_lbl.setPixmap(ph)

    def _open_edit(self):
        dlg = ProfileEditDialog(self.avatar)
        def _on_update(path):
            self.avatar = path
            update_user_stats(
                self.parent_app.db_conn,
                self.xp, self.level, self.succ, self.fail, self.avatar
            )
            self._refresh_avatar()
        dlg.updated.connect(_on_update)
        dlg.exec_()

    def _tier(self):
        if self.level <= 20: return "🌱 Tier 1 — The Seedling"
        if self.level <= 50: return "🌿 Tier 2 — The Sprout"
        if self.level <= 80: return "🌸 Tier 3 — The Bloom"
        return "🌳 Tier 4 — The Master Gardener"

    def _xp_for_level(self, lvl):
        return int(((lvl - 1) ** (1 / 0.6)) * 100)

    def _xp_for_next_level(self):
        return self._xp_for_level(self.level + 1) - self._xp_for_level(self.level)

    def _unlocked_perks(self):
        all_perks = [
            (1,   "Bloom Buddy AI Access — errors explained in plain English"),
            (10,  "Custom Prompt Color"),
            (15,  "Command History Search (visual Ctrl+R)"),
            (20,  "New Theme Unlock — Spring / Minimalist palette"),
            (25,  "Visual Breadcrumbs — persistent path bar"),
            (30,  "Split-Pane View — multitask with two terminals"),
            (40,  "Auto-Complete Magic — smart predictive text"),
            (50,  "Desktop Widgets — live CPU/Memory dashboard"),
            (60,  "Alias Builder — GUI shortcut creator"),
            (70,  "Script Gallery — one-click Bloom Scripts"),
            (80,  "Custom Badge/Avatar Frame — Master borders"),
            (90,  "Developer Mode — advanced engine config"),
            (100, "Bloom Architect Title — export & share custom themes"),
        ]
        return [f"Level {lvl}: {desc}" for lvl, desc in all_perks if self.level >= lvl]
