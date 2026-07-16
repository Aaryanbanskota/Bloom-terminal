# Bloom Terminal — AI Context File (`forai.md`)

> This file is the single source of truth for any AI or developer picking up this project.
> Updated after every structural or functional change.

---

## What This Project Is

A Python desktop GUI terminal app called **Bloom Terminal**, built with PyQt5.
It looks like a real interactive shell (powered by `ptyprocess` PTY) but adds:
- 🎮 RPG-style gamification — XP, levels, unlockable perks
- 🔒 Directory sandbox that jails the shell inside a user-chosen folder
- 👤 Avatar/profile editor with circular crop and preset avatars
- 🚀 Bloom built-in commands for launching extra tools

---

## Project File Structure (as of 2026-07-16)

```
python-bloom/
│
├── bloom/                               # Main Python package
│   ├── __init__.py
│   ├── __main__.py                      # python -m bloom
│   ├── app.py                           # Main window, tab bar, intro screen, BloomTerminalApp
│   │
│   ├── core/                            # Core app infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                    # App constants (XP values, timing, debug flag)
│   │   ├── constants.py                 # UI design tokens (colours, HINTS list)
│   │   ├── logger.py                    # Centralised logging → data/logs/bloom.log
│   │   └── paths.py                     # All filesystem paths (ROOT_DIR, ASSETS, DB, etc.)
│   │
│   ├── terminal/                        # Shell backend
│   │   ├── __init__.py
│   │   ├── terminal.py                  # TerminalTab + WatermarkTerminal (PTY shell)
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── builtin/                 # bloom profile, bloom help, bloom browser, etc.
│   │       │   └── __init__.py
│   │       ├── system/                  # OS-level command hooks
│   │       │   └── __init__.py
│   │       └── custom/                  # User-defined command extensions
│   │           └── __init__.py
│   │
│   ├── ui/                              # All PyQt5 widgets / dialogs / windows
│   │   ├── __init__.py
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── setup_widget.py          # First-time setup screen (name + folder picker)
│   │   │   └── avatar_cropper.py        # Custom QPainter circular image cropper
│   │   ├── dialogs/
│   │   │   ├── __init__.py
│   │   │   └── profile_dialog.py        # Profile/XP/perks dialog + avatar editor
│   │   ├── layouts/
│   │   │   └── __init__.py
│   │   ├── themes/
│   │   │   └── __init__.py
│   │   └── windows/
│   │       └── __init__.py
│   │
│   ├── storage/                         # Database layer
│   │   ├── __init__.py
│   │   ├── database.py                  # init_db, get_user_data, save_user_setup, update_user_stats
│   │   ├── migrations/
│   │   │   └── __init__.py
│   │   └── repositories/
│   │       └── __init__.py
│   │
│   ├── services/                        # Extra standalone tools launched via bloom commands
│   │   ├── __init__.py
│   │   ├── cinestream_v5.py             # bloom -server  → personal media server (Flask)
│   │   ├── share_app.py                 # bloom -share   → file sharing between devices
│   │   ├── usbcleaner.py                # bloom -usb     → USB cleaner
│   │   ├── usb_mover.py                 # bloom -usb     → USB file mover (Porter)
│   │   └── vault.py                     # bloom lockfile → Ghost Vault Pro (file encryption)
│   │
│   ├── ai/                              # AI integration stubs (future)
│   │   ├── __init__.py
│   │   ├── memory/       __init__.py
│   │   ├── prompts/      __init__.py
│   │   ├── providers/    __init__.py
│   │   └── tools/        __init__.py
│   │
│   ├── learning/                        # Gamified learning system (future)
│   │   ├── __init__.py
│   │   ├── achievements/ __init__.py
│   │   ├── lessons/      __init__.py
│   │   ├── progress/     __init__.py
│   │   └── quizzes/      __init__.py
│   │
│   ├── plugins/                         # Plugin system (future)
│   │   ├── __init__.py
│   │   └── builtin/      __init__.py
│   │
│   ├── profile/                         # Profile data helpers (future)
│   │   └── __init__.py
│   │
│   ├── reports/                         # Reporting subsystem (future)
│   │   ├── __init__.py
│   │   ├── ai/           __init__.py
│   │   ├── analytics/    __init__.py
│   │   ├── command/      __init__.py
│   │   ├── crashes/      __init__.py
│   │   └── exports/      __init__.py
│   │
│   ├── security/                        # Security utilities (future)
│   │   └── __init__.py
│   │
│   ├── utils/                           # Shared utility helpers (future)
│   │   └── __init__.py
│   │
│   └── assets/                          # Static resources
│       ├── bloom-terminal-logo.png       # App window + dock icon
│       ├── bloom-art-raw.png             # Watermark drawn behind terminal output
│       ├── bloom-flower.png
│       ├── butterfly.png
│       └── avatars/                      # Preset avatar images + saved_avatar.png
│           ├── saved_avatar.png
│           ├── brakingbad-profile.jpg
│           ├── dog-profile.png
│           ├── flame-guy-profile.jpg
│           ├── ghost-rider-profile.jpg
│           ├── sketch-guy.jpg
│           ├── spiderman-profile.jpg
│           ├── tomandjarry-profile.jpg
│           └── wolf-profile.jpg
│
├── data/                                # Runtime-generated data (git-ignored)
│   ├── database/
│   │   └── data.sql                     # SQLite database (created on first run)
│   ├── logs/
│   │   └── bloom.log                    # App log (created by bloom.core.logger)
│   ├── cache/
│   ├── reports/
│   │   └── command_report.txt
│   ├── exports/
│   └── backups/
│
├── docs/                                # Documentation
│   ├── screenshots/                     # UI screenshots
│   ├── api/
│   ├── architecture/
│   ├── development/
│   ├── diagrams/
│   ├── setup/
│   └── problem.md
│
├── tests/                               # Test suite
│   ├── unit/
│   │   ├── test_pty.py
│   │   └── test_sudo.py
│   ├── integration/
│   ├── ui/
│   ├── performance/
│   └── fixtures/
│
├── examples/
│   ├── plugins/
│   └── tutorials/
│
├── scripts/                             # Dev/ops helper scripts
│
├── bloom_runner.sh                      # Primary launcher (creates venv, installs deps)
├── run.py                               # Entry point: from bloom.app import main
├── pyproject.toml                       # Package metadata and build config
├── requirements.txt                     # Runtime dependencies
├── .gitignore
├── LICENSE
├── README.md
└── forai.md                             # This file
```

---

## How to Run

### Easy way (recommended)
```bash
./bloom_runner.sh
```
Creates venv, installs all deps, detects Wayland vs X11, launches app.

### Manual way
```bash
source venv/bin/activate
python run.py
# or
python -m bloom
```

---

## Architecture Overview

```
run.py
  └─→ bloom.app.main()
        └─→ QApplication + BloomTerminalApp(QWidget)
              ├─→ SetupWidget          (first-time setup screen)
              ├─→ IntroScreen          (60s splash, click to skip)
              └─→ Terminal page
                    ├─→ BloomTabBar    (custom pill-shaped QPainter tab bar)
                    └─→ TerminalTab(s)
                          ├─→ WatermarkTerminal (QTextEdit + watermark overlay)
                          └─→ ptyprocess.PtyProcessUnicode (real PTY shell)
```

### Key Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `bloom/app.py` | Main window, tab management, XP updates, page navigation |
| `bloom/core/paths.py` | Single source of truth for all filesystem paths |
| `bloom/core/config.py` | App-level settings (XP constants, timing values, debug flag) |
| `bloom/core/constants.py` | UI design tokens (hex colours, HINTS list) |
| `bloom/core/logger.py` | Centralized logging → console (WARNING+) + file (DEBUG+) |
| `bloom/storage/database.py` | SQLite init, read user data, write stats |
| `bloom/terminal/terminal.py` | PTY shell, ANSI stripping, sentinel parsing, bloom commands |
| `bloom/ui/widgets/setup_widget.py` | First-run name/folder setup |
| `bloom/ui/widgets/avatar_cropper.py` | Circular pan+zoom avatar editor |
| `bloom/ui/dialogs/profile_dialog.py` | XP/perks/avatar dialog |

---

## App Flow

```
Launch
  ├─→ First time? (no data.sql / base_dir missing)
  │     └─→ SetupWidget  →  enter name + pick sandbox folder  →  save to SQLite
  └─→ Returning user?
        └─→ IntroScreen (60s splash, Re-setup btn top-right)
              └─→ click / timeout  →  Terminal page (tabs + PTY shell)
```

---

## Database Schema (SQLite — data/database/data.sql)

Table: `user_data`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key (autoincrement) |
| name | TEXT | User display name |
| base_dir | TEXT | Sandbox root folder path |
| xp | INTEGER | Total XP earned |
| level | INTEGER | Derived from XP formula |
| success_cmds | INTEGER | Count of successful commands |
| failed_cmds | INTEGER | Count of failed commands |
| avatar | TEXT | Path to current avatar image |

---

## Terminal Sandbox (Jail System)

- User picks a base folder during setup — that becomes `jail_root`.
- All `cd` commands are **intercepted by the app** before reaching bash.
- Any `cd` that resolves above `jail_root` → blocked with a red bash-style error.
- `~` inside the terminal maps to `jail_root`, not `$HOME`.
- Shell sentinel: every command appends `echo __BLOOM_DONE__:$?:$(pwd)` so the app tracks exit code + current directory.
- PTY is set to **no-echo** mode so commands aren't double-printed.

---

## Bloom Built-in Commands

| Command | What it does |
|---------|-------------|
| `bloom profile` | Opens XP / perks / avatar dialog |
| `bloom help` | Prints command reference in terminal |
| `bloom intro` | Replays the intro splash screen |
| `bloom setup` | Goes back to first-time setup page |
| `bloom terminal` | Spawns a new Bloom Terminal window |
| `bloom tab` | Opens a new shell tab |
| `bloom browser <url/text>` | Opens URL or Google-searches text in system browser |
| `bloom -server` | Launches CineStream media server |
| `bloom -share` | Launches file-share app |
| `bloom -usb` | Shows USB Cleaner / Porter selection dialog |
| `bloom lockfile` | Launches Ghost Vault Pro (file encryption) |

---

## XP & Level System

```
Successful command  →  +10 XP
Failed command      →  +5 XP  (still learning)
Level formula       →  level = int((xp / 100) ** 0.6) + 1
```

Perk unlock levels: 1, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100

---

## Shell Backend (PTY)

- Uses `ptyprocess.PtyProcessUnicode.spawn()` for a real PTY session.
- PTY ECHO is disabled via `termios` so commands aren't double-printed.
- PTY fd is made non-blocking via `fcntl`.
- `QSocketNotifier` wakes Qt event loop when PTY output arrives.
- Password prompts (`password for` / `password:`) detected → hidden input mode (shows `*`).
- ANSI escape sequences are stripped via regex before display.
- Shell: detects `$SHELL`, falls back to `/bin/bash`, then `/bin/sh`.

---

## Profile / Avatar Editor

- `bloom profile` → opens `ProfileDialog` showing:
  - Circular avatar with colour-coded level tier border
  - XP progress bar + stats (commands run, success/fail)
  - List of unlocked perks
- Edit Profile → opens `AvatarCropper`:
  - Left: drag to pan, scroll/slider to zoom custom image
  - Right: grid of preset avatars from `bloom/assets/avatars/`
  - Upload Image button for any file
  - Save → renders cropped circle → saves as `bloom/assets/avatars/saved_avatar.png`

---

## Tab Bar

- `BloomTabBar` extends `QTabBar`, draws all tabs manually via `QPainter`.
- Pill-shaped tabs with fill colour (active vs idle), border, text.
- Red dot × button drawn at right of each pill (tracked via `_close_rects`).
- Double-click tab → rename dialog (`QInputDialog`).
- Closing a tab with a running process → confirmation popup.
- `+` circle button in top-right of tab row adds a new tab.

---

## Cross-Platform OS Detection

| Platform | Shell | Font |
|----------|-------|------|
| Linux | `$SHELL` / `/bin/bash` / `/bin/sh` | Courier New |
| macOS | `$SHELL` / `/bin/bash` / `/bin/sh` | Monaco |
| Windows | `%COMSPEC%` (cmd.exe) | Courier New |

---

## Path Resolution (bloom/core/paths.py)

