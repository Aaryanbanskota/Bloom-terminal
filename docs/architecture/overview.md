# Project Architecture Overview

Bloom Terminal is a modular desktop GUI terminal app built with PyQt5.

## Modules:
- `bloom/app.py`: Coordinates the screens and main application state.
- `bloom/ui/widgets/`: Modular, customizable UI widgets (Intro Dashboard, Weather, Song Player, Battery/CPU Stats).
- `bloom/security/`: Handles user security, AES-256 database encryption, and lock screens.
- `bloom/terminal/`: Wraps PTY process handling for cross-platform shell compatibility.
