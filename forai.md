# Bloom Terminal — AI Context File (`forai.md`)

> This file is the **single source of truth** for any AI or developer picking up this project.
> Updated after every structural or functional change.
> Last updated: **2026-07-16** (Session: music folder fix + threading overhaul + install.sh)

---

## What This Project Is

A Python desktop GUI terminal app called **Bloom Terminal**, built with PyQt5.
It looks like a real interactive shell (powered by `ptyprocess` PTY) but adds:
- 🎮 RPG-style gamification — XP, levels, unlockable perks
- 🔒 Directory sandbox that jails the shell inside a user-chosen folder
- 👤 Avatar/profile editor with circular crop and preset avatars
- 🎵 Music player widget with non-blocking folder picker (QThread)
- 🌤 Live weather widget (wttr.in, no API key)
- 📊 System analytics widget (battery + CPU arc gauges via psutil)
- 🚀 Bloom built-in commands for launching extra tools
- 🔐 Encryption support (`bloom lock`, Ghost Vault Pro)

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
│   │   │   ├── avatar_cropper.py        # Custom QPainter circular image cropper
│   │   │   ├── intro_dashboard.py       # Live intro dashboard (weather/profile/music/stats)
│   │   │   ├── song_player_widget.py    # Music player — non-blocking QThread folder picker ⭐
│   │   │   ├── system_stats_widget.py   # Battery + CPU arc gauges (psutil)
│   │   │   └── weather_widget.py        # Live weather via wttr.in (no API key)
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
│   ├── security/                        # Security utilities
│   │   └── __init__.py
│   │
│   ├── ai/                              # AI integration stubs (future)
│   │   └── __init__.py
│   │
│   ├── learning/                        # Gamified learning system (future)
│   │   └── __init__.py
│   │
│   ├── plugins/                         # Plugin system (future)
│   │   └── __init__.py
│   │
│   ├── profile/                         # Profile data helpers (future)
│   │   └── __init__.py
│   │
│   ├── reports/                         # Reporting subsystem (future)
│   │   └── __init__.py
│   │
│   ├── utils/                           # Shared utility helpers (future)
│   │   └── __init__.py
│   │
│   └── assets/                          # Static resources
│       ├── bloom-terminal-logo.png
│       ├── bloom-art-raw.png
│       ├── bloom-flower.png
│       ├── butterfly.png
│       └── avatars/
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
│   │   ├── data.sql                     # SQLite database (created on first run)
│   │   ├── data.sql.enc                 # Encrypted DB backup (AES via pycryptodome)
│   │   └── data.sql.meta               # Encryption metadata file
│   ├── logs/
│   │   └── bloom.log                    # App log (created by bloom.core.logger)
│   ├── cache/
│   ├── reports/
│   │   └── command_report.txt
│   ├── exports/
│   └── backups/
│
├── docs/                                # Documentation
│   ├── screenshots/
│   │   └── open-music-error.png         # Bug evidence screenshot (music folder crash)
│   ├── api/
│   ├── architecture/
│   ├── development/
│   ├── diagrams/
│   ├── setup/
│   └── problem.md                       # Static audit report
│
├── tests/
│   ├── unit/
│   │   ├── test_pty.py
│   │   └── test_sudo.py
│   ├── integration/
│   ├── ui/
│   ├── performance/
│   └── fixtures/
│
├── examples/
├── scripts/
├── install.sh                           # ⭐ One-command installer (new)
├── bloom.sh                             # ⭐ Generated launcher (sets QT_QPA_PLATFORM=xcb)
├── bloom_runner.sh                      # Legacy launcher (creates venv, installs deps)
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

### ⭐ Quickest way (fresh clone, any terminal)
```bash
git clone https://github.com/Aaryanbanskota/Bloom-terminal.git
cd Bloom-terminal
bash install.sh
./bloom.sh
```
`install.sh` handles:
- Python 3.8+ check
- Qt system libs + zenity (via `apt-get`)
- Python venv creation
- All pip packages
- Generates `bloom.sh` launcher (sets `QT_QPA_PLATFORM=xcb`)

