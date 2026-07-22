import axios from 'axios'

export const API_BASE = 'http://localhost:8000'
export const WS_BASE = 'ws://localhost:8000'

// timeout added so a hung backend/yfinance call fails after 20s instead of
// leaving the UI spinner stuck forever
export const api = axios.create({ baseURL: API_BASE, timeout: 20000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export interface Candle {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Quote {
  ticker: string
  price: number
  change: number
  change_pct: number
  volume: number
  timestamp: string
  currency_symbol: string
}

export interface Prediction {
  ticker: string
  status: 'training' | 'done'
  predicted_price?: number
  prediction_date?: string
  on_demand?: boolean
  currency_symbol?: string
  confidence_low?: number | null
  confidence_high?: number | null
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  const { data } = await axios.post(`${API_BASE}/auth/login`, form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    timeout: 20000,
  })
  return data.access_token as string
}

export async function register(username: string, password: string) {
  const { data } = await axios.post(`${API_BASE}/auth/register`, { username, password }, {
    timeout: 20000,
  })
  return data.message as string
}

export async function fetchHistory(ticker: string, period = '1y') {
  const { data } = await api.get(`/stock/${ticker}/history`, { params: { period } })
  return data as { ticker: string; candles: Candle[]; currency_symbol: string }
}

export async function fetchPrediction(ticker: string) {
  const { data } = await api.get(`/stock/${ticker}/predict`)
  return data as Prediction
}

/**
 * Polls /predict until the model finishes training (status: "done").
 * - Only calls onUpdate with a FINISHED result — intermediate "training"
 *   responses are ignored so the UI never renders a half-empty prediction card.
 * - Caps total polling time (maxAttempts * intervalMs) so a ticker that
 *   never finishes training (e.g. bad/illiquid symbol) fails loudly instead
 *   of polling forever.
 */
export async function fetchPredictionWithPolling(
  ticker: string,
  onUpdate: (p: Prediction) => void,
  isCancelled: () => boolean,
  intervalMs = 2000,
  maxAttempts = 60, // ~2 minutes total
) {
  let attempts = 0
  while (!isCancelled() && attempts < maxAttempts) {
    const pred = await fetchPrediction(ticker)
    if (pred.status === 'done') {
      onUpdate(pred)
      return
    }
    attempts++
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  if (!isCancelled()) {
    throw new Error('Prediction is taking longer than expected for this ticker')
  }
}

export async function fetchWatchlist() {
  const { data } = await api.get('/watchlist')
  return data.watchlist as string[]
}

export async function addToWatchlist(ticker: string) {
  await api.post('/watchlist', { ticker })
}

export async function removeFromWatchlist(ticker: string) {
  await api.delete(`/watchlist/${ticker}`)
}

export async function searchTickers(q: string) {
  const { data } = await api.get('/search', { params: { q } })
  return data.results as { symbol: string; name: string; exchange: string; type: string }[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export async function sendChatMessage(message: string, history: ChatMessage[]) {
  const { data } = await api.post('/chat', { message, history })
  return data.reply as string
}

export type SocketStatus = 'connecting' | 'live' | 'stale' | 'reconnecting' | 'closed'

interface PriceSocketHandle {
  close: () => void
}

const STALE_TIMEOUT_MS = 15000   // no message in 15s => mark stale
const MAX_BACKOFF_MS = 30000     // cap reconnect delay at 30s
const BASE_BACKOFF_MS = 1000     // start at 1s

export function openPriceSocket(
  ticker: string,
  onMessage: (q: Quote) => void,
  onStatusChange: (status: SocketStatus) => void,
): PriceSocketHandle {
  let ws: WebSocket | null = null
  let closedByCaller = false
  let attempt = 0
  let staleTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function clearStaleTimer() {
    if (staleTimer) clearTimeout(staleTimer)
    staleTimer = null
  }

  function armStaleTimer() {
    clearStaleTimer()
    staleTimer = setTimeout(() => {
      onStatusChange('stale')
      ws?.close()
    }, STALE_TIMEOUT_MS)
  }

  function connect() {
    if (closedByCaller) return
    onStatusChange(attempt === 0 ? 'connecting' : 'reconnecting')

    ws = new WebSocket(`${WS_BASE}/ws/prices/${ticker}`)

    ws.onopen = () => {
      attempt = 0
      onStatusChange('live')
      armStaleTimer()
    }

    ws.onmessage = (event) => {
      armStaleTimer()
      onStatusChange('live')
      try {
        onMessage(JSON.parse(event.data))
      } catch {
        // ignore malformed frame
      }
    }

    ws.onclose = () => {
      clearStaleTimer()
      if (closedByCaller) {
        onStatusChange('closed')
        return
      }
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function scheduleReconnect() {
    onStatusChange('reconnecting')
    const delay = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS)
    attempt++
    reconnectTimer = setTimeout(connect, delay)
  }

  connect()

  return {
    close: () => {
      closedByCaller = true
      clearStaleTimer()
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    },
  }
}

export interface PredictionHistoryEntry {
  prediction_date: string
  predicted_price: number
  currency_symbol: string
  model_type: string
  created_at: string
  actual_price: number | null
  error_pct: number | null
  status: 'resolved' | 'pending'
}

export async function fetchPredictionHistory(ticker: string): Promise<PredictionHistoryEntry[]> {
  const res = await api.get(`/stock/${ticker}/prediction-history`)
  return res.data.history
}

export async function fetchTrendingTickers() {
  const { data } = await api.get('/trending-tickers')
  return data.trending as Record<string, string[]>
}

export async function validateTicker(ticker: string) {
  const { data } = await api.get(`/stock/${ticker}/validate`)
  return data.valid as boolean
}