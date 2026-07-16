import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QStackedWidget, QPushButton, QTabWidget,
                             QTabBar, QInputDialog, QLineEdit, QSizePolicy,
                             QMessageBox)
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QColor, QBrush, QPen, QFont
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QPoint, QRectF, QSettings

from bloom.core.constants import BG_DARK, TAB_ACTIVE, TAB_IDLE, TAB_BORDER, DOT_RED, TAB_TEXT, TAB_TEXT_SEL
from bloom.core.paths import LOGO_PATH
from bloom.storage.database import init_db, get_user_data, update_user_stats
from bloom.ui.widgets.setup_widget import SetupWidget
from bloom.ui.widgets.intro_dashboard import IntroDashboard
from bloom.ui.dialogs.profile_dialog import ProfileDialog
from bloom.terminal.terminal import TerminalTab

# Optional: settings dialog and security (graceful if not yet created)
try:
    from bloom.ui.dialogs.settings_dialog import SettingsDialog
    _HAS_SETTINGS = True
except ImportError:
    _HAS_SETTINGS = False

try:
    from bloom.security.encryption import SecurityManager, PasswordLockScreen
    _HAS_SECURITY = True
except ImportError:
    _HAS_SECURITY = False

class BloomTabBar(QTabBar):
    TAB_H      = 24
    TAB_MIN_W  = 80
    TAB_RADIUS = 12
    CLOSE_R    = 5
    CLOSE_RPAD = 13

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setMovable(True)
        self.setTabsClosable(False)
        self.setExpanding(False)
        self._close_rects: dict[int, QRect] = {}
        self.setStyleSheet("""
            QTabBar {
                background: transparent;
                border: none;
            }
            QTabBar::tab {
                background: transparent;
                color: transparent;
                padding: 0px;
                margin-right: 6px;
                min-width: 80px;
                height: 24px;
            }
            QTabBar::tab:selected { background: transparent; }
            QTabBar::tab:hover    { background: transparent; }
            QTabBar::scroller     { width: 0px; }
        """)
        self.setFont(QFont("Inter", 10) if _font_available("Inter")
                     else QFont("Segoe UI" if sys.platform == "win32"
                                else "Sans Serif", 10))

    def tabSizeHint(self, index: int) -> QSize:
        text = self.tabText(index)
        fm   = self.fontMetrics()
        w    = max(self.TAB_MIN_W,
                   fm.horizontalAdvance(text) + self.CLOSE_RPAD * 2 + 18 + 12)
        return QSize(w, self.TAB_H + 6)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._close_rects.clear()

        for i in range(self.count()):
            rect    = self.tabRect(i)
            is_sel  = (i == self.currentIndex())
            text    = self.tabText(i)

            ph = self.TAB_H
            pw = rect.width()
            px = rect.x()
            py = rect.y() + (rect.height() - ph) // 2

            pill = QRectF(px, py, pw, ph)

            fill_color = QColor(TAB_ACTIVE if is_sel else TAB_IDLE)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(QColor(TAB_BORDER), 0.8 if is_sel else 0.5))
            painter.drawRoundedRect(pill, self.TAB_RADIUS, self.TAB_RADIUS)

            cx = int(pill.right()) - self.CLOSE_RPAD
            cy = int(pill.center().y())
            r  = self.CLOSE_R
            close_rect = QRect(cx - r, cy - r, r * 2, r * 2)
            self._close_rects[i] = close_rect

            painter.setBrush(QBrush(QColor(DOT_RED)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(close_rect)

            painter.setPen(QPen(QColor("white"), 1.3))
            o = 2
            painter.drawLine(QPoint(cx - o, cy - o), QPoint(cx + o, cy + o))
            painter.drawLine(QPoint(cx + o, cy - o), QPoint(cx - o, cy + o))

            text_color = QColor(TAB_TEXT_SEL if is_sel else TAB_TEXT)
            painter.setPen(text_color)
            font = painter.font()
            font.setBold(is_sel)
            painter.setFont(font)

            text_rect = QRect(
                int(pill.x()) + 10,
                int(pill.y()),
                int(pill.width()) - self.CLOSE_RPAD * 2,
                int(pill.height())
            )
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for i, r in self._close_rects.items():
                if r.contains(event.pos()):
                    tw = getattr(self, "_tab_widget_ref", None) or self.parent()
                    if tw and isinstance(tw, QTabWidget):
                        tw.tabCloseRequested.emit(i)
                    return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx >= 0:
            if idx in self._close_rects and self._close_rects[idx].contains(event.pos()):
                return
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Rename Tab")
            dlg.setLabelText("New name:")
            dlg.setTextValue(self.tabText(idx))
            dlg.setStyleSheet("""
                QDialog, QWidget {
                    background-color: #1a202c;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 13px;
                }
                QLineEdit {
                    background-color: #2d3748;
                    color: #ffffff;
                    border: 1px solid #4a5568;
                    border-radius: 5px;
                    padding: 5px 8px;
                    font-size: 13px;
                    selection-background-color: #3b8eea;
                }
                QPushButton {
                    background-color: #3b8eea;
                    color: #ffffff;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 16px;
                    font-size: 13px;
                    min-width: 60px;
                }
                QPushButton:hover  { background-color: #2b7dd9; }
                QPushButton:pressed { background-color: #1a6cc8; }
            """)
            if dlg.exec_() == QInputDialog.Accepted:
                name = dlg.textValue()
                if name.strip():
                    self.setTabText(idx, name.strip())
        super().mouseDoubleClickEvent(event)


def _font_available(name: str) -> bool:
    from PyQt5.QtGui import QFontDatabase
    return name in QFontDatabase().families()


# IntroScreen replaced by IntroDashboard (see bloom/ui/widgets/intro_dashboard.py)


class BloomTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        # If database is locked, we will initialize the connection after unlocking
        from bloom.security.encryption import SecurityManager
        self.sec = SecurityManager()
        if self.sec.is_locked():
            self.db_conn = None
        else:
            self.db_conn = init_db()
        self.load_user_data()
        self._init_ui()

    def cache_user_data(self):
        settings = QSettings("Bloom", "BloomTerminal")
        settings.setValue("cached_user_name", self.user_name)
        settings.setValue("cached_base_dir", self.base_dir)
        settings.setValue("cached_xp", self.xp)
        settings.setValue("cached_level", self.level)
        settings.setValue("cached_succ", self.succ)
        settings.setValue("cached_fail", self.fail)
        settings.setValue("cached_avatar", self.avatar)

    def load_cached_user_data(self):
        settings = QSettings("Bloom", "BloomTerminal")
        self.user_name = settings.value("cached_user_name", "User")
        self.base_dir = settings.value("cached_base_dir", "")
        self.xp = settings.value("cached_xp", 0, type=int)
        self.level = settings.value("cached_level", 1, type=int)
        self.succ = settings.value("cached_succ", 0, type=int)
        self.fail = settings.value("cached_fail", 0, type=int)
        self.avatar = settings.value("cached_avatar", "")

    def load_user_data(self):
        if self.sec.is_locked() and self.db_conn is None:
            self.load_cached_user_data()
            self.has_setup = True
            return

        try:
            data = get_user_data(self.db_conn)
            if data:
                self.user_name, self.base_dir, self.xp, self.level, \
                    self.succ, self.fail, self.avatar = data
                # Validate the sandbox dir; fall back to home if gone
                if not self.base_dir or not os.path.isdir(self.base_dir):
                    self.has_setup = False
                else:
                    self.has_setup = True
                # Always persist the latest values to QSettings cache
                self.cache_user_data()
            else:
                self.user_name = self.base_dir = self.avatar = ""
                self.xp = self.succ = self.fail = 0
                self.level = 1
                self.has_setup = False
        except Exception:
            self.load_cached_user_data()
            self.has_setup = True

    def on_database_unlocked(self):
        self.db_conn = init_db()
        self.load_user_data()
        self._intro.refresh_user(
            self.user_name,
            self.xp,
            self.level,
            self.avatar
        )
        # Update jail root for the terminal tabs
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, "jail_root"):
                tab.jail_root = os.path.realpath(self.base_dir)
                tab.current_dir = tab.jail_root
                tab.username = self.user_name

    def _init_ui(self):
        self.setWindowTitle("Bloom Terminal")
        self.setMinimumSize(820, 540)
        self.setStyleSheet(f"background-color: {BG_DARK};")

        if os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack)

        self.setup_widget = SetupWidget(self)
        self.stack.addWidget(self.setup_widget)

        self._intro = IntroDashboard(
            user_name   = self.user_name,
            xp          = self.xp,
            level       = self.level,
            avatar_path = self.avatar,
            on_click    = self.skip_intro,
            on_resetup  = self.go_to_setup,
            on_settings = self._open_settings,
            parent_app  = self,
        )
        self.stack.addWidget(self._intro)

        self.stack.addWidget(self._build_terminal())

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.skip_intro)

        if self.has_setup:
            self.show_intro()
        else:
            self.stack.setCurrentIndex(0)

    def _build_terminal(self):
        page = QWidget()
        page.setStyleSheet(f"background-color: {BG_DARK};")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        tab_row = QWidget()
        tab_row.setStyleSheet(f"background-color: {BG_DARK};")
        tab_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_row.setFixedHeight(36)

        row_lay = QHBoxLayout(tab_row)
        row_lay.setContentsMargins(8, 5, 8, 0)
        row_lay.setSpacing(5)

        self.tab_widget = QTabWidget()
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self._bar = BloomTabBar(self.tab_widget)
        self.tab_widget.setTabBar(self._bar)
        self._bar._tab_widget_ref = self.tab_widget

        self._bar.setParent(tab_row)
        row_lay.addWidget(self._bar, 1)

        self._add_btn = _CirclePlusButton(parent=tab_row)
        self._add_btn.clicked.connect(lambda _: self.add_new_tab())
        row_lay.addWidget(self._add_btn, 0, Qt.AlignVCenter)

        outer.addWidget(tab_row)

        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {BG_DARK};
                margin-top: 0px;
            }}
            QTabWidget > QTabBar {{
                max-height: 0px;
                min-height: 0px;
                border: none;
            }}
        """)
        self.tab_widget.setDocumentMode(True)
        outer.addWidget(self.tab_widget, 1)

        return page

    def add_new_tab(self, label="New"):
        if not isinstance(label, str):
            label = "New"
        if not self.base_dir or not os.path.isdir(self.base_dir):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("No Base Folder")
            dlg.setText("You have not selected a valid sandbox base folder yet.")
            dlg.setInformativeText("Click here to select folder on the Setup Page.")
            dlg.setIcon(QMessageBox.Warning)
            btn = dlg.addButton("Go to Setup", QMessageBox.ActionRole)
            dlg.addButton("Cancel", QMessageBox.RejectRole)
            dlg.setStyleSheet("""
                QMessageBox, QDialog, QWidget {
                    background-color: #1a202c;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #3b8eea;
                    color: #ffffff;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 16px;
                }
            """)
            dlg.exec_()
            if dlg.clickedButton() == btn:
                self.go_to_setup()
            return

        tab = TerminalTab(self, self.base_dir)
        idx = self.tab_widget.addTab(tab, label)
        self.tab_widget.setCurrentIndex(idx)
        tab.text_area.setFocus()

    def close_tab(self, index):
        tab = self.tab_widget.widget(index)
        if tab and tab.request_close():
            self.tab_widget.removeTab(index)
            tab.deleteLater()
            if self.tab_widget.count() == 0:
                self.add_new_tab()

    def lock_app(self):
        # Secure the DB connection and lock state
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None
        self.sec.settings.setValue("lock_enabled", True)
        self._intro.is_locked = True
        self._intro.pass_edit.setVisible(True)
        self._intro.pass_edit.clear()
        self._intro.pass_edit.setFocus()
        self._intro.pulsing_lbl.setVisible(False)
        self.show_intro()

    def go_to_setup(self):
        self._timer.stop()
        self.stack.setCurrentIndex(0)

    def show_intro(self):
        self._intro.refresh_user(
            self.user_name,
            self.xp,
            self.level,
            self.avatar,
        )
        self.stack.setCurrentIndex(1)
        self._timer.start(60_000)

    def skip_intro(self, _event=None):
        if self._intro.is_locked:
            return  # block entering if locked
        self._timer.stop()
        self.show_terminal()

    def show_terminal(self):
        if self._intro.is_locked:
            return
        if not self.base_dir or not os.path.isdir(self.base_dir):
            self.go_to_setup()
            return
        if self.tab_widget.count() == 0:
            self.add_new_tab()
        self.stack.setCurrentIndex(2)

    def add_xp(self, success: bool):
        if success:
            self.succ += 1
            self.xp   += 10
        else:
            self.fail += 1
            self.xp   += 5
        self.level = int((self.xp / 100) ** 0.6) + 1
        if self.db_conn is not None:
            update_user_stats(self.db_conn, self.xp, self.level,
                              self.succ, self.fail, self.avatar)
        # Always keep the QSettings cache up to date
        self.cache_user_data()
        # Refresh live dashboard profile widget so XP/level update in real-time
        if hasattr(self, '_intro') and self._intro is not None:
            self._intro.refresh_user(
                self.user_name,
                self.xp,
                self.level,
                self.avatar,
            )

    def _open_settings(self):
        """Open the settings dialog (gear button callback)."""
        if _HAS_SETTINGS:
            dlg = SettingsDialog(self)
            dlg.exec_()
        else:
            QMessageBox.information(
                self, "Settings",
                "Settings dialog is loading.\nRun the app once to generate all files."
            )

    def show_profile(self):
        self.load_user_data()
        dlg = ProfileDialog(
            (self.user_name, self.base_dir, self.xp, self.level,
             self.succ, self.fail, self.avatar),
            self
        )
        dlg.exec_()


class _CirclePlusButton(QPushButton):
    _SIZE = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self._hovered = False

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        sz   = self._SIZE
        r    = sz // 2 - 1
        cx   = sz // 2
        cy   = sz // 2

        fill = QColor("#dde3ee") if not self._hovered else QColor("#3b8eea")
        p.setBrush(QBrush(fill))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        arm = r - 5
        col = QColor("#0a0d14") if not self._hovered else QColor("white")
        pen = QPen(col, 2.0, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(cx - arm, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy + arm)
        p.end()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Bloom Terminal")
    app.setApplicationDisplayName("Bloom Terminal")
    app.setOrganizationName("Bloom")
    if os.path.exists(LOGO_PATH):
        app.setWindowIcon(QIcon(LOGO_PATH))

    # The password lock screen is integrated directly inside the IntroDashboard now,
    # so we load the main application immediately!
    ex = BloomTerminalApp()
    ex.resize(1100, 680)
    ex.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
