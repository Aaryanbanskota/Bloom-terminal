# Bloom Terminal — AI Context File (`forai.md`)

> This file is updated every time a change is made to the project.
> Written so any AI assistant can understand the project state instantly.

---

## What This Project Is

A Python desktop GUI terminal app called **Bloom Terminal**, built with PyQt5.
It looks like a real terminal but adds RPG-style gamification (XP, levels, perks)
and a directory sandbox that locks the shell inside a user-chosen folder.

---

## Project File Structure

```
python-bloom/
├── main.py                  # App entry point. Window, tab bar, navigation logic.
├── bloom_db.py              # SQLite helpers (init, read, write user data).
├── bloom_setup.py           # First-time setup screen (name + base directory).
├── bloom_terminal_tab.py    # The actual terminal tab (shell, sandbox, key input).
├── bloom_profile.py         # Profile view dialog + avatar editor.
├── bloom_runner.sh          # Easy launcher: creates venv, installs deps, auto-detects Wayland/X11.
├── asset/
│   ├── bloom-terminal-logo.png   # App icon (shown in dock/taskbar).
│   ├── bloom-art-raw.png         # Watermark drawn at ~6% opacity in terminal.
│   ├── bloom-flower.png
│   └── butterfly.png
├── profile-selection/            # User avatar images (PNG/JPG).
├── data.sql                      # SQLite database (auto-created on first run).
├── venv/                         # Python virtual environment.
└── forai.md                      # This file.
```

---

## How to Run

### Easy way (recommended for everyone)
```bash
bash bloom_runner.sh
# or, after making it executable once:
./bloom_runner.sh
```
The script automatically creates the venv, installs PyQt5, and detects Wayland vs X11.

### Manual way
```bash
source venv/bin/activate
export QT_QPA_PLATFORM=wayland   # Linux/GNOME Wayland only
python3 main.py
```

---

## App Flow

```
Launch
  -> First time? (no data.sql / base_dir missing or invalid)
        -> Setup Screen  ->  enter name + choose sandbox folder
  -> Returning user?
        -> Intro Screen (60 sec splash, click to skip, Re-setup button top right)
              -> Terminal Screen (tabs, commands, bloom built-ins)
```

---

## Database (data.sql - SQLite)

Table: user_data

| Column        | Type    | Notes                          |
|---------------|---------|--------------------------------|
| id            | INTEGER | Primary key                    |
| name          | TEXT    | User display name              |
| base_dir      | TEXT    | Sandbox root folder            |
| xp            | INTEGER | Total XP earned                |
| level         | INTEGER | Derived from XP                |
| success_cmds  | INTEGER | Count of successful commands   |
| failed_cmds   | INTEGER | Count of failed commands       |
| avatar        | TEXT    | Path to saved avatar image     |

---

## Terminal Sandbox

- User picks a folder during setup. That folder is the jail root.
- cd commands are intercepted before reaching the shell.
- Any cd that would go above the jail root is blocked with a red bash-style error.
- ~ inside the terminal expands to the jail root, not $HOME.
- Sentinel: every command appends echo __BLOOM_DONE__:$?:$(pwd) so the app
  can track exit code and current directory without a PTY.

---

## Bloom Built-in Commands

| Command          | What it does                                |
|------------------|---------------------------------------------|
| bloom profile    | Opens the profile/XP dialog                |
| bloom help       | Prints available Bloom commands in terminal |

---

## XP and Levelling

- Successful command -> +10 XP
- Failed command -> +5 XP (still learning)
- Level formula: level = int((xp / 100) ** 0.6) + 1
- Perks unlock at levels: 1, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100

---

## Profile / Avatar Editor

- bloom profile command opens a dialog showing:
  - Circular avatar (red border) with tier/level/XP/stats
  - XP progress bar to next level
  - List of unlocked perks
- Edit Profile button opens ProfileEditDialog:
  - Left: custom AvatarCropper widget - drag to pan, scroll/slider to zoom
  - Right: grid of preset avatars from profile-selection/
  - Upload Image button for any file
  - Save Avatar renders cropped circle, saves as profile-selection/saved_avatar.png

---

## Tab Bar

