import sqlite3
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
    cursor.execute('SELECT name, base_dir, xp, level, success_cmds, failed_cmds, avatar FROM user_data LIMIT 1')
    return cursor.fetchone()

def save_user_setup(conn, name, base_dir):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_data')
    cursor.execute('INSERT INTO user_data (name, base_dir) VALUES (?, ?)', (name, base_dir))
    conn.commit()

def update_user_stats(conn, xp, level, success, failed, avatar):
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute('''UPDATE user_data SET 
        xp = ?, level = ?, success_cmds = ?, failed_cmds = ?, avatar = ?
    ''', (xp, level, success, failed, avatar))
    conn.commit()
