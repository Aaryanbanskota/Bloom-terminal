#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  🌸 Bloom Terminal — Bootstrap Installer
#  Downloads and installs Bloom Terminal directly from the official repository.
# ─────────────────────────────────────────────────────────────────────────────

set -e

BOLD="\033[1m"
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

echo -e "\n${BOLD}🌸 Bloom Terminal Installer${RESET}\n"

# ── 1. Detect OS ──────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
else
    OS_NAME="Linux"
fi
echo -e "${GREEN}✓${RESET} Detecting ${OS_NAME}..."

# ── 2. Install/Check Basic Bootstrapping Dependencies ─────────────────────────
if ! command -v curl &>/dev/null; then
    echo -e "${YELLOW}⚠ curl is missing. Attempting to install curl...${RESET}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -y && sudo apt-get install -y curl
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y curl
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm curl
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y curl
    fi
fi

if ! command -v tar &>/dev/null; then
    echo -e "${YELLOW}⚠ tar is missing. Attempting to install tar...${RESET}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -y && sudo apt-get install -y tar
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y tar
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm tar
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y tar
    fi
fi
echo -e "${GREEN}✓${RESET} Installing dependencies..."

# ── 3. Download Latest Bloom Release from GitHub ──────────────────────────────
API_URL="https://api.github.com/repos/Aaryanbanskota/Bloom-terminal/releases/latest"
RELEASE_JSON=$(curl -fsSL "$API_URL" 2>/dev/null || echo "")

TAG_NAME=$(echo "$RELEASE_JSON" | grep -m 1 '"tag_name":' | cut -d '"' -f 4 || echo "")
TARBALL_URL=$(echo "$RELEASE_JSON" | grep -m 1 '"tarball_url":' | cut -d '"' -f 4 || echo "")

# Graceful fallback to main branch tarball URL
if [ -z "$TARBALL_URL" ] || [ "$TARBALL_URL" = "null" ]; then
    TAG_NAME="v0.1.0-beta"
    TARBALL_URL="https://github.com/Aaryanbanskota/Bloom-terminal/archive/refs/heads/main.tar.gz"
fi

echo -e "${GREEN}✓${RESET} Downloading Bloom ${TAG_NAME}..."

INSTALL_DIR="$HOME/.bloom-terminal"
mkdir -p "$INSTALL_DIR"

TEMP_TAR="/tmp/bloom-${TAG_NAME}.tar.gz"
DOWNLOAD_SUCCESS=true

# Try to download release archive
if ! curl -fsSL -o "$TEMP_TAR" "$TARBALL_URL"; then
    DOWNLOAD_SUCCESS=false
fi

if [ "$DOWNLOAD_SUCCESS" = "true" ] && [ -f "$TEMP_TAR" ]; then
    # Extract archive
    tar -xzf "$TEMP_TAR" -C "$INSTALL_DIR" --strip-components=1
    rm -f "$TEMP_TAR"
else
    # Fallback to git clone if download failed (e.g., due to private repo auth)
    echo -e "${YELLOW}⚠ Archive download not accessible. Falling back to git clone...${RESET}"
    if ! command -v git &>/dev/null; then
        echo -e "${YELLOW}⚠ git is missing. Installing git...${RESET}"
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -y && sudo apt-get install -y git
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y git
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm git
        elif command -v zypper &>/dev/null; then
            sudo zypper install -y git
        fi
    fi
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 git@github.com:Aaryanbanskota/Bloom-terminal.git "$INSTALL_DIR"
fi

# ── 4. Run Core Installer ─────────────────────────────────────────────────────
echo -e "${GREEN}✓${RESET} Installing..."
cd "$INSTALL_DIR"
bash scripts/setup.sh