### Manual way
```bash
source venv/bin/activate
export QT_QPA_PLATFORM=xcb    # suppresses Wayland warning
python -m bloom
```

### VS Code users
Add to `.vscode/settings.json`:
```json
{
  "terminal.integrated.env.linux": {
    "QT_QPA_PLATFORM": "xcb"
  }
}
```

---

## Architecture Overview

```
run.py
  └─→ bloom.app.main()
        └─→ QApplication + BloomTerminalApp(QWidget)
              ├─→ SetupWidget          (first-time setup screen)
              ├─→ IntroDashboard       (live splash: weather/profile/music/stats)
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
| `bloom/ui/widgets/intro_dashboard.py` | Live 3-column intro dashboard |
| `bloom/ui/widgets/song_player_widget.py` | **Non-blocking** music player (QThread) |
| `bloom/ui/widgets/system_stats_widget.py` | Battery + CPU live arc gauges |
| `bloom/ui/widgets/weather_widget.py` | wttr.in weather fetch |
| `bloom/ui/dialogs/profile_dialog.py` | XP/perks/avatar dialog |

---

## SongPlayerWidget — Threading Architecture (Critical)

> **This is the most complex widget. Read this before touching it.**

### Problem history
1. Original: `QFileDialog` with `DontUseNativeDialog` → rendered Qt dialog inside app window → **crash / UI corruption**
2. Fix attempt 1: `QFileDialog.getExistingDirectory()` → still used Qt dialog renderer on some systems → **same crash**
3. Fix attempt 2: `subprocess.run(["zenity", ...])` on main thread → **blocks Qt event loop → entire app freezes**
4. Fix attempt 3: `QMetaObject.invokeMethod(worker, "pick_folder", ...)` → **RuntimeError: No such method** (PyQt5 requires `@pyqtSlot` decorator for meta-object discovery)
5. ✅ **Final fix**: Pure signal/slot cross-thread dispatch with `@pyqtSlot` decorators

### Final threading model
```
Main thread emits _pick_trigger signal
    ↓ (Qt.QueuedConnection → executes on worker thread)
_FolderWorker.pick_folder()   ← @pyqtSlot()
    runs: subprocess.run(["zenity", ...])   ← blocks worker thread only
    emits: folder_picked(path_str)
    ↓ (auto QueuedConnection → executes on main thread)
SongPlayerWidget._on_folder_picked(folder)
    emits: _scan_trigger(folder)
    ↓ (Qt.QueuedConnection → executes on worker thread)
_FolderWorker.scan_folder(folder)   ← @pyqtSlot(str)
    runs: os.walk(folder)   ← blocks worker thread only
    emits: songs_ready(list_of_paths)
    ↓ (auto QueuedConnection → executes on main thread)
SongPlayerWidget._on_songs_ready(songs)
    updates UI, loads playlist
```

### Key rules
- `@pyqtSlot()` / `@pyqtSlot(str)` decorators are **mandatory** on all worker slots — without them PyQt5's meta-object system cannot route the calls across threads
- `Qt.QueuedConnection` on the `main → worker` signal connections ensures the slot runs on the worker's thread (not the main thread)
- `worker → main` connections are auto-QueuedConnection (PyQt5 detects the thread boundary)
- `QMetaObject.invokeMethod` is **NOT used anywhere** — it requires `@pyqtSlot` AND doesn't easily accept arguments in PyQt5
- `QFileDialog` is **NOT used** — it renders a Qt widget that corrupts the widget tree on some Wayland/X11 hybrid setups

### Folder picker fallback chain
```
1. zenity  (GTK — GNOME/Ubuntu)     subprocess.run(["zenity", "--file-selection", ...])
2. kdialog (KDE/Plasma)             subprocess.run(["kdialog", "--getexistingdirectory", ...])
3. tkinter filedialog               Separate GUI toolkit, own event loop
```

### Signals defined on SongPlayerWidget
| Signal | Type | Direction | Purpose |
|--------|------|-----------|---------|
| `_pick_trigger` | `pyqtSignal()` | main → worker | Triggers `pick_folder()` on worker thread |
| `_scan_trigger` | `pyqtSignal(str)` | main → worker | Triggers `scan_folder(path)` on worker thread |

### Signals defined on _FolderWorker
| Signal | Type | Direction | Purpose |
|--------|------|-----------|---------|
| `folder_picked` | `pyqtSignal(str)` | worker → main | Delivers chosen path ('' = cancelled) |
| `songs_ready` | `pyqtSignal(list)` | worker → main | Delivers sorted list of audio file paths |
| `error` | `pyqtSignal(str)` | worker → main | Delivers error message string |

---

## App Flow

```
Launch
  ├─→ First time? (no data.sql / base_dir missing)
  │     └─→ SetupWidget  →  enter name + pick sandbox folder  →  save to SQLite
  └─→ Returning user?
        └─→ IntroDashboard (live splash: weather / profile / music player / system stats)
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

