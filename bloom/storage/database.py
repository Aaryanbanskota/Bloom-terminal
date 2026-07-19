import sqlite3
from PyQt5.QtCore import QSettings
from bloom.core.paths import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            base_dir TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            success_cmds INTEGER DEFAULT 0,
            failed_cmds INTEGER DEFAULT 0,
            avatar TEXT DEFAULT ''
        )
    ''')
    for col, def_val in [('xp', '0'), ('level', '1'), ('success_cmds', '0'), ('failed_cmds', '0'), ('avatar', '""')]:
        try:
            cursor.execute(f'ALTER TABLE user_data ADD COLUMN {col} INTEGER DEFAULT {def_val}')
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn

def get_user_data(conn):
    if conn is None:
        return None
    cursor = conn.cursor()
    settings = QSettings("Bloom", "BloomTerminal")
    cached_name = settings.value("cached_user_name", None)
    if cached_name:
        cursor.execute('SELECT name, base_dir, xp, level, success_cmds, failed_cmds, avatar FROM user_data WHERE name = ?', (cached_name,))
        row = cursor.fetchone()
        if row:
            return row
    # Fallback to the first row if none or if cached_name doesn't match a row
    cursor.execute('SELECT name, base_dir, xp, level, success_cmds, failed_cmds, avatar FROM user_data LIMIT 1')
    return cursor.fetchone()

def save_user_setup(conn, name, base_dir):
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM user_data WHERE name = ?', (name,))
    if cursor.fetchone():
        cursor.execute('UPDATE user_data SET base_dir = ? WHERE name = ?', (base_dir, name))
    else:
        cursor.execute('INSERT INTO user_data (name, base_dir) VALUES (?, ?)', (name, base_dir))
    conn.commit()

def update_user_stats(conn, xp, level, success, failed, avatar, name=None):
    if conn is None:
        return
    cursor = conn.cursor()
    if name is None:
        settings = QSettings("Bloom", "BloomTerminal")
        name = settings.value("cached_user_name", "")
    
    cursor.execute('''UPDATE user_data SET 
        xp = ?, level = ?, success_cmds = ?, failed_cmds = ?, avatar = ?
        WHERE name = ?
    ''', (xp, level, success, failed, avatar, name))
    
    # If no row exists yet, insert one
    if cursor.rowcount == 0:
        cursor.execute(
            '''INSERT INTO user_data (name, base_dir, xp, level, success_cmds, failed_cmds, avatar)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (name, "", xp, level, success, failed, avatar)
        )
    conn.commit()
