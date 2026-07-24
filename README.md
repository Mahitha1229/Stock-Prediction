# StockSense — AI-Powered Stock Market Predictor

A full-stack stock prediction platform combining an ensemble machine learning pipeline with real-time market data, a conversational finance assistant, and prediction accuracy tracking. Built with FastAPI (Python) and React + TypeScript.

**Live demo:** https://stock-prediction-swart.vercel.app

---

## Features

- **Ensemble ML predictions** — next-day price forecasts using XGBoost + Random Forest (with an LSTM component for locally-run/higher-memory deployments), with 95% confidence intervals derived from model disagreement and recent volatility
- **Live price feeds** — WebSocket-based streaming quotes, polling underlying data sources every 5 seconds
- **Global ticker support** — works with any exchange covered by Yahoo Finance (US, India, Europe, Asia-Pacific, crypto), with automatic currency detection
- **Prediction accuracy tracking** — logs every prediction and resolves it against actual closing prices, surfacing mean absolute error and directional accuracy over time
- **Model comparison view** — see each individual model's prediction side-by-side with the ensemble average
- **Backtesting** — compares a model-driven trading strategy against simple buy-and-hold using historical predictions
- **Watchlist** — authenticated, per-user, persisted across sessions
- **AI finance assistant** — Groq-powered chat for natural-language questions about stocks, indices, and crypto
- **Candlestick charts** — interactive price history with prediction overlays and confidence bands
- **Resilient data layer** — automatic fallback across multiple providers (yfinance → Twelve Data → Finnhub → NewsAPI) so rate limits on one source don't break the app

---

## Tech Stack

**Backend**
- FastAPI (Python 3.11)
- PostgreSQL (hosted on Neon) for users, watchlists, and prediction history
- XGBoost, scikit-learn, TensorFlow/Keras for modeling
- yfinance, Twelve Data, Finnhub, NewsAPI for market data and news
- Groq API for the chat assistant
- JWT-based authentication
- Docker for containerized deployment

**Frontend**
- React + TypeScript (Vite)
- React Router for client-side routing
- Axios for API communication
- WebSockets for live price streaming
- Custom CSS design system (dark theme, token-based)

**Infrastructure**
- Backend: Render (Docker web service)
- Frontend: Vercel
- Database: Neon (serverless Postgres)
- Model storage: GitHub Releases (large model files served outside git)

---

## Architecture Notes

A few deliberate engineering decisions worth calling out:

- **Lazy model loading with LRU eviction** — curated tickers' models are downloaded and cached on first request rather than all loaded into memory at startup, keeping the app within free-tier memory limits (512MB) while still supporting 15+ pretrained tickers.
- **Multi-provider fallback chain** — every external data call (quotes, history, fundamentals, news) tries a primary source first and falls back to a secondary provider if the primary is rate-limited or unavailable, since Yahoo Finance is known to rate-limit requests from cloud/data-center IP ranges.
- **On-demand training** — tickers outside the curated list are trained on first request (XGBoost + Random Forest) and cached to disk, so the app supports effectively any ticker without pre-training everything upfront.

---

## Getting Started (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- A PostgreSQL database (local or hosted, e.g. Neon)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with:

```
DATABASE_URL=postgresql://user:password@host/dbname
GROQ_API_KEY=your_key
NEWSAPI_API_KEY=your_key
FINNHUB_API_KEY=your_key
TWELVE_DATA_API_KEY=your_key
JWT_SECRET=your_secret
```

Run the server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend Setup

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/` with:

```
VITE_API_BASE_URL=http://localhost:8000
```

Run the dev server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Deployment

- **Backend** is containerized with the included `Dockerfile` and deployed to Render as a Docker web service. Environment variables (API keys, `DATABASE_URL`, `FRONTEND_URL`, `MODEL_URL`) are set directly in Render's dashboard.
- **Frontend** is deployed to Vercel with `VITE_API_BASE_URL` pointing at the live backend URL.
- **Curated model files** are hosted as GitHub Release assets (rather than committed to git, due to size) and downloaded lazily by the backend on first request per ticker.

---

## API Overview

| Endpoint | Description |
|---|---|
| `POST /auth/register`, `POST /auth/login` | User authentication |
| `GET /stock/{ticker}/predict` | Next-day price prediction with confidence interval |
| `GET /stock/{ticker}/model-comparison` | Individual model predictions vs. ensemble |
| `GET /stock/{ticker}/prediction-history` | Historical predictions with resolved accuracy |
| `GET /stock/{ticker}/backtest` | Strategy backtest vs. buy-and-hold |
| `GET /stock/{ticker}/history`, `/quote`, `/news`, `/fundamentals` | Market data |
| `GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{ticker}` | Watchlist management |
| `POST /chat` | AI finance assistant |
| `WS /ws/prices/{ticker}` | Live price stream |
