# Contributing to Bloom Terminal

## Quick Setup:
1. Clone repository
2. Run `./bloom_runner.sh` to install virtual environment & dependencies automatically.

## Rules for Adding New Widgets:
1. Store under `bloom/ui/widgets/`
2. Ensure any non-standard libraries (e.g., psutil) fail gracefully with try/except fallbacks so the application runs on bare systems.
3. Hook settings toggle via `QSettings` inside `SettingsDialog`.
