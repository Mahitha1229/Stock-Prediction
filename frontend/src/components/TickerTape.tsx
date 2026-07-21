import { useEffect, useState } from 'react'
import { openPriceSocket, Quote } from '../api'

export default function TickerTape({
  tickers,
  onSelect,
}: {
  tickers: string[]
  onSelect?: (ticker: string) => void
}) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})

  useEffect(() => {
    const sockets = tickers.map((t) =>
      openPriceSocket(t, (q) => setQuotes((prev) => ({ ...prev, [t]: q })))
    )
    return () => sockets.forEach((s) => s.close())
  }, [tickers.join(',')])

  const items = tickers
    .map((t) => quotes[t])
    .filter((q): q is Quote => Boolean(q))

  const loop = [...items, ...items]

  if (items.length === 0) {
    return <div className="ticker-tape"><div className="ticker-tape__track" style={{ padding: '0 20px', color: 'var(--text-dim)', fontSize: 13 }}>Connecting to live feed…</div></div>
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