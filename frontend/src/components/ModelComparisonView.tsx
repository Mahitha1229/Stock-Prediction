import { useEffect, useState } from 'react'
import { fetchModelComparison, ModelComparison } from '../api'

const MODEL_COLORS: Record<string, string> = {
  LSTM: '#7C9CF0',
  XGBoost: '#F0A93B',
  'Random Forest': '#3DD68C',
}

export default function ModelComparisonView({ ticker }: { ticker: string }) {
  const [data, setData] = useState<ModelComparison | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchModelComparison(ticker)
      .then((d) => { if (!cancelled) setData(d) })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || 'Could not load model comparison')
          setData(null)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticker])

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton" style={{ height: 36, width: '100%' }} />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>{error ?? 'No data available.'}</div>
  }

  const allValues = [...Object.values(data.models), data.ensemble_price]
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const range = max - min || 1

  function barWidth(value: number): string {
    // Scale bars relative to the spread of values, with a floor so small
    // differences are still visible rather than all bars looking identical.
    const pct = 40 + ((value - min) / range) * 55
    return `${pct}%`
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 14 }}>
        Individual model predictions for {data.target_date}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Object.entries(data.models).map(([name, value]) => (
          <div key={name}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
              <span style={{ color: 'var(--text-secondary)' }}>{name}</span>
              <span className="mono">{data.currency_symbol}{value.toFixed(2)}</span>
            </div>
            <div style={{ background: 'var(--surface-elevated)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
              <div
                style={{
                  width: barWidth(value),
                  height: '100%',
                  background: MODEL_COLORS[name] ?? 'var(--accent)',
                  borderRadius: 4,
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
        ))}

        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
            <span>Ensemble (avg)</span>
            <span className="mono price-lg" style={{ fontSize: 18 }}>
              {data.currency_symbol}{data.ensemble_price.toFixed(2)}
            </span>
          </div>
          <div style={{ background: 'var(--surface-elevated)', borderRadius: 4, height: 10, overflow: 'hidden' }}>
            <div
              style={{
                width: barWidth(data.ensemble_price),
                height: '100%',
                background: 'var(--accent)',
                borderRadius: 4,
              }}
            />
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 14 }}>
        {data.on_demand
          ? 'On-demand model: XGBoost + Random Forest ensemble.'
          : 'Curated model: LSTM + XGBoost + Random Forest ensemble.'}{' '}
        The ensemble prediction is the simple average of each model above — averaging reduces the impact of any single model's blind spots or overfitting.
      </div>
    </div>
  )
}