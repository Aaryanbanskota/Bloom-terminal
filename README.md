# Bloom Terminal 🌸

Bloom Terminal is a beautiful, custom Python desktop GUI terminal application built using **PyQt5** and `ptyprocess`. It acts as a real Linux terminal but adds unique RPG-style gamification, custom UI designs, and directory sandboxing.

## Features

- 🎮 **Gamification**: Earn XP and level up by successfully running commands! Unlock perks at higher levels.
- 🛡️ **Sandbox Mode**: Locks the terminal inside a user-chosen base folder. Prevents accidental modifications outside of your sandbox.
- 🎨 **Beautiful UI**: Pill-shaped tabs, customized avatars, sleek dark mode, and an embedded watermark.
- 🔒 **Real PTY Backend**: Uses `ptyprocess` to spawn a real Pseudo-Terminal (PTY) in the background. Full support for password prompts like `sudo` with visual masking (`***`).
- 🛠️ **Built-in Tools**: Use special `bloom` commands (like `bloom profile`, `bloom browser`, `bloom -server`) without leaving your terminal.

## Prerequisites

- Python 3.8+
- `ptyprocess`

## Installation & Running

For the easiest setup, simply run the included auto-runner script which creates a virtual environment, installs the required dependencies, and launches the app!

```bash
bash bloom_runner.sh
```

Alternatively, you can manually set it up:
```bash
python3 -m venv venv
source venv/bin/activate
pip install PyQt5 ptyprocess
python3 main.py
```

## Bloom Built-in Commands

- `bloom profile`: Opens your XP and avatar profile.
- `bloom help`: View all available custom commands.
- `bloom browser <query>`: Open your system browser directly.
- `bloom -server`: Launch CineStream, a personal media server.
- `bloom lockfile`: Open Ghost Vault Pro for file encryption.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
