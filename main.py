import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QStackedWidget, QPushButton, QTabWidget,
                             QTabBar, QInputDialog, QLineEdit, QSizePolicy,
                             QMessageBox)
from PyQt5.QtGui import (QPixmap, QIcon, QPainter, QColor, QBrush, QPen,
                          QFont, QPainterPath)
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QPoint, QRectF

from bloom_db import init_db, get_user_data, update_user_stats
from bloom_setup import SetupWidget
from bloom_profile import ProfileDialog
from bloom_terminal_tab import TerminalTab

ASSET_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset")
LOGO_PATH  = os.path.join(ASSET_DIR, "bloom-terminal-logo.png")
INTRO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "Screenshot from 2026-07-07 13-31-54.png")

# ── Design tokens (match screenshot exactly) ──────────────────────────────────
BG_DARK      = "#0a0d14"   # main app background
TAB_IDLE     = "#1c2230"   # unselected tab pill fill
TAB_ACTIVE   = "#2a3347"   # selected tab pill fill  (slightly lighter)
TAB_TEXT     = "#c8d0e0"   # unselected tab text
TAB_TEXT_SEL = "#ffffff"   # selected tab text
TAB_BORDER   = "#2d3748"   # subtle border on pills
DOT_RED      = "#e53e3e"   # close dot


# ─────────────────────────────────────────────────────────────────
#  Custom Tab Bar — pill-shaped tabs, painted red ✕, double-click rename
#  Matches the screenshot: rounded pill with no flat bottom edge.
# ─────────────────────────────────────────────────────────────────
class BloomTabBar(QTabBar):
    """
    Fully custom-painted tab bar.
    Each tab is drawn as a fully-rounded pill (all 4 corners rounded),
    identical to the screenshot design.  The red dot close button is
    painted on the right side of each pill.
    """
    TAB_H      = 24   # pill height
    TAB_MIN_W  = 80   # minimum pill width
    TAB_RADIUS = 12   # corner radius (half of height → full pill)
    CLOSE_R    = 5    # close dot radius
    CLOSE_RPAD = 13   # distance from right edge of pill to dot centre

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setMovable(True)
        self.setTabsClosable(False)
        self.setExpanding(False)
        self._close_rects: dict[int, QRect] = {}
        # Make the Qt-drawn part invisible — we paint everything ourselves
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
        return QSize(w, self.TAB_H + 6)   # +6 breathing room

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._close_rects.clear()

        fm = painter.fontMetrics()

        for i in range(self.count()):
            rect    = self.tabRect(i)
            is_sel  = (i == self.currentIndex())
            text    = self.tabText(i)

            # ── pill geometry (vertically centred in the tab rect) ──
            ph = self.TAB_H
            pw = rect.width()
            px = rect.x()
            py = rect.y() + (rect.height() - ph) // 2

            pill = QRectF(px, py, pw, ph)

            # ── pill fill ──────────────────────────────────────────
            fill_color = QColor(TAB_ACTIVE if is_sel else TAB_IDLE)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(QColor(TAB_BORDER), 0.8 if is_sel else 0.5))
            painter.drawRoundedRect(pill, self.TAB_RADIUS, self.TAB_RADIUS)

            # ── close dot position ─────────────────────────────────
            cx = int(pill.right()) - self.CLOSE_RPAD
            cy = int(pill.center().y())
            r  = self.CLOSE_R
            close_rect = QRect(cx - r, cy - r, r * 2, r * 2)
            self._close_rects[i] = close_rect

            painter.setBrush(QBrush(QColor(DOT_RED)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(close_rect)

            # white ✕ on dot
            painter.setPen(QPen(QColor("white"), 1.3))
            o = 2
            painter.drawLine(QPoint(cx - o, cy - o), QPoint(cx + o, cy + o))
            painter.drawLine(QPoint(cx + o, cy - o), QPoint(cx - o, cy + o))

            # ── label text ────────────────────────────────────────
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
                    # Use stored ref — parent() changes after reparenting into tab_row
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
            # Dark-themed rename dialog with white text
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


# ─────────────────────────────────────────────────────────────────
#  Intro screen — image fills widget, Re-setup button floats on top
# ─────────────────────────────────────────────────────────────────
class IntroScreen(QWidget):
    """
    Intro splash.  The Re-setup button is a bare child widget positioned
    via resizeEvent — no layout touches this widget, so no border/line
    can ever appear.
    """
    def __init__(self, on_click, on_resetup, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self._pixmap   = QPixmap(INTRO_PATH) if os.path.exists(INTRO_PATH) else QPixmap()
        self.setAttribute(Qt.WA_StyledBackground, False)

        self._btn = QPushButton("⚙  Re-setup", self)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet("""
            QPushButton {
                background: rgba(10, 13, 20, 0.65);
                color: #a0aec0;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(59,142,234,0.5);
                color: white;
            }
        """)
        self._btn.adjustSize()
        self._btn.clicked.connect(on_resetup)
        self._btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 12
        bw = self._btn.sizeHint().width()
        bh = self._btn.sizeHint().height()
        self._btn.setGeometry(self.width() - bw - margin, margin, bw, bh)

    def mousePressEvent(self, event):
        if not self._btn.geometry().contains(event.pos()):
            self._on_click(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG_DARK))
        if not self._pixmap.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        painter.end()


# ─────────────────────────────────────────────────────────────────
#  Main application window
# ─────────────────────────────────────────────────────────────────
class BloomTerminalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db_conn = init_db()
        self.load_user_data()
        self._init_ui()

    # ── Data ─────────────────────────────────────────────────────
    def load_user_data(self):
        data = get_user_data(self.db_conn)
        if data and data[0] and data[1] and os.path.isdir(data[1]):
            self.user_name, self.base_dir, self.xp, self.level, \
                self.succ, self.fail, self.avatar = data
            self.has_setup = True
        else:
            self.user_name = self.base_dir = self.avatar = ""
            self.xp = self.succ = self.fail = 0
            self.level = 1
            self.has_setup = False

    # ── UI ───────────────────────────────────────────────────────
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
        self.stack.addWidget(self.setup_widget)       # 0

        self._intro = IntroScreen(self.skip_intro, self.go_to_setup)
        self.stack.addWidget(self._intro)             # 1

        self.stack.addWidget(self._build_terminal())  # 2

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.show_terminal)

        if self.has_setup:
            self.show_intro()
        else:
            self.stack.setCurrentIndex(0)

    # ── Terminal page ────────────────────────────────────────────
    def _build_terminal(self):
        """
        Terminal page layout — matches screenshot precisely:

            ┌─────────────────────────────────────────────────────┐
            │  BG_DARK padding  [●New] [●tab2]    ⊕              │  ← tab_row
            ├─────────────────────────────────────────────────────┤
            │                                                     │
            │   terminal content (QTabWidget pane, no header)    │
            │                                                     │
            └─────────────────────────────────────────────────────┘

        Approach:
        • tab_row is a plain QWidget with the SAME background as the terminal
          (BG_DARK) — no border, no contrasting strip, blends seamlessly.
        • BloomTabBar (pill tabs) is installed on QTabWidget via setTabBar(),
          then reparented into tab_row's HBoxLayout so we fully control layout.
        • + button is a white circle matching the screenshot.
        • QTabWidget hides its own built-in tab bar area via stylesheet.
        """
        page = QWidget()
        page.setStyleSheet(f"background-color: {BG_DARK};")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Tab row — same background as terminal, no separator ───
        tab_row = QWidget()
        tab_row.setStyleSheet(f"background-color: {BG_DARK};")
        tab_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_row.setFixedHeight(36)

        row_lay = QHBoxLayout(tab_row)
        row_lay.setContentsMargins(8, 5, 8, 0)
        row_lay.setSpacing(5)

        # Tab widget + bar setup
        self.tab_widget = QTabWidget()
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self._bar = BloomTabBar(self.tab_widget)
        self.tab_widget.setTabBar(self._bar)
        # Store direct reference BEFORE reparenting so close button can always reach it
        self._bar._tab_widget_ref = self.tab_widget

        # Reparent bar into tab_row (safe after setTabBar)
        self._bar.setParent(tab_row)
        row_lay.addWidget(self._bar, 1)

        # ⊕ Add-tab button — white circle, exactly like screenshot
        self._add_btn = _CirclePlusButton(parent=tab_row)
        self._add_btn.clicked.connect(lambda _: self.add_new_tab())
        row_lay.addWidget(self._add_btn, 0, Qt.AlignVCenter)

        outer.addWidget(tab_row)

        # ── QTabWidget pane — hidden tab header, seamless background ─
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

    # ── Tab management ───────────────────────────────────────────
    def add_new_tab(self, label="New"):
        if not isinstance(label, str):
            label = "New"
        if not self.base_dir or not os.path.isdir(self.base_dir):
            # Prompt user to select base folder
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

    # ── Navigation ───────────────────────────────────────────────
    def go_to_setup(self):
        self._timer.stop()
        self.stack.setCurrentIndex(0)

    def show_intro(self):
        self.stack.setCurrentIndex(1)
        self._timer.start(60_000)

    def skip_intro(self, _event=None):
        self._timer.stop()
        self.show_terminal()

    def show_terminal(self):
        if not self.base_dir or not os.path.isdir(self.base_dir):
            self.go_to_setup()
            return
        if self.tab_widget.count() == 0:
            self.add_new_tab()
        self.stack.setCurrentIndex(2)


    # ── XP ───────────────────────────────────────────────────────
    def add_xp(self, success: bool):
        if success:
            self.succ += 1
            self.xp   += 10
        else:
            self.fail += 1
            self.xp   += 5
        self.level = int((self.xp / 100) ** 0.6) + 1
        update_user_stats(self.db_conn, self.xp, self.level,
                          self.succ, self.fail, self.avatar)

    # ── Profile ──────────────────────────────────────────────────
    def show_profile(self):
        self.load_user_data()
        dlg = ProfileDialog(
            (self.user_name, self.base_dir, self.xp, self.level,
             self.succ, self.fail, self.avatar),
            self
        )
        dlg.exec_()


# ─────────────────────────────────────────────────────────────────
#  ⊕  Circle + button — exactly matches screenshot
# ─────────────────────────────────────────────────────────────────
class _CirclePlusButton(QPushButton):
    """
    White-filled circle with a dark + inside it.
    Painted entirely with QPainter so it looks identical to screenshot.
    """
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

        # Circle fill: white normally, soft blue on hover
        fill = QColor("#dde3ee") if not self._hovered else QColor("#3b8eea")
        p.setBrush(QBrush(fill))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # + symbol
        arm = r - 5
        col = QColor("#0a0d14") if not self._hovered else QColor("white")
        pen = QPen(col, 2.0, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(cx - arm, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy + arm)

        p.end()


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Bloom Terminal")
    app.setApplicationDisplayName("Bloom Terminal")
    if os.path.exists(LOGO_PATH):
        app.setWindowIcon(QIcon(LOGO_PATH))

    ex = BloomTerminalApp()
    ex.resize(960, 600)
    ex.show()
    sys.exit(app.exec_())
