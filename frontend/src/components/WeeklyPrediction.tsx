import { useEffect, useState } from 'react'
import { fetchWeeklyPredictionWithPolling, WeeklyPrediction as WeeklyPredictionData } from '../api'

export default function WeeklyPrediction({ ticker }: { ticker: string }) {
  const [data, setData] = useState<WeeklyPredictionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    setLoading(true)

    fetchWeeklyPredictionWithPolling(
      ticker,
      (result) => {
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      },
      () => cancelled,
    ).catch((err) => {
      if (!cancelled) {
        setError(err.message || 'Failed to load weekly prediction')
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [ticker])

  if (loading) {
    return (
      <div className="card">
        <div className="label">Weekly Average Forecast — {ticker}</div>
        <div style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: 8 }}>
          Training model and forecasting the week ahead…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="label">Weekly Average Forecast — {ticker}</div>
        <div style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: 8 }}>{error}</div>
      </div>
    )
  }

  if (!data || data.weekly_average_price == null) return null

  const isUp = (data.change_pct ?? 0) >= 0
  const symbol = data.currency_symbol ?? ''

  return (
    <div className="card">
      <div className="label">Weekly Average Forecast — {ticker}</div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 12,
          margin: '12px 0 16px',
        }}
      >
        <StatBox
          label="Weekly Avg Price"
          value={`${symbol}${data.weekly_average_price.toFixed(2)}`}
          hint={`${data.week_start} → ${data.week_end}`}
        />
        <StatBox
          label="Current Price"
          value={`${symbol}${data.current_price?.toFixed(2)}`}
        />
        <StatBox
          label="Projected Change"
          value={
            <span className={isUp ? 'up' : 'down'}>
              {isUp ? '+' : ''}{data.change_pct}%
            </span> as unknown as string
          }
          hint={isUp ? 'Avg. above current price' : 'Avg. below current price'}
        />
      </div>

      {data.daily_predictions && (
        <table className="history-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Predicted Close</th>
              <th>Range (95%)</th>
            </tr>
          </thead>
          <tbody>
            {data.daily_predictions.map((d) => (
              <tr key={d.date}>
                <td>{d.date}</td>
                <td>{symbol}{d.predicted_price.toFixed(2)}</td>
                <td style={{ color: 'var(--text-dim)', fontSize: 12 }}>
                  {symbol}{d.confidence_low.toFixed(2)} – {symbol}{d.confidence_high.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 10 }}>
        Forecast built by recursively predicting each trading day and averaging the results.
        Later days carry more uncertainty since they build on earlier forecasts rather than real data.
      </div>
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