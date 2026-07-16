# Security Manager API Reference

Handles encryption of SQLite database files when Password Lock is enabled.

### Methods
- `is_locked() -> bool`: Returns lock active state.
- `enable_lock(password: str) -> bool`: Encrypts SQLite database file via AES-256-GCM.
- `disable_lock(password: str) -> bool`: Decrypts database and restores it.
- `decrypt_for_access(password: str) -> bool`: Verifies and loads the database in-memory for the current session.
