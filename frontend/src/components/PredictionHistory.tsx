import { useEffect, useState } from 'react'
import { fetchPredictionHistory, PredictionHistoryEntry } from '../api'

export default function PredictionHistory({ ticker, refreshKey }: { ticker: string; refreshKey?: unknown }) {
  const [rows, setRows] = useState<PredictionHistoryEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPredictionHistory(ticker)
      .then((data) => { if (!cancelled) setRows(data) })
      .catch(() => { if (!cancelled) setRows([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticker, refreshKey])

  if (loading) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Loading prediction history…</div>
  if (rows.length === 0) return null

  return (
    <div className="card">
      <div className="label">Prediction Accuracy History — {ticker}</div>
      <table style={{ width: '100%', marginTop: 10, borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ color: 'var(--text-dim)', textAlign: 'left' }}>
            <th style={{ padding: '4px 8px' }}>Target Date</th>
            <th style={{ padding: '4px 8px' }}>Predicted</th>
            <th style={{ padding: '4px 8px' }}>Actual</th>
            <th style={{ padding: '4px 8px' }}>Error</th>
            <th style={{ padding: '4px 8px' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.prediction_date} style={{ borderTop: '1px solid var(--border, #22262F)' }}>
              <td style={{ padding: '6px 8px' }}>{r.prediction_date}</td>
              <td style={{ padding: '6px 8px' }}>{r.currency_symbol}{r.predicted_price.toFixed(2)}</td>
              <td style={{ padding: '6px 8px' }}>
                {r.actual_price !== null ? `${r.currency_symbol}${r.actual_price.toFixed(2)}` : '—'}
              </td>
              <td style={{ padding: '6px 8px' }}>
                {r.error_pct !== null ? (
                  <span className={r.error_pct >= 0 ? 'up' : 'down'}>
                    {r.error_pct >= 0 ? '+' : ''}{r.error_pct}%
                  </span>
                ) : '—'}
              </td>
              <td style={{ padding: '6px 8px' }}>
                {r.status === 'resolved' ? (
                  <span style={{ color: 'var(--text-secondary)' }}>✓ Resolved</span>
                ) : (
                  <span style={{ color: 'var(--text-dim)' }}> Pending</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}