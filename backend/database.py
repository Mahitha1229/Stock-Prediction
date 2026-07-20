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