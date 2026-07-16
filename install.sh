#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Bloom Terminal — One-command installer
#  Usage:
#    git clone https://github.com/Aaryanbanskota/Bloom-terminal.git
#    cd Bloom-terminal
#    bash install.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e  # exit on any error

BOLD="\033[1m"
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

step() { echo -e "\n${CYAN}▶ $1${RESET}"; }
ok()   { echo -e "${GREEN}✔ $1${RESET}"; }
warn() { echo -e "${YELLOW}⚠ $1${RESET}"; }
fail() { echo -e "${RED}✘ $1${RESET}"; exit 1; }

echo -e "${BOLD}"
echo "  ██████╗ ██╗      ██████╗  ██████╗ ███╗   ███╗"
echo "  ██╔══██╗██║     ██╔═══██╗██╔═══██╗████╗ ████║"
echo "  ██████╔╝██║     ██║   ██║██║   ██║██╔████╔██║"
echo "  ██╔══██╗██║     ██║   ██║██║   ██║██║╚██╔╝██║"
echo "  ██████╔╝███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║"
echo "  ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝"
echo -e "${RESET}  Terminal — Installer\n"

# ── 1. Check Python ───────────────────────────────────────────────────────────
step "Checking Python version"
if ! command -v python3 &>/dev/null; then
    fail "Python 3 not found. Install it with: sudo apt install python3 python3-pip python3-venv"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    fail "Python 3.8+ required. Found: $PY_VER"
fi
ok "Python $PY_VER found"

# ── 2. System dependencies ────────────────────────────────────────────────────
step "Checking system dependencies"

MISSING=()

# Qt platform plugins need libxcb
if ! python3 -c "import PyQt5" &>/dev/null 2>&1; then
    if command -v apt-get &>/dev/null; then
        echo "  Installing Qt system libs..."
        sudo apt-get install -y -q \
            python3-pyqt5 \
            python3-pyqt5.qtmultimedia \
            libxcb-xinerama0 \
            libxcb-icccm4 \
            libxcb-image0 \
            libxcb-keysyms1 \
            libxcb-randr0 \
            libxcb-render-util0 \
            libgstreamer1.0-0 \
            gstreamer1.0-plugins-base \
            gstreamer1.0-plugins-good \
            gstreamer1.0-alsa \
            zenity 2>/dev/null || warn "Some system libs may be missing"
    else
        warn "apt-get not available — install Qt5 + zenity manually if needed"
    fi
fi

# zenity (native folder picker — avoids Qt dialog crashes)
if ! command -v zenity &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        echo "  Installing zenity..."
        sudo apt-get install -y -q zenity 2>/dev/null || warn "Could not install zenity"
    else
        warn "zenity not found — folder picker will use tkinter fallback"
    fi
fi

ok "System dependencies ready"

# ── 3. Virtual environment ────────────────────────────────────────────────────
step "Setting up Python virtual environment"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

source venv/bin/activate

# ── 4. Upgrade pip quietly ────────────────────────────────────────────────────
step "Upgrading pip"
pip install --upgrade pip --quiet
ok "pip up to date"

# ── 5. Install Python dependencies ───────────────────────────────────────────
step "Installing Python packages"
pip install --quiet \
    "PyQt5>=5.15.0" \
    "pycryptodome>=3.10.0" \
    "customtkinter>=5.0.0" \
    "Flask>=2.0.0" \
    "ptyprocess>=0.7.0" \
    "psutil>=5.9.0" \
    "requests>=2.28.0"

# Try multimedia support (optional — gracefully skipped if unavailable)
pip install --quiet "PyQt5-Qt5" 2>/dev/null || true

ok "Python packages installed"

# ── 6. Create run script ──────────────────────────────────────────────────────
step "Creating launch script"
cat > bloom.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
# Suppress XDG_SESSION_TYPE warning on mixed Wayland/X11 systems
export QT_QPA_PLATFORM=xcb
export PYTHONPATH="$(pwd)"
exec python3 -m bloom "$@"
EOF
chmod +x bloom.sh
ok "Launch script created: ./bloom.sh"

# ── 7. Done ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  ✅  Bloom Terminal installed successfully!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Run Bloom Terminal with:"
echo -e "  ${BOLD}  ./bloom.sh${RESET}"
echo ""
echo -e "  Or manually:"
echo -e "  ${BOLD}  source venv/bin/activate${RESET}"
echo -e "  ${BOLD}  python3 -m bloom${RESET}"
echo ""
