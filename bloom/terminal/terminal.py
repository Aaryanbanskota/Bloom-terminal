import os
import re
import sys
import random
import platform
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QSocketNotifier
from PyQt5.QtGui import QPixmap, QPainter, QColor, QTextCursor, QFont, QTextCharFormat

try:
    import ptyprocess
    import termios
    import fcntl
except ImportError:
    ptyprocess = None

from bloom.core.constants import HINTS, BG_TERMINAL
from bloom.core.paths import WATERMARK_PATH, BLOOM_DIR
from bloom.storage.database import update_user_stats

_PLATFORM = platform.system()
IS_WINDOWS = _PLATFORM == "Windows"
IS_MAC     = _PLATFORM == "Darwin"
IS_LINUX   = _PLATFORM == "Linux"

def _detect_shell():
    if IS_WINDOWS:
        return os.environ.get("COMSPEC", "cmd.exe"), []
    for candidate in [os.environ.get("SHELL", ""), "/bin/bash",
                      "/usr/bin/bash", "/bin/sh"]:
        if candidate and os.path.isfile(candidate):
            return candidate, ["--norc", "--noprofile"]
    return "/bin/sh", []

SHELL_EXE, SHELL_ARGS = _detect_shell()

_ANSI_RE = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b[()][AB012]'
    r'|\r'
)

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

_FMT_DEFAULT = QTextCharFormat()
_FMT_DEFAULT.setForeground(QColor("#e2e8f0"))

