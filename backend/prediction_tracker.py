import sqlite3
from datetime import datetime
import sqlite3
import pandas as pd
from datetime import datetime

PRED_DB_PATH = "predictions.db"

# Add to prediction_tracker.py

from datetime import datetime
import ml_utils  # for get_stock_history


def _get_actual_close(ticker: str, target_date: str):
    """Fetch actual close price for a given date. Returns None if the
    market hasn't reached that date yet, or if it was a non-trading day
    with no nearby data."""
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
        if target > datetime.now().date():
            return None  # prediction target is still in the future

        # Pull a small window around the target date so weekends/holidays
        # don't cause a miss — yfinance history index is trading days only.
        hist = ml_utils.get_stock_history(ticker, period="6mo")
        if hist.empty:
            return None

        hist = hist.copy()
        hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
        target_ts = pd.Timestamp(target)

        # Exact match first, else nearest trading day on/after target
        if target_ts in hist.index:
            return float(hist.loc[target_ts, "Close"])
        later = hist[hist.index >= target_ts]
        if not later.empty:
            return float(later.iloc[0]["Close"])
        return None
    except Exception:
        return None


def get_predictions_with_accuracy(ticker: str, limit: int = 30) -> list[dict]:
    """Same as get_predictions_for_ticker, but enriches each row with the
    actual price (once available) and the prediction error."""
    raw = get_predictions_for_ticker(ticker, limit=limit)
    enriched = []
    for row in raw:
        actual = _get_actual_close(ticker, row["prediction_date"])
        error_pct = None
        status = "pending"
        if actual is not None:
            status = "resolved"
            error_pct = round(((row["predicted_price"] - actual) / actual) * 100, 2)
        enriched.append({
            **row,
            "actual_price": actual,
            "error_pct": error_pct,
            "status": status,
        })
    return enriched

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