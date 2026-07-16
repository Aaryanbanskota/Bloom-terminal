# Contributing to Bloom Terminal

Thank you for considering contributing to Bloom Terminal!

## Quick Setup

```bash
git clone https://github.com/Aaryanbanskota/Bloom-terminal.git
cd Bloom-terminal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Rules for Adding New Widgets

1. Store under `bloom/ui/widgets/`
2. Ensure any non-standard libraries (e.g., `psutil`) fail gracefully with `try/except` fallbacks so the application runs on bare systems
3. Hook settings toggles via `QSettings` inside `SettingsDialog`
4. Use `QThread` + `@pyqtSlot` for any blocking I/O (file pickers, HTTP, disk scans) — **never** block the Qt main thread

## Rules for Terminal Commands

- Bloom-specific commands are intercepted in `terminal.py` inside `_handle_bloom_command()`
- Shell builtins that require native handling (e.g., `clear`, `exit`) must be intercepted in `eventFilter()` **before** being sent to the PTY
- Any new `bloom <cmd>` command must also be documented in `bloom help` output and in `forai.md`

## Code Style

- Use `QTextCharFormat` for all terminal text rendering (never raw HTML in the main output area)
- Keep XP updates in `app.py::add_xp()` only — never call `update_user_stats` directly from widgets
- All database writes must call `conn.commit()` or use the `update_user_stats` helper

## Testing

Run the app from your terminal session (not VS Code debugger) to avoid Qt thread issues:

```bash
bash bloom_runner.sh
```

Or after installation:

```bash
bloom
```
