import { useEffect, useState } from 'react'
import { fetchModelComparison, ModelComparison } from '../api'

// Keyed by the actual backend keys (xgb, rf, lstm) — not display names.
const MODEL_STYLE: Record<string, { label: string; color: string; glow: string }> = {
  lstm: { label: 'LSTM', color: '#7C9CF0', glow: 'rgba(124,156,240,0.35)' },
  xgb: { label: 'XGBoost', color: '#F0A93B', glow: 'rgba(240,169,59,0.35)' },
  rf: { label: 'Random Forest', color: '#3DD68C', glow: 'rgba(61,214,140,0.35)' },
}

function styleFor(key: string) {
  return MODEL_STYLE[key.toLowerCase()] ?? { label: key, color: '#9C8CF0', glow: 'rgba(156,140,240,0.35)' }
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
    const pct = 40 + ((value - min) / range) * 55
    return `${pct}%`
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 16 }}>
        Individual model predictions for {data.target_date}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {Object.entries(data.models).map(([name, value], i) => {
          const s = styleFor(name)
          return (
            <div key={name}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, marginBottom: 6 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color, boxShadow: `0 0 8px ${s.glow}` }} />
                  {s.label}
                </span>
                <span className="mono" style={{ fontWeight: 600 }}>{data.currency_symbol}{value.toFixed(2)}</span>
              </div>
              <div style={{ background: 'var(--surface-elevated)', borderRadius: 999, height: 10, overflow: 'hidden' }}>
                <div
                  style={{
                    width: barWidth(value),
                    height: '100%',
                    borderRadius: 999,
                    background: `linear-gradient(90deg, ${s.color}99, ${s.color})`,
                    boxShadow: `0 0 10px ${s.glow}`,
                    transition: 'width 0.5s ease',
                    transitionDelay: `${i * 80}ms`,
                  }}
                />
              </div>
            </div>
          )
        })}

        <div
          style={{
            borderTop: '1px solid var(--border)',
            paddingTop: 16,
            marginTop: 4,
            background: 'linear-gradient(180deg, transparent, rgba(240,169,59,0.04))',
            borderRadius: 8,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              ✨ Ensemble (avg)
            </span>
            <span className="mono price-lg" style={{ fontSize: 20, background: 'linear-gradient(90deg, #F0A93B, #3DD68C)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              {data.currency_symbol}{data.ensemble_price.toFixed(2)}
            </span>
          </div>
          <div style={{ background: 'var(--surface-elevated)', borderRadius: 999, height: 12, overflow: 'hidden' }}>
            <div
              style={{
                width: barWidth(data.ensemble_price),
                height: '100%',
                borderRadius: 999,
                background: 'linear-gradient(90deg, #F0A93B, #3DD68C)',
                boxShadow: '0 0 14px rgba(240,169,59,0.3)',
                transition: 'width 0.5s ease',
              }}
            />
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 16, lineHeight: 1.5 }}>
        {data.on_demand
          ? 'On-demand model: XGBoost + Random Forest ensemble.'
          : 'Curated model: LSTM + XGBoost + Random Forest ensemble.'}{' '}
        The ensemble prediction is the simple average of each model above — averaging reduces the impact of any single model's blind spots or overfitting.
      </div>
    </div>
  )
}