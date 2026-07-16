#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  bloom_runner.sh  —  Easy launcher for Bloom Terminal
#
#  Usage:
#    ./bloom_runner.sh          # normal launch
#    bash bloom_runner.sh       # works too
#
#  What it does:
#    1. Finds the project directory (same folder as this script)
#    2. Creates a Python venv if one doesn't exist
#    3. Installs PyQt5 if not installed
#    4. Detects the display server (Wayland / X11) automatically
#    5. Launches Bloom Terminal
# ─────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON="python3"

# ── Colour helpers ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'
info()  { echo -e "${CYAN}[Bloom]${RESET} $*"; }
ok()    { echo -e "${GREEN}[Bloom]${RESET} $*"; }
err()   { echo -e "${RED}[Bloom] ERROR:${RESET} $*" >&2; }

# ── Check Python ─────────────────────────────────────────────────
if ! command -v "$PYTHON" &>/dev/null; then
    err "python3 not found. Please install Python 3.8+ first."
    exit 1
fi

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY_VER"

# ── Create venv if missing ───────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment in $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

# ── Activate venv ────────────────────────────────────────────────
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "Virtual environment activated."

# ── Install dependencies if not present ────────────────────────
DEPS_NEEDED=0
"$PYTHON" -c "import PyQt5" &>/dev/null || DEPS_NEEDED=1
"$PYTHON" -c "import PyQt6" &>/dev/null || DEPS_NEEDED=1
"$PYTHON" -c "import Crypto" &>/dev/null || DEPS_NEEDED=1
"$PYTHON" -c "import customtkinter" &>/dev/null || DEPS_NEEDED=1
"$PYTHON" -c "import flask" &>/dev/null || DEPS_NEEDED=1

if [ $DEPS_NEEDED -eq 1 ]; then
    info "Installing dependencies (PyQt5, PyQt6, pycryptodome, customtkinter, Flask) — this may take a moment..."
    pip install --quiet --upgrade pip
    pip install --quiet PyQt5 PyQt6 pycryptodome customtkinter Flask
    ok "Dependencies installed."
else
    info "Dependencies are already up to date."
fi

# ── Detect display server ────────────────────────────────────────
# Prefer Wayland when available; fall back to xcb (X11)
if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    QT_PLATFORM="wayland"
else
    QT_PLATFORM="xcb"
fi
info "Display backend: $QT_PLATFORM"

# ── Launch ───────────────────────────────────────────────────────
ok "Starting Bloom Terminal 🌸"
cd "$SCRIPT_DIR"
export QT_QPA_PLATFORM="$QT_PLATFORM"
exec "$PYTHON" run.py "$@"
