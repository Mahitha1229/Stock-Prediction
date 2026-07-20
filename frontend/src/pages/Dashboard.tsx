import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  Candle, Quote, Prediction,
  fetchHistory, fetchPredictionWithPolling, openPriceSocket, fetchTrendingTickers,
} from '../api'
import CandlestickChart from '../components/CandlestickChart'
import TickerTape from '../components/TickerTape'
import Watchlist from '../components/Watchlist'
import Chat from '../components/Chat'

export default function Dashboard() {
  const { username, logout } = useAuth()
  const [ticker, setTicker] = useState('AAPL')
  const [inputValue, setInputValue] = useState('AAPL')
  const [candles, setCandles] = useState<Candle[]>([])
  const [liveQuote, setLiveQuote] = useState<Quote | null>(null)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tapeTickers, setTapeTickers] = useState<string[]>(['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL'])

  // Pull a global mix (a couple per region) for the scrolling ticker tape,
  // instead of a hardcoded US-only list.
  useEffect(() => {
    fetchTrendingTickers()
      .then((trending) => {
        const mix = Object.values(trending).flatMap((tickers) => tickers.slice(0, 2))
        if (mix.length > 0) setTapeTickers(mix)
      })
      .catch(() => {
        // keep the fallback US list if trending fetch fails
      })
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      setPrediction(null)
      try {
        const hist = await fetchHistory(ticker)
        if (cancelled) return
        setCandles(hist.candles)

        ws = openPriceSocket(ticker, (q) => { if (!cancelled) setLiveQuote(q) })

        await fetchPredictionWithPolling(
          ticker,
          (pred) => { if (!cancelled) setPrediction(pred) },
          () => cancelled,
        )
      } catch (err: any) {
        if (!cancelled) setError(err?.response?.data?.detail || 'Could not load this ticker')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()

    return () => {
      cancelled = true
      ws?.close()
    }
  }, [ticker])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (inputValue.trim()) setTicker(inputValue.trim().toUpperCase())
  }

  return (
    <div className="app-shell">
      <TickerTape tickers={tapeTickers} />

      <div className="topbar">
        <div className="brand"><span className="brand__mark" />Quantis</div>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flex: 1, maxWidth: 360, margin: '0 24px' }}>
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search ticker (e.g. AAPL, RELIANCE.NS)"
          />
          <button className="ghost" type="submit">Go</button>
        </form>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{username}</span>
          <button className="ghost" onClick={logout}>Log out</button>
        </div>
      </div>

      <div className="main-grid">
        <div className="panel">
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div>
                <div className="label">{ticker}</div>
                {liveQuote ? (
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                    <span className="price-lg">{liveQuote.currency_symbol}{liveQuote.price.toFixed(2)}</span>
                    <span className={`mono ${liveQuote.change >= 0 ? 'up' : 'down'}`}>
                      {liveQuote.change >= 0 ? '+' : ''}{liveQuote.change.toFixed(2)} ({liveQuote.change_pct.toFixed(2)}%)
                    </span>
                  </div>
                ) : (
                  <div className="price-lg" style={{ color: 'var(--text-dim)' }}>—</div>
                )}
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="live-dot" /> LIVE
              </span>
            </div>

            <div style={{ marginTop: 16 }}>
              {loading && <div style={{ color: 'var(--text-dim)' }}>Loading chart…</div>}
              {error && <div className="error-text">{error}</div>}
              {!loading && !error && candles.length > 0 && <CandlestickChart candles={candles} />}
            </div>
          </div>

          {prediction && (
            <div className="card">
              <div className="label">Prediction for {prediction.prediction_date}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 6 }}>
                <span className="price-lg">{prediction.currency_symbol}{prediction.predicted_price?.toFixed(2) ?? '—'}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
                {prediction.on_demand ? '⚡ On-demand model (XGBoost + Random Forest ensemble)' : '🎯 Curated model (LSTM + XGBoost + Random Forest ensemble)'}
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <Watchlist onSelect={(t) => { setTicker(t); setInputValue(t) }} />
          <div style={{ marginTop: 16 }}>
            <Chat />
          </div>
        </div>
      </div>
    </div>
  )
}