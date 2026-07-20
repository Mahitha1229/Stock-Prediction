import sqlite3
import bcrypt
import requests
import pickle
import os
from datetime import datetime, timedelta
from streamlit_searchbox import st_searchbox

import streamlit as st
import yfinance as yf
import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler

DB_PATH = "users.db"
MODEL_PATH = "stock_models.pkl"
MODEL_CACHE_DIR = "model_cache"
ON_DEMAND_TIME_STEP = 10
CACHE_MAX_AGE_HOURS = 24

# ---------- Auth / DB ----------

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

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def register_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                   (username, hash_password(password)))
        conn.commit()
        st.success("Account created! Please log in.")
    except sqlite3.IntegrityError:
        st.error("Username already exists. Try another.")
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return bool(user and verify_password(password, user[0]))

def add_to_watchlist(username, stock):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO watchlist (username, stock) VALUES (?, ?)", (username, stock))
    conn.commit()
    conn.close()

def remove_from_watchlist(username, stock):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE username = ? AND stock = ?", (username, stock))
    conn.commit()
    conn.close()

def get_watchlist(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT stock FROM watchlist WHERE username = ?", (username,))
    stocks = [row[0] for row in c.fetchall()]
    conn.close()
    return stocks

def require_login():
    """Call this at the very top of every page, right after st.set_page_config."""
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if st.session_state["user"] is None:
        st.warning("Please log in from the main page first.")
        st.stop()

def login_page():
    st.sidebar.header("Login / Sign Up")
    option = st.sidebar.radio("Select Option", ["Login", "Register"])
    username = st.sidebar.text_input("Username:")
    password = st.sidebar.text_input("Password:", type="password")
    if option == "Register":
        if st.sidebar.button("Create Account"):
            register_user(username, password)
    else:
        if st.sidebar.button("Login"):
            if login_user(username, password):
                st.session_state["user"] = username
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials.")

# ---------- Currency / formatting ----------

CURRENCY_MAP = {
    ".NS": "₹", ".BO": "₹",                            # India
    ".L": "£",                                          # London
    ".T": "¥",                                          # Tokyo
    ".HK": "HK$",                                       # Hong Kong
    ".SS": "¥", ".SZ": "¥",                             # Shanghai / Shenzhen
    ".DE": "€", ".PA": "€", ".AS": "€", ".MI": "€",     # Europe
    ".TO": "C$", ".V": "C$",                            # Canada
    ".AX": "A$",                                        # Australia
    ".SA": "R$",                                        # Brazil
}

def get_currency_symbol(ticker):
    ticker = ticker.upper()
    for suffix, symbol in CURRENCY_MAP.items():
        if ticker.endswith(suffix):
            return symbol
    return "$"  # default: US equities, crypto, and unlisted-suffix tickers

def validate_ticker(ticker):
    """Check whether a ticker returns real data before using it elsewhere."""
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        return not hist.empty
    except Exception:
        return False

# ---------- Stock data ----------

def get_stock_history(ticker, period="1y", interval="1d"):
    """
    Fetch price history and drop trailing incomplete/NaN rows.
    yfinance sometimes appends a row for the current session before
    Close settles (mid-session, holidays, etc.) — this filters that out.
    """
    hist = yf.Ticker(ticker).history(period=period, interval=interval)
    if not hist.empty:
        hist = hist.dropna(subset=['Close'])
    return hist

@st.cache_data(show_spinner=False)
def get_cached_stock_history(ticker, period="60d", interval="1d"):
    hist = yf.Ticker(ticker).history(period=period, interval=interval)
    if not hist.empty:
        hist = hist.dropna(subset=['Close'])
    return hist

def get_technical_indicators(stock_data):
    df = stock_data.copy()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['Stochastic'] = ((df['Close'] - df['Low'].rolling(14).min()) /
                         (df['High'].rolling(14).max() - df['Low'].rolling(14).min())) * 100
    df['ROC'] = df['Close'].pct_change(periods=10) * 100
    df['ADX'] = abs(df['High'] - df['Low']).rolling(14).mean()
    df.fillna(0, inplace=True)
    return df

# ---------- Pretrained models (curated Indian stocks) ----------

@st.cache_resource
def load_models():
    try:
        with open(MODEL_PATH, "rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        st.error("Model file not found. Please train models first.")
        return {}
    except Exception as e:
        st.error(f"Error loading models: {e}")
        return {}
    
def resolve_ticker(query):
    """
    Resolve a company/index/crypto name to Yahoo Finance ticker symbol(s).
    Uses Yahoo's public search endpoint directly — no API key required.
    """
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 5, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        matches = []
        for r in data.get("quotes", []):
            symbol = r.get("symbol")
            if not symbol:
                continue
            matches.append({
                "symbol": symbol,
                "name": r.get("shortname") or r.get("longname") or symbol,
                "exchange": r.get("exchange"),
                "type": r.get("quoteType"),
            })
        return matches
    except Exception:
        return []

# ---------- Stock-specific news (free, no API key needed) ----------

def get_stock_news(ticker, limit=6):
    """
    Fetch recent news for a ticker directly from Yahoo Finance via yfinance.
    Handles both the old and new yfinance news response schemas.
    """
    try:
        raw_items = yf.Ticker(ticker).news or []
        articles = []
        for item in raw_items[:limit]:
            content = item.get("content", item)  # newer yfinance nests under "content"
            if isinstance(content, dict) and "title" in content:
                title = content.get("title")
                url = (
                    (content.get("canonicalUrl") or {}).get("url")
                    or (content.get("clickThroughUrl") or {}).get("url")
                )
                publisher = (content.get("provider") or {}).get("displayName")
            else:
                title = item.get("title")
                url = item.get("link")
                publisher = item.get("publisher")
            if title:
                articles.append({"title": title, "publisher": publisher, "url": url})
        return articles
    except Exception:
        return []

# ---------- Reusable stock search/picker widget ----------

from streamlit_searchbox import st_searchbox

def _search_tickers(query):
    if not query:
        return []
    matches = resolve_ticker(query)
    return [
        (f"{m['symbol']} — {m['name']} ({m.get('exchange') or m.get('type') or ''})", m['symbol'])
        for m in matches
    ]

def render_ticker_picker(input_key, curated_tickers=None, default_ticker="AAPL"):
    if curated_tickers:
        st.caption("Popular:")
        cols = st.columns(len(curated_tickers))
        for i, t in enumerate(curated_tickers):
            if cols[i].button(t, key=f"{input_key}_quick_{t}"):
                st.session_state[f"{input_key}_selected"] = t

    selected = st_searchbox(
        _search_tickers,
        key=f"{input_key}_searchbox",
        placeholder="Search any stock, index, or crypto worldwide...",
        default=st.session_state.get(f"{input_key}_selected", default_ticker),
    )
    if selected:
        st.session_state[f"{input_key}_selected"] = selected

    manual = st.text_input(
        "Or type exact ticker directly:",
        value=st.session_state.get(f"{input_key}_selected", default_ticker),
        key=f"{input_key}_manual",
    ).strip().upper()

    return manual

# ---------- On-demand models (any global ticker) ----------

def _cache_path(ticker):
    safe = ticker.upper().replace("/", "_").replace("^", "IDX_").replace(".", "_")
    return os.path.join(MODEL_CACHE_DIR, f"{safe}.pkl")

def train_on_demand_model(ticker):
    """
    Trains a lightweight XGBoost + Random Forest ensemble for a ticker
    that has no pretrained model, using its own 2-year history.
    Skips LSTM (too slow to train synchronously in a web request).
    """
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    hist = get_stock_history(ticker, period="2y")
    if hist.empty or len(hist) < ON_DEMAND_TIME_STEP + 30:
        return None

    data = get_technical_indicators(hist)
    features = ['Close', 'RSI', 'Stochastic', 'ROC', 'ADX']
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data[features])

    X, y = [], []
    for i in range(ON_DEMAND_TIME_STEP, len(scaled) - 1):
        X.append(scaled[i - ON_DEMAND_TIME_STEP:i].flatten())
        y.append(scaled[i + 1, 0])  # next day's scaled Close
    X, y = np.array(X), np.array(y)

    if len(X) < 30:
        return None

    xgb_model = xgb.XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05)
    xgb_model.fit(X, y)

    rf_model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    rf_model.fit(X, y)

    model_dict = {
        'scaler': scaler,
        'time_step': ON_DEMAND_TIME_STEP,
        'xgb': xgb_model,
        'rf': rf_model,
        'trained_at': datetime.now().isoformat(),
        'on_demand': True,
    }
    with open(_cache_path(ticker), 'wb') as f:
        pickle.dump(model_dict, f)
    return model_dict

def get_or_train_model(ticker, pretrained_models):
    """
    Returns a model for any ticker: pretrained if curated, cached if
    previously trained on-demand, or freshly trained (and cached) otherwise.
    """
    if ticker in pretrained_models:
        return pretrained_models[ticker]

    path = _cache_path(ticker)
    if os.path.exists(path):
        age_hours = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            try:
                with open(path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                pass  # fall through and retrain if cache is corrupted

    return train_on_demand_model(ticker)

def predict_next_day(ticker, model_dict):
    hist = get_cached_stock_history(ticker, period="60d")
    if hist.empty:
        return None, "No data available for this stock"

    data = get_technical_indicators(hist)
    features = ['Close', 'RSI', 'Stochastic', 'ROC', 'ADX']
    scaler = model_dict['scaler']
    time_step = model_dict['time_step']

    if len(data) < time_step:
        return None, "Not enough recent data for this stock"

    data_scaled = scaler.transform(data[features].tail(time_step))
    X_flat = data_scaled.reshape(1, -1)

    preds = []
    if 'lstm' in model_dict:
        X_lstm = data_scaled.reshape(1, time_step, len(features))
        preds.append(float(model_dict['lstm'].predict(X_lstm, verbose=0)[0][0]))
    if 'xgb' in model_dict:
        preds.append(float(model_dict['xgb'].predict(X_flat)[0]))
    if 'rf' in model_dict:
        preds.append(float(model_dict['rf'].predict(X_flat)[0]))

    if not preds:
        return None, "No valid model components available"

    ensemble_pred = sum(preds) / len(preds)
    pred_scaled = np.zeros((1, len(features)))
    pred_scaled[0, 0] = ensemble_pred
    predicted_price = scaler.inverse_transform(pred_scaled)[0, 0]
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    return predicted_price, tomorrow