import { useEffect, useState } from 'react'
import { fetchStockNews, NewsArticle } from '../api'

export default function NewsPanel({ ticker }: { ticker: string }) {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchStockNews(ticker)
      .then((data) => { if (!cancelled) setArticles(data) })
      .catch(() => { if (!cancelled) setArticles([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticker])

  return (
    <div className="card">
      <div className="label" style={{ marginBottom: 10 }}>Latest News — {ticker}</div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 16, width: `${90 - i * 10}%` }} />
          ))}
        </div>
      )}

      {!loading && articles.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          No recent news found for this ticker.
        </div>
      )}

      {!loading && articles.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {articles.map((a, i) => (
            
              key={i}
              href={a.url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                textDecoration: 'none',
                color: 'var(--text-primary)',
                fontSize: 13,
                lineHeight: 1.4,
                paddingBottom: 8,
                borderBottom: i < articles.length - 1 ? '1px solid var(--border)' : 'none',
                display: 'block',
              }}
            >
              {a.title}
              {a.publisher && (
                <span style={{ display: 'block', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  {a.publisher}
                </span>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}