import { useEffect, useState } from 'react'
import { openPriceSocket, Quote, SocketStatus } from '../api'

export default function TickerTape({
  tickers,
  onSelect,
}: {
  tickers: string[]
  onSelect?: (ticker: string) => void
}) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [statuses, setStatuses] = useState<Record<string, SocketStatus>>({})
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    setStatuses({})
    const sockets = tickers.map((t) =>
      openPriceSocket(
        t,
        (q) => setQuotes((prev) => ({ ...prev, [t]: q })),
        (status) => setStatuses((prev) => ({ ...prev, [t]: status }))
      )
    )
    return () => sockets.forEach((s) => s.close())
  }, [tickers.join(','), retryKey])

  const items = tickers
    .map((t) => quotes[t])
    .filter((q): q is Quote => Boolean(q))

  const loop = [...items, ...items]

  // If nothing has loaded and every socket is stuck reconnecting, the
  // backend is very likely still waking up (Render cold start) or down.
  const statusValues = tickers.map((t) => statuses[t])
  const allReconnecting =
    tickers.length > 0 && statusValues.every((s) => s === 'reconnecting' || s === 'stale')

  if (items.length === 0) {
    return (
      <div className="ticker-tape">
        <div
          className="ticker-tape__track"
          style={{ padding: '0 20px', color: 'var(--text-dim)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 10 }}
        >
          {allReconnecting ? (
            <>
              <span>First load can take a moment to wake the server. Please refresh or retry.</span>
              <button
                onClick={() => setRetryKey((k) => k + 1)}
                style={{
                  fontSize: 12,
                  padding: '2px 10px',
                  borderRadius: 4,
                  border: '1px solid var(--text-dim)',
                  background: 'transparent',
                  color: 'inherit',
                  cursor: 'pointer',
                }}
              >
                Retry
              </button>
            </>
          ) : (
            'Connecting to live feed…'
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="ticker-tape">
      <div className="ticker-tape__track">
        {loop.map((q, i) => (
          <span
            className="ticker-tape__item"
            key={`${q.ticker}-${i}`}
            onClick={() => onSelect?.(q.ticker)}
            style={{ cursor: onSelect ? 'pointer' : 'default' }}
            title={onSelect ? `View ${q.ticker}` : undefined}
          >
            <span className="ticker-tape__symbol">{q.ticker}</span>
            <span className={q.change >= 0 ? 'up' : 'down'}>
              {q.currency_symbol}{q.price.toFixed(2)} {q.change >= 0 ? '▲' : '▼'} {Math.abs(q.change_pct).toFixed(2)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}