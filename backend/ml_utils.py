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

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")

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

def _fetch_history_twelvedata(ticker: str, period: str = "1y", interval: str = "1d") -> "pd.DataFrame":
    """Secondary history source. Twelve Data's free tier is scoped mainly
    to US markets/forex/crypto — most non-US equities may return nothing
    here unless the account is on a paid plan."""
    if not TWELVE_DATA_API_KEY:
        return pd.DataFrame()
    interval_map = {"1d": "1day", "1wk": "1week", "1mo": "1month"}
    td_interval = interval_map.get(interval, "1day")
    period_days_map = {"5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
    outputsize = min(period_days_map.get(period, 365), 5000)
    try:
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={"symbol": ticker, "interval": td_interval, "outputsize": outputsize, "apikey": TWELVE_DATA_API_KEY},
            timeout=8,
        )
        data = resp.json()
        if data.get("status") == "error" or "values" not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


def _fetch_quote_finnhub(ticker: str) -> dict:
    """Secondary live-quote source. Finnhub's free tier gives real-time US
    quotes; international symbols are end-of-day only even on paid plans
    for many exchanges, and historical candles are blocked on the free key."""
    if not FINNHUB_API_KEY:
        return {}
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": FINNHUB_API_KEY},
            timeout=6,
        )
        data = resp.json()
        if not data or not data.get("c"):
            return {}
        return {
            "price": data["c"],
            "prev_close": data.get("pc"),
            "change": data.get("d"),
            "change_pct": data.get("dp"),
        }
    except Exception:
        return {}

def _fetch_fundamentals_finnhub(ticker: str) -> dict:
    """Secondary fundamentals source when yfinance is rate-limited.
    Finnhub's free tier covers company profile + basic financials for
    most major exchanges; international coverage is more limited than US."""
    if not FINNHUB_API_KEY:
        return {}
    try:
        profile_resp = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": ticker, "token": FINNHUB_API_KEY},
            timeout=8,
        )
        profile = profile_resp.json()
        if not profile or not profile.get("name"):
            return {}

        metrics_resp = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": FINNHUB_API_KEY},
            timeout=8,
        )
        metrics = metrics_resp.json().get("metric", {})

        raw_market_cap = profile.get("marketCapitalization")
        raw_dividend_yield = metrics.get("dividendYieldIndicatedAnnual")

        return {
            "ticker": ticker.upper(),
            "name": profile.get("name"),
            "sector": profile.get("finnhubIndustry"),
            "industry": None,  # Finnhub free tier doesn't separate sector/industry
            "market_cap": round(raw_market_cap * 1_000_000) if raw_market_cap else None,
            "pe_ratio": metrics.get("peExclExtraTTM"),
            "eps": metrics.get("epsExclExtraItemsTTM"),
            "dividend_yield_pct": round(raw_dividend_yield, 2) if raw_dividend_yield else None,
            "week_52_high": metrics.get("52WeekHigh"),
            "week_52_low": metrics.get("52WeekLow"),
        }
    except Exception as e:
        print(f"Finnhub fundamentals fetch failed for {ticker}: {e}")
        return {}


def get_stock_history(ticker: str, period: str = "1y", interval: str = "1d"):
    hist = yf.Ticker(ticker).history(period=period, interval=interval)
    if not hist.empty:
        return hist.dropna(subset=["Close"])
    # yfinance had nothing — try Twelve Data as a secondary source
    return _fetch_history_twelvedata(ticker, period=period, interval=interval)


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
    now = time.time()
    if ticker in _quote_cache:
        cached_at, data = _quote_cache[ticker]
        if now - cached_at < QUOTE_CACHE_TTL_SECONDS:
            return data

    hist = yf.Ticker(ticker).history(period="2d", interval="1m")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")

    if not hist.empty:
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
            "source": "yfinance",
        }
        _quote_cache[ticker] = (now, result)
        return result

    # yfinance had nothing — try Finnhub as a secondary source
    fh = _fetch_quote_finnhub(ticker)
    if fh:
        result = {
            "ticker": ticker,
            "price": round(float(fh["price"]), 2),
            "change": round(float(fh["change"] or 0), 2),
            "change_pct": round(float(fh["change_pct"] or 0), 2),
            "volume": 0,
            "timestamp": datetime.now().isoformat(),
            "source": "finnhub",
        }
        _quote_cache[ticker] = (now, result)
        return result

    return {}


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

