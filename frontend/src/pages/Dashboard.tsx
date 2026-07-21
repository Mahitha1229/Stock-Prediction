import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  Candle, Quote, Prediction,
  fetchHistory, fetchPredictionWithPolling, openPriceSocket, fetchTrendingTickers, searchTickers,
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

  // Search dropdown state
  const [searchResults, setSearchResults] = useState<{ symbol: string; name: string; exchange?: string }[]>([])
  const [showResults, setShowResults] = useState(false)
  const [searching, setSearching] = useState(false)

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

  function selectTicker(symbol: string) {
    setTicker(symbol)
    setInputValue(symbol)
    setShowResults(false)
    setSearchResults([])
  }

  // Live search-as-you-type, debounced so we don't hit /search on every keystroke.
  useEffect(() => {
    const query = inputValue.trim()

    // Don't re-search right after picking a result (inputValue === selected symbol)
    if (!query || query.length < 2) {
      setSearchResults([])
      setShowResults(false)
      return
    }

    let cancelled = false
    setSearching(true)

    const timer = setTimeout(async () => {
      try {
        const results = await searchTickers(query)
        if (cancelled) return
        setSearchResults(results)
        setShowResults(results.length > 0)
      } catch {
        if (!cancelled) {
          setSearchResults([])
          setShowResults(false)
        }
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [inputValue])

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const query = inputValue.trim()
    if (!query) return

    // If the dropdown already has results showing, Enter/Go picks the top match.
    if (searchResults.length > 0) {
      selectTicker(searchResults[0].symbol)
      return
    }

    setSearching(true)
    try {
      const results = await searchTickers(query)
      if (results.length > 0) {
        selectTicker(results[0].symbol)
        return
      }
    } catch {
      // search failed — fall through to direct ticker attempt
    } finally {
      setSearching(false)
    }

    // fallback: treat input as a literal ticker (covers exact symbols like AAPL, RELIANCE.NS)
    selectTicker(query.toUpperCase())
  }

  return (
    <div className="app-shell">
      <TickerTape tickers={tapeTickers} />

      <div className="topbar">
        <div className="brand"><span className="brand__mark" />Quantis</div>

        <div style={{ position: 'relative', flex: 1, maxWidth: 360, margin: '0 24px' }}>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={() => { if (searchResults.length > 0) setShowResults(true) }}
              placeholder="Search ticker (e.g. AAPL, RELIANCE.NS)"
              style={{ flex: 1 }}
              autoComplete="off"
            />
            <button className="ghost" type="submit" disabled={searching}>
              {searching ? '…' : 'Go'}
            </button>
          </form>

          {showResults && searchResults.length > 0 && (
            <>
              {/* click-away overlay */}
              <div
                onClick={() => setShowResults(false)}
                style={{ position: 'fixed', inset: 0, zIndex: 10 }}
              />
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: 4,
                  background: 'var(--bg-panel, #12141a)',
                  border: '1px solid var(--border, #22262F)',
                  borderRadius: 8,
                  overflow: 'hidden',
                  zIndex: 20,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                }}
              >
                {searching && (
                  <div style={{ padding: '8px 12px', color: 'var(--text-dim)', fontSize: 12 }}>
                    Searching…
                  </div>
                )}
                {searchResults.map((r) => (
                  <button
                    key={r.symbol}
                    type="button"
                    onClick={() => selectTicker(r.symbol)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      width: '100%',
                      padding: '8px 12px',
                      background: 'none',
                      border: 'none',
                      borderBottom: '1px solid var(--border, #22262F)',
                      color: 'var(--text-primary, #e6e6e6)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 13,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <strong>{r.symbol}</strong>
                      <span style={{ color: 'var(--text-dim)', marginLeft: 8 }}>{r.name}</span>
                    </span>
                    {r.exchange && (
                      <span style={{ color: 'var(--text-secondary)', marginLeft: 8, flexShrink: 0, fontSize: 11 }}>
                        {r.exchange}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

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
          <Watchlist onSelect={(t) => selectTicker(t)} />
          <div style={{ marginTop: 16 }}>
            <Chat />
          </div>
        </div>
      </div>
    </div>
  )
}