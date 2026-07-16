# Changelog

All notable changes to Bloom Terminal are documented here.

---

## [v0.1.0-beta] — 2026-07-16

### 🚀 New Features
- **Bootstrap installer** (`install.sh`) — one-command `curl | bash` installer that downloads the latest release from GitHub Releases API, falls back to `git clone`, extracts to `~/.bloom-terminal`, and triggers core setup automatically
- **Core installer** (`scripts/setup.sh`) — handles system dependency installation (apt/dnf/pacman/zypper), Python virtualenv creation, pip packages, global `bloom` command symlink, and `.desktop` launcher file
- **Interactive Intro Dashboard** — full live dashboard with Weather, Song Player (folder/URL playback), System Stats (Battery + CPU arc gauges), Running Programs list
- **Settings Dialog** — toggle switches for lock screen and active widgets
- **`bloom doctor` command** — system diagnostics: OS, Python, Qt, audio backend, database validity, dependencies, folder permissions

### 🐛 Bug Fixes
- **`clear` / `cls` commands** — previously had no effect (ANSI clear codes were being stripped before rendering); now intercepted natively to wipe `QTextEdit` directly
- **`exit` / `logout` commands** — now gracefully closes the current terminal tab via `close_tab()` instead of leaving a dead shell
- **XP & Level persistence** — fixed three separate bugs:
  1. `update_user_stats` silently updated 0 rows before first setup row existed → added upsert fallback
  2. `load_user_data` reset XP to 0 if `base_dir` was missing or deleted → fixed to always restore XP/level from DB row
  3. Intro dashboard XP/level label never refreshed during session → `add_xp()` now calls `refresh_user()` after every command
- **CLI color output** — replaced flat `_strip_ansi()` rendering with full ANSI SGR color parser; removed `NO_COLOR=1` from shell environment; tools like `ls`, `git`, `grep`, `python` now render in correct colors

### 🎨 Improvements
- **Full ANSI SGR color engine** — `_AnsiState` class tracks fg/bg/bold/italic/underline/reverse across PTY `read()` boundaries; supports standard 8/16 colors, bright colors (90-97), 256-color (`38;5;n`), true-color (`38;2;r;g;b`)
- **Secure local encryption** — AES-256-GCM to lock SQLite data files
- **Responsive dashboard layout** — resizes based on window size classes
- **ProfileWidget** — now displays both XP and level together in real-time
- **Universal installer** — supports apt (Debian/Ubuntu), dnf (Fedora/RHEL), pacman (Arch), zypper (openSUSE)

---

## [Pre-beta Sessions] — 2026-07-08 to 2026-07-15

### Added
- PyQt5 GUI terminal with intro splash and terminal view
- Real PTY backend using `ptyprocess`
- Tab system with pill-shaped custom painted tabs
- First-time setup flow (username + sandbox directory)
- SQLite database for XP and user stats
- Directory sandboxing — `cd` is intercepted and jailed
- AES-256-GCM encryption (`bloom lock`)
- Avatar system with circular crop and preset avatars
- `bloom profile` dialog with XP ring and perks
- `bloom browser`, `bloom tab`, `bloom -server`, `bloom -share`, `bloom -usb`, `bloom lockfile` commands
- Music folder picker via threaded `zenity` GTK dialog (fixes Qt freeze on Wayland/X11)
- `bloom_runner.sh` legacy launcher
