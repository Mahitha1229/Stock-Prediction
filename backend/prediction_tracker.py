import os
import psycopg2
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        prediction_date TEXT NOT NULL,
        predicted_price REAL NOT NULL,
        currency_symbol TEXT,
        model_type TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def save_prediction(ticker: str, prediction_date: str, predicted_price: float,
                     currency_symbol: str, model_type: str):
    """Records a prediction. If the same ticker already got a prediction for
    this same target date today, updates it instead of creating a duplicate
    (covers cases where the cached model re-serves the same call)."""
    conn = _get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute(
        "SELECT id FROM predictions WHERE ticker=%s AND prediction_date=%s AND created_at::date=%s",
        (ticker, prediction_date, today),
    )
    existing = c.fetchone()
    if existing:
        c.execute(
            "UPDATE predictions SET predicted_price=%s, currency_symbol=%s, model_type=%s WHERE id=%s",
            (predicted_price, currency_symbol, model_type, existing[0]),
        )
    else:
        c.execute(
            "INSERT INTO predictions (ticker, prediction_date, predicted_price, currency_symbol, model_type, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (ticker, prediction_date, predicted_price, currency_symbol, model_type, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def get_predictions_for_ticker(ticker: str, limit: int = 30) -> list[dict]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT prediction_date, predicted_price, currency_symbol, model_type, created_at "
        "FROM predictions WHERE ticker=%s ORDER BY prediction_date DESC LIMIT %s",
        (ticker, limit),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {
            "prediction_date": r[0],
            "predicted_price": r[1],
            "currency_symbol": r[2],
            "model_type": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]