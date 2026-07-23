import { PredictionHistoryEntry, PredictionSummary } from '../api'

export default function PredictionHistory({
  ticker,
  rows,
  loading,
  summary,
}: {
  ticker: string
  rows: PredictionHistoryEntry[]
  loading: boolean
  summary: PredictionSummary | null
}) {
  if (loading) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Loading prediction history…</div>
  if (rows.length === 0) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>No predictions logged yet for {ticker}.</div>

  // Derive stats client-side from the resolved rows, so the card works
  // even if the backend `summary` payload doesn't include every field yet.
  const resolved = rows.filter((r) => r.status === 'resolved' && r.actual_price !== null)
  const totalResolved = resolved.length

  const mae =
    totalResolved > 0
      ? resolved.reduce((sum, r) => sum + Math.abs(r.error_pct ?? 0), 0) / totalResolved
      : null

  // Directional accuracy: did the predicted move (up/down vs the previous
  // resolved close) match the actual move? We approximate "predicted direction"
  // by comparing predicted_price to actual_price's own prior day via error sign
  // is not reliable, so instead we compare predicted vs actual directly:
  // a prediction is "directionally correct" if predicted and actual moved
  // the same way relative to the previous row's actual price.
  let directionalHits = 0
  let directionalTotal = 0
  const sortedResolved = [...resolved].sort(
    (a, b) => new Date(a.prediction_date).getTime() - new Date(b.prediction_date).getTime()
  )
  for (let i = 1; i < sortedResolved.length; i++) {
    const prev = sortedResolved[i - 1]
    const curr = sortedResolved[i]
    if (prev.actual_price == null || curr.actual_price == null) continue
    const actualDirection = curr.actual_price - prev.actual_price
    const predictedDirection = curr.predicted_price - prev.actual_price
    if (actualDirection === 0 || predictedDirection === 0) continue
    directionalTotal++
    if (Math.sign(actualDirection) === Math.sign(predictedDirection)) directionalHits++
  }
  const directionalAccuracy = directionalTotal > 0 ? (directionalHits / directionalTotal) * 100 : null

  return (
    <div className="card">
      <div className="label">Prediction Accuracy History — {ticker}</div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 12,
          margin: '12px 0 16px',
        }}
      >
        <StatBox
          label="Mean Absolute Error"
          value={mae !== null ? `${mae.toFixed(2)}%` : '—'}
          hint="Avg. % deviation of predicted vs actual close"
        />
        <StatBox
          label="Directional Accuracy"
          value={directionalAccuracy !== null ? `${directionalAccuracy.toFixed(1)}%` : '—'}
          hint={directionalTotal > 0 ? `${directionalHits}/${directionalTotal} correct up/down calls` : 'Not enough data yet'}
        />
        <StatBox
          label="Resolved Predictions"
          value={String(totalResolved)}
          hint={`${rows.length - totalResolved} still pending`}
        />
      </div>

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

function StatBox({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-panel, #12141a)',
        border: '1px solid var(--border, #22262F)',
        borderRadius: 8,
        padding: '10px 12px',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.3 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>{value}</div>
      {hint && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{hint}</div>}
    </div>
  )
}