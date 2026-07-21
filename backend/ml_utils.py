import os
import time
import pickle
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import pandas as pd

import yfinance as yf
import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler

MODEL_PATH = "stock_models.pkl"
MODEL_CACHE_DIR = "model_cache"
ON_DEMAND_TIME_STEP = 10
CACHE_MAX_AGE_HOURS = 24

# ---------- Simple TTL cache (replaces st.cache_data) ----------
_history_cache: dict[str, tuple[float, "pd.DataFrame"]] = {}
HISTORY_CACHE_TTL_SECONDS = 60  # short TTL since prices should feel live

_quote_cache: dict[str, tuple[float, dict]] = {}
QUOTE_CACHE_TTL_SECONDS = 5  # matches websocket poll interval

_validate_cache: dict[str, tuple[float, bool]] = {}
VALIDATE_CACHE_TTL_SECONDS = 3600  # ticker validity rarely changes within an hour

# ---------- Currency / formatting ----------
#
# We detect currency by asking yfinance what currency the ticker ACTUALLY
# trades in (an ISO code like "INR", "JPY", "USD"), rather than guessing
# from the ticker's suffix. This works for any stock on any exchange
# yfinance covers, not just a hand-picked list of exchanges.

CURRENCY_SYMBOLS = {
    "USD": "$", "INR": "₹", "GBP": "£",
    "EUR": "€", "JPY": "¥", "CNY": "¥", "HKD": "HK$",
    "CAD": "C$", "AUD": "A$", "NZD": "NZ$", "BRL": "R$",
    "CHF": "CHF ", "KRW": "₩", "SGD": "S$", "TWD": "NT$",
    "IDR": "Rp", "MXN": "MX$", "ZAR": "R", "SEK": "kr",
    "NOK": "kr", "DKK": "kr", "THB": "฿", "MYR": "RM",
    "PHP": "₱", "VND": "₫", "TRY": "₺", "RUB": "₽",
    "PLN": "zł", "ILS": "₪", "AED": "AED ", "SAR": "SAR ",
    "QAR": "QAR ", "KWD": "KWD ", "EGP": "E£", "PKR": "₨",
    "BDT": "৳", "LKR": "Rs", "CLP": "CLP$", "COP": "COL$",
    "ARS": "AR$", "PEN": "S/", "CZK": "Kč", "HUF": "Ft",
    "RON": "lei", "BGN": "лв", "ISK": "kr", "UAH": "₴",
    "NGN": "₦", "KES": "KSh", "GHS": "GH₵",
}

# Fallback suffix map — only used if the live yfinance currency lookup
# fails (network hiccup, ticker briefly unresolvable, etc.)
CURRENCY_MAP = {
    ".NS": "₹", ".BO": "₹",
    ".L": "£",
    ".T": "¥",
    ".HK": "HK$",
    ".SS": "¥", ".SZ": "¥",
    ".DE": "€", ".PA": "€", ".AS": "€", ".MI": "€", ".BR": "€", ".MC": "€", ".LS": "€",
    ".TO": "C$", ".V": "C$",
    ".AX": "A$",
    ".SA": "R$",
    ".SW": "CHF ",
    ".KS": "₩", ".KQ": "₩",
    ".SI": "S$",
    ".TW": "NT$", ".TWO": "NT$",
    ".JK": "Rp",
    ".NZ": "NZ$",
    ".MX": "MX$",
}

_currency_cache: dict[str, tuple[float, str]] = {}
CURRENCY_CACHE_TTL_SECONDS = 3600  # a ticker's trading currency doesn't change intraday


def _suffix_fallback_symbol(ticker: str) -> str:
    ticker = ticker.upper()
    for suffix, symbol in CURRENCY_MAP.items():
        if ticker.endswith(suffix):
            return symbol
    return "$"


def get_currency_symbol(ticker: str) -> str:
    """Returns the correct currency symbol for ANY ticker by asking yfinance
    what currency it actually trades in, instead of guessing from the
    ticker's suffix. Falls back to a suffix map only if the live lookup
    fails, and falls back to "$" only if both fail."""
    now = time.time()
    if ticker in _currency_cache:
        cached_at, symbol = _currency_cache[ticker]
        if now - cached_at < CURRENCY_CACHE_TTL_SECONDS:
            return symbol

    symbol = None
    try:
        info = yf.Ticker(ticker).fast_info
        currency_code = info.get("currency") if hasattr(info, "get") else getattr(info, "currency", None)
        if currency_code:
            currency_code = currency_code.upper()
            # GBp/GBX = British pence (LSE quirk) — display as pounds
            if currency_code in ("GBP", "GBX", "GBP."):
                symbol = "£"
            else:
                symbol = CURRENCY_SYMBOLS.get(currency_code)
    except Exception:
        symbol = None

    if not symbol:
        symbol = _suffix_fallback_symbol(ticker)

    _currency_cache[ticker] = (now, symbol)
    return symbol


def is_index_ticker(ticker: str) -> bool:
    """Yahoo prefixes indices with '^' (e.g. ^NSEI, ^GSPC). Indices don't
    have meaningful volume data, so training a price-prediction model on
    them isn't meaningful the way it is for a single stock."""
    return ticker.strip().upper().startswith("^")


def validate_ticker(ticker: str) -> bool:
    now = time.time()
    if ticker in _validate_cache:
        cached_at, is_valid = _validate_cache[ticker]
        if now - cached_at < VALIDATE_CACHE_TTL_SECONDS:
            return is_valid
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        is_valid = not hist.empty
    except Exception:
        is_valid = False
    _validate_cache[ticker] = (now, is_valid)
    return is_valid


# ---------- Stock data ----------

def get_stock_history(ticker: str, period: str = "1y", interval: str = "1d"):
    hist = yf.Ticker(ticker).history(period=period, interval=interval)
    if not hist.empty:
        hist = hist.dropna(subset=["Close"])
    return hist


def get_cached_stock_history(ticker: str, period: str = "60d", interval: str = "1d"):
    """TTL-cached history fetch — short cache so live views stay fresh
    without hammering yfinance on every request/websocket tick."""
    key = f"{ticker}|{period}|{interval}"
    now = time.time()
    if key in _history_cache:
        cached_at, df = _history_cache[key]
        if now - cached_at < HISTORY_CACHE_TTL_SECONDS:
            return df
    hist = yf.Ticker(ticker).history(period=period, interval=interval)
    if not hist.empty:
        hist = hist.dropna(subset=["Close"])
    _history_cache[key] = (now, hist)
    return hist


def get_latest_quote(ticker: str) -> dict:
    """Lightweight latest-price fetch, used by the websocket price feed.
    Cached briefly so multiple users watching the same ticker share one Yahoo request."""
    now = time.time()
    if ticker in _quote_cache:
        cached_at, data = _quote_cache[ticker]
        if now - cached_at < QUOTE_CACHE_TTL_SECONDS:
            return data

    hist = yf.Ticker(ticker).history(period="2d", interval="1m")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
    if hist.empty:
        return {}
    last = hist.iloc[-1]
    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last["Close"]
    change = float(last["Close"] - prev_close)
    change_pct = (change / prev_close) * 100 if prev_close else 0.0
    result = {
        "ticker": ticker,
        "price": round(float(last["Close"]), 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(last["Volume"]) if not np.isnan(last["Volume"]) else 0,
        "timestamp": datetime.now().isoformat(),
    }
    _quote_cache[ticker] = (now, result)
    return result


def get_technical_indicators(stock_data):
    df = stock_data.copy()

    # RSI
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(50)

    # Stochastic Oscillator
    low14 = df["Low"].rolling(window=14).min()
    high14 = df["High"].rolling(window=14).max()
    df["Stochastic"] = 100 * (df["Close"] - low14) / (high14 - low14)
    df["Stochastic"] = df["Stochastic"].fillna(50)

    # Rate of Change
    df["ROC"] = df["Close"].pct_change(periods=12) * 100
    df["ROC"] = df["ROC"].fillna(0)

    # ADX (Average Directional Index)
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df["ADX"] = dx.rolling(window=14).mean()
    df["ADX"] = df["ADX"].fillna(0)

    return df


# ---------- Pretrained models (curated tickers) ----------

_models_cache = None


def load_models() -> dict:
    global _models_cache
    if _models_cache is not None:
        return _models_cache
    try:
        with open(MODEL_PATH, "rb") as f:
            _models_cache = pickle.load(f)
    except FileNotFoundError:
        _models_cache = {}
    except Exception:
        _models_cache = {}
    return _models_cache


def resolve_ticker(query: str) -> list[dict]:
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {
            "q": query,
            "quotesCount": 20,
            "newsCount": 0,
            "enableFuzzyQuery": True,
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()

        query_lower = query.strip().lower()

        # Exchanges considered "primary" real listings — OTC/pink-sheet
        # duplicates and foreign depositary receipts (F suffix on Frankfurt,
        # SAO DRs, PNK, etc.) get ranked below these when names tie.
        PRIMARY_EXCHANGES = {
            "NMS", "NYQ", "NGM", "NCM",  # US: Nasdaq / NYSE
            "NSI", "BSE",                 # India
            "JPX", "TYO",                 # Japan
            "LSE",                        # London
            "GER",                         # Xetra (Germany's primary exchange)
            "HKG",                        # Hong Kong
            "SHH", "SHZ",                  # China
            "KSC", "KOE",                  # Korea
            "ASX",                         # Australia
            "TOR",                         # Canada
            "PAR", "AMS", "MIL", "MCE",   # major EU exchanges
        }
        LOW_QUALITY_EXCHANGES = {"PNK", "OTC", "CCC"}  # pink sheets, crypto-pair noise, etc.

        matches = []
        for r in data.get("quotes", []):
            symbol = r.get("symbol")
            if not symbol:
                continue
            name = r.get("shortname") or r.get("longname") or symbol
            quote_type = r.get("quoteType", "")
            exchange = r.get("exchange", "")
            name_lower = name.lower()

            score = 0
            if name_lower == query_lower:
                score += 100
            elif name_lower.startswith(query_lower):
                score += 50
            elif query_lower in name_lower:
                score += 20
            elif symbol.lstrip("^").lower().startswith(query_lower):
                score += 15

            if quote_type == "EQUITY":
                score += 30

            if exchange in PRIMARY_EXCHANGES:
                score += 25
            elif exchange in LOW_QUALITY_EXCHANGES:
                score -= 15

            # Frankfurt/other secondary-listing suffixes (.F) on symbols
            # that already look like they're a foreign depositary receipt
            # of something with a cleaner home listing — slight penalty
            if symbol.upper().endswith(".F") or symbol.upper().endswith(".SA"):
                score -= 10

            matches.append({
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
                "type": quote_type,
                "_score": score,
            })

        filtered = [m for m in matches if m["_score"] > 0]
        matches = filtered if filtered else matches

        matches.sort(key=lambda m: m["_score"], reverse=True)
        for m in matches:
            m.pop("_score", None)
        return matches[:8]
    except Exception:
        return []


def get_stock_news(ticker: str, limit: int = 6) -> list[dict]:
    try:
        raw_items = yf.Ticker(ticker).news or []
        articles = []
        for item in raw_items[:limit]:
            content = item.get("content", item)
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


# ---------- On-demand models ----------

def _cache_path(ticker: str) -> str:
    safe = ticker.upper().replace("/", "_").replace("^", "IDX_").replace(".", "_")
    return os.path.join(MODEL_CACHE_DIR, f"{safe}.pkl")

def get_cached_on_demand_model(ticker: str):
    """Check disk cache only — never trains. Used by the async predict endpoint
    to decide whether a request can be answered instantly or needs a background job."""
    path = _cache_path(ticker)
    if os.path.exists(path):
        age_hours = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass
    return None

def train_on_demand_model(ticker: str):
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    hist = get_stock_history(ticker, period="2y")
    if hist.empty or len(hist) < ON_DEMAND_TIME_STEP + 30:
        return None

    data = get_technical_indicators(hist)
    features = ["Close", "RSI", "Stochastic", "ROC", "ADX"]
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data[features])

    X, y = [], []
    for i in range(ON_DEMAND_TIME_STEP, len(scaled) - 1):
        X.append(scaled[i - ON_DEMAND_TIME_STEP:i].flatten())
        y.append(scaled[i + 1, 0])
    X, y = np.array(X), np.array(y)

    if len(X) < 30:
        return None

    xgb_model = xgb.XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05)
    xgb_model.fit(X, y)

    rf_model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    rf_model.fit(X, y)

    model_dict = {
        "scaler": scaler,
        "time_step": ON_DEMAND_TIME_STEP,
        "xgb": xgb_model,
        "rf": rf_model,
        "trained_at": datetime.now().isoformat(),
        "on_demand": True,
    }
    with open(_cache_path(ticker), "wb") as f:
        pickle.dump(model_dict, f)
    return model_dict


def get_or_train_model(ticker: str, pretrained_models: dict):
    if ticker in pretrained_models:
        return pretrained_models[ticker]
 
    cached = get_cached_on_demand_model(ticker)
    if cached:
        return cached
 
    return train_on_demand_model(ticker)


def predict_next_day(ticker: str, model_dict: dict):
    hist = get_cached_stock_history(ticker, period="60d")
    if hist.empty:
        return None, "No data available for this stock"

    data = get_technical_indicators(hist)
    features = ["Close", "RSI", "Stochastic", "ROC", "ADX"]
    scaler = model_dict["scaler"]
    time_step = model_dict["time_step"]

    if len(data) < time_step:
        return None, "Not enough recent data for this stock"

    data_scaled = scaler.transform(data[features].tail(time_step))
    X_flat = data_scaled.reshape(1, -1)

    preds = []
    if "lstm" in model_dict:
        X_lstm = data_scaled.reshape(1, time_step, len(features))
        preds.append(float(model_dict["lstm"].predict(X_lstm, verbose=0)[0][0]))
    if "xgb" in model_dict:
        preds.append(float(model_dict["xgb"].predict(X_flat)[0]))
    if "rf" in model_dict:
        preds.append(float(model_dict["rf"].predict(X_flat)[0]))

    if not preds:
        return None, "No valid model components available"

    ensemble_pred = sum(preds) / len(preds)
    pred_scaled = np.zeros((1, len(features)))
    pred_scaled[0, 0] = ensemble_pred
    predicted_price = scaler.inverse_transform(pred_scaled)[0, 0]
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return predicted_price, tomorrow

# === Add this to ml_utils.py ===

TRENDING_TICKERS = {
    "US": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META"],
    "India": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
    "Europe": ["SAP.DE", "ASML.AS", "MC.PA", "NESN.SW"],
    "Asia-Pacific": ["7203.T", "0700.HK", "005930.KS", "BHP.AX"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
}


def get_trending_tickers() -> dict:
    return TRENDING_TICKERS