import os
import psycopg2
from psycopg2 import errors
from auth import hash_password, verify_password

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def create_db():
    conn = get_connection()
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
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hash_password(password)),
        )
        conn.commit()
        return True, "Account created successfully."
    except errors.UniqueViolation:
        conn.rollback()
        return False, "Username already exists."
    finally:
        conn.close()


def login_user(username: str, password: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = %s", (username,))
    user = c.fetchone()
    conn.close()
    return bool(user and verify_password(password, user[0]))


def add_to_watchlist(username: str, stock: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO watchlist (username, stock) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (username, stock),
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(username: str, stock: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE username = %s AND stock = %s", (username, stock))
    conn.commit()
    conn.close()


def get_watchlist(username: str) -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT stock FROM watchlist WHERE username = %s", (username,))
    stocks = [row[0] for row in c.fetchall()]
    conn.close()
    return stocks