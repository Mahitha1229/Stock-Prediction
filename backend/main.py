import asyncio
from typing import Optional
import chat_utils as chat
import threading
import prediction_tracker as pt

import asyncio
from typing import Optional
import chat_utils as chat
import threading
import prediction_tracker as pt
import pandas as pd          # ← add this line
from fastapi.responses import JSONResponse

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

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
    """Runs in a background thread. Trains (if needed) and predicts,
    then stashes the result so the polling endpoint can pick it up."""
    try:
        model_dict = ml.get_or_train_model(ticker, all_models)
        if not model_dict:
            with _prediction_jobs_lock:
                _prediction_jobs[ticker] = {
                    "status": "error",
                    "detail": "Not enough historical data to train a model for this stock",
                }
            return
 
        predicted_price, prediction_date = ml.predict_next_day(ticker, model_dict)
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


@app.get("/watchlist")
def get_watchlist(user: str = Depends(get_current_user)):
    return {"watchlist": db.get_watchlist(user)}


@app.post("/watchlist")
def add_watchlist(req: WatchlistRequest, user: str = Depends(get_current_user)):
    db.add_to_watchlist(user, req.ticker.upper())
    return {"message": f"{req.ticker.upper()} added to watchlist"}


@app.delete("/watchlist/{ticker}")
def remove_watchlist(ticker: str, user: str = Depends(get_current_user)):
    db.remove_from_watchlist(user, ticker.upper())
    return {"message": f"{ticker.upper()} removed from watchlist"}


@app.get("/search")
def search_ticker(q: str):
    return {"results": ml.resolve_ticker(q)}


@app.get("/curated-tickers")
def curated_tickers():
    return {"tickers": list(all_models.keys())}


@app.get("/stock/{ticker}/validate")
def validate(ticker: str):
    return {"valid": ml.validate_ticker(ticker.upper())}


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


@app.get("/stock/{ticker}/predict")
def predict(ticker: str):
    ticker = ticker.upper()
    
 
    # Fast path 1: pretrained curated model already in memory
    if ticker in all_models:
        model_dict = all_models[ticker]
        predicted_price, prediction_date = ml.predict_next_day(ticker, model_dict)
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
            "status": "done",
        }

    cached = ml.get_cached_on_demand_model(ticker)
    if cached:
        predicted_price, prediction_date = ml.predict_next_day(ticker, cached)
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


@app.get("/stock/{ticker}/news")
def news(ticker: str, limit: int = 6):
    return {"articles": ml.get_stock_news(ticker.upper(), limit=limit)}

@app.post("/chat")
def chat_endpoint(req: ChatRequest, user: str = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    reply = chat.run_chat(req.message, history)
    return {"reply": reply}


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
@app.get("/trending-tickers")
def trending_tickers():
    """Global default suggestions grouped by region, for dashboard/search defaults.
    Distinct from /curated-tickers, which lists only the pretrained high-accuracy models."""
    return {"trending": ml.get_trending_tickers()}

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
            if not match.empty:
                actual_price = round(float(match["Close"].iloc[0]), 2)

        error_pct = None
        direction_correct = None
        if actual_price is not None:
            error_pct = round(((r["predicted_price"] - actual_price) / actual_price) * 100, 2)

        results.append({
            **r,
            "actual_price": actual_price,
            "error_pct": error_pct,
            "status": "resolved" if actual_price is not None else "pending",
        })

    return {"ticker": ticker, "history": results}