import { PredictionHistoryEntry } from '../api'

export default function PredictionHistory({
  ticker,
  rows,
  loading,
}: {
  ticker: string
  rows: PredictionHistoryEntry[]
  loading: boolean
}) {
  if (loading) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Loading prediction history…</div>
  if (rows.length === 0) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>No predictions logged yet for {ticker}.</div>

  return (
    <div className="card">
      <div className="label">Prediction Accuracy History — {ticker}</div>
      <table className="history-table">
        <thead>
          <tr>
            <th>Target Date</th>
            <th>Predicted</th>
            <th>Actual</th>
            <th>Error</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.prediction_date}>
              <td>{r.prediction_date}</td>
              <td>{r.currency_symbol}{r.predicted_price.toFixed(2)}</td>
              <td>{r.actual_price !== null ? `${r.currency_symbol}${r.actual_price.toFixed(2)}` : '—'}</td>
              <td>
                {r.error_pct !== null ? (
                  <span className={r.error_pct >= 0 ? 'up' : 'down'}>
                    {r.error_pct >= 0 ? '+' : ''}{r.error_pct}%
                  </span>
                ) : '—'}
              </td>
              <td>
                {r.status === 'resolved'
                  ? <span className="status-resolved"> Resolved</span>
                  : <span className="status-pending"> Pending</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}