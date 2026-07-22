import sqlite3
from datetime import datetime

PRED_DB_PATH = "predictions.db"


def _get_conn():
    conn = sqlite3.connect(PRED_DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        prediction_date TEXT NOT NULL,
        predicted_price REAL NOT NULL,
        currency_symbol TEXT,
        model_type TEXT,
        created_at TEXT NOT NULL
    )""")
    return conn


def save_prediction(ticker: str, prediction_date: str, predicted_price: float,
                     currency_symbol: str, model_type: str):
    """Records a prediction. If the same ticker already got a prediction for
    this same target date today, updates it instead of creating a duplicate
    (covers cases where the cached model re-serves the same call)."""
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    existing = conn.execute(
        "SELECT id FROM predictions WHERE ticker=? AND prediction_date=? AND date(created_at)=?",
        (ticker, prediction_date, today),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE predictions SET predicted_price=?, currency_symbol=?, model_type=? WHERE id=?",
            (predicted_price, currency_symbol, model_type, existing[0]),
        )
    else:
        conn.execute(
            "INSERT INTO predictions (ticker, prediction_date, predicted_price, currency_symbol, model_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, prediction_date, predicted_price, currency_symbol, model_type, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def get_predictions_for_ticker(ticker: str, limit: int = 30) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT prediction_date, predicted_price, currency_symbol, model_type, created_at "
        "FROM predictions WHERE ticker=? ORDER BY prediction_date DESC LIMIT ?",
        (ticker, limit),
    ).fetchall()
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