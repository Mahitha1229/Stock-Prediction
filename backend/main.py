import asyncio
import threading
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

import chat_utils as chat
import prediction_tracker as pt
import database as db
import ml_utils as ml
from auth import create_access_token, get_current_user

app = FastAPI(title="AI/ML Finance Market Predictor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.create_db()
all_models = ml.load_models()
_prediction_jobs: dict[str, dict] = {}
_prediction_jobs_lock = threading.Lock()


def _train_and_store_prediction(ticker: str):
    try:
        model_dict = ml.get_or_train_model(ticker, all_models)
        if not model_dict:
            with _prediction_jobs_lock:
                _prediction_jobs[ticker] = {
                    "status": "error",
                    "detail": "Not enough historical data to train a model for this stock",
                }
            return

        predicted_price, prediction_date, confidence = ml.predict_next_day(ticker, model_dict)
        if predicted_price is None:
            with _prediction_jobs_lock:
                _prediction_jobs[ticker] = {"status": "error", "detail": prediction_date}
            return

        result = {
            "ticker": ticker,
            "predicted_price": round(float(predicted_price), 2),
            "prediction_date": prediction_date,
            "on_demand": bool(model_dict.get("on_demand")),
            "currency_symbol": ml.get_currency_symbol(ticker),
            "confidence_low": confidence["lower"] if confidence else None,
            "confidence_high": confidence["upper"] if confidence else None,
        }
        pt.save_prediction(
            ticker, prediction_date, result["predicted_price"],
            result["currency_symbol"],
            "on-demand" if result["on_demand"] else "curated",
        )
        with _prediction_jobs_lock:
            _prediction_jobs[ticker] = {"status": "done", "data": result}
    except Exception as e:
        with _prediction_jobs_lock:
            _prediction_jobs[ticker] = {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WatchlistRequest(BaseModel):
    ticker: str


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class BacktestResult(BaseModel):
    ticker: str
    starting_capital: float
    strategy_final_value: float
    buy_hold_final_value: float
    strategy_return_pct: float
    buy_hold_return_pct: float
    equity_curve: list[dict]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/register")
def register(req: RegisterRequest):
    success, message = db.register_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not db.login_user(form_data.username, form_data.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(form_data.username)
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

@app.get("/watchlist")
def get_watchlist(user: str = Depends(get_current_user)):
    return {"watchlist": db.get_watchlist(user)}


@app.post("/watchlist")
def add_watchlist(req: WatchlistRequest, user: str = Depends(get_current_user)):
    ticker = req.ticker.upper()
    if not ml.validate_ticker(ticker):
        raise HTTPException(status_code=404, detail=f'"{req.ticker}" is not a recognized ticker')
    db.add_to_watchlist(user, ticker)
    return {"message": f"{ticker} added to watchlist"}


@app.delete("/watchlist/{ticker}")
def remove_watchlist(ticker: str, user: str = Depends(get_current_user)):
    db.remove_from_watchlist(user, ticker.upper())
    return {"message": f"{ticker.upper()} removed from watchlist"}


# ---------------------------------------------------------------------------
# Search / tickers
# ---------------------------------------------------------------------------

@app.get("/search")
def search_ticker(q: str):
    return {"results": ml.resolve_ticker(q)}


@app.get("/curated-tickers")
def curated_tickers():
    return {"tickers": list(all_models.keys())}


@app.get("/trending-tickers")
def trending_tickers():
    """Global default suggestions grouped by region, for dashboard/search defaults.
    Distinct from /curated-tickers, which lists only the pretrained high-accuracy models."""
    return {"trending": ml.get_trending_tickers()}


@app.get("/stock/{ticker}/validate")
def validate(ticker: str):
    return {"valid": ml.validate_ticker(ticker.upper())}


# ---------------------------------------------------------------------------
# Stock data
# ---------------------------------------------------------------------------

@app.get("/stock/{ticker}/history")
def history(ticker: str, period: str = "1y", interval: str = "1d"):
    ticker = ticker.upper()
    hist = ml.get_stock_history(ticker, period=period, interval=interval)
    if hist.empty:
        raise HTTPException(status_code=404, detail="No historical data found for this ticker")
    candles = [
        {
            "date": idx.strftime("%Y-%m-%d %H:%M"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        for idx, row in hist.iterrows()
    ]
    return {"ticker": ticker, "candles": candles, "currency_symbol": ml.get_currency_symbol(ticker)}


@app.get("/stock/{ticker}/quote")
def quote(ticker: str):
    ticker = ticker.upper()
    q = ml.get_latest_quote(ticker)
    if not q:
        raise HTTPException(status_code=404, detail="No quote data found for this ticker")
    q["currency_symbol"] = ml.get_currency_symbol(ticker)
    return q


@app.get("/stock/{ticker}/news")
def news(ticker: str, limit: int = 6):
    return {"articles": ml.get_stock_news(ticker.upper(), limit=limit)}


@app.get("/stock/{ticker}/fundamentals")
def fundamentals(ticker: str):
    data = ml.get_fundamentals(ticker.upper())
    if not data:
        raise HTTPException(status_code=404, detail="No fundamentals data found for this ticker")
    return data


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@app.get("/stock/{ticker}/predict")
def predict(ticker: str):
    ticker = ticker.upper()

    if ticker in ml.CURATED_TICKERS:
        model_dict = ml.get_curated_model(ticker)
        if model_dict is None:
            raise HTTPException(status_code=503, detail="Could not load model for this ticker right now, please try again")
        predicted_price, prediction_date, confidence = ml.predict_next_day(ticker, model_dict)
        if predicted_price is None:
            raise HTTPException(status_code=422, detail=prediction_date)
        currency_symbol = ml.get_currency_symbol(ticker)
        pt.save_prediction(ticker, prediction_date, round(float(predicted_price), 2), currency_symbol, "curated")
        return {
            "ticker": ticker,
            "predicted_price": round(float(predicted_price), 2),
            "prediction_date": prediction_date,
            "on_demand": False,
            "currency_symbol": currency_symbol,
            "confidence_low": confidence["lower"] if confidence else None,
            "confidence_high": confidence["upper"] if confidence else None,
            "status": "done",
        }

    cached = ml.get_cached_on_demand_model(ticker)
    if cached:
        predicted_price, prediction_date, confidence = ml.predict_next_day(ticker, cached)
        if predicted_price is None:
            raise HTTPException(status_code=422, detail=prediction_date)
        currency_symbol = ml.get_currency_symbol(ticker)
        pt.save_prediction(ticker, prediction_date, round(float(predicted_price), 2), currency_symbol, "on-demand")
        return {
            "ticker": ticker,
            "predicted_price": round(float(predicted_price), 2),
            "prediction_date": prediction_date,
            "on_demand": True,
            "currency_symbol": currency_symbol,
            "confidence_low": confidence["lower"] if confidence else None,
            "confidence_high": confidence["upper"] if confidence else None,
            "status": "done",
        }

    # New ticker with no cached/pretrained model — validate before training
    if not ml.validate_ticker(ticker):
        raise HTTPException(status_code=404, detail="Invalid ticker")

    # Slow path: no model yet -> train in the background, respond immediately
    with _prediction_jobs_lock:
        job = _prediction_jobs.get(ticker)
        if job is None or job["status"] == "error":
            _prediction_jobs[ticker] = {"status": "training"}
            threading.Thread(target=_train_and_store_prediction, args=(ticker,), daemon=True).start()
            job = _prediction_jobs[ticker]

    if job["status"] == "training":
        return JSONResponse(status_code=202, content={"ticker": ticker, "status": "training"})

    if job["status"] == "error":
        raise HTTPException(status_code=422, detail=job["detail"])

    result = dict(job["data"])
    result["status"] = "done"
    return result


@app.get("/stock/{ticker}/prediction-history")
def prediction_history(ticker: str):
    ticker = ticker.upper()
    records = pt.get_predictions_for_ticker(ticker)
    hist = ml.get_stock_history(ticker, period="6mo")

    results = []
    for r in records:
        pred_date = r["prediction_date"]
        actual_price = None
        if not hist.empty:
            match = hist[hist.index.strftime("%Y-%m-%d") == pred_date]
            if match.empty:
                pred_ts = pd.Timestamp(pred_date)
                idx_naive = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                later = hist[idx_naive >= pred_ts]
                if not later.empty:
                    match = later.iloc[[0]]
            if not match.empty:
                actual_price = round(float(match["Close"].iloc[0]), 2)

        error_pct = None
        if actual_price is not None:
            error_pct = round(((r["predicted_price"] - actual_price) / actual_price) * 100, 2)

        results.append({
            **r,
            "actual_price": actual_price,
            "error_pct": error_pct,
            "status": "resolved" if actual_price is not None else "pending",
        })

    resolved = [r for r in results if r["status"] == "resolved"]
    summary = None
    if resolved:
        errors_abs_pct = [abs(r["error_pct"]) for r in resolved if r["error_pct"] is not None]
        mae_pct = round(sum(errors_abs_pct) / len(errors_abs_pct), 2) if errors_abs_pct else None

        directional_correct = 0
        directional_total = 0
        sorted_hist = hist.sort_index() if not hist.empty else hist
        for r in resolved:
            try:
                target_ts = pd.Timestamp(r["prediction_date"])
                prior = (
                    sorted_hist[sorted_hist.index.tz_localize(None) < target_ts]
                    if sorted_hist.index.tz is not None
                    else sorted_hist[sorted_hist.index < target_ts]
                )
                if prior.empty:
                    continue
                prior_close = float(prior["Close"].iloc[-1])
                predicted_up = r["predicted_price"] > prior_close
                actual_up = r["actual_price"] > prior_close
                if predicted_up == actual_up:
                    directional_correct += 1
                directional_total += 1
            except Exception:
                continue

        directional_accuracy_pct = (
            round((directional_correct / directional_total) * 100, 1) if directional_total > 0 else None
        )

        summary = {
            "resolved_count": len(resolved),
            "mean_abs_error_pct": mae_pct,
            "directional_accuracy_pct": directional_accuracy_pct,
            "directional_sample_size": directional_total,
        }

    return {"ticker": ticker, "history": results, "summary": summary}


@app.get("/stock/{ticker}/model-comparison")
def model_comparison(ticker: str):
    ticker = ticker.upper()
    model_dict = ml.get_curated_model(ticker) or ml.get_cached_on_demand_model(ticker)
    if not model_dict:
        raise HTTPException(status_code=404, detail="No trained model available yet for this ticker — view the Predict tab first")

    result = ml.predict_with_breakdown(ticker, model_dict)
    if not result:
        raise HTTPException(status_code=422, detail="Could not compute model breakdown for this ticker")

    return {
        "ticker": result["ticker"],
        "target_date": result["target_date"],
        "models": result["model_predictions"],
        "ensemble_price": result["ensemble_prediction"],
        "currency_symbol": ml.get_currency_symbol(ticker),
        "on_demand": bool(model_dict.get("on_demand")),
    }


# ---------------------------------------------------------------------------
# Backtesting — compares a model-driven strategy against buy-and-hold
# ---------------------------------------------------------------------------

@app.get("/stock/{ticker}/backtest", response_model=BacktestResult)
def backtest(ticker: str, starting_capital: float = 10000.0):
    ticker = ticker.upper()
    records = pt.get_predictions_for_ticker(ticker)
    if not records:
        raise HTTPException(
            status_code=404,
            detail="No prediction history yet for this ticker — predictions accumulate over time as you use the app",
        )

    hist = ml.get_stock_history(ticker, period="1y")
    if hist.empty:
        raise HTTPException(status_code=404, detail="No historical price data found for this ticker")

    hist = hist.sort_index()
    hist_naive_index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index

    sorted_records = sorted(records, key=lambda r: r["prediction_date"])

    strategy_value = starting_capital
    buy_hold_units = None
    equity_curve = []
    resolved_any = False

    for r in sorted_records:
        target_ts = pd.Timestamp(r["prediction_date"])
        prior = hist[hist_naive_index < target_ts]
        after = hist[hist_naive_index >= target_ts]
        if prior.empty or after.empty:
            continue

        prior_close = float(prior["Close"].iloc[-1])
        actual_close = float(after["Close"].iloc[0])
        predicted_up = r["predicted_price"] > prior_close

        if buy_hold_units is None:
            buy_hold_units = starting_capital / prior_close

        day_return = (actual_close - prior_close) / prior_close
        if predicted_up:
            strategy_value *= (1 + day_return)

        resolved_any = True
        equity_curve.append({
            "date": r["prediction_date"],
            "strategy_value": round(strategy_value, 2),
            "buy_hold_value": round(buy_hold_units * actual_close, 2),
            "predicted_up": predicted_up,
        })

    if not resolved_any:
        raise HTTPException(status_code=422, detail="Predictions exist but none are resolved against historical prices yet")

    buy_hold_final = equity_curve[-1]["buy_hold_value"]

    return BacktestResult(
        ticker=ticker,
        starting_capital=starting_capital,
        strategy_final_value=round(strategy_value, 2),
        buy_hold_final_value=round(buy_hold_final, 2),
        strategy_return_pct=round(((strategy_value - starting_capital) / starting_capital) * 100, 2),
        buy_hold_return_pct=round(((buy_hold_final - starting_capital) / starting_capital) * 100, 2),
        equity_curve=equity_curve,
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/chat")
def chat_endpoint(req: ChatRequest, user: str = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    reply = chat.run_chat(req.message, history)
    return {"reply": reply}


# ---------------------------------------------------------------------------
# Live prices (WebSocket)
# ---------------------------------------------------------------------------

@app.websocket("/ws/prices/{ticker}")
async def ws_prices(websocket: WebSocket, ticker: str):
    """
    Streams a live-ish quote for `ticker` every 5 seconds.
    yfinance isn't push-based, so this polls server-side and pushes
    to the client — frontend just opens one connection.
    """
    await websocket.accept()
    ticker = ticker.upper()
    try:
        while True:
            quote_data = await asyncio.to_thread(ml.get_latest_quote, ticker)
            if quote_data:
                quote_data["currency_symbol"] = ml.get_currency_symbol(ticker)
                await websocket.send_json(quote_data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass