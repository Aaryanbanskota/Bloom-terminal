"""
bloom/ui/windows/dev_page.py
Developer inspection window — shows all stored Bloom data.
Access: bloom-0068devpage-acc"<password>" in terminal.
ponytail: only one window class, no abstractions. ceiling: no live-reload of data.
"""

import os
import sqlite3
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QTextEdit, QSizePolicy, QScrollArea, QFrame, QApplication, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QColor

from bloom.core.paths import DB_PATH
from bloom.storage.database import init_db

_BG      = "#0a0d14"
_CARD    = "#111827"
_BORDER  = "#1e2d4a"
_ACCENT  = "#3b8eea"
_GREEN   = "#4ade80"
_RED     = "#f87171"
_YELLOW  = "#fbbf24"
_TEXT    = "#e2e8f8"
_SUBTEXT = "#8a9bb8"

_STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: 'Courier New', monospace;
}}
QTabWidget::pane {{
    border: 1px solid {_BORDER};
    border-radius: 8px;
    background: {_CARD};
}}
QTabBar::tab {{
    background: {_BG};
    color: {_SUBTEXT};
    border: 1px solid {_BORDER};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 6px 18px;
    margin-right: 3px;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: {_CARD};
    color: {_TEXT};
    border-color: {_ACCENT};
}}
QTableWidget {{
    background: {_CARD};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    gridline-color: {_BORDER};
    selection-background-color: {_ACCENT};
    font-size: 12px;
}}
QHeaderView::section {{
    background: #1a2035;
    color: {_ACCENT};
    border: none;
    border-right: 1px solid {_BORDER};
    padding: 6px;
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: #111827;
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {_ACCENT};
    border-radius: 3px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTextEdit {{
    background: {_CARD};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    color: {_TEXT};
    font-size: 12px;
    padding: 8px;
}}
QPushButton {{
    background: {_ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{ background: #2b7dd9; }}
QPushButton#danger {{
    background: #7f1d1d;
    color: {_RED};
    border: 1px solid {_RED};
}}
QPushButton#danger:hover {{ background: #991b1b; }}
QPushButton#copy {{
    background: #1e2740;
    color: {_SUBTEXT};
    border: 1px solid {_BORDER};
}}
QPushButton#copy:hover {{ background: #253050; color: {_TEXT}; }}
QLabel#section_hdr {{
    color: {_ACCENT};
    font-size: 13px;
    font-weight: bold;
    padding: 4px 0;
}}
QLabel#stat_val {{
    color: {_GREEN};
    font-size: 22px;
    font-weight: bold;
}}
QLabel#stat_lbl {{
    color: {_SUBTEXT};
    font-size: 10px;
}}
"""


def _cell(text: str, align=Qt.AlignLeft) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text) if text is not None else "NULL")
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    item.setTextAlignment(align | Qt.AlignVCenter)
    return item


class DevPage(QWidget):
    """Full developer inspection panel for all Bloom stored data."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🌸 Bloom Dev Page — Database Inspector")
        self.setMinimumSize(960, 640)
        self.setStyleSheet(_STYLESHEET)
        self._conn = None
        self._build_ui()
        QTimer.singleShot(0, self._load_data)

    def _open_conn(self):
        """Open a read-only connection to the DB if available."""
        try:
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                return conn
        except Exception:
            pass
        return None

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header bar ──
        hdr = QHBoxLayout()
        title = QLabel("🌸  BLOOM  /  DEV INSPECTOR")
        title.setFont(QFont("Courier New", 16, QFont.Bold))
        title.setStyleSheet(f"color: {_ACCENT}; letter-spacing: 2px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._ts_lbl = QLabel("")
        self._ts_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 11px;")
        hdr.addWidget(self._ts_lbl)

        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setFixedWidth(110)
        refresh_btn.clicked.connect(self._load_data)
        hdr.addWidget(refresh_btn)

        copy_btn = QPushButton("📋  Copy All")
        copy_btn.setObjectName("copy")
        copy_btn.setFixedWidth(110)
        copy_btn.clicked.connect(self._copy_all)
        hdr.addWidget(copy_btn)

        root.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {_BORDER};")
        root.addWidget(div)

        # ── Stat cards row ──
        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(12)
        self._stat_cards: dict[str, QLabel] = {}
        for key in ("username", "level", "xp", "success", "failed", "db_path"):
            card = self._make_stat_card(key)
            self._stats_row.addWidget(card)
        root.addLayout(self._stats_row)

        # ── Tabs ──
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # Tab 1: user_data table
        self._tbl_user = self._make_table(
            ["id", "name", "base_dir", "xp", "level", "success_cmds", "failed_cmds", "avatar"]
        )
        self._tbl_user.itemSelectionChanged.connect(self._on_table_selection_changed)
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(10, 10, 10, 10)
        l1.addWidget(QLabel("user_data table (select row to edit or view)", objectName="section_hdr"))
        l1.addWidget(self._tbl_user, 1)

        # Form layout row for edits
        edit_lay = QHBoxLayout()
        edit_lay.setSpacing(6)
        
        self._edit_username = QLineEdit()
        self._edit_username.setPlaceholderText("Username")
        self._edit_username.setStyleSheet("QLineEdit { background: #111827; border: 1px solid #1e2d4a; padding: 5px; border-radius: 4px; color: #e2e8f8; }")
        
        self._edit_level = QLineEdit()
        self._edit_level.setPlaceholderText("Level")
        self._edit_level.setFixedWidth(50)
        self._edit_level.setStyleSheet("QLineEdit { background: #111827; border: 1px solid #1e2d4a; padding: 5px; border-radius: 4px; color: #e2e8f8; }")
        
        self._edit_xp = QLineEdit()
        self._edit_xp.setPlaceholderText("XP")
        self._edit_xp.setFixedWidth(70)
        self._edit_xp.setStyleSheet("QLineEdit { background: #111827; border: 1px solid #1e2d4a; padding: 5px; border-radius: 4px; color: #e2e8f8; }")
        
        self._edit_success = QLineEdit()
        self._edit_success.setPlaceholderText("Success")
        self._edit_success.setFixedWidth(80)
        self._edit_success.setStyleSheet("QLineEdit { background: #111827; border: 1px solid #1e2d4a; padding: 5px; border-radius: 4px; color: #e2e8f8; }")
        
        self._edit_failed = QLineEdit()
        self._edit_failed.setPlaceholderText("Failed")
        self._edit_failed.setFixedWidth(80)
        self._edit_failed.setStyleSheet("QLineEdit { background: #111827; border: 1px solid #1e2d4a; padding: 5px; border-radius: 4px; color: #e2e8f8; }")
        
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self._save_changes)
        
        edit_lay.addWidget(QLabel("Edit:"))
        edit_lay.addWidget(self._edit_username)
        edit_lay.addWidget(QLabel("Lvl:"))
        edit_lay.addWidget(self._edit_level)
        edit_lay.addWidget(QLabel("XP:"))
        edit_lay.addWidget(self._edit_xp)
        edit_lay.addWidget(QLabel("Succ:"))
        edit_lay.addWidget(self._edit_success)
        edit_lay.addWidget(QLabel("Fail:"))
        edit_lay.addWidget(self._edit_failed)
        edit_lay.addWidget(save_btn)
        l1.addLayout(edit_lay)

        self.tabs.addTab(w1, "👤  user_data")

        # Tab 2: all tables listing
        self._tbl_tables = self._make_table(["table_name", "row_count"])
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        l2.setContentsMargins(10, 10, 10, 10)
        l2.addWidget(QLabel("All tables in database", objectName="section_hdr"))
        l2.addWidget(self._tbl_tables, 1)
        self.tabs.addTab(w2, "📋  Tables")

        # Tab 3: raw SQL console
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(10, 10, 10, 10)
        l3.setSpacing(8)
        l3.addWidget(QLabel("Raw SQL Query", objectName="section_hdr"))
        self._sql_input = QTextEdit()
        self._sql_input.setFixedHeight(80)
        self._sql_input.setPlaceholderText("SELECT * FROM user_data;")
        l3.addWidget(self._sql_input)
        run_sql_btn = QPushButton("▶  Run Query")
        run_sql_btn.setFixedWidth(140)
        run_sql_btn.clicked.connect(self._run_sql)
        l3.addWidget(run_sql_btn, 0, Qt.AlignLeft)
        self._sql_result = QTextEdit()
        self._sql_result.setReadOnly(True)
        l3.addWidget(self._sql_result, 1)
        self.tabs.addTab(w3, "💻  SQL Console")

        # Tab 4: file system / paths
        self._path_log = QTextEdit()
        self._path_log.setReadOnly(True)
        w4 = QWidget()
        l4 = QVBoxLayout(w4)
        l4.setContentsMargins(10, 10, 10, 10)
        l4.addWidget(QLabel("Bloom Paths & File System", objectName="section_hdr"))
        l4.addWidget(self._path_log, 1)
        self.tabs.addTab(w4, "📁  Paths")

        # Tab 5: QSettings dump
        self._settings_log = QTextEdit()
        self._settings_log.setReadOnly(True)
        w5 = QWidget()
        l5 = QVBoxLayout(w5)
        l5.setContentsMargins(10, 10, 10, 10)
        l5.addWidget(QLabel("QSettings (Bloom / BloomTerminal)", objectName="section_hdr"))
        l5.addWidget(self._settings_log, 1)
        self.tabs.addTab(w5, "⚙️  Settings")

        # ── Status bar ──
        self._status_lbl = QLabel("Connecting to database…")
        self._status_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 11px;")
        root.addWidget(self._status_lbl)

    def _make_stat_card(self, key: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {_CARD};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        val_lbl = QLabel("—")
        val_lbl.setObjectName("stat_val")
        val_lbl.setFont(QFont("Courier New", 18, QFont.Bold))
        val_lbl.setAlignment(Qt.AlignCenter)
        lbl = QLabel(key.upper().replace("_", " "))
        lbl.setObjectName("stat_lbl")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(val_lbl)
        lay.addWidget(lbl)
        self._stat_cards[key] = val_lbl
        card.setMinimumWidth(110)
        return card

    def _make_table(self, columns: list) -> QTableWidget:
        tbl = QTableWidget(0, len(columns))
        tbl.setHorizontalHeaderLabels(columns)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        tbl.setStyleSheet(tbl.styleSheet() + "QTableWidget {alternate-background-color: #0f1520;}")
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        return tbl

    def _load_data(self):
        self._ts_lbl.setText(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
        self._conn = self._open_conn()

        if self._conn is None:
            self._status_lbl.setText("⚠️  Database locked or not found. Unlock app first.")
            self._status_lbl.setStyleSheet(f"color: {_RED}; font-size: 11px;")
            for lbl in self._stat_cards.values():
                lbl.setText("LOCKED")
                lbl.setStyleSheet(f"color: {_RED}; font-size: 18px; font-weight: bold;")
            return

        self._status_lbl.setText(f"✅  Connected: {DB_PATH}")
        self._status_lbl.setStyleSheet(f"color: {_GREEN}; font-size: 11px;")

        self._refresh_user_table()
        self._refresh_tables_tab()
        self._refresh_paths()
        self._refresh_settings()

    def _refresh_user_table(self):
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT id, name, base_dir, xp, level, success_cmds, failed_cmds, avatar FROM user_data")
            rows = cur.fetchall()
        except Exception as e:
            self._status_lbl.setText(f"⚠️  user_data query failed: {e}")
            return

        self._tbl_user.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self._tbl_user.setItem(r, c, _cell(val))

        # Update stat cards from active row matching cached_user_name
        if rows:
            settings = QSettings("Bloom", "BloomTerminal")
            active_name = settings.value("cached_user_name", "")
            active_row = None
            for r in rows:
                if r[1] == active_name:
                    active_row = r
                    break
            if not active_row:
                active_row = rows[0]

            _id, name, base_dir, xp, level, success, failed, avatar = active_row
            self._stat_cards["username"].setText(str(name or "—"))
            self._stat_cards["level"].setText(str(level or "—"))
            self._stat_cards["xp"].setText(str(xp or "0"))
            self._stat_cards["success"].setText(str(success or "0"))
            self._stat_cards["failed"].setText(str(failed or "0"))
            self._stat_cards["db_path"].setText("SQLite")
            for lbl in self._stat_cards.values():
                lbl.setStyleSheet(f"color: {_GREEN}; font-size: 18px; font-weight: bold;")

            # Populate edits form if not focused
            if not self._edit_username.hasFocus():
                self._edit_username.setText(str(name or ""))
            if not self._edit_level.hasFocus():
                self._edit_level.setText(str(level or "1"))
            if not self._edit_xp.hasFocus():
                self._edit_xp.setText(str(xp or "0"))
            if not self._edit_success.hasFocus():
                self._edit_success.setText(str(success or "0"))
            if not self._edit_failed.hasFocus():
                self._edit_failed.setText(str(failed or "0"))
        else:
            for k, lbl in self._stat_cards.items():
                lbl.setText("N/A")

    def _refresh_tables_tab(self):
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
        except Exception as e:
            return

        self._tbl_tables.setRowCount(len(tables))
        for r, tname in enumerate(tables):
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
                cnt = cur.fetchone()[0]
            except Exception:
                cnt = "?"
            self._tbl_tables.setItem(r, 0, _cell(tname))
            self._tbl_tables.setItem(r, 1, _cell(cnt, Qt.AlignCenter))

    def _refresh_paths(self):
        from bloom.core.paths import BLOOM_DIR, DB_PATH as dp
        lines = []
        paths_to_check = [
            ("BLOOM_DIR", BLOOM_DIR),
            ("DB_PATH", dp),
            ("DB_PATH.enc", dp + ".enc"),
            ("DB_PATH.meta", dp + ".meta"),
        ]
        for label, path in paths_to_check:
            exists = os.path.exists(path)
            size = ""
            if exists and os.path.isfile(path):
                size = f"  ({os.path.getsize(path):,} bytes)"
            status = "✅" if exists else "❌"
            lines.append(f"{status}  {label:<20}  {path}{size}")

        # Walk bloom dir
        lines.append("\n── bloom/ directory contents ──")
        try:
            for root_d, dirs, files in os.walk(BLOOM_DIR):
                rel = os.path.relpath(root_d, BLOOM_DIR)
                indent = "  " * rel.count(os.sep)
                lines.append(f"{indent}📁  {os.path.basename(root_d)}/")
                for f in files:
                    fpath = os.path.join(root_d, f)
                    sz = os.path.getsize(fpath)
                    lines.append(f"{indent}  📄  {f}  ({sz:,}b)")
        except Exception as e:
            lines.append(f"Error walking dir: {e}")

        self._path_log.setPlainText("\n".join(lines))

    def _refresh_settings(self):
        from PyQt5.QtCore import QSettings
        s = QSettings("Bloom", "BloomTerminal")
        lines = [f"QSettings file: {s.fileName()}", ""]
        for key in s.allKeys():
            val = s.value(key)
            # Redact password hash for safety (partial)
            if "hash" in key.lower() or "salt" in key.lower():
                val = str(val)[:8] + "…[redacted]"
            lines.append(f"  {key:<30}  =  {val}")
        if not s.allKeys():
            lines.append("  (no settings stored)")
        self._settings_log.setPlainText("\n".join(lines))

    def _run_sql(self):
        sql = self._sql_input.toPlainText().strip()
        if not sql:
            return
        if self._conn is None:
            self._sql_result.setPlainText("⚠️  No database connection.")
            return
        try:
            cur = self._conn.cursor()
            cur.execute(sql)
            if sql.strip().upper().startswith("SELECT"):
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                out = ["\t".join(cols)]
                out += ["\t".join(str(v) for v in row) for row in rows]
                self._sql_result.setPlainText("\n".join(out))
            else:
                self._conn.commit()
                self._sql_result.setPlainText(f"✅  OK — {cur.rowcount} rows affected.")
        except Exception as e:
            self._sql_result.setPlainText(f"❌  Error: {e}")

    def _on_table_selection_changed(self):
        selected_ranges = self._tbl_user.selectedRanges()
        if not selected_ranges:
            return
        row_idx = selected_ranges[0].topRow()
        row_vals = []
        for c in range(self._tbl_user.columnCount()):
            item = self._tbl_user.item(row_idx, c)
            row_vals.append(item.text() if item else "")
        if len(row_vals) >= 7:
            self._edit_username.setText(row_vals[1])
            self._edit_xp.setText(row_vals[3])
            self._edit_level.setText(row_vals[4])
            self._edit_success.setText(row_vals[5])
            self._edit_failed.setText(row_vals[6])

    def _save_changes(self):
        if self._conn is None:
            self._status_lbl.setText("❌ No database connection.")
            return
        username = self._edit_username.text().strip()
        try:
            level = int(self._edit_level.text())
            xp = int(self._edit_xp.text())
            success = int(self._edit_success.text())
            failed = int(self._edit_failed.text())
        except ValueError:
            self._status_lbl.setText("❌ Error: Level, XP, Success, Failed must be integers")
            self._status_lbl.setStyleSheet(f"color: {_RED}; font-size: 11px;")
            return

        settings = QSettings("Bloom", "BloomTerminal")
        active_user = settings.value("cached_user_name", "")

        try:
            cur = self._conn.cursor()
            cur.execute('''
                UPDATE user_data 
                SET name = ?, level = ?, xp = ?, success_cmds = ?, failed_cmds = ?
                WHERE name = ?
            ''', (username, level, xp, success, failed, active_user))
            self._conn.commit()

            # Update cache
            settings.setValue("cached_user_name", username)
            settings.setValue("cached_xp", xp)
            settings.setValue("cached_level", level)
            settings.setValue("cached_succ", success)
            settings.setValue("cached_fail", failed)

            self._status_lbl.setText("✅  Changes saved successfully!")
            self._status_lbl.setStyleSheet(f"color: {_GREEN}; font-size: 11px;")
            self._load_data()
        except Exception as e:
            self._status_lbl.setText(f"❌ Save failed: {e}")
            self._status_lbl.setStyleSheet(f"color: {_RED}; font-size: 11px;")

    def _copy_all(self):
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM user_data")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            text = "\t".join(cols) + "\n"
            text += "\n".join("\t".join(str(v) for v in row) for row in rows)
            QApplication.clipboard().setText(text)
            self._show_copied_tooltip(self.sender() or self)
        except Exception as e:
            pass

    def _show_copied_tooltip(self, widget):
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtCore import QPoint
        pos = widget.mapToGlobal(QPoint(widget.width() // 2, 0))
        QToolTip.showText(pos, "Copied!", widget)
        QTimer.singleShot(1000, lambda: QToolTip.hideText())

    def closeEvent(self, event):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        super().closeEvent(event)
