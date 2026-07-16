# Installation Guide

## Requirements
- Python 3.8+
- PyQt5
- psutil
- pycryptodome
- curl / wget (for bootstrap installation)
- tar (for archive extraction)

## Recommended: One-Command Bootstrap Installation
This is the easiest way to install Bloom Terminal. It will automatically download the latest release, extract it, install dependencies, register the global command, and create the desktop launcher.

```bash
curl -fsSL https://raw.githubusercontent.com/Aaryanbanskota/Bloom-terminal/main/install.sh | bash
```

Or using `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/Aaryanbanskota/Bloom-terminal/main/install.sh | bash
```

## Manual Setup (Developers)
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