```python
ROOT_DIR      = python-bloom/                      # repo root
BLOOM_DIR     = python-bloom/bloom/                # package root
ASSETS_DIR    = python-bloom/bloom/assets/
LOGO_PATH     = bloom/assets/bloom-terminal-logo.png
WATERMARK_PATH= bloom/assets/bloom-art-raw.png
AVATARS_DIR   = bloom/assets/avatars/
DATA_DIR      = python-bloom/data/
DB_DIR        = python-bloom/data/database/
DB_PATH       = python-bloom/data/database/data.sql
```

---

## Dependencies (requirements.txt)

```
PyQt5
ptyprocess
pycryptodome
customtkinter
flask
```

---

## Change Log

| # | Date | Request | Result |
|---|------|---------|--------|
| 1 | — | Create GUI terminal like screenshots | PyQt5 app with intro splash + terminal view |
| 2 | — | Show in dock, run it | `app.setApplicationName`, ran with `QT_QPA_PLATFORM=wayland` |
| 3 | — | Fix white edges, click to skip intro | Set bg `#0f1219`, `mousePressEvent` on intro label |
| 4 | — | Real terminal, tabs, first-time setup, save name to SQLite | SetupWidget, data.sql, tab widget with + button |
| 5 | — | Refactor into separate files, tab close with confirmation | Split into bloom_db, bloom_setup, bloom_profile, bloom_terminal_tab, main.py |
| 6 | — | Fix Enter typing literal `\n` | Fixed escaped string to real newline |
| 7 | — | Smooth cropper, red dot close, double-click rename, watermark, hints | Custom AvatarCropper QPainter, BloomTabBar painted X, hint timer |
| 8 | — | App icon in dock, watermark, smooth avatar editor | QIcon on app+window, WatermarkTerminal, full avatar editor |
| 9 | — | All commands work, OS detection | Persistent shell (one bash per tab), OS detection, Ctrl+C, history arrows |
| 10 | — | Sandbox jail, bloom profile working, real terminal errors | `_inside_jail()` check, cd intercepted, bloom built-ins intercepted, colours |
| 11 | — | forai.md, force setup if no folder selected | Created forai.md, bloom_setup shows warning+blocks, main.py checks isdir |
| 12 | — | Fix intro dividing line, + button clipping, tab bar border | IntroScreen uses pure paintEvent+resizeEvent, top_bar HBox layout, setTabBar+reparent, documentMode |
| 13 | — | Redesign terminal to match screenshot + bloom_runner.sh | Pill-shaped custom-painted tabs, white circle + button, seamless BG_DARK tab row, bloom_runner.sh auto-venv launcher |
| 14 | — | Remove welcome banner, fix prompt colors, protect output editing, style popups & bloom page commands | Prompt colors updated, output area made read-only, dark stylesheet for right-click, dialogs & rename menus, bloom setup/intro/terminal/tab commands, fixed QMessageBox navigation |
| 15 | — | Fix add tab signal binding, integrate extra tools (server, share, usb, lockfile) | Wrapped `add_new_tab` in lambda to prevent bool pass-through crash; integrated extra-feature apps under bloom commands; added pycryptodome & customtkinter dependency checks in bloom_runner.sh |
| 16 | — | Fix bloom -server crashing silently (No module named 'flask') | Installed Flask into venv; added `_launch_extra_tool()` helper showing crash errors inline |
| 17 | — | Fix bloom commands going to bash, close tab broken, add bloom browser | Fixed bloom interception via token-split check; stored `_tab_widget_ref`; added `bloom browser <url/text>`; fixed help stats attributes |
| 18 | — | Fix modifier keys shifting page view down | Updated keypress event filter to ignore standalone modifier key presses in read-only buffer area |
| 19 | — | Rewrite shell backend to use ptyprocess | Replaced QProcess with `ptyprocess` real PTY; added password hiding; interactive `sudo` works |
| 20 | 2026-07-16 | Restructure project to modular package | Full `bloom/` package layout; updated all imports; `run.py` entry point; `pyproject.toml`/`requirements.txt` |
| 21 | 2026-07-16 | Final pre-push audit + forai.md update | Created `bloom/core/config.py` & `logger.py`; added all missing `__init__.py` (13 subpackages); verified 39 files compile + 10 modules import cleanly; updated forai.md; pushed to GitHub |
