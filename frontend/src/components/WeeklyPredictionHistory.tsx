import { WeeklyPredictionHistoryEntry, PredictionSummary } from '../api'

export default function WeeklyPredictionHistory({
  ticker,
  rows,
  loading,
  summary,
}: {
  ticker: string
  rows: WeeklyPredictionHistoryEntry[]
  loading: boolean
  summary: PredictionSummary | null
}) {
  if (loading) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Loading weekly prediction history…</div>
  if (rows.length === 0) return <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>No weekly predictions logged yet for {ticker}.</div>

  const resolved = rows.filter((r) => r.status === 'resolved' && r.actual_average_price !== null)
  const totalResolved = resolved.length

  const mae = summary?.mean_abs_error_pct ?? (
    totalResolved > 0
      ? resolved.reduce((sum, r) => sum + Math.abs(r.error_pct ?? 0), 0) / totalResolved
      : null
  )

  const directionalAccuracy = summary?.directional_accuracy_pct ?? null
  const directionalSample = summary?.directional_sample_size ?? 0

  return (
    <div className="card">
      <div className="label">Weekly Average Accuracy History — {ticker}</div>

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
          hint="Avg. % deviation of predicted vs actual weekly average"
        />
        <StatBox
          label="Directional Accuracy"
          value={directionalAccuracy !== null ? `${directionalAccuracy.toFixed(1)}%` : '—'}
          hint={directionalSample > 0 ? `${directionalSample} weeks compared` : 'Not enough data yet'}
        />
        <StatBox
          label="Resolved Weeks"
          value={String(totalResolved)}
          hint={`${rows.length - totalResolved} still pending`}
        />
      </div>

      <table className="history-table">
        <thead>
          <tr>
            <th>Week</th>
            <th>Predicted Avg</th>
            <th>Actual Avg</th>
            <th>Error</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.week_start}>
              <td>{r.week_start} → {r.week_end}</td>
              <td>{r.currency_symbol}{r.weekly_average_price.toFixed(2)}</td>
              <td>{r.actual_average_price !== null ? `${r.currency_symbol}${r.actual_average_price.toFixed(2)}` : '—'}</td>
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