# ── Watermark-capable QTextEdit ───────────────────────────────────────────────
class WatermarkTerminal(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._wm = QPixmap(WATERMARK_PATH)
        mono = "Monaco" if IS_MAC else "Courier New"
        self.setFont(QFont(mono, 13))
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_TERMINAL};
                color: #e2e8f0;
                border: none;
                selection-background-color: #2d3748;
            }}
            QScrollBar:vertical {{
                background: #1a202c;
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #3b8eea;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QMenu {{
                background-color: #1a202c;
                color: #ffffff;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px 0px;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 6px 22px 6px 14px;
                color: #ffffff;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: #3b8eea;
                color: #ffffff;
            }}
            QMenu::item:disabled {{
                color: #4a5568;
            }}
            QMenu::separator {{
                height: 1px;
                background: #2d3748;
                margin: 3px 0px;
            }}
        """)

    def paintEvent(self, event):
        if not self._wm.isNull():
            vp = self.viewport()
            p = QPainter(vp)
            p.setOpacity(0.055)
            wm = self._wm.scaled(vp.size(), Qt.KeepAspectRatio,
                                  Qt.SmoothTransformation)
            p.drawPixmap((vp.width() - wm.width()) // 2,
                         (vp.height() - wm.height()) // 2, wm)
            p.end()
        super().paintEvent(event)


# ── Terminal Tab ──────────────────────────────────────────────────────────────
class TerminalTab(QWidget):
    def __init__(self, app_ref, start_dir: str):
        super().__init__()
        self.app_ref     = app_ref
        self.username    = app_ref.user_name
        self.jail_root   = os.path.realpath(start_dir)
        self.current_dir = self.jail_root
        self.is_running  = False
        self._cmd_start  = 0
        self._history:   list[str] = []
        self._stdout_buf = ""
        self.awaiting_password = False
        self.password_buffer = ""

        self.setStyleSheet(f"background-color: {BG_TERMINAL};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.text_area = WatermarkTerminal(self)
        lay.addWidget(self.text_area)

        # Shell process setup
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["NO_COLOR"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["PYTHONUNBUFFERED"] = "1"
        env["BLOOM_JAIL"] = self.jail_root
        env["PS1"] = ""
        env["PROMPT_COMMAND"] = ""

        if not ptyprocess:
            self._insert_error("[Bloom] ptyprocess not found. Fallback mode.\n")
            return

        try:
            self.pty = ptyprocess.PtyProcessUnicode.spawn(
                [SHELL_EXE] + SHELL_ARGS,
                cwd=self.current_dir,
                env=env
            )
            # Turn off ECHO so commands aren't printed twice
            attrs = termios.tcgetattr(self.pty.fd)
            attrs[3] = attrs[3] & ~termios.ECHO
            termios.tcsetattr(self.pty.fd, termios.TCSANOW, attrs)

            # Make pty non-blocking
            flags = fcntl.fcntl(self.pty.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.pty.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        except Exception as e:
            self._insert_error(f"[Bloom] Could not start shell: {e}\n")
            return

        self.notifier = None  # created after event loop starts
        QTimer.singleShot(0, self._setup_notifier)

        if IS_WINDOWS:
            self.pty.write("@echo off\r\nprompt $\r\n")

        self._write_prompt()
        self.text_area.installEventFilter(self)
        self._schedule_hint()

    def _setup_notifier(self):
        """Create QSocketNotifier after the Qt event loop is running to avoid thread warning."""
        if not hasattr(self, 'pty'):
            return
        self.notifier = QSocketNotifier(self.pty.fd, QSocketNotifier.Read, self)
        self.notifier.activated.connect(self._on_pty_read)

    def _inside_jail(self, path: str) -> bool:
        real = os.path.realpath(path)
        return real == self.jail_root or real.startswith(self.jail_root + os.sep)

    def _resolve_cd(self, target: str) -> str | None:
        if os.path.isabs(target):
            candidate = os.path.realpath(target)
        else:
            candidate = os.path.realpath(os.path.join(self.current_dir, target))

        if not self._inside_jail(candidate):
            return None
        if not os.path.isdir(candidate):
            return None
        return candidate

    def _send(self, text: str):
        if hasattr(self, 'pty'):
            self.pty.write(text)

    def _run_command(self, command: str):
        self.is_running = True
        self._history.append(command)
        self._hist_idx = -1
        if IS_WINDOWS:
            payload = f"{command}\r\necho __BLOOM_DONE__:0 & cd\r\n"
        else:
            payload = f"{command}\necho __BLOOM_DONE__:$?:$(pwd)\n"
        self._send(payload)

    def _on_pty_read(self, fd):
        try:
            raw = self.pty.read(4096)
            if not raw:
                if self.notifier:
                    self.notifier.setEnabled(False)
                self._on_shell_exit(0, 0)
                return
        except EOFError:
            if self.notifier:
                self.notifier.setEnabled(False)
            self._on_shell_exit(0, 0)
            return
        except BlockingIOError:
            return

        text = _strip_ansi(raw)
        self._stdout_buf += text
        
        # Split using standard splitlines
        lines = self._stdout_buf.splitlines(keepends=True)
        
        # If the last line doesn't end with a newline but contains __BLOOM_DONE__,
        # we process the whole buffer now instead of waiting.
        if lines and not lines[-1].endswith("\n") and not lines[-1].endswith("\r"):
            if "__BLOOM_DONE__" in lines[-1]:
                self._stdout_buf = ""
            else:
                self._stdout_buf = lines.pop()
        else:
            self._stdout_buf = ""

        display = []
        for line in lines:
            lower_line = line.lower()
            if "password for" in lower_line or "password:" in lower_line:
                self.awaiting_password = True

            if "__BLOOM_DONE__" in line:
                self._parse_sentinel(line)
            else:
                display.append(line)

        out = "".join(display)
        if out:
            self._insert_colored(out, QColor("#e2e8f0"))

    def _parse_sentinel(self, line: str):
        self.is_running = False
        success = True

        if not IS_WINDOWS:
            m = re.search(r"__BLOOM_DONE__:(\d+):(.*)", line)
            if m:
                success = (m.group(1) == "0")
                cwd = m.group(2).strip()
                if cwd and os.path.isdir(cwd):
                    if self._inside_jail(cwd):
                        self.current_dir = cwd
                    else:
                        self._send(f"cd {self.jail_root}\n")
                        self.current_dir = self.jail_root

        self.app_ref.add_xp(success)
        
        # Show a hint when a command is executed
        hint = random.choice(HINTS)
        clean_hint = hint.replace("💡 ", "")
        self._insert_html(f"<br/><span style='color:#8a9bb8;'>💡 Hint: {clean_hint}</span><br/>")
        
        QTimer.singleShot(60, self._write_prompt)

    def _on_shell_exit(self, code, _status):
        self._insert_colored(
            f"\n[Shell exited — code {code}. Close this tab or open a new one.]\n",
            QColor("#ffd700")
        )

    def _handle_bloom_command(self, command: str) -> bool:
        cmd = " ".join(command.strip().split()).lower()

        if cmd == "bloom profile":
            self.app_ref.show_profile()
            self._write_prompt()
            return True

        if cmd == "bloom lock":
            self.app_ref.lock_app()
            return True

        if cmd == "bloom doctor":
            self._run_doctor_diagnostic()
            return True

        if cmd == "bloom intro":
            self.app_ref.show_intro()
            return True

        if cmd == "bloom setup":
            self.app_ref.go_to_setup()
            return True

        if cmd == "bloom terminal":
            import subprocess
            subprocess.Popen([sys.executable, os.path.join(BLOOM_DIR, "app.py")])
            self._write_prompt()
            return True

        if cmd == "bloom tab":
            self.app_ref.add_new_tab()
            return True

        services_dir = os.path.join(BLOOM_DIR, "services")

        if cmd == "bloom -server":
            self._launch_extra_tool(os.path.join(services_dir, "cinestream_v5.py"), "CineStream Server")
            return True

        if cmd == "bloom -share":
            self._launch_extra_tool(os.path.join(services_dir, "share_app.py"), "File Share")
            return True

        if cmd == "bloom -usb":
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Select USB Tool")
            dlg.setText("Choose the USB action to run:")
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
            btn_cleaner = dlg.addButton("USB Cleaner", QMessageBox.ActionRole)
            btn_mover = dlg.addButton("USB Mover (Porter)", QMessageBox.ActionRole)
            dlg.addButton("Cancel", QMessageBox.RejectRole)
            dlg.exec_()

            if dlg.clickedButton() == btn_cleaner:
                self._launch_extra_tool(os.path.join(services_dir, "usbcleaner.py"), "USB Cleaner")
            elif dlg.clickedButton() == btn_mover:
                self._launch_extra_tool(os.path.join(services_dir, "usb_mover.py"), "USB Mover")
            else:
                self._write_prompt()
            return True

        if cmd == "bloom lockfile":
            self._launch_extra_tool(os.path.join(services_dir, "vault.py"), "Ghost Vault Pro")
            return True

        if cmd.startswith("bloom browser"):
            orig_parts = command.strip().split(None, 2)
            raw = orig_parts[2].strip() if len(orig_parts) >= 3 else ""

            if not raw:
                self._insert_error(
                    "bloom browser: usage — bloom browser <url or search text>\n"
                    "  Examples:\n"
                    "    bloom browser https://youtube.com\n"
                    "    bloom browser youtube\n"
                )
                self._write_prompt()
                return True

            if raw.startswith(("http://", "https://", "ftp://")):
                url = raw
            elif "." in raw and " " not in raw and len(raw) > 3:
                url = "https://" + raw
            else:
                import urllib.parse
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)

            self._insert_colored(f"[Bloom] Opening browser → {url}\n", QColor("#3b8eea"))

            import subprocess as _sp
            launched = False
            try:
                _sp.Popen(
                    ["xdg-open", url],
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    start_new_session=True,
                    env={**os.environ,
                         "DISPLAY": os.environ.get("DISPLAY", ":0"),
                         "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
                         "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")},
                )
                launched = True
            except FileNotFoundError:
                pass
            except Exception as exc:
                self._insert_error(f"[Bloom] xdg-open error: {exc}\n")

            if not launched:
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception as exc:
                    self._insert_error(f"[Bloom] Could not open browser: {exc}\n")

            self._write_prompt()
            return True

        if cmd == "bloom help":
            try:
                xp   = self.app_ref.xp
                lvl  = self.app_ref.level
                name = self.app_ref.user_name
            except Exception:
                xp, lvl, name = 0, 1, "User"

            sep  = "━" * 45
            sep2 = "─" * 45

            help_text = (
                f"\n\n  🌸  BLOOM TERMINAL  ─  Command Reference\n"
                f"  {sep}\n"
                f"\n"
                f"  👤  {name}   ·   Level {lvl}   ·   {xp} XP\n"
                f"\n"
                f"  {sep2}\n"
                f"  PROFILE & NAVIGATION\n"
                f"  {sep2}\n"
                f"  bloom profile     →  Open profile / XP / perks dialog\n"
                f"  bloom intro       →  Replay the intro splash screen\n"
                f"  bloom setup       →  Re-run first-time setup (name + folder)\n"
                f"\n"
                f"  {sep2}\n"
                f"  WINDOW & TABS\n"
                f"  {sep2}\n"
                f"  bloom terminal    →  Open a brand-new Bloom window\n"
                f"  bloom tab         →  Add a new tab in this window\n"
                f"\n"
                f"  {sep2}\n"
                f"  EXTRA TOOLS  (open in their own window)\n"
                f"  {sep2}\n"
                f"  bloom -server     →  🎬  CineStream — personal media server\n"
                f"  bloom -share      →  📤  File Share — send files between devices\n"
                f"  bloom -usb        →  💾  USB Tools — wipe junk or bulk move\n"
                f"  bloom lockfile    →  🔐  Ghost Vault Pro — encrypt files\n"
                f"\n"
                f"  {sep2}\n"
                f"  BROWSER\n"
                f"  {sep2}\n"
                f"  bloom browser <url>   →  🌐  Open URL in default browser\n"
                f"  bloom browser <text>  →  🔍  Search Google for text\n"
                f"\n"
                f"  {sep2}\n"
                f"  HELP & DIAGNOSTICS\n"
                f"  {sep2}\n"
                f"  bloom help        →  Show this reference\n"
                f"  bloom doctor      →  🩺  Run system diagnostics check\n"
                f"\n"
                f"  {sep}\n"
                f"  Sandbox root  :  {self.jail_root}\n"
                f"  Shell         :  {SHELL_EXE}\n"
                f"  {sep}\n\n"
            )
            self._insert_colored(help_text, QColor("#3b8eea"))
            self._write_prompt()
            return True

        return False

    def _run_doctor_diagnostic(self):
        import sys
        import os
        import platform
        import shutil

        # Header
        sep = "━" * 45
        self._insert_colored(f"\n🌸 BLOOM DOCTOR  ─  System Diagnostics\n{sep}\n", QColor("#7c6af7"))

        # 1. OS & Python
        self._insert_colored("🖥️ OS & Python\n", QColor("#3b8eea"))
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        py_path = sys.executable
        self._insert_colored(f"  · OS Platform  :  {platform.system()} ({platform.release()})\n", QColor("#e2e8f0"))
        self._insert_colored(f"  · Python Version:  {py_ver}\n", QColor("#e2e8f0"))
        self._insert_colored(f"  · Python Path   :  {py_path}\n", QColor("#e2e8f0"))

        # 2. Qt Libraries
        self._insert_colored("\n🎨 Qt Libraries\n", QColor("#3b8eea"))
        try:
            from PyQt5.QtCore import QT_VERSION_STR
            self._insert_colored(f"  · PyQt5        :  Installed ({QT_VERSION_STR})\n", QColor("#4ade80"))
        except ImportError:
            self._insert_colored("  · PyQt5        :  ❌ NOT FOUND\n", QColor("#ff6b6b"))

        # 3. Audio Backend
        self._insert_colored("\n🎵 Audio Backend\n", QColor("#3b8eea"))
        from bloom.ui.widgets.song_player_widget import MEDIA_OK
        if MEDIA_OK:
            self._insert_colored("  · QtMultimedia :  ✅ Installed & Ready\n", QColor("#4ade80"))
        else:
            self._insert_colored(
                "  · QtMultimedia :  ❌ Missing (Qt-backed audio player won't work)\n"
                "    Tip          :  Run 'pip install PyQt5-Qt5' or install python3-pyqt5.qtmultimedia\n",
                QColor("#ff6b6b")
            )

        # 4. Database Status
        self._insert_colored("\n💾 Database Status\n", QColor("#3b8eea"))
        db_valid = False
        if self.app_ref.db_conn:
            try:
                cur = self.app_ref.db_conn.cursor()
                cur.execute("SELECT name, base_dir FROM user_data LIMIT 1;")
                row = cur.fetchone()
                db_valid = True
                self._insert_colored(f"  · DB Connection:  ✅ Active\n", QColor("#4ade80"))
                if row:
                    self._insert_colored(f"  · Active Profile:  {row[0]}\n", QColor("#e2e8f0"))
                else:
                    self._insert_colored("  · Active Profile:  ❌ No setup data in table\n", QColor("#ff6b6b"))
            except Exception as e:
                self._insert_colored(f"  · DB Integrity :  ❌ Corrupted ({e})\n", QColor("#ff6b6b"))
        else:
            self._insert_colored("  · DB Connection:  ❌ No Connection\n", QColor("#ff6b6b"))

        # 5. Sandbox Folder
        self._insert_colored("\n🔒 Sandbox Workspace\n", QColor("#3b8eea"))
        self._insert_colored(f"  · Sandbox path :  {self.jail_root}\n", QColor("#e2e8f0"))
        if os.path.isdir(self.jail_root):
            self._insert_colored("  · Status       :  ✅ Exists & Valid\n", QColor("#4ade80"))
            # Permissions check
            readable = os.access(self.jail_root, os.R_OK)
            writable = os.access(self.jail_root, os.W_OK)
            perm_str = []
            if readable: perm_str.append("Read")
            if writable: perm_str.append("Write")
            self._insert_colored(f"  · Permissions  :  {', '.join(perm_str) if perm_str else 'None'}\n", QColor("#e2e8f0"))
        else:
            self._insert_colored("  · Status       :  ❌ Directory missing!\n", QColor("#ff6b6b"))

        # 6. Missing Dependencies
        self._insert_colored("\n⚙️ Core Dependencies\n", QColor("#3b8eea"))
        deps = [
            ("ptyprocess", "ptyprocess"),
            ("pycryptodome", "Cryptodome"),
            ("customtkinter", "customtkinter"),
            ("Flask", "flask"),
            ("psutil", "psutil"),
            ("requests", "requests")
        ]
        for name, lib in deps:
            try:
                __import__(lib)
                self._insert_colored(f"  · {name:<13}:  ✅ Installed\n", QColor("#4ade80"))
            except ImportError:
                self._insert_colored(f"  · {name:<13}:  ❌ MISSING\n", QColor("#ff6b6b"))

        # 7. Utilities & Environment
        self._insert_colored("\n🛠️ Picker Utilities\n", QColor("#3b8eea"))
        zenity_ok = bool(shutil.which("zenity"))
        kdialog_ok = bool(shutil.which("kdialog"))
        self._insert_colored(f"  · Zenity (GTK) :  {'✅ Available' if zenity_ok else '❌ Missing (falling back)'}\n", QColor("#4ade80" if zenity_ok else "#ffd700"))
        self._insert_colored(f"  · Kdialog (KDE):  {'✅ Available' if kdialog_ok else '❌ Missing (falling back)'}\n", QColor("#4ade80" if kdialog_ok else "#ffd700"))

        # Display Wayland/X11 vars
        self._insert_colored(f"  · Platform QPA :  {os.environ.get('QT_QPA_PLATFORM', 'default')}\n", QColor("#e2e8f0"))

        self._insert_colored(f"{sep}\nDiagnostics completed successfully.\n\n", QColor("#7c6af7"))
        self._write_prompt()

    def _launch_extra_tool(self, script: str, label: str):
        import subprocess, threading

        if not os.path.isfile(script):
            self._insert_error(f"[Bloom] {label}: script not found: {script}\n")
            self._write_prompt()
            return

        self._insert_colored(f"[Bloom] Launching {label}…\n", QColor("#3b8eea"))

        try:
            proc = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except Exception as exc:
            self._insert_error(f"[Bloom] Failed to start {label}: {exc}\n")
            self._write_prompt()
            return

        def _watch():
            import time
            time.sleep(1.5)
            ret = proc.poll()
            if ret is not None and ret != 0:
                err_out = ""
                try:
                    err_out = proc.stderr.read().decode(errors="replace").strip()
                except Exception:
                    pass
                msg = f"[Bloom] {label} exited with code {ret}"
                if err_out:
                    msg += f":\n{err_out}"
                msg += "\n"
                QTimer.singleShot(0, lambda m=msg: self._insert_error(m))
                QTimer.singleShot(0, self._write_prompt)
            else:
                try:
                    proc.stderr.close()
                except Exception:
                    pass

        t = threading.Thread(target=_watch, daemon=True)
        t.start()
        self._write_prompt()

    def _write_prompt(self):
        real_curr = os.path.realpath(self.current_dir)
        real_jail = os.path.realpath(self.jail_root)
        try:
            if real_curr == real_jail:
                display = "~"
            elif real_curr.startswith(real_jail + os.sep):
                rel = os.path.relpath(real_curr, real_jail)
                display = f"~/{rel}"
            else:
                display = real_curr
        except ValueError:
            display = real_curr

        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt_user = QTextCharFormat()
        fmt_user.setForeground(QColor("#73d936"))
        fmt_user.setFontWeight(700)
        cursor.setCharFormat(fmt_user)
        if self.text_area.toPlainText() == "":
            cursor.insertText(f"{self.username}")
        else:
            cursor.insertText(f"\n{self.username}")

        fmt_white = QTextCharFormat()
        fmt_white.setForeground(QColor("#e2e8f0"))
        fmt_white.setFontWeight(400)
        cursor.setCharFormat(fmt_white)
        cursor.insertText(":")

        fmt_path = QTextCharFormat()
        fmt_path.setForeground(QColor("#3b8eea"))
        fmt_path.setFontWeight(400)
        cursor.setCharFormat(fmt_path)
        cursor.insertText(display)

        cursor.setCharFormat(fmt_white)
        cursor.insertText("$ ")

        cursor.setCharFormat(_FMT_DEFAULT)
        self.text_area.setTextCursor(cursor)
        self._cmd_start = cursor.position()

    def _insert_colored(self, text: str, color: QColor):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        cursor.setCharFormat(_FMT_DEFAULT)
        self.text_area.setTextCursor(cursor)
        self.text_area.ensureCursorVisible()

    def _insert_html(self, html: str):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        cursor.setCharFormat(_FMT_DEFAULT)
        self.text_area.setTextCursor(cursor)
        self.text_area.ensureCursorVisible()

    def _insert_error(self, text: str):
        self._insert_colored(text, QColor("#ff6b6b"))

    def _insert_jail_error(self, target: str):
        msg = (
            f"bash: cd: {target}: Permission denied\n"
            f"  (Bloom sandbox: cannot navigate above '{self.jail_root}')\n"
        )
        self._insert_error(msg)

    def _schedule_hint(self):
        QTimer.singleShot(random.randint(90_000, 180_000), self._show_hint)

    def _show_hint(self):
        if not self.is_running:
            hint = random.choice(HINTS)
            self._insert_html(f"<br/><span style='color:#4a5568;'>{hint}</span><br/>")
            self._write_prompt()
        self._schedule_hint()

    def eventFilter(self, source, event):
        if event.type() != event.KeyPress or source is not self.text_area:
            return super().eventFilter(source, event)

        key  = event.key()
        mods = event.modifiers()

        if self.awaiting_password:
            if key == Qt.Key_V and (mods & Qt.ControlModifier):
                import PyQt5.QtWidgets as QtWidgets
                text = QtWidgets.QApplication.clipboard().text()
                if text:
                    self.password_buffer += text
                    self._insert_colored("*" * len(text), QColor("#e2e8f0"))
                return True

            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._send(self.password_buffer + '\n')
                self.password_buffer = ""
                self.awaiting_password = False
                self._insert_colored("\n", QColor("#e2e8f0"))
                return True
            
            elif key == Qt.Key_Backspace:
                if len(self.password_buffer) > 0:
                    self.password_buffer = self.password_buffer[:-1]
                    c = self.text_area.textCursor()
                    c.deletePreviousChar()
                return True
                
            elif key == Qt.Key_C and (mods & Qt.ControlModifier):
                self.password_buffer = ""
                self.awaiting_password = False
                self._insert_colored("^C\n", QColor("#ffd700"))
                self._send('\x03')
                return True
                
            elif event.text() and event.text().isprintable():
                self.password_buffer += event.text()
                self._insert_colored("*", QColor("#e2e8f0"))
                return True
                
            return True

        if key in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.text_area.textCursor()
            cursor.setPosition(self._cmd_start)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            command = cursor.selectedText().strip().replace('\u2029', '\n')

            self._insert_colored("\n", QColor("#e2e8f0"))

            if not command:
                self._write_prompt()
                return True

            tokens = command.split()
            if tokens and tokens[0].lower() == "bloom":
                if not self._handle_bloom_command(command):
                    self._insert_error(f"bloom: unknown command '{command}'. Try 'bloom help'.\n")
                    self._write_prompt()
                return True

            if command == "cd" or command.startswith("cd "):
                parts  = command.split(None, 1)
                target = parts[1] if len(parts) > 1 else self.jail_root

                if target == "~" or target.startswith("~/"):
                    target = self.jail_root + target[1:]

                resolved = self._resolve_cd(target)
                if resolved is None:
                    if not os.path.exists(os.path.join(self.current_dir, target)
                                         if not os.path.isabs(target) else target):
                        self._insert_error(f"bash: cd: {target}: No such file or directory\n")
                    else:
                        self._insert_jail_error(target)
                    self._write_prompt()
                else:
                    self.current_dir = resolved
                    self._send(f"cd {resolved}\n")
                    self.app_ref.add_xp(True)
                    self._run_command("true")
                return True

            self._run_command(command)
            return True

        if key == Qt.Key_C and (mods & Qt.ControlModifier) and (mods & Qt.ShiftModifier):
            self.text_area.copy()
            return True

        if key == Qt.Key_V and (mods & Qt.ControlModifier) and (mods & Qt.ShiftModifier):
            self.text_area.paste()
            return True

        if key == Qt.Key_Backspace:
            if self.text_area.textCursor().position() <= self._cmd_start:
                return True

        if self.text_area.textCursor().position() < self._cmd_start:
            if key not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, 
                           Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown,
                           Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                c = self.text_area.textCursor()
                c.movePosition(QTextCursor.End)
                self.text_area.setTextCursor(c)
                if self.text_area.textCursor().position() < self._cmd_start:
                    return True

        if key == Qt.Key_C and (mods & Qt.ControlModifier):
            self._send('\x03')
            self._insert_colored("^C\n", QColor("#ffd700"))
            self.is_running = False
            QTimer.singleShot(80, self._write_prompt)
            return True

        if key == Qt.Key_Up:
            if self._history:
                if self._hist_idx == -1:
                    # Start at the latest command
                    self._hist_idx = len(self._history) - 1
                else:
                    # Move to older command but stop at the first command (index 0)
                    self._hist_idx = max(0, self._hist_idx - 1)
                self._replace_input(self._history[self._hist_idx])
            return True

        if key == Qt.Key_Down:
            if self._hist_idx >= 0:
                self._hist_idx += 1
                if self._hist_idx >= len(self._history):
                    self._hist_idx = -1
                    self._replace_input("")
                else:
                    self._replace_input(self._history[self._hist_idx])
            return True

        if key == Qt.Key_Home:
            c = self.text_area.textCursor()
            c.setPosition(self._cmd_start)
            self.text_area.setTextCursor(c)
            return True

        return super().eventFilter(source, event)

    def _replace_input(self, text: str):
        c = self.text_area.textCursor()
        c.setPosition(self._cmd_start)
        c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        c.setCharFormat(_FMT_DEFAULT)
        c.insertText(text)
        self.text_area.setTextCursor(c)

    def request_close(self) -> bool:
        if self.is_running:
            reply = QMessageBox.question(
                self, "Process Running",
                "A program is running in this tab. Close it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return False
        if hasattr(self, 'pty'):
            self.pty.terminate(force=True)
        return True