Encryption files (`data/database/data.sql.enc` + `data.sql.meta`) are created by the `bloom lock` command using AES via `pycryptodome`.

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
| `bloom doctor` | 🩺 Runs system diagnostic environment check |
| `bloom intro` | Replays the intro splash screen |
| `bloom setup` | Goes back to first-time setup page |
| `bloom terminal` | Spawns a new Bloom Terminal window |
| `bloom tab` | Opens a new shell tab |
| `bloom browser <url/text>` | Opens URL or Google-searches text in system browser |
| `bloom lock` | Launches Ghost Vault Pro encryption (AES via pycryptodome) |
| `bloom -server` | Launches CineStream media server (Flask) |
| `bloom -share` | Launches file-share app |
| `bloom -usb` | Shows USB Cleaner / Porter selection dialog |
| `bloom lockfile` | Alias for Ghost Vault Pro |

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

## Intro Dashboard Widgets

### IntroDashboard (`bloom/ui/widgets/intro_dashboard.py`)
3-column live dashboard replacing the old static image splash:
- **Left column**: Weather widget + Profile card (name, XP, level, colour orbs)
- **Centre column**: Digital clock + Song player card (with Open Music Folder button)
- **Right column**: Avatar + Hint ticker + Battery/CPU gauges + Running programs

### WeatherWidget (`bloom/ui/widgets/weather_widget.py`)
- Fetches from `wttr.in/?format=j1` (JSON, no API key needed)
- Runs HTTP request in a `QThread` worker to avoid blocking UI
- Displays: condition description, temperature °C, feels-like, weather icon emoji
- Falls back gracefully if network unavailable

### SystemStatsWidget (`bloom/ui/widgets/system_stats_widget.py`)
- Uses `psutil` for live battery % and CPU %
- Draws arc gauges via `QPainter` with gradient fills
- Updates on a `QTimer` (interval: 2000ms)

### SongPlayerWidget (`bloom/ui/widgets/song_player_widget.py`)
- See "SongPlayerWidget — Threading Architecture" section above for full detail
- Prev / Play-Pause / Next controls
- Marquee label for long track names
- Supports: `.mp3 .wav .ogg .flac .m4a .aac .opus .wma`
- Falls back gracefully if `PyQt5.QtMultimedia` unavailable

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
ROOT_DIR       = python-bloom/
BLOOM_DIR      = python-bloom/bloom/
ASSETS_DIR     = python-bloom/bloom/assets/
LOGO_PATH      = bloom/assets/bloom-terminal-logo.png
WATERMARK_PATH = bloom/assets/bloom-art-raw.png
AVATARS_DIR    = bloom/assets/avatars/
DATA_DIR       = python-bloom/data/
DB_DIR         = python-bloom/data/database/
DB_PATH        = python-bloom/data/database/data.sql
```

---

## Dependencies

### Python packages (`requirements.txt`)
```
PyQt5>=5.15.0
pycryptodome>=3.10.0
customtkinter>=5.0.0
Flask>=2.0.0
ptyprocess>=0.7.0
psutil>=5.9.0
requests>=2.28.0
```

### System packages (auto-installed by `install.sh`)
```
python3-pyqt5
python3-pyqt5.qtmultimedia
libxcb-xinerama0 + other xcb libs
gstreamer1.0-plugins-good (audio backend)
zenity                    (native folder picker — critical for SongPlayerWidget)
```

> **Why zenity?** The Qt file dialog (`QFileDialog`) renders its own widget tree and on Wayland/X11 hybrid systems (GNOME with `QT_QPA_PLATFORM=xcb`) it can corrupt the parent widget layout causing a full freeze. `zenity` is a separate GTK process — it runs completely outside Qt.

---

## Bootstrap & Core Installer Architecture

The installation process is split into two components to facilitate a seamless, single-command installation experience for end-users:

### 1. The Bootstrapper (`install.sh` at the root)
- **Role**: This is the script downloaded and run by the user via the `curl` or `wget` command.
- **Workflow**:
  1. **OS Detection**: Detects the Linux distribution name to present a tailored console output.
  2. **Bootstrap Dependencies**: Verifies if basic command line utilities like `curl` and `tar` are installed, and automatically installs them if missing.
  3. **Release Querying**: Contacts the GitHub Releases API (`api.github.com/repos/Aaryanbanskota/Bloom-terminal/releases/latest`) to resolve the newest tag name and tarball download URL.
  4. **Fallback Handler**: If the repository is private or the GitHub API rate limit is exceeded, it falls back to copying/cloning the repository using Git SSH (`git@github.com:Aaryanbanskota/Bloom-terminal.git`).
  5. **Extraction**: Downloads and extracts the release directly into the user's home directory under `~/.bloom-terminal`, stripping any archive parent directories.
  6. **Handover**: Executes `scripts/setup.sh` inside `~/.bloom-terminal`.

### 2. The Core Setup (`scripts/setup.sh` in the codebase)
- **Role**: Runs inside the target installation directory to configure system packages, virtual environments, command registration, and desktop icons.
- **Workflow**:
  1. **Package Manager Selection**: Identifies if the system uses `apt`, `dnf`, `pacman`, or `zypper`.
  2. **System Dependencies**: Installs the required Qt5 and GStreamer system libraries (like `python3-pyqt5`, `zenity`, XCB libraries, etc.).
  3. **Virtualenv Setup**: Creates a Python virtual environment at `~/.bloom-terminal/venv` to ensure isolated executions.
  4. **PIP Requirements**: Installs and upgrades Python libraries (`PyQt5`, `customtkinter`, `psutil`, `pycryptodome`, etc.).
  5. **Executable Script**: Generates a launcher script (`~/.bloom-terminal/bloom.sh`) exporting critical configurations (e.g. `QT_QPA_PLATFORM=xcb` and `PYTHONPATH`).
  6. **Global Terminal Command**: Symlinks `bloom.sh` to `/usr/local/bin/bloom` (or falling back to `~/.local/bin/bloom` if write permissions are denied).
  7. **Desktop Application Shortcut**: Generates a `.desktop` launcher file in `~/.local/share/applications/bloom-terminal.desktop` linking the correct launcher script and logo file.

---

## Known Issues / Open GitHub Issues

| # | Title | Status | Notes |
|---|-------|--------|-------|
| 1 | 🐛 Broken Music Selector | Open | Filed on GitHub after initial push. Fixed by threading rewrite in session 2026-07-16 |

---

## Change Log

| # | Date | Request | What Changed | Files Affected |
|---|------|---------|-------------|----------------|
| 1 | — | Create GUI terminal like screenshots | PyQt5 app with intro splash + terminal view | `app.py` |
| 2 | — | Show in dock, run it | `app.setApplicationName`, ran with `QT_QPA_PLATFORM=wayland` | `app.py` |
| 3 | — | Fix white edges, click to skip intro | Set bg `#0f1219`, `mousePressEvent` on intro label | `app.py` |
| 4 | — | Real terminal, tabs, first-time setup, save name to SQLite | SetupWidget, data.sql, tab widget with + button | `setup_widget.py`, `database.py` |
| 5 | — | Refactor into separate files, tab close with confirmation | Split into bloom_db, bloom_setup, bloom_profile, bloom_terminal_tab, main.py | multiple |
| 6 | — | Fix Enter typing literal `\n` | Fixed escaped string to real newline | `terminal.py` |
| 7 | — | Smooth cropper, red dot close, double-click rename, watermark, hints | Custom AvatarCropper QPainter, BloomTabBar painted X, hint timer | `avatar_cropper.py`, `app.py` |
| 8 | — | App icon in dock, watermark, smooth avatar editor | QIcon on app+window, WatermarkTerminal, full avatar editor | `app.py`, `avatar_cropper.py` |
| 9 | — | All commands work, OS detection | Persistent shell (one bash per tab), OS detection, Ctrl+C, history arrows | `terminal.py` |
| 10 | — | Sandbox jail, bloom profile working, real terminal errors | `_inside_jail()` check, cd intercepted, bloom built-ins intercepted, colours | `terminal.py` |
| 11 | — | forai.md, force setup if no folder selected | Created forai.md, bloom_setup shows warning+blocks | `forai.md`, `setup_widget.py` |
| 12 | — | Fix intro dividing line, + button clipping, tab bar border | IntroScreen pure paintEvent+resizeEvent, top_bar HBox layout | `app.py` |
| 13 | — | Redesign terminal + bloom_runner.sh | Pill-shaped custom-painted tabs, bloom_runner.sh auto-venv launcher | `app.py`, `bloom_runner.sh` |
| 14 | — | Remove welcome banner, fix prompt colors, style popups | Prompt colors, output read-only, dark stylesheet, bloom commands | `terminal.py`, `app.py` |
| 15 | — | Fix add tab signal binding, integrate extra tools | lambda fix for bool crash; extra tools under bloom commands | `app.py`, `services/` |
| 16 | — | Fix bloom -server silent crash (no flask) | Installed Flask; `_launch_extra_tool()` helper with inline errors | `app.py` |
| 17 | — | Fix bloom commands going to bash, bloom browser | Token-split interception; `_tab_widget_ref`; `bloom browser` command | `terminal.py` |
| 18 | — | Fix modifier keys shifting page view | Updated keypress filter to ignore standalone modifier keys | `terminal.py` |
| 19 | — | Rewrite shell backend to use ptyprocess | Replaced QProcess with `ptyprocess` real PTY; password hiding; interactive sudo | `terminal.py` |
| 20 | 2026-07-16 | Restructure project to modular package | Full `bloom/` package layout; updated all imports; `run.py`; `pyproject.toml` | whole project |
| 21 | 2026-07-16 | Final pre-push audit + forai.md update | `bloom/core/config.py` & `logger.py`; all `__init__.py`; verified 39 files | `forai.md`, `core/` |
| 22 | 2026-07-16 | Add wingit components + live intro dashboard | `song_player_widget.py`, `system_stats_widget.py`, `weather_widget.py`, `intro_dashboard.py` | `ui/widgets/` |
| 23 | 2026-07-16 | Fix startup crashes, real-time widgets, QSocketNotifier warnings | Fixed `AttributeError` connections; restructured dashboard layout; `RunningProgramsWidget` via psutil | `intro_dashboard.py`, `system_stats_widget.py` |
| 24 | 2026-07-16 | **Git push** — UI, bloom lock, encryption, weather/analytics from intro | Committed avatar + encrypted DB files; pushed 2 commits to GitHub; filed GitHub issue: "Broken Music Selector" | `data/database/`, `assets/avatars/`, GitHub |
| 25 | 2026-07-16 | **Fix: music folder dialog crashes app** (attempt 1) | Replaced `QFileDialog(DontUseNativeDialog)` with `QFileDialog.getExistingDirectory()` — still used Qt widget renderer, still crashed on Wayland/X11 hybrid | `song_player_widget.py` |
| 26 | 2026-07-16 | **Fix: music folder dialog crashes app** (attempt 2 — partial) | Replaced Qt dialog with `subprocess.run(zenity)` — fixed crash but blocked main thread → app froze while zenity was open | `song_player_widget.py` |
| 27 | 2026-07-16 | **Fix: music folder picker freezes app** (attempt 3 — broken) | Tried `QMetaObject.invokeMethod(worker, "pick_folder", QueuedConnection)` → **RuntimeError: No such method** because `@pyqtSlot` was missing | `song_player_widget.py` |
| 28 | 2026-07-16 | **Fix: music folder picker** — final correct solution | Full `QThread` + `@pyqtSlot` rewrite. Two signals: `_pick_trigger → worker.pick_folder()` and `_scan_trigger → worker.scan_folder(path)`. `QMetaObject.invokeMethod` removed entirely. OS.walk also moved to worker thread. Button shows `…` + disabled while picker is open. Smooth, non-blocking, correct. | `song_player_widget.py` |
| 29 | 2026-07-16 | **Add `install.sh`** — one-command installer for fresh clone | `install.sh` checks Python version, installs Qt system libs + zenity via apt, creates venv, installs all pip packages, generates `bloom.sh` launcher with `QT_QPA_PLATFORM=xcb` | `install.sh`, `bloom.sh` |
| 30 | 2026-07-16 | **Bump version & universal installer updates** | Bumped version to `v0.1.0-beta` in configs, pyproject, and README. Overhauled `install.sh` to auto-detect and support `apt`, `dnf`, `pacman`, `zypper`. Registered `bloom` symlink/binary and a desktop launcher menu item (`bloom-terminal.desktop`). | `pyproject.toml`, `README.md`, `install.sh`, `bloom/core/config.py` |
| 31 | 2026-07-16 | **Add `bloom doctor` command** | Created system check diagnostics command `bloom doctor` to print OS, python, Qt status, audio player plugins, database setup validity, dependencies, folder permissions, and active picker tools. | `bloom/terminal/terminal.py`, `forai.md` |
| 32 | 2026-07-16 | **Refactor Installer into Bootstrap and Core** | Split the single repository installer into a lightweight bootstrapping `install.sh` and a core installer `scripts/setup.sh` inside the code folder. | `install.sh`, `scripts/setup.sh` |
| 33 | 2026-07-16 | **Add Release Downloader & Git Clone Fallback** | Updated `install.sh` to download/extract release archives automatically and fall back to `git clone` if downloading fails (due to testing on private repos). | `install.sh` |
| 34 | 2026-07-16 | **Update Documentation & Release Tags** | Updated `README.md` and `forai.md` to document the new installer. Created and updated the `v0.1.0-beta` git release tag. | `README.md`, `forai.md`, Git |

---

## Debugging Tips

### "QSocketNotifier: Can only be used with threads started with QThread"
This means a `QSocketNotifier` (used by the PTY backend) is being created from a non-Qt thread. The PTY notifier must be created on the main thread. Ensure `TerminalTab.__init__` and `_setup_pty()` are called from the main thread only.

### "QMetaObject::invokeMethod: No such method _FolderWorker::pick_folder()"
`QMetaObject.invokeMethod` cannot find the method — the slot is missing its `@pyqtSlot()` decorator OR `invokeMethod` is being used (it's been removed). Use signal→slot connections with `Qt.QueuedConnection` instead.

### "Warning: Ignoring XDG_SESSION_TYPE=wayland on Gnome"
Not an error — just a warning. Set `QT_QPA_PLATFORM=xcb` before launching to suppress it. `install.sh` + `bloom.sh` do this automatically.

### App freezes when opening folder picker
`subprocess.run()` was called on the main thread. All blocking calls must be on `_FolderWorker` (the QThread worker). See "SongPlayerWidget — Threading Architecture" above.

### VS Code lags when running Bloom
VS Code's Python debugger attaches to all threads including Qt's render thread. Run with `--no-debug` or use `bloom.sh` from an external terminal for smooth performance.
