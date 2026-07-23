import { useEffect, useState } from 'react'
import { fetchFundamentals, Fundamentals } from '../api'

function formatMarketCap(value: number | null): string {
  if (value == null) return '—'
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
  return `$${value.toLocaleString()}`
}

function Row({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span className="mono">{value ?? '—'}</span>
    </div>
  )
}

export default function FundamentalsCard({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Fundamentals | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchFundamentals(ticker)
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setData(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticker])

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton" style={{ height: 16, width: `${85 - i * 8}%` }} />
        ))}
      </div>
    )
  }

  if (!data) {
    return <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>No fundamentals data available for this ticker.</div>
  }

  return (
    <div>
      {data.name && (
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{data.name}</div>
      )}
      {(data.sector || data.industry) && (
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 12 }}>
          {[data.sector, data.industry].filter(Boolean).join(' · ')}
        </div>
      )}
      <Row label="Market Cap" value={formatMarketCap(data.market_cap)} />
      <Row label="P/E Ratio" value={data.pe_ratio?.toFixed(2) ?? null} />
      <Row label="EPS" value={data.eps?.toFixed(2) ?? null} />
      <Row label="Dividend Yield" value={data.dividend_yield_pct != null ? `${data.dividend_yield_pct}%` : null} />
      <Row label="52-Week High" value={data.week_52_high?.toFixed(2) ?? null} />
      <Row label="52-Week Low" value={data.week_52_low?.toFixed(2) ?? null} />
    </div>
  )
}