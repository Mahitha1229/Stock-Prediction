import { useEffect, useState } from 'react'
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, fetchTrendingTickers } from '../api'

export default function Watchlist({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [items, setItems] = useState<string[]>([])
  const [newTicker, setNewTicker] = useState('')
  const [trending, setTrending] = useState<Record<string, string[]>>({})

  async function refresh() {
    setItems(await fetchWatchlist())
  }

  useEffect(() => {
    refresh()
    fetchTrendingTickers().then(setTrending).catch(() => setTrending({}))
  }, [])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!newTicker.trim()) return
    await addToWatchlist(newTicker.trim().toUpperCase())
    setNewTicker('')
    refresh()
  }

  async function handleQuickAdd(ticker: string) {
    await addToWatchlist(ticker)
    refresh()
  }

  async function handleRemove(ticker: string) {
    await removeFromWatchlist(ticker)
    refresh()
  }

  return (
    <div className="card">
      <div className="label" style={{ marginBottom: 12 }}>Watchlist</div>
      <form onSubmit={handleAdd} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          placeholder="Add ticker (any global symbol)…"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value)}
        />
        <button className="ghost" type="submit">Add</button>
      </form>

      {items.length === 0 && (
        <div style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>No tickers yet.</div>
      )}
      {items.map((t) => (
        <div className="watchlist-row" key={t}>
          <span className="mono" style={{ cursor: 'pointer' }} onClick={() => onSelect(t)}>{t}</span>
          <button className="ghost" onClick={() => handleRemove(t)}>Remove</button>
        </div>
      ))}

      {Object.keys(trending).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div className="label" style={{ marginBottom: 8, fontSize: 12 }}>Suggested — quick add</div>
          {Object.entries(trending).map(([region, tickers]) => (
            <div key={region} style={{ marginBottom: 10 }}>
              <div style={{ color: 'var(--text-dim)', fontSize: 11, marginBottom: 4 }}>{region}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {tickers
                  .filter((t) => !items.includes(t))
                  .map((t) => (
                    <button
                      key={t}
                      className="ghost mono"
                      style={{ fontSize: 12, padding: '2px 8px' }}
                      onClick={() => handleQuickAdd(t)}
                      title={`Add ${t} to watchlist`}
                    >
                      + {t}
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}