import os
import json
import random
import re
import streamlit as st
import yfinance as yf
import requests
from dotenv import load_dotenv
from groq import Groq

from utils import (
    require_login, get_currency_symbol, get_stock_history,
    load_models, get_or_train_model, predict_next_day,
    resolve_ticker, get_stock_news
)

load_dotenv()

st.set_page_config(page_title="Global Finance Assistant", page_icon="💸", layout="wide")
require_login()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")
MODEL_NAME = "openai/gpt-oss-120b"

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
_pretrained_models = load_models()

finance_jokes = [
    "Why did the banker break up with the calculator? He felt like he was just another number.",
    "I'm friends with all my bank accounts. They know I'm checking on them daily!",
    "Why did the stock market go to therapy? Too many issues with resistance!",
    "Money talks... but all mine ever says is goodbye!",
    "Why don't investors trust stairs? They're always up to something!"
]

SAMPLE_QUESTIONS = {
    "Stock Prices (any market)": [
        "What is the price of AAPL?",
        "Price of RELIANCE.NS",
        "How much is 7203.T trading at?",
        "Current price of BTC-USD"
    ],
    "Predictions": [
        "What will TSLA be worth tomorrow?",
        "Predict the price of INFY.NS",
        "Give me a prediction for MSFT"
    ],
    "Fundamentals": [
        "PE ratio of TSLA",
        "Market cap of INFY.NS",
        "What is the dividend yield of KO?"
    ],
    "Market Concepts": [
        "What is a bull market?",
        "Explain the difference between P/E and PEG ratio",
        "What is dollar-cost averaging?"
    ],
    "Indices": [
        "Where is the S&P 500 right now?",
        "What is the Nifty 50 doing today?",
        "Current level of the Nasdaq"
    ],
    "Latest Updates": [
        "Latest global finance news",
        "What's happening in the markets today?"
    ]
}

# ---------- Tool implementations ----------

