"""
Bloom Command Auto-Suggest Plugin.

Provides real-time command suggestions based on terminal history and built-in bloom commands.
Suggestions are shown as inline greyed-out text. Pressing Tab, Right Arrow, or End accepts them.
"""

from PyQt5.QtGui import QColor, QTextCursor, QTextCharFormat

# Built-in bloom commands list for suggestions
BUILT_IN_CMDS = [
    "bloom help",
    "bloom profile",
    "bloom messenger",
    "bloom message",
    "bloom shortcut",
    "bloom lock",
    "bloom doctor",
    "bloom intro",
    "bloom setup",
    "bloom terminal",
    "bloom tab",
    "bloom lockfile",
    "bloom browser",
    "bloom -server",
    "bloom -share",
    "bloom -usb",
]

class AutoSuggestPlugin:
    def __init__(self, terminal_tab):
        self.term = terminal_tab
        self.skip_suggest = False

    def handle_key_press(self, key, mods) -> bool:
        """
        Intercept suggestions acceptance keys.
        Returns True if handled, False otherwise.
        """
        # If backspace, skip suggesting for the next text change
        if key == 16777219:  # Qt.Key_Backspace
            self.skip_suggest = True
            return False

        # Tab, Right, or End accepts suggestion
        if key in (16777217, 16777236, 16777233):  # Qt.Key_Tab, Qt.Key_Right, Qt.Key_End
            c = self.term.text_area.textCursor()
            if c.hasSelection() and c.selectionEnd() == self.term.text_area.document().characterCount() - 1:
                # Accept suggestion
                c.clearSelection()
                c.movePosition(QTextCursor.End)
                # Restore default character format
                from bloom.terminal.terminal import _FMT_DEFAULT
                c.setCharFormat(_FMT_DEFAULT)
                self.term.text_area.setTextCursor(c)
                return True
        return False

    def on_text_changed(self):
        if self.skip_suggest:
            self.skip_suggest = False
            return

        c = self.term.text_area.textCursor()
        pos = c.position()
        if pos < self.term._cmd_start:
            return

        # If has selection at the end, clear selection anchor to get true typed length
        if c.hasSelection() and c.selectionEnd() == self.term.text_area.document().characterCount() - 1:
            pos = min(c.anchor(), c.position())

        # Get typed text
        c.setPosition(self.term._cmd_start)
        c.setPosition(pos, QTextCursor.KeepAnchor)
        typed = c.selectedText().replace('\u2029', '\n')

        if not typed or typed.endswith('\n') or typed.endswith('\r'):
            return

        # Find match
        match = None
        # Try current session history first
        for cmd in reversed(self.term._history):
            if cmd.startswith(typed) and len(cmd) > len(typed):
                match = cmd
                break
        if not match:
            # Try built-in commands
            for cmd in BUILT_IN_CMDS:
                if cmd.startswith(typed) and len(cmd) > len(typed):
                    match = cmd
                    break

        if match:
            suggestion = match[len(typed):]
            self.term.text_area.blockSignals(True)
            try:
                # Select from pos to end of document (any existing suggestion)
                c = self.term.text_area.textCursor()
                c.setPosition(pos)
                c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                c.removeSelectedText()

                # Insert suggestion in grey color
                fmt = QTextCharFormat()
                fmt.setForeground(QColor("#64748b"))  # Slate grey
                c.setCharFormat(fmt)
                c.insertText(suggestion)

                # Keep suggestion selected
                c.setPosition(pos, QTextCursor.MoveAnchor)
                c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                self.term.text_area.setTextCursor(c)
            finally:
                self.term.text_area.blockSignals(False)
