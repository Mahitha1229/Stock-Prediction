import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { register } from '../api'

export default function Login() {
  const { loginUser } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'register') {
        await register(username, password)
        setMode('login')
        setError('Account created — log in below.')
      } else {
        await loginUser(username, password)
      }
    } catch (err: any) {
      if (err?.code === 'ECONNABORTED' || !err?.response) {
        // no response = timeout, network drop, or backend still waking up
        setError('First load can take a moment to wake the server. Please refresh or retry.')
      } else {
        setError(err?.response?.data?.detail || 'Please refresh or retry.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <div className="brand" style={{ marginBottom: 20 }}>
          <span className="brand__mark" />
          StockSense
        </div>
        <div className="field">
          <label>Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="primary" type="submit" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>
        {error && (
          <div className="error-text" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span>{error}</span>
            {error.includes('refresh or retry') && (
              <button
                type="button"
                onClick={handleSubmit as any}
                disabled={busy}
                style={{
                  fontSize: 12,
                  padding: '2px 10px',
                  borderRadius: 4,
                  border: '1px solid var(--text-secondary)',
                  background: 'transparent',
                  color: 'inherit',
                  cursor: 'pointer',
                }}
              >
                Retry
              </button>
            )}
          </div>
        )}
        <div style={{ marginTop: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
          {mode === 'login' ? (
            <>No account? <a href="#" onClick={(e) => { e.preventDefault(); setMode('register') }} style={{ color: 'var(--accent)' }}>Register</a></>
          ) : (
            <>Have an account? <a href="#" onClick={(e) => { e.preventDefault(); setMode('login') }} style={{ color: 'var(--accent)' }}>Log in</a></>
          )}
        </div>
      </form>
    </div>
  )
}