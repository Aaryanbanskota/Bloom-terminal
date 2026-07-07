import sys
import os
import sqlite3
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit, 
                             QLabel, QStackedWidget, QLineEdit, QPushButton, 
                             QFileDialog, QHBoxLayout, QTabWidget, QTabBar,
                             QDialog, QGridLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem)
from PyQt5.QtGui import QPixmap, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtCore import Qt, QTimer, QProcess, pyqtSignal, QPointF

DB_PATH = 'data.sql'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            base_dir TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            success_cmds INTEGER DEFAULT 0,
            failed_cmds INTEGER DEFAULT 0,
            avatar TEXT DEFAULT ''
        )
    ''')
    # Try adding columns if they don't exist (basic migration)
    try: cursor.execute('ALTER TABLE user_data ADD COLUMN xp INTEGER DEFAULT 0')
    except: pass
    try: cursor.execute('ALTER TABLE user_data ADD COLUMN level INTEGER DEFAULT 1')
    except: pass
    try: cursor.execute('ALTER TABLE user_data ADD COLUMN success_cmds INTEGER DEFAULT 0')
    except: pass
    try: cursor.execute('ALTER TABLE user_data ADD COLUMN failed_cmds INTEGER DEFAULT 0')
    except: pass
    try: cursor.execute('ALTER TABLE user_data ADD COLUMN avatar TEXT DEFAULT ""')
    except: pass
    
    conn.commit()
    return conn

def get_user_data(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT name, base_dir, xp, level, success_cmds, failed_cmds, avatar FROM user_data LIMIT 1')
    return cursor.fetchone()

def save_user_setup(conn, name, base_dir):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_data')
    cursor.execute('INSERT INTO user_data (name, base_dir) VALUES (?, ?)', (name, base_dir))
    conn.commit()

def update_user_stats(conn, xp, level, success, failed, avatar):
    cursor = conn.cursor()
    cursor.execute('''UPDATE user_data SET 
        xp = ?, level = ?, success_cmds = ?, failed_cmds = ?, avatar = ?
    ''', (xp, level, success, failed, avatar))
    conn.commit()

class ImageCropper(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setStyleSheet("background: transparent; border: 2px solid red; border-radius: 125px;")
        self.setFixedSize(250, 250)
        
        self.pixmap_item = None
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def set_image(self, pixmap):
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        # Center the image
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)


class ProfileEditDialog(QDialog):
    updated = pyqtSignal(str) # Emits the chosen avatar path

    def __init__(self, current_avatar):
        super().__init__()
        self.setWindowTitle("Edit Profile")
        self.setFixedSize(600, 400)
        self.setStyleSheet("background-color: #0f1219; color: white;")
        
        layout = QHBoxLayout(self)
        
        # Left side: Image Cropper
        left_layout = QVBoxLayout()
        self.cropper = ImageCropper()
        left_layout.addWidget(self.cropper, alignment=Qt.AlignCenter)
        
        save_btn = QPushButton("Save Avatar")
        save_btn.setStyleSheet("background-color: #3b8eea; padding: 5px; border-radius: 3px;")
        save_btn.clicked.connect(self.save_avatar)
        left_layout.addWidget(save_btn, alignment=Qt.AlignCenter)
        layout.addLayout(left_layout)
        
        # Right side: Avatar selections
        right_layout = QGridLayout()
        self.avatar_dir = "/home/aaryan/Documents/bloom/python-bloom/profile-selection"
        self.selected_avatar = current_avatar
        
        # Create folder if it doesn't exist
        os.makedirs(self.avatar_dir, exist_ok=True)
        
        # List images
        images = [f for f in os.listdir(self.avatar_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))] if os.path.exists(self.avatar_dir) else []
        
        row, col = 0, 0
        for i in range(4): # Show up to 4 placeholders/images
            btn = QPushButton()
            btn.setFixedSize(80, 80)
            if i < len(images):
                path = os.path.join(self.avatar_dir, images[i])
                btn.setStyleSheet(f"background-image: url({path}); background-color: lightgray; border: none;")
                btn.clicked.connect(lambda checked, p=path: self.load_to_cropper(p))
            else:
                btn.setStyleSheet("background-color: lightgray; border: none;")
            
            right_layout.addWidget(btn, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
                
        layout.addLayout(right_layout)

        if current_avatar and os.path.exists(current_avatar):
            self.load_to_cropper(current_avatar)

    def load_to_cropper(self, path):
        self.selected_avatar = path
        self.cropper.set_image(QPixmap(path))

    def save_avatar(self):
        # In a real app we'd save the cropped image, here we just save the path
        self.updated.emit(self.selected_avatar)
        self.accept()

class ProfileDialog(QDialog):
    def __init__(self, user_data, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.setWindowTitle("User Profile")
        self.setFixedSize(600, 500)
        self.setStyleSheet("background-color: #0f1219; color: white;")
        
        self.name, self.base_dir, self.xp, self.level, self.succ, self.fail, self.avatar = user_data
        
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(100, 100)
        self.update_avatar_display()
        header.addWidget(self.avatar_label)
        
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"<h2 style='margin:0;'>{self.name}</h2>"))
        info_layout.addWidget(QLabel(f"Level {self.level} - XP: {self.xp}"))
        info_layout.addWidget(QLabel(f"Success: {self.succ} | Failed: {self.fail}"))
        header.addLayout(info_layout)
        header.addStretch()
        
        edit_btn = QPushButton("Edit Profile")
        edit_btn.setStyleSheet("background-color: #3b8eea; padding: 10px; border-radius: 5px;")
        edit_btn.clicked.connect(self.open_edit)
        header.addWidget(edit_btn)
        
        layout.addLayout(header)
        
        # Perks List
        perks_label = QLabel("<h3>Unlocked Perks</h3>")
        layout.addWidget(perks_label)
        
        perks = QTextEdit()
        perks.setReadOnly(True)
        perks.setStyleSheet("background: #1a202c; border: none;")
        
        perk_text = self.get_perks_text()
        perks.setHtml(perk_text)
        layout.addWidget(perks)

    def update_avatar_display(self):
        if self.avatar and os.path.exists(self.avatar):
            pixmap = QPixmap(self.avatar).scaled(100, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        else:
            pixmap = QPixmap(100, 100)
            pixmap.fill(QColor("lightgray"))
        
        # Mask to circle
        rounded = QPixmap(100, 100)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, 100, 100)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        
        # Draw red border
        painter.setClipping(False)
        painter.setPen(QPen(Qt.red, 3))
        painter.drawEllipse(1, 1, 98, 98)
        painter.end()
        
        self.avatar_label.setPixmap(rounded)

    def open_edit(self):
        dialog = ProfileEditDialog(self.avatar)
        if dialog.exec_():
            pass # update is handled via signal in parent_app but we update UI here too
            
    def get_perks_text(self):
        html = "<ul>"
        if self.level >= 1: html += "<li><b>Level 1:</b> Bloom Buddy AI Access</li>"
        if self.level >= 10: html += "<li><b>Level 10:</b> Custom Prompt Color</li>"
        if self.level >= 15: html += "<li><b>Level 15:</b> Command History Search</li>"
        if self.level >= 20: html += "<li><b>Level 20:</b> New Theme Unlock</li>"
        if self.level >= 25: html += "<li><b>Level 25:</b> Visual Breadcrumbs</li>"
        if self.level >= 30: html += "<li><b>Level 30:</b> Split-Pane View</li>"
        if self.level >= 40: html += "<li><b>Level 40:</b> Auto-Complete Magic</li>"
        if self.level >= 50: html += "<li><b>Level 50:</b> Desktop Widgets</li>"
        if self.level >= 60: html += "<li><b>Level 60:</b> Alias Builder</li>"
        if self.level >= 70: html += "<li><b>Level 70:</b> Script Gallery</li>"
        if self.level >= 80: html += "<li><b>Level 80:</b> Custom Badge/Avatar Frame</li>"
        if self.level >= 90: html += "<li><b>Level 90:</b> Developer Mode</li>"
        if self.level >= 100: html += "<li><b>Level 100:</b> Bloom Architect Title</li>"
        html += "</ul>"
        return html


class TerminalTab(QWidget):
    def __init__(self, app_ref, current_dir):
        super().__init__()
        self.app_ref = app_ref
        self.username = app_ref.user_name
        self.current_dir = current_dir
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_area = QTextEdit(self)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(15, 18, 25, 255);
                color: white;
                font-family: 'Courier New', Courier, monospace;
                font-size: 14px;
                border: none;
            }
        """)
        self.layout.addWidget(self.text_area)
        
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.current_dir)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
        self.append_prompt()
        self.text_area.installEventFilter(self)
        self.current_command = ""
        
    def append_prompt(self):
        prompt = f'<br><span style="color:#73d936;">{self.username}</span> <span style="color:white;">:</span> <span style="color:#3b8eea;">{self.current_dir}$</span> '
        self.text_area.insertHtml(prompt)
        self.text_area.insertPlainText("")
        
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        self.text_area.setTextCursor(cursor)
        self.command_start_pos = self.text_area.textCursor().position()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.text_area.insertPlainText(data)
        
    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        self.text_area.insertPlainText(data)
        
    def process_finished(self, exitCode, exitStatus):
        if exitCode == 0:
            self.app_ref.add_xp(True)
        else:
            self.app_ref.add_xp(False)
        self.append_prompt()

    def eventFilter(self, source, event):
        if event.type() == event.KeyPress and source is self.text_area:
            if event.key() == Qt.Key_Return:
                cursor = self.text_area.textCursor()
                cursor.movePosition(cursor.End)
                self.text_area.setTextCursor(cursor)
                
                command = self.text_area.toPlainText()[self.command_start_pos:].strip()
                self.text_area.insertPlainText('\n')
                
                if command:
                    if command == "bloom profile":
                        self.app_ref.show_profile()
                        self.append_prompt()
                    elif command.startswith("cd "):
                        new_dir = command[3:].strip()
                        if os.path.exists(os.path.join(self.current_dir, new_dir)):
                            self.current_dir = os.path.abspath(os.path.join(self.current_dir, new_dir))
                            self.process.setWorkingDirectory(self.current_dir)
                            self.app_ref.add_xp(True)
                        else:
                            self.text_area.insertPlainText(f"cd: {new_dir}: No such file or directory\n")
                            self.app_ref.add_xp(False)
                        self.append_prompt()
                    else:
                        self.process.start(command)
                else:
                    self.append_prompt()
                return True
                
            elif event.key() == Qt.Key_Backspace:
                if self.text_area.textCursor().position() <= self.command_start_pos:
                    return True # Prevent deleting prompt
        return super().eventFilter(source, event)


class SetupWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("First Time Setup")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name...")
        self.name_input.setStyleSheet("padding: 10px; font-size: 16px; border-radius: 5px; background: white; color: black;")
        layout.addWidget(self.name_input)
        
        self.dir_label = QLabel("No directory selected")
        self.dir_label.setStyleSheet("color: lightgray; margin-top: 10px;")
        layout.addWidget(self.dir_label)
        
        dir_btn = QPushButton("Select Base Directory")
        dir_btn.setStyleSheet("padding: 10px; font-size: 16px; background-color: #3b8eea; color: white; border-radius: 5px;")
        dir_btn.clicked.connect(self.select_directory)
        layout.addWidget(dir_btn)
        
        save_btn = QPushButton("Save & Continue")
        save_btn.setStyleSheet("padding: 10px; font-size: 16px; background-color: #73d936; color: black; border-radius: 5px; margin-top: 20px;")
        save_btn.clicked.connect(self.save_setup)
        layout.addWidget(save_btn)
        
        self.selected_dir = ""

    def select_directory(self):
        # Force a generic style so Wayland dark mode doesn't ruin the QFileDialog text
        dialog = QFileDialog(self, "Select Base Directory")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet("QWidget { color: white; background-color: #1a202c; }")
        if dialog.exec_():
            directory = dialog.selectedFiles()[0]
            if directory:
                self.selected_dir = directory
                self.dir_label.setText(f"Selected: {directory}")

    def save_setup(self):
        name = self.name_input.text().strip()
        if name and self.selected_dir:
            save_user_setup(self.parent_app.db_conn, name, self.selected_dir)
            self.parent_app.load_user_data()
            self.parent_app.show_intro()


class BloomTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db_conn = init_db()
        self.load_user_data()
        self.initUI()

    def load_user_data(self):
        data = get_user_data(self.db_conn)
        if data:
            self.user_name, self.base_dir, self.xp, self.level, self.succ, self.fail, self.avatar = data
            self.has_setup = True
        else:
            self.user_name, self.base_dir, self.xp, self.level, self.succ, self.fail, self.avatar = "", "", 0, 1, 0, 0, ""
            self.has_setup = False

    def initUI(self):
        self.setWindowTitle('Bloom Terminal')
        self.setFixedSize(800, 500)
        self.setStyleSheet("background-color: #0f1219;") 

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)

        # 1. Setup Screen
        self.setup_widget = SetupWidget(self)
        self.stacked_widget.addWidget(self.setup_widget)

        # 2. Intro Screen
        self.intro_widget = QWidget()
        self.intro_layout = QVBoxLayout(self.intro_widget)
        self.intro_layout.setContentsMargins(0, 0, 0, 0)
        
        # Resetup Button
        resetup_btn = QPushButton("Re-setup")
        resetup_btn.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); color: white; border-radius: 5px; padding: 5px;")
        resetup_btn.clicked.connect(self.go_to_setup)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(resetup_btn)
        
        self.intro_label = QLabel(self.intro_widget)
        intro_pixmap = QPixmap("/home/aaryan/Documents/bloom/python-bloom/Screenshot from 2026-07-07 13-31-54.png")
        self.intro_label.setPixmap(intro_pixmap.scaled(800, 500, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        self.intro_label.mousePressEvent = self.skip_intro
        
        # Overlay layout
        overlay = QVBoxLayout(self.intro_label)
        overlay.addLayout(btn_layout)
        overlay.addStretch()
        
        self.intro_layout.addWidget(self.intro_label)
        self.stacked_widget.addWidget(self.intro_widget)

        # 3. Main Terminal Screen
        self.terminal_widget = QWidget()
        self.terminal_layout = QVBoxLayout(self.terminal_widget)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tab_widget = QTabWidget(self.terminal_widget)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: #1a202c; color: white; padding: 8px 15px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #2d3748; }
        """)
        
        # Fix nav bar + button
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setStyleSheet("background-color: #3b8eea; color: white; width: 30px; font-weight: bold; font-size: 16px; margin: 2px;")
        self.add_tab_btn.clicked.connect(self.add_new_tab)
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.TopRightCorner)
        
        self.terminal_layout.addWidget(self.tab_widget)
        self.stacked_widget.addWidget(self.terminal_widget)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_terminal)

        if not self.has_setup:
            self.stacked_widget.setCurrentIndex(0)
        else:
            self.show_intro()

    def go_to_setup(self):
        self.timer.stop()
        self.stacked_widget.setCurrentIndex(0)

    def add_new_tab(self):
        new_tab = TerminalTab(self, self.base_dir)
        idx = self.tab_widget.addTab(new_tab, "New Tab")
        self.tab_widget.setCurrentIndex(idx)
        new_tab.text_area.setFocus()

    def show_intro(self):
        self.stacked_widget.setCurrentIndex(1)
        self.timer.start(60000)

    def skip_intro(self, event):
        self.timer.stop()
        self.show_terminal()

    def show_terminal(self):
        if self.tab_widget.count() == 0:
            self.add_new_tab()
        self.stacked_widget.setCurrentIndex(2)
        
    def add_xp(self, success):
        if success:
            self.succ += 1
            self.xp += 10
        else:
            self.fail += 1
            self.xp += 5
            
        # Level up formula (simple)
        self.level = int((self.xp / 100) ** 0.6) + 1
        update_user_stats(self.db_conn, self.xp, self.level, self.succ, self.fail, self.avatar)

    def show_profile(self):
        # Update user data from DB before showing
        self.load_user_data()
        dialog = ProfileDialog((self.user_name, self.base_dir, self.xp, self.level, self.succ, self.fail, self.avatar), self)
        
        # Connect to edit updates
        def on_avatar_update(new_avatar):
            self.avatar = new_avatar
            update_user_stats(self.db_conn, self.xp, self.level, self.succ, self.fail, self.avatar)
            dialog.update_avatar_display()
            
        # Hook into edit dialog created inside ProfileDialog
        original_open_edit = dialog.open_edit
        def new_open_edit():
            edit_dialog = ProfileEditDialog(self.avatar)
            edit_dialog.updated.connect(on_avatar_update)
            edit_dialog.exec_()
        dialog.open_edit = new_open_edit
        
        dialog.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Bloom Terminal")
    ex = BloomTerminalApp()
    ex.show()
    sys.exit(app.exec_())
