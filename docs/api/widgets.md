# UI Widgets API Reference

## IntroDashboard
Constructor:
`IntroDashboard(user_name, xp, level, avatar_path, on_click, on_resetup, on_settings, parent)`

### Signals
- `clicked()`: Emitted when user clicks to enter.
- `settings_clicked()`: Emitted when settings gear button is clicked.

## SongPlayerWidget
Plays files from a folder or URL stream.
`SongPlayerWidget(parent)`

## BatteryCpuWidget
Displays CPU & battery usage statistics.
`BatteryCpuWidget(parent)`