def tool_get_stock_price(ticker: str) -> str:
    try:
        hist = get_stock_history(ticker, period="5d")
        if hist.empty:
            return json.dumps({"error": f"No data found for ticker '{ticker}'. It may be an invalid symbol."})
        last_price = hist['Close'].iloc[-1]
        symbol = get_currency_symbol(ticker)
        change = None
        if len(hist) > 1:
            prev = hist['Close'].iloc[-2]
            change = round(((last_price - prev) / prev) * 100, 2)
        return json.dumps({
            "ticker": ticker.upper(),
            "price": round(float(last_price), 2),
            "currency_symbol": symbol,
            "day_change_pct": change,
            "as_of_date": str(hist.index[-1].date())
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def tool_get_fundamentals(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        result = {
            "ticker": ticker.upper(),
            "name": info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield_pct": round(info["dividendYield"], 2) if info.get("dividendYield") else None,
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})

def tool_get_price_trend(ticker: str, period: str = "1mo") -> str:
    valid_periods = {"5d", "1mo", "3mo", "6mo", "1y", "5y"}
    if period not in valid_periods:
        period = "1mo"
    try:
        hist = get_stock_history(ticker, period=period)
        if hist.empty:
            return json.dumps({"error": f"No data found for ticker '{ticker}'."})
        start = hist['Close'].iloc[0]
        end = hist['Close'].iloc[-1]
        pct_change = round(((end - start) / start) * 100, 2)
        return json.dumps({
            "ticker": ticker.upper(),
            "period": period,
            "start_price": round(float(start), 2),
            "end_price": round(float(end), 2),
            "pct_change": pct_change,
            "high": round(float(hist['Close'].max()), 2),
            "low": round(float(hist['Close'].min()), 2),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

INDEX_TICKERS = {
    "s&p 500": "^GSPC", "sp500": "^GSPC", "nasdaq": "^IXIC", "dow jones": "^DJI",
    "dow": "^DJI", "sensex": "^BSESN", "nifty": "^NSEI", "nifty 50": "^NSEI",
    "ftse": "^FTSE", "ftse 100": "^FTSE", "dax": "^GDAXI", "nikkei": "^N225",
    "hang seng": "^HSI",
}

def tool_get_index_level(index_name: str) -> str:
    key = index_name.lower().strip()
    ticker = INDEX_TICKERS.get(key)
    if not ticker:
        for name, t in INDEX_TICKERS.items():
            if name in key or key in name:
                ticker = t
                break
    if not ticker:
        return json.dumps({"error": f"Unknown index '{index_name}'. Known indices: {list(INDEX_TICKERS.keys())}"})
    try:
        hist = get_stock_history(ticker, period="5d")
        if hist.empty:
            return json.dumps({"error": "No data available."})
        last = hist['Close'].iloc[-1]
        change = None
        if len(hist) > 1:
            prev = hist['Close'].iloc[-2]
            change = round(((last - prev) / prev) * 100, 2)
        return json.dumps({"index": index_name, "level": round(float(last), 2), "day_change_pct": change})
    except Exception as e:
        return json.dumps({"error": str(e)})

def tool_get_financial_news(query: str = "") -> str:
    articles = []

    # 1. If a topic/company was given, resolve it to a real ticker and pull its news
    if query:
        matches = resolve_ticker(query)
        if matches:
            articles = get_stock_news(matches[0]["symbol"])

    # 2. Fall back to NewsAPI for general headlines, if configured
    if not articles and NEWSAPI_API_KEY:
        url = "https://newsapi.org/v2/everything" if query else "https://newsapi.org/v2/top-headlines"
        params = {"apiKey": NEWSAPI_API_KEY, "language": "en", "pageSize": 6}
        if query:
            params["q"] = f"{query} finance stock market"
            params["sortBy"] = "publishedAt"
        else:
            params["category"] = "business"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = [
                {"title": a["title"], "publisher": a.get("source", {}).get("name"), "url": a["url"]}
                for a in data.get("articles", [])
            ]
        except Exception:
            pass

    # 3. Last resort: general market news via a broad index ticker (always free, no key needed)
    if not articles:
        articles = get_stock_news("^GSPC")

    if not articles:
        return json.dumps({"error": "Couldn't retrieve news right now."})
    return json.dumps({"articles": articles})

def tool_resolve_ticker(query: str) -> str:
    """Look up the correct ticker symbol for a company/index/crypto name."""
    matches = resolve_ticker(query)
    if not matches:
        return json.dumps({"error": f"No matches found for '{query}'."})
    return json.dumps({"matches": matches})

def tool_predict_stock_price(ticker: str) -> str:
    """Predicts next-day closing price for any ticker, training an on-demand model if none exists."""
    try:
        hist = get_stock_history(ticker, period="5d")
        if hist.empty:
            return json.dumps({"error": f"No data found for ticker '{ticker}'."})
        last_price = float(hist['Close'].iloc[-1])
        currency_symbol = get_currency_symbol(ticker)

        model_dict = get_or_train_model(ticker.upper(), _pretrained_models)
        if not model_dict:
            return json.dumps({"error": f"Not enough historical data to build a prediction model for '{ticker}'."})

        predicted_price, prediction_date = predict_next_day(ticker.upper(), model_dict)
        if predicted_price is None:
            return json.dumps({"error": prediction_date})

        pct_change = round(((predicted_price - last_price) / last_price) * 100, 2)
        return json.dumps({
            "ticker": ticker.upper(),
            "current_price": round(last_price, 2),
            "predicted_price": round(float(predicted_price), 2),
            "prediction_date": prediction_date,
            "predicted_change_pct": pct_change,
            "currency_symbol": currency_symbol,
            "model_type": "on-demand XGBoost + Random Forest" if model_dict.get("on_demand") else "curated LSTM + XGBoost + Random Forest",
            "disclaimer": "This is a statistical estimate from historical patterns, not financial advice."
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_ticker",
            "description": "Look up the correct Yahoo Finance ticker symbol for a company, index, or crypto name when you're not fully sure of the exact symbol (e.g. 'Nikkei 225', 'Tata Motors', 'Bitcoin', 'Adani'). Call this BEFORE telling the user data is unavailable for an unfamiliar name — never guess or give up without trying this first.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Company, index, or asset name to search for"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current/latest price and day change for any global stock, ETF, or crypto ticker (Yahoo Finance format, e.g. AAPL, RELIANCE.NS, 7203.T, BTC-USD). Always call this for ANY question about a current, latest, or today's price — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Ticker symbol in Yahoo Finance format"}},
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": "Get fundamental data for a stock: PE ratio, market cap, sector, dividend yield, 52-week range, EPS. Always call this — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Ticker symbol in Yahoo Finance format"}},
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_trend",
            "description": "Get price trend/performance of a stock over a period (5d, 1mo, 3mo, 6mo, 1y, 5y).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "period": {"type": "string", "enum": ["5d", "1mo", "3mo", "6mo", "1y", "5y"]}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_index_level",
            "description": "Get the current level of a major global market index (S&P 500, Nasdaq, Dow, Sensex, Nifty, FTSE, DAX, Nikkei, Hang Seng). Always call this — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {"index_name": {"type": "string"}},
                "required": ["index_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_news",
            "description": "Get latest financial/business news headlines, optionally filtered by a topic or company query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Optional topic/company to search news for. Leave empty for general top business headlines."}},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "predict_stock_price",
            "description": "Predict the next trading day's closing price for ANY global stock ticker using the app's ML ensemble models. Call this whenever the user asks for a prediction, forecast, or what a stock 'will be worth'.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Ticker symbol in Yahoo Finance format"}},
                "required": ["ticker"]
            }
        }
    },
]

