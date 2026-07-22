import { useEffect, useState } from 'react'
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, fetchTrendingTickers, searchTickers, validateTicker } from '../api'

interface SearchResult { symbol: string; name: string; exchange?: string }

export default function Watchlist({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [items, setItems] = useState<string[]>([])
  const [newTicker, setNewTicker] = useState('')
  const [trending, setTrending] = useState<Record<string, string[]>>({})

  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [searching, setSearching] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  async function refresh() {
    setItems(await fetchWatchlist())
  }

  useEffect(() => {
    refresh()
    fetchTrendingTickers().then(setTrending).catch(() => setTrending({}))
  }, [])

  // Debounced live search, same pattern as the main ticker search bar.
  useEffect(() => {
    const query = newTicker.trim()
    if (!query) {
      setSearchResults([])
      setShowResults(false)
      setSearching(false)
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
  }, [newTicker])

  async function addResolvedTicker(ticker: string) {
    setAddError(null)
    try {
      await addToWatchlist(ticker)
      setNewTicker('')
      setSearchResults([])
      setShowResults(false)
      await refresh()
    } catch {
      setAddError(`Could not add ${ticker}`)
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    const query = newTicker.trim()
    if (!query) return
    setAddError(null)

    // If a dropdown match is showing, use the top match — never save raw typed text.
    if (searchResults.length > 0) {
      await addResolvedTicker(searchResults[0].symbol)
      return
    }

    // No dropdown matches yet (e.g. user typed an exact symbol and hit
    // Enter fast) — validate before saving instead of trusting raw input.
    const candidate = query.toUpperCase()
    setSearching(true)
    try {
      const isValid = await validateTicker(candidate)
      if (isValid) {
        await addResolvedTicker(candidate)
      } else {
        setAddError(`"${query}" isn't a recognized ticker — try picking from the dropdown`)
      }
    } catch {
      setAddError('Could not verify this ticker right now')
    } finally {
      setSearching(false)
    }
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

      <div style={{ position: 'relative', marginBottom: 12 }}>
        <form onSubmit={handleAdd} style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            placeholder="Add ticker (any global symbol)…"
            value={newTicker}
            onChange={(e) => { setNewTicker(e.target.value); setAddError(null) }}
            onFocus={() => { if (searchResults.length > 0) setShowResults(true) }}
            autoComplete="off"
            style={{ flex: 1 }}
          />
          <button className="ghost" type="submit" disabled={searching}>
            {searching ? '…' : 'Add'}
          </button>
        </form>

        {showResults && searchResults.length > 0 && (
          <>
            <div onClick={() => setShowResults(false)} style={{ position: 'fixed', inset: 0, zIndex: 10 }} />
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
              {searchResults.map((r) => (
                <button
                  key={r.symbol}
                  type="button"
                  onClick={() => addResolvedTicker(r.symbol)}
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

      {addError && (
        <div style={{ color: 'var(--down, #ff5c5c)', fontSize: 12, marginTop: -6, marginBottom: 10 }}>
          {addError}
        </div>
      )}

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
      <div key={region}>
        <div className="chip-region-label">{region}</div>
        <div className="chip-group">
          {tickers
            .filter((t) => !items.includes(t))
            .map((t) => (
              <button
                key={t}
                className="chip mono"
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