from collections import OrderedDict

CURATED_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "ITC.NS", "SBIN.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
]

MODEL_RELEASE_BASE_URL = "https://github.com/Mahitha1229/Stock-Prediction/releases/download/v3.0-models-no-lstm"
MAX_LOADED_CURATED_MODELS = 4

_curated_model_cache: "OrderedDict[str, dict]" = OrderedDict()


def _safe_ticker_name(ticker: str) -> str:
    return ticker.upper().replace("/", "_").replace("^", "IDX_").replace(".", "_")


def _curated_cache_path(ticker: str) -> str:
    safe = _safe_ticker_name(ticker)
    return os.path.join(MODEL_CACHE_DIR, f"curated_v3_{safe}.pkl")


def _download_curated_model(ticker: str) -> bool:
    path = _curated_cache_path(ticker)
    if os.path.exists(path):
        return True
    safe = _safe_ticker_name(ticker)
    url = f"{MODEL_RELEASE_BASE_URL}/{safe}.pkl"
    try:
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
        print(f"Downloading model for {ticker}...")
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded model for {ticker}.")
        return True
    except Exception as e:
        print(f"Failed to download model for {ticker}: {e}")
        return False


def get_curated_model(ticker: str):
    if ticker not in CURATED_TICKERS:
        return None

    if ticker in _curated_model_cache:
        _curated_model_cache.move_to_end(ticker)
        return _curated_model_cache[ticker]

    if not _download_curated_model(ticker):
        return None

    try:
        with open(_curated_cache_path(ticker), "rb") as f:
            model_dict = pickle.load(f)
    except Exception as e:
        print(f"Failed to load model for {ticker}: {e}")
        return None

    _curated_model_cache[ticker] = model_dict
    if len(_curated_model_cache) > MAX_LOADED_CURATED_MODELS:
        _curated_model_cache.popitem(last=False)

    return model_dict


def load_models() -> dict:
    return {ticker: None for ticker in CURATED_TICKERS}


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


def get_fundamentals(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        if info and info.get("shortName"):
            return {
                "ticker": ticker.upper(),
                "name": info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "dividend_yield_pct": round(info["dividendYield"], 2) if info.get("dividendYield") else None,
                "week_52_high": info.get("fiftyTwoWeekHigh"),
                "week_52_low": info.get("fiftyTwoWeekLow"),
            }
    except Exception as e:
        print(f"Fundamentals fetch failed for {ticker}: {e}")

    # yfinance failed or was rate-limited — try Finnhub as a secondary source
    return _fetch_fundamentals_finnhub(ticker)


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
        return None, "No data available for this stock", None

    data = get_technical_indicators(hist)
    features = ["Close", "RSI", "Stochastic", "ROC", "ADX"]
    scaler = model_dict["scaler"]
    time_step = model_dict["time_step"]

    if len(data) < time_step:
        return None, "Not enough recent data for this stock", None

    data_scaled = scaler.transform(data[features].tail(time_step))
    X_flat = data_scaled.reshape(1, -1)

    def _inverse(scaled_val: float) -> float:
        row = np.zeros((1, len(features)))
        row[0, 0] = scaled_val
        return float(scaler.inverse_transform(row)[0, 0])

    scaled_preds = []
    rf_tree_scaled_preds = None

    if "lstm" in model_dict:
        X_lstm = data_scaled.reshape(1, time_step, len(features))
        scaled_preds.append(float(model_dict["lstm"].predict(X_lstm, verbose=0)[0][0]))
    if "xgb" in model_dict:
        scaled_preds.append(float(model_dict["xgb"].predict(X_flat)[0]))
    if "rf" in model_dict:
        rf_model = model_dict["rf"]
        scaled_preds.append(float(rf_model.predict(X_flat)[0]))
        # Every tree's individual vote — free uncertainty signal from an
        # ensemble we already trained, no extra cost.
        rf_tree_scaled_preds = np.array([
            tree.predict(X_flat)[0] for tree in rf_model.estimators_
        ])

    if not scaled_preds:
        return None, "No valid model components available", None

    # Point estimate: average each model's prediction in price-space
    # (converting first, then averaging, avoids compounding scaler error)
    individual_price_preds = [_inverse(v) for v in scaled_preds]
    predicted_price = float(np.mean(individual_price_preds))

    # --- Confidence range ---
    uncertainty_sources = []

    if len(individual_price_preds) > 1:
        uncertainty_sources.append(np.std(individual_price_preds))  # model disagreement

    if rf_tree_scaled_preds is not None:
        rf_tree_prices = [_inverse(v) for v in rf_tree_scaled_preds]
        uncertainty_sources.append(np.std(rf_tree_prices))  # RF internal spread

    recent_returns = data["Close"].pct_change().dropna().tail(30)
    volatility_floor = (
        float(recent_returns.std()) * predicted_price if len(recent_returns) > 5 else 0.0
    )

    model_uncertainty = max(uncertainty_sources) if uncertainty_sources else 0.0
    combined_std = max(model_uncertainty, volatility_floor)

    Z_95 = 1.96
    confidence = {
        "lower": round(predicted_price - Z_95 * combined_std, 2),
        "upper": round(predicted_price + Z_95 * combined_std, 2),
        "level": 0.95,
    }

    def _next_trading_day(d: datetime) -> datetime:
        nxt = d + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt

    target_date = _next_trading_day(datetime.now()).strftime("%Y-%m-%d")
    return predicted_price, target_date, confidence


def predict_with_breakdown(ticker: str, model_dict: dict):
    """Like predict_next_day, but returns each individual model's prediction
    separately so the frontend's Model Comparison view can show
    XGBoost vs Random Forest vs LSTM side by side, instead of just the
    ensemble average. This is what /stock/{ticker}/model-comparison calls."""
    hist = get_cached_stock_history(ticker, period="60d")
    if hist.empty:
        return None

    data = get_technical_indicators(hist)
    features = ["Close", "RSI", "Stochastic", "ROC", "ADX"]
    scaler = model_dict["scaler"]
    time_step = model_dict["time_step"]

    if len(data) < time_step:
        return None

    data_scaled = scaler.transform(data[features].tail(time_step))
    X_flat = data_scaled.reshape(1, -1)

    def _inverse(scaled_val: float) -> float:
        row = np.zeros((1, len(features)))
        row[0, 0] = scaled_val
        return float(scaler.inverse_transform(row)[0, 0])

    breakdown = {}

    if "lstm" in model_dict:
        X_lstm = data_scaled.reshape(1, time_step, len(features))
        scaled_pred = float(model_dict["lstm"].predict(X_lstm, verbose=0)[0][0])
        breakdown["lstm"] = round(_inverse(scaled_pred), 2)

    if "xgb" in model_dict:
        scaled_pred = float(model_dict["xgb"].predict(X_flat)[0])
        breakdown["xgb"] = round(_inverse(scaled_pred), 2)

    if "rf" in model_dict:
        scaled_pred = float(model_dict["rf"].predict(X_flat)[0])
        breakdown["rf"] = round(_inverse(scaled_pred), 2)

    if not breakdown:
        return None

    ensemble_avg = round(sum(breakdown.values()) / len(breakdown), 2)

    def _next_trading_day(d: datetime) -> datetime:
        nxt = d + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt

    target_date = _next_trading_day(datetime.now()).strftime("%Y-%m-%d")

    return {
        "ticker": ticker,
        "target_date": target_date,
        "model_predictions": breakdown,
        "ensemble_prediction": ensemble_avg,
    }


# ---------- Trending tickers ----------

TRENDING_TICKERS = {
    "US": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META"],
    "India": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
    "Europe": ["SAP.DE", "ASML.AS", "MC.PA", "NESN.SW"],
    "Asia-Pacific": ["7203.T", "0700.HK", "005930.KS", "BHP.AX"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
}


def get_trending_tickers() -> dict:
    return TRENDING_TICKERS