- Custom BloomTabBar draws red dot X buttons manually via QPainter.
- Double-click a tab -> rename dialog (QInputDialog).
- Closing a tab while a process runs -> confirmation popup.
- + corner button adds new tab at sandbox root.

---

## Cross-Platform OS Detection

- Linux/Mac: uses $SHELL, falls back to /bin/bash then /bin/sh
- Windows: uses %COMSPEC% (cmd.exe)
- Shell font: Courier New (Linux/Windows), Monaco (Mac)

---

## Change Log

| # | Request | Done |
|---|---------|------|
| 1 | Create GUI terminal like screenshots | PyQt5 app with intro splash + terminal view |
| 2 | Show in dock, run it | app.setApplicationName, ran with QT_QPA_PLATFORM=wayland |
| 3 | Fix white edges, click to skip intro | Set bg #0f1219, mousePressEvent on intro label |
| 4 | Real terminal, tabs, first-time setup, save name to SQLite | SetupWidget, data.sql, tab widget with + button |
| 5 | Refactor into separate files, tab close with confirmation | Split into bloom_db, bloom_setup, bloom_profile, bloom_terminal_tab, main.py |
| 6 | Fix Enter typing literal slash-n | Fixed escaped string to real newline |
| 7 | Smooth cropper, red dot close, double-click rename, watermark, hints | Custom AvatarCropper QPainter, BloomTabBar painted X, hint timer |
| 8 | App icon in dock, watermark, smooth avatar editor | QIcon on app+window, WatermarkTerminal, full avatar editor |
| 9 | All commands work, OS detection | Persistent shell (one bash per tab), OS detection, Ctrl+C, history arrows |
| 10 | Sandbox jail, bloom profile working, real terminal errors | _inside_jail() check, cd intercepted, bloom built-ins intercepted, colours |
| 11 | forai.md, force setup if no folder selected | Created forai.md, bloom_setup shows warning+blocks, main.py checks isdir |
| 12 | Fix intro dividing line, + button clipping, tab bar border | IntroScreen uses pure paintEvent+resizeEvent, top_bar HBox layout, setTabBar+reparent, documentMode |
| 13 | Redesign terminal to match screenshot + bloom_runner.sh | Pill-shaped custom-painted tabs, white circle + button, seamless BG_DARK tab row, bloom_runner.sh auto-venv launcher |
| 14 | Remove welcome banner, fix prompt colors, protect output editing, style popups & add bloom page commands | Prompt colors updated, output area made read-only, dark stylesheet for right click, dialogs & rename menus, added bloom setup/intro/terminal/tab commands, fixed QMessageBox navigation |
| 15 | Fix add tab signal binding, integrate extra tools (server, share, usb, lockfile) | Wrapped add_new_tab in lambda to prevent checked bool pass-through crash, integrated extra-feature apps under bloom commands, and added pycryptodome & customtkinter dependencies check inside bloom_runner.sh |
| 16 | Fix bloom -server crashing silently (No module named 'flask') | Installed Flask into venv; added _launch_extra_tool() helper in bloom_terminal_tab.py that shows crash errors inline in the terminal instead of silently swallowing them; all extra-feature commands (server, share, usb, lockfile) now use this helper |
| 17 | Fix: bloom commands going to bash, close tab broken, add bloom browser | Fixed bloom interception to use token-split check (tokens[0].lower()=="bloom") instead of fragile startswith; fixed close tab — BloomTabBar parent changes after reparenting so stored _tab_widget_ref directly on bar; added bloom browser <url/text> command (auto-detects URL vs search, opens system browser); fixed help stats attributes (xp/level not user_xp/user_level); added bloom browser section to bloom help |
| 18 | Fix: modifier keys shifting page view down | Updated keypress event filter to ignore standalone modifier key presses (Control, Shift, Alt, Meta) in the read-only buffer area, preventing the typing protection guard from jumping the text cursor down to the bottom of the page when selecting text |
| 19 | Rewrite shell backend to use ptyprocess | Replaced QProcess with ptyprocess for a real PTY with password hiding, allowing interactive commands like `sudo` to work correctly while maintaining custom prompt/interception. |
