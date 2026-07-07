"""
bloom_terminal_tab.py
─────────────────────
Persistent-shell terminal tab with directory sandboxing.

Key behaviours
──────────────
• ONE bash/sh/cmd process per tab — shell state (cd, export, alias…) persists.
• SANDBOX: the selected folder is the "jail root".  cd cannot escape it.
  Any cd that would take the user above the jail root is blocked with a
  clear error message — just like a permission-denied error in a real terminal.
• Bloom built-in commands (bloom profile, bloom help …) are intercepted
  before being sent to the shell.
• Errors from the shell are shown in red exactly like a real terminal.
• Ctrl+C sends SIGINT (Linux/Mac) or 0x03 (Windows) to the running process.
• ↑ / ↓  navigate command history.
• Home key goes to start of typed input, not start of line.
• OS detection: Linux / macOS / Windows handled transparently.
"""

import os
import re
import sys
import signal
import random
import platform
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QSocketNotifier
from PyQt5.QtGui import (QPixmap, QPainter, QColor, QTextCursor,
                         QFont, QTextCharFormat)

try:
    import ptyprocess
    import termios
    import fcntl
except ImportError:
    ptyprocess = None


# ── OS detection ─────────────────────────────────────────────────────────────
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

# ── Assets ────────────────────────────────────────────────────────────────────
_HERE          = os.path.dirname(os.path.abspath(__file__))
WATERMARK_PATH = os.path.join(_HERE, "asset", "bloom-art-raw.png")

# ── Hints ─────────────────────────────────────────────────────────────────────
HINTS = [
    "💡 Type <b>bloom profile</b> to view your XP, level and unlocked perks.",
    "💡 Every successful command earns you <b>10 XP</b>. Keep going!",
    "💡 Pipes, redirects and <b>&&</b> work — it's a real shell inside.",
    "💡 Press <b>+</b> to open another tab. Double-click a tab to rename it.",
    "💡 Press <b>↑</b> / <b>↓</b> to scroll through your command history.",
    "💡 At <b>Level 20</b> you unlock a new colour theme.",
    "💡 At <b>Level 30</b> you unlock Split-Pane View.",
    "💡 At <b>Level 50</b> you unlock the Desktop Widget dashboard.",
    "💡 At <b>Level 100</b> you become a <b>Bloom Architect</b>!",
    "💡 Even failed commands earn you <b>5 XP</b> — every mistake teaches!",
    "💡 This terminal is sandboxed to your selected folder for safety.",
]

# Strip ANSI colour codes that some tools emit even with TERM=dumb
_ANSI_RE = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'      # CSI sequences (colors, cursor movements, bracketed paste)
    r'|\x1b[()][AB012]'            # character-set shifts
    r'|\r'                         # carriage returns
)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ── Colour helpers ────────────────────────────────────────────────────────────
_FMT_DEFAULT = QTextCharFormat()
_FMT_DEFAULT.setForeground(QColor("#e2e8f0"))

_FMT_ERROR = QTextCharFormat()
_FMT_ERROR.setForeground(QColor("#ff6b6b"))

_FMT_WARN = QTextCharFormat()
_FMT_WARN.setForeground(QColor("#ffd700"))

_FMT_HINT = QTextCharFormat()
_FMT_HINT.setForeground(QColor("#4a5568"))
_FMT_HINT.setFontItalic(True)


# ── Watermark-capable QTextEdit ───────────────────────────────────────────────
class WatermarkTerminal(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._wm = QPixmap(WATERMARK_PATH)
        mono = "Monaco" if IS_MAC else "Courier New"
        self.setFont(QFont(mono, 13))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #0f1219;
                color: #e2e8f0;
                border: none;
                selection-background-color: #2d3748;
            }
            QScrollBar:vertical {
                background: #1a202c;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3b8eea;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QMenu {
                background-color: #1a202c;
                color: #ffffff;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px 0px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 22px 6px 14px;
                color: #ffffff;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #3b8eea;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #4a5568;
            }
            QMenu::separator {
                height: 1px;
                background: #2d3748;
                margin: 3px 0px;
            }
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
        self.jail_root   = os.path.realpath(start_dir)   # ← SANDBOX root
        self.current_dir = self.jail_root
        self.is_running  = False
        self._cmd_start  = 0
        self._history:   list[str] = []
        self._stdout_buf = ""   # accumulate partial lines
        self.awaiting_password = False
        self.password_buffer = ""

        self.setStyleSheet("background-color: #0f1219;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.text_area = WatermarkTerminal(self)
        lay.addWidget(self.text_area)

        # ── Shell process (PTY via ptyprocess) ─────────────────
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

        # ── QSocketNotifier to read async ──────────────────────
        self.notifier = QSocketNotifier(self.pty.fd, QSocketNotifier.Read, self)
        self.notifier.activated.connect(self._on_pty_read)

        if IS_WINDOWS:
            self.pty.write("@echo off\r\nprompt $\r\n")

        self._write_prompt()
        self.text_area.installEventFilter(self)
        self._schedule_hint()

    # ─────────────────────────────────────────────────────────────
    #  Sandbox check
    # ─────────────────────────────────────────────────────────────
    def _inside_jail(self, path: str) -> bool:
        """Return True if `path` is at or below the jail root."""
        real = os.path.realpath(path)
        return real == self.jail_root or real.startswith(self.jail_root + os.sep)

    def _resolve_cd(self, target: str) -> str | None:
        """
        Resolve a cd target relative to current_dir.
        Returns the resolved absolute path, or None if it escapes the jail.
        """
        if os.path.isabs(target):
            candidate = os.path.realpath(target)
        else:
            candidate = os.path.realpath(os.path.join(self.current_dir, target))

        if not self._inside_jail(candidate):
            return None
        if not os.path.isdir(candidate):
            return None      # path does not exist
        return candidate

    # ─────────────────────────────────────────────────────────────
    #  Shell I/O
    # ─────────────────────────────────────────────────────────────
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
                self.notifier.setEnabled(False)
                self._on_shell_exit(0, 0)
                return
        except EOFError:
            self.notifier.setEnabled(False)
            self._on_shell_exit(0, 0)
            return
        except BlockingIOError:
            return

        text = _strip_ansi(raw)
        
        # Buffer until we have complete lines
        self._stdout_buf += text
        lines = self._stdout_buf.splitlines(keepends=True)

        if lines and not lines[-1].endswith("\n"):
            self._stdout_buf = lines.pop()
        else:
            self._stdout_buf = ""

        display = []
        for line in lines:
            # Mask passwords: if the PTY asks for a password, enable hiding
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
        """Parse __BLOOM_DONE__:<exit>:<cwd> and update state."""
        self.is_running = False
        success = True

        if not IS_WINDOWS:
            # Format: __BLOOM_DONE__:<exit_code>:<cwd>
            # cwd may itself contain ':' (rare but possible on Mac)
            m = re.search(r"__BLOOM_DONE__:(\d+):(.*)", line)
            if m:
                success = (m.group(1) == "0")
                cwd = m.group(2).strip()
                if cwd and os.path.isdir(cwd):
                    # Clamp back inside jail if something sneaked out
                    if self._inside_jail(cwd):
                        self.current_dir = cwd
                    else:
                        # Force shell back to jail root
                        self._send(f"cd {self.jail_root}\n")
                        self.current_dir = self.jail_root

        self.app_ref.add_xp(success)
        QTimer.singleShot(60, self._write_prompt)

    def _on_shell_exit(self, code, _status):
        self._insert_colored(
            f"\n[Shell exited — code {code}. Close this tab or open a new one.]\n",
            QColor("#ffd700")
        )

    # ─────────────────────────────────────────────────────────────
    #  Bloom built-in commands
    # ─────────────────────────────────────────────────────────────
    def _handle_bloom_command(self, command: str) -> bool:
        """
        Handle `bloom *` commands.  Return True if consumed.
        command is the raw text from the input area, already stripped.
        """
        # Normalize: strip invisible chars and collapse whitespace
        cmd = " ".join(command.strip().split()).lower()

        if cmd == "bloom profile":
            self.app_ref.show_profile()
            self._write_prompt()
            return True

        if cmd == "bloom intro":
            self.app_ref.show_intro()
            return True

        if cmd == "bloom setup":
            self.app_ref.go_to_setup()
            return True

        if cmd == "bloom terminal":
            # Start new terminal in a new window by launching the script in a process
            import subprocess
            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")])
            self._write_prompt()
            return True

        if cmd == "bloom tab":
            self.app_ref.add_new_tab()
            return True

        if cmd == "bloom -server":
            extra_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra-feature")
            self._launch_extra_tool(os.path.join(extra_dir, "cinestream_v5.py"), "CineStream Server")
            return True

        if cmd == "bloom -share":
            extra_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra-feature")
            self._launch_extra_tool(os.path.join(extra_dir, "share_app.py"), "File Share")
            return True

        if cmd == "bloom -usb":
            # Prompt user to select usbcleaner or usb mover
            from PyQt5.QtWidgets import QMessageBox
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

            extra_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra-feature")
            if dlg.clickedButton() == btn_cleaner:
                self._launch_extra_tool(os.path.join(extra_dir, "usbcleaner.py"), "USB Cleaner")
            elif dlg.clickedButton() == btn_mover:
                self._launch_extra_tool(os.path.join(extra_dir, "usb_mover.py"), "USB Mover")
            else:
                self._write_prompt()
            return True

        if cmd == "bloom lockfile":
            extra_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra-feature")
            self._launch_extra_tool(os.path.join(extra_dir, "vault.py"), "Ghost Vault Pro")
            return True

        # bloom browser <url|text>
        if cmd.startswith("bloom browser"):
            # Use original command (not lowercased cmd) to preserve URL case
            orig_parts = command.strip().split(None, 2)  # ['bloom', 'browser', rest]
            raw = orig_parts[2].strip() if len(orig_parts) >= 3 else ""

            if not raw:
                self._insert_error(
                    "bloom browser: usage — bloom browser <url or search text>\n"
                    "  Examples:\n"
                    "    bloom browser https://youtube.com\n"
                    "    bloom browser youtube\n"
                    "    bloom browser how to use linux\n"
                )
                self._write_prompt()
                return True

            # Build the final URL
            if raw.startswith(("http://", "https://", "ftp://")):
                url = raw
            elif "." in raw and " " not in raw and len(raw) > 3:
                url = "https://" + raw
            else:
                import urllib.parse
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)

            self._insert_colored(
                f"[Bloom] Opening browser → {url}\n", QColor("#3b8eea")
            )

            # Use xdg-open (system-level, works on Wayland + X11)
            # Fall back to webbrowser module if xdg-open not found
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
                pass  # xdg-open not available, try webbrowser below
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
            # ── Pull live user stats ──────────────────────────────
            try:
                xp   = self.app_ref.xp     if hasattr(self.app_ref, "xp")    else 0
                lvl  = self.app_ref.level  if hasattr(self.app_ref, "level") else 1
                name = self.app_ref.user_name if hasattr(self.app_ref, "user_name") else "User"
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
                f"                         Stream videos to any device on your\n"
                f"                         local network via browser\n"
                f"\n"
                f"  bloom -share      →  📤  File Share — send files between\n"
                f"                         devices on the same Wi-Fi, no cables\n"
                f"\n"
                f"  bloom -usb        →  💾  USB Tools — choose:\n"
                f"                           • USB Cleaner  — wipe junk files\n"
                f"                           • USB Mover    — bulk move files\n"
                f"\n"
                f"  bloom lockfile    →  🔐  Ghost Vault Pro — encrypt / hide\n"
                f"                         files with AES-256 password lock\n"
                f"\n"
                f"  {sep2}\n"
                f"  BROWSER\n"
                f"  {sep2}\n"
                f"  bloom browser <url>   →  🌐  Open a URL directly in your\n"
                f"                            default browser\n"
                f"                            e.g. bloom browser https://github.com\n"
                f"\n"
                f"  bloom browser <text>  →  🔍  Search Google for any text\n"
                f"                            e.g. bloom browser how to exit vim\n"
                f"\n"
                f"  {sep2}\n"
                f"  HELP\n"
                f"  {sep2}\n"
                f"  bloom help        →  Show this reference (you are here)\n"
                f"\n"
                f"  {sep}\n"
                f"  Sandbox root  :  {self.jail_root}\n"
                f"  Shell         :  {SHELL_EXE}\n"
                f"  XP formula    :  level = int((xp / 100) ** 0.6) + 1\n"
                f"  XP per cmd    :  +10 (success)  /  +5 (failed — still learning!)\n"
                f"  {sep}\n\n"
            )
            self._insert_colored(help_text, QColor("#3b8eea"))
            self._write_prompt()
            return True

        return False

    # ─────────────────────────────────────────────────────────────
    #  Extra-feature launcher (with error reporting)
    # ─────────────────────────────────────────────────────────────
    def _launch_extra_tool(self, script: str, label: str):
        """
        Launch an extra-feature Python script as a detached subprocess.
        Uses sys.executable (the venv Python) so all installed deps are available.
        If the process crashes within the first second the stderr is shown inline.
        """
        import subprocess, threading

        if not os.path.isfile(script):
            self._insert_error(f"[Bloom] {label}: script not found: {script}\n")
            self._write_prompt()
            return

        self._insert_colored(
            f"[Bloom] Launching {label}…\n", QColor("#3b8eea")
        )

        try:
            proc = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,   # detach from terminal
            )
        except Exception as exc:
            self._insert_error(f"[Bloom] Failed to start {label}: {exc}\n")
            self._write_prompt()
            return

        # Watch for a quick crash in a background thread (non-blocking)
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
                # Post to GUI thread safely
                QTimer.singleShot(0, lambda m=msg: self._insert_error(m))
                QTimer.singleShot(0, self._write_prompt)
            else:
                # Process is still running fine — just close the pipe
                try:
                    proc.stderr.close()
                except Exception:
                    pass

        t = threading.Thread(target=_watch, daemon=True)
        t.start()

        self._write_prompt()

    def _write_prompt(self):
        # Make directory relative to jail root for display
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

        # Draw username in bright green
        fmt_user = QTextCharFormat()
        fmt_user.setForeground(QColor("#73d936"))
        fmt_user.setFontWeight(700)
        cursor.setCharFormat(fmt_user)
        # Avoid double newline at the very beginning of the session
        if self.text_area.toPlainText() == "":
            cursor.insertText(f"{self.username}")
        else:
            cursor.insertText(f"\n{self.username}")

        # ":" — white
        fmt_white = QTextCharFormat()
        fmt_white.setForeground(QColor("#e2e8f0"))
        fmt_white.setFontWeight(400)
        cursor.setCharFormat(fmt_white)
        cursor.insertText(":")

        # path — blue
        fmt_path = QTextCharFormat()
        fmt_path.setForeground(QColor("#3b8eea"))
        fmt_path.setFontWeight(400)
        cursor.setCharFormat(fmt_path)
        cursor.insertText(display)

        # "$" — white
        cursor.setCharFormat(fmt_white)
        cursor.insertText("$ ")

        # reset to default white for user input
        cursor.setCharFormat(_FMT_DEFAULT)
        self.text_area.setTextCursor(cursor)
        self._cmd_start = cursor.position()

    # ─────────────────────────────────────────────────────────────
    #  Colour insertion helpers
    # ─────────────────────────────────────────────────────────────
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

    def _insert_error(self, text: str):
        self._insert_colored(text, QColor("#ff6b6b"))

    def _insert_jail_error(self, target: str):
        msg = (
            f"bash: cd: {target}: Permission denied\n"
            f"  (Bloom sandbox: cannot navigate above '{self.jail_root}')\n"
        )
        self._insert_error(msg)

    # ─────────────────────────────────────────────────────────────
    #  Hints
    # ─────────────────────────────────────────────────────────────
    def _schedule_hint(self):
        QTimer.singleShot(random.randint(90_000, 180_000), self._show_hint)

    def _show_hint(self):
        if not self.is_running:
            hint = random.choice(HINTS)
            self._insert_colored(f"\n{hint}\n", QColor("#4a5568"))
            self._write_prompt()
        self._schedule_hint()

    # ─────────────────────────────────────────────────────────────
    #  Keyboard event filter
    # ─────────────────────────────────────────────────────────────
    def eventFilter(self, source, event):
        if event.type() != event.KeyPress or source is not self.text_area:
            return super().eventFilter(source, event)

        key  = event.key()
        mods = event.modifiers()

        # ── Password Mode Interception ──────────────────────────
        if self.awaiting_password:
            # If pasting (Ctrl+V)
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
                    # delete last char (which is *)
                    c = self.text_area.textCursor()
                    c.deletePreviousChar()
                return True
                
            elif key == Qt.Key_C and (mods & Qt.ControlModifier):
                # Ctrl+C clears password mode and interrupts
                self.password_buffer = ""
                self.awaiting_password = False
                self._insert_colored("^C\n", QColor("#ffd700"))
                self._send('\x03')
                return True
                
            elif event.text() and event.text().isprintable():
                self.password_buffer += event.text()
                self._insert_colored("*", QColor("#e2e8f0"))
                return True
                
            return True # block other keys during password mode

        # ── Enter ────────────────────────────────────────────────
        if key in (Qt.Key_Return, Qt.Key_Enter):
            # Extract user input safely using cursor selection from _cmd_start to End
            cursor = self.text_area.textCursor()
            cursor.setPosition(self._cmd_start)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            command = cursor.selectedText().strip().replace('\u2029', '\n') # replace paragraph separator with newline if any

            # Write newline for visual feedback
            self._insert_colored("\n", QColor("#e2e8f0"))

            if not command:
                self._write_prompt()
                return True

            # ── Bloom built-ins ──────────────────────────────────
            # Use split-based check to handle any stray whitespace/invisible chars
            tokens = command.split()
            if tokens and tokens[0].lower() == "bloom":
                if not self._handle_bloom_command(command):
                    self._insert_error(
                        f"bloom: unknown command '{command}'. "
                        "Try 'bloom help'.\n"
                    )
                    self._write_prompt()
                return True

            # ── cd — intercept so we can enforce the sandbox ─────
            if command == "cd" or command.startswith("cd "):
                # cd with no arg → go to jail root (not $HOME)
                parts  = command.split(None, 1)
                target = parts[1] if len(parts) > 1 else self.jail_root

                # Expand ~ to jail_root (not real $HOME, keeps user inside)
                if target == "~" or target.startswith("~/"):
                    target = self.jail_root + target[1:]

                resolved = self._resolve_cd(target)
                if resolved is None:
                    if not os.path.exists(os.path.join(self.current_dir, target)
                                         if not os.path.isabs(target) else target):
                        self._insert_error(
                            f"bash: cd: {target}: No such file or directory\n"
                        )
                    else:
                        self._insert_jail_error(target)
                    self._write_prompt()
                else:
                    self.current_dir = resolved
                    # Tell the shell to cd too so subsequent commands run there
                    self._send(f"cd {resolved}\n")
                    self.proc.setWorkingDirectory(resolved)
                    self.app_ref.add_xp(True)
                    # Consume the shell's empty output + sentinel
                    self._run_command("true")   # lightweight no-op to flush prompt
                return True

            # ── Everything else → hand to the shell ─────────────
            self._run_command(command)
            return True

        # ── Copy selection (Ctrl + Shift + C) ────────────────────
        if key == Qt.Key_C and (mods & Qt.ControlModifier) and (mods & Qt.ShiftModifier):
            self.text_area.copy()
            return True

        # ── Paste clipboard (Ctrl + Shift + V) ───────────────────
        if key == Qt.Key_V and (mods & Qt.ControlModifier) and (mods & Qt.ShiftModifier):
            self.text_area.paste()
            return True

        # ── Backspace — protect prompt ────────────────────────────
        if key == Qt.Key_Backspace:
            if self.text_area.textCursor().position() <= self._cmd_start:
                return True

        # ── Prevent typing inside the read-only output buffer area ───────
        if self.text_area.textCursor().position() < self._cmd_start:
            # Let copy, select all, navigation, and standalone modifier keys pass through
            if key not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, 
                           Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown,
                           Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                # Move cursor to end to prevent writing
                c = self.text_area.textCursor()
                c.movePosition(QTextCursor.End)
                self.text_area.setTextCursor(c)
                if self.text_area.textCursor().position() < self._cmd_start:
                    return True

        # ── Ctrl+C — interrupt running process ───────────────────
        if key == Qt.Key_C and (mods & Qt.ControlModifier):
            self._send('\x03')
            self._insert_colored("^C\n", QColor("#ffd700"))
            self.is_running = False
            QTimer.singleShot(80, self._write_prompt)
            return True

        # ── ↑  history prev ──────────────────────────────────────
        if key == Qt.Key_Up:
            if self._history:
                self._hist_idx = (
                    len(self._history) - 1
                    if self._hist_idx == -1
                    else max(0, self._hist_idx - 1)
                )
                self._replace_input(self._history[self._hist_idx])
            return True

        # ── ↓  history next ──────────────────────────────────────
        if key == Qt.Key_Down:
            if self._hist_idx >= 0:
                self._hist_idx += 1
                if self._hist_idx >= len(self._history):
                    self._hist_idx = -1
                    self._replace_input("")
                else:
                    self._replace_input(self._history[self._hist_idx])
            return True

        # ── Home — start of user input, not start of line ────────
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

    # ─────────────────────────────────────────────────────────────
    #  Tab close guard
    # ─────────────────────────────────────────────────────────────
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
