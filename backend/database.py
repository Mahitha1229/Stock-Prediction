import sqlite3
from auth import hash_password, verify_password

DB_PATH = "users.db"


def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS watchlist (
        username TEXT, stock TEXT,
        PRIMARY KEY (username, stock),
        FOREIGN KEY (username) REFERENCES users(username))""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        role TEXT,
        content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (username) REFERENCES users(username))""")
    conn.commit()
    conn.close()


def register_user(username: str, password: str) -> tuple[bool, str]:
    """Returns (success, message)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def login_user(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return bool(user and verify_password(password, user[0]))


def add_to_watchlist(username: str, stock: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO watchlist (username, stock) VALUES (?, ?)", (username, stock))
    conn.commit()
    conn.close()


def remove_from_watchlist(username: str, stock: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE username = ? AND stock = ?", (username, stock))
    conn.commit()
    conn.close()


def get_watchlist(username: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT stock FROM watchlist WHERE username = ?", (username,))
    stocks = [row[0] for row in c.fetchall()]
    conn.close()
    return stocks


def save_chat_message(username: str, role: str, content: str):
    """role should be 'user' or 'assistant'."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_messages (username, role, content) VALUES (?, ?, ?)",
        (username, role, content),
    )
    conn.commit()
    conn.close()


def get_chat_history(username: str, limit: int = 100) -> list[dict]:
    """Returns messages oldest -> newest, capped at `limit` most recent."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """SELECT role, content, created_at FROM chat_messages
           WHERE username = ?
           ORDER BY id DESC
           LIMIT ?""",
        (username, limit),
    )
    rows = c.fetchall()
    conn.close()
    # rows came back newest -> oldest because of ORDER BY id DESC; flip for display
    return [
        {"role": r[0], "content": r[1], "created_at": r[2]}
        for r in reversed(rows)
    ]


def clear_chat_history(username: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_messages WHERE username = ?", (username,))
    conn.commit()
    conn.close()