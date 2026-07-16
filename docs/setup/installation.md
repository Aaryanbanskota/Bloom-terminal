# Installation Guide

## System Requirements

| Requirement | Minimum Version |
|-------------|----------------|
| Python | 3.8+ |
| PyQt5 | 5.15.0+ |
| ptyprocess | 0.7.0+ |
| pycryptodome | 3.10.0+ |
| psutil | 5.9.0+ |
| curl or wget | any |
| tar | any |

Supported Linux distributions: **Ubuntu / Debian** (apt), **Fedora / RHEL** (dnf), **Arch** (pacman), **openSUSE** (zypper).

---

## ✅ Recommended: One-Command Bootstrap Installation

This is the easiest way to install Bloom Terminal. The bootstrap script automatically:

1. Detects your Linux distribution
2. Installs `curl` and `tar` if missing
3. Downloads the latest release from GitHub Releases API
4. Falls back to `git clone` if release download is unavailable
5. Extracts the project to `~/.bloom-terminal`
6. Installs all system and Python dependencies
7. Registers the global `bloom` command
8. Creates a desktop application launcher

```bash
curl -fsSL https://raw.githubusercontent.com/Aaryanbanskota/Bloom-terminal/main/install.sh | bash
```

Or using `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/Aaryanbanskota/Bloom-terminal/main/install.sh | bash
```

After installation:

```bash
bloom
```

Or search **Bloom Terminal** from your desktop applications menu.

---

## 🔧 Manual Setup (Developers)

If you prefer to clone the repository and run Bloom Terminal manually:

```bash
# 1. Clone the repository
git clone https://github.com/Aaryanbanskota/Bloom-terminal.git
cd Bloom-terminal

# 2. Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Run the app
python run.py
```

---

## 📁 Installation Layout

After bootstrap installation, Bloom Terminal lives in:

```
~/.bloom-terminal/          ← installation root
  ├── bloom/                ← Python package
  ├── scripts/setup.sh      ← core installer (already ran)
  ├── venv/                 ← isolated Python environment
  └── bloom.sh              ← launcher wrapper script

/usr/local/bin/bloom        ← global symlink (or ~/.local/bin/bloom)
~/.local/share/applications/bloom-terminal.desktop ← desktop launcher
```

---

## 🗑️ Uninstalling

```bash
rm -rf ~/.bloom-terminal
rm -f /usr/local/bin/bloom        # or ~/.local/bin/bloom
rm -f ~/.local/share/applications/bloom-terminal.desktop
```
