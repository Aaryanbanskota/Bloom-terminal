#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  🌸 Bloom Terminal — Multi-Distribution Installer & Service Configurator
#  Supports: apt (Debian/Ubuntu), dnf (RHEL/Fedora), pacman (Arch), zypper (SUSE)
# ─────────────────────────────────────────────────────────────────────────────

set -e

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
echo -e "${RESET}  Universal Terminal Installer (v0.1.0-beta)\n"

# ── 1. Detect Package Manager and OS ──────────────────────────────────────────
step "Detecting package manager and OS distribution"

OS_NAME=""
PKG_MANAGER=""
INSTALL_CMD=""

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
fi

if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    INSTALL_CMD="sudo apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    INSTALL_CMD="sudo dnf install -y"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    INSTALL_CMD="sudo pacman -S --noconfirm"
elif command -v zypper &>/dev/null; then
    PKG_MANAGER="zypper"
    INSTALL_CMD="sudo zypper install -y"
else
    warn "Unsupported distribution/package manager. You will need to install system dependencies manually."
fi

ok "Detected $OS_NAME using $PKG_MANAGER"

# ── 2. Install System Dependencies ────────────────────────────────────────────
step "Installing system dependencies"

if [ -n "$PKG_MANAGER" ]; then
    case "$PKG_MANAGER" in
        apt)
            echo "Running apt update and package installation..."
            sudo apt-get update -q
            $INSTALL_CMD \
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
                zenity \
                python3-venv \
                python3-pip \
                python3-tk
            ;;
        dnf)
            echo "Running dnf installation..."
            $INSTALL_CMD \
                python3-qt5 \
                zenity \
                python3-tkinter \
                gstreamer1-plugins-base \
                gstreamer1-plugins-good
            ;;
        pacman)
            echo "Running pacman installation..."
            $INSTALL_CMD \
                python-pyqt5 \
                zenity \
                tk \
                gstreamer \
                gst-plugins-base \
                gst-plugins-good
            ;;
        zypper)
            echo "Running zypper installation..."
            $INSTALL_CMD \
                python3-qt5 \
                zenity \
                python3-tk \
                gstreamer-plugins-base \
                gstreamer-plugins-good
            ;;
    esac
    ok "System packages installed successfully"
else
    warn "Skipped system dependency installation (manual installation required)"
fi

# ── 3. Setup Python Virtual Environment ────────────────────────────────────────
step "Setting up virtual environment"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

source venv/bin/activate

# ── 4. Upgrade pip and Install Python packages ────────────────────────────────
step "Installing Python packages inside virtual environment"
pip install --upgrade pip --quiet
pip install --quiet \
    "PyQt5>=5.15.0" \
    "pycryptodome>=3.10.0" \
    "customtkinter>=5.0.0" \
    "Flask>=2.0.0" \
    "ptyprocess>=0.7.0" \
    "psutil>=5.9.0" \
    "requests>=2.28.0"

# Optional PyQt5 QtMultimedia packages support
pip install --quiet "PyQt5-Qt5" 2>/dev/null || true
ok "Python packages configured successfully"

# ── 5. Create Desktop Launcher and Binary Symlink ─────────────────────────────
step "Registering 'bloom' command and desktop launcher"

# Create launch wrapper in repo
LAUNCH_SCRIPT="$(pwd)/bloom.sh"
cat > "$LAUNCH_SCRIPT" << EOF
#!/usr/bin/env bash
cd "$(pwd)"
source venv/bin/activate
export QT_QPA_PLATFORM=xcb
export PYTHONPATH="$(pwd)"
exec python3 -m bloom "\$@"
EOF
chmod +x "$LAUNCH_SCRIPT"

# Register global bin symlink if /usr/local/bin exists and is writable, or fallback to ~/.local/bin
BIN_DIR="/usr/local/bin"
if [ -w "$BIN_DIR" ]; then
    sudo ln -sf "$LAUNCH_SCRIPT" "$BIN_DIR/bloom"
    ok "Global terminal command registered: type 'bloom' anywhere!"
else
    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"
    ln -sf "$LAUNCH_SCRIPT" "$LOCAL_BIN/bloom"
    warn "Could not write to $BIN_DIR. Symlinked to $LOCAL_BIN/bloom instead."
    warn "Ensure $LOCAL_BIN is in your PATH."
fi

# Create custom desktop file
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/bloom-terminal.desktop"
LOGO_PATH="$(pwd)/bloom/assets/bloom-terminal-logo.png"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=0.1.0-beta
Type=Application
Name=Bloom Terminal
Comment=A beautifully crafted, gamified, sandboxed desktop terminal emulator.
Exec=$LAUNCH_SCRIPT
Icon=$LOGO_PATH
Terminal=false
Categories=System;TerminalEmulator;Utility;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"
ok "Desktop application launcher created: $DESKTOP_FILE"

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  ✅  Bloom Terminal installation complete!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  You can now run Bloom Terminal by:"
echo -e "  1. Typing ${BOLD}bloom${RESET} in any terminal session."
echo -e "  2. Finding ${BOLD}Bloom Terminal${RESET} in your Applications menu."
echo ""