AVAILABLE_FUNCTIONS = {
    "get_stock_price": tool_get_stock_price,
    "get_fundamentals": tool_get_fundamentals,
    "get_price_trend": tool_get_price_trend,
    "get_index_level": tool_get_index_level,
    "get_financial_news": tool_get_financial_news,
    "predict_stock_price": tool_predict_stock_price,
    "resolve_ticker": tool_resolve_ticker,
}

SYSTEM_PROMPT = """You are a knowledgeable global financial assistant, and also a helpful general-purpose assistant. You help with:
- Stock prices, fundamentals, and trends for ANY market worldwide (US, India, Europe, Asia, crypto)
- Next-day price predictions for any global ticker using the app's ML models
- Explaining financial and market concepts clearly
- Investment planning concepts (general education only, never personalized financial advice)
- Latest financial news
- General questions outside finance — answer these normally using your own knowledge, you are not restricted to finance topics.

CRITICAL RULE: You have NO reliable memorized knowledge of current prices, ratios, index levels, or predictions — that data changes constantly. For ANY question mentioning a price, "today," "current," "latest," a prediction/forecast, or a specific figure (PE ratio, market cap, dividend yield, 52-week high/low), you MUST call the matching tool. Never say data is "unavailable" without first calling the tool — the tool has live data.

Ticker resolution rule: if the user names a company, index, or asset by name rather than exact ticker (e.g. "Nikkei", "Tata Motors", "Adani Green"), and you're not fully certain of the exact Yahoo Finance ticker, call resolve_ticker first to find it, then use that ticker with the other tools. Never respond that something is "unavailable" or "unknown" without trying resolve_ticker first.

Other rules:
- When a user mentions a company name instead of a ticker, infer the most likely ticker (e.g. "Apple" -> AAPL, "Reliance" -> RELIANCE.NS, "Toyota" -> 7203.T, "TCS" -> TCS.NS). If genuinely ambiguous or unfamiliar, call resolve_ticker.
- When giving a prediction, always pass along the tool's disclaimer that it's a statistical estimate, not financial advice.
- Never give direct "buy/sell" recommendations or personalized financial advice. Explain concepts and data, and note that decisions should factor in the user's own research or a licensed advisor.
- Format numbers clearly with the correct currency symbol returned by the tools.
- Be concise but complete.
"""

def is_greeting(text):
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon"]
    return any(text.lower().strip().startswith(g) for g in greetings) and len(text.split()) <= 4

def extract_failed_tool_call(error_str):
    """
    Groq sometimes fails to package a tool call properly but still shows us
    what it intended in 'failed_generation', e.g.:
    '<function=get_stock_price{"ticker": "RELIANCE.NS"}></function>'
    Extract and run that call ourselves instead of giving up.
    """
    match = re.search(r'<function=(\w+)(\{.*?\})>', error_str)
    if not match:
        return None
    fn_name, args_str = match.group(1), match.group(2)
    try:
        fn_args = json.loads(args_str)
    except json.JSONDecodeError:
        return None
    return fn_name, fn_args

def run_chat(user_input, history):
    if not client:
        return "The chatbot isn't configured yet — please add GROQ_API_KEY to your .env file."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in history[-10:]:
        messages.append({"role": "user" if role == "User" else "assistant", "content": content})
    messages.append({"role": "user", "content": user_input})

    try:
        MAX_TOOL_ROUNDS = 5
        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=800,
                )
                response_message = response.choices[0].message
            except Exception as e:
                # Groq failed to package the tool call, but often tells us
                # what it tried to do — extract and run it ourselves.
                recovered = extract_failed_tool_call(str(e))
                if not recovered:
                    raise
                fn_name, fn_args = recovered
                fn = AVAILABLE_FUNCTIONS.get(fn_name)
                result = fn(**fn_args) if fn else json.dumps({"error": "Unknown tool"})
                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "recovered_call_1",
                        "type": "function",
                        "function": {"name": fn_name, "arguments": json.dumps(fn_args)},
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": "recovered_call_1",
                    "name": fn_name,
                    "content": result,
                })
                continue  # loop again, ask the model to now form a normal reply

            if not response_message.tool_calls:
                return response_message.content or "I'm not sure how to respond to that — could you rephrase?"

            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response_message.tool_calls
                ],
            })

            for tool_call in response_message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                fn = AVAILABLE_FUNCTIONS.get(fn_name)
                result = fn(**fn_args) if fn else json.dumps({"error": "Unknown tool"})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": result,
                })

        return "I had trouble getting a complete answer — please try rephrasing your question."

    except Exception as e:
        return f"Sorry, something went wrong: {str(e)}"

def main():
    if not client:
        st.error("GROQ_API_KEY missing or invalid — chatbot will not work until this is set correctly in .env / Render env vars.")

    with st.sidebar:
        st.title("💡 Sample Questions")
        for category, questions in SAMPLE_QUESTIONS.items():
            with st.expander(f"📌 {category}"):
                for question in questions:
                    if st.button(question, key=f"btn_{question}"):
                        st.session_state.pending_input = question

        with st.expander("📊 Market Overview", expanded=True):
            try:
                sp500_hist = get_stock_history("^GSPC", period="5d")
                sensex_hist = get_stock_history("^BSESN", period="5d")
                col1, col2 = st.columns(2)
                col1.metric("S&P 500", f"{sp500_hist['Close'].iloc[-1]:,.2f}")
                col2.metric("Sensex", f"{sensex_hist['Close'].iloc[-1]:,.2f}")
            except Exception as e:
                st.error(f"Could not load market data: {e}")

        st.markdown("---")
        st.markdown("Powered by Groq (Llama 3.3 70B) + yfinance")

    st.title("Global Finance Assistant")
    st.markdown("Ask about stocks, indices, predictions, or crypto from any market worldwide")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "pending_input" in st.session_state:
        user_input = st.session_state.pending_input
        del st.session_state.pending_input
    else:
        user_input = None

    typed_input = st.chat_input("Ask me anything about global finance...")
    if typed_input:
        user_input = typed_input

    if user_input:
        if is_greeting(user_input):
            answer = f"👋 Hey! Here's a finance joke while you think of your question:\n\n_{random.choice(finance_jokes)}_"
        else:
            with st.spinner("Thinking..."):
                answer = run_chat(user_input, st.session_state.chat_history)

        st.session_state.chat_history.append(("User", user_input))
        st.session_state.chat_history.append(("Bot", answer))

    for role, msg in st.session_state.chat_history:
        with st.chat_message(role.lower()):
            st.markdown(msg)

if __name__ == "__main__":
    main()