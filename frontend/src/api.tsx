import axios from 'axios'

export const API_BASE = 'http://localhost:8000'
export const WS_BASE = 'ws://localhost:8000'

export const api = axios.create({ baseURL: API_BASE })

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
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  const { data } = await axios.post(`${API_BASE}/auth/login`, form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data.access_token as string
}

export async function register(username: string, password: string) {
  const { data } = await axios.post(`${API_BASE}/auth/register`, { username, password })
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

export async function fetchPredictionWithPolling(
  ticker: string,
  onUpdate: (p: Prediction) => void,
  isCancelled: () => boolean,
  intervalMs = 2000,
) {
  while (!isCancelled()) {
    const pred = await fetchPrediction(ticker)
    onUpdate(pred)
    if (pred.status === 'done') return
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
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

export function openPriceSocket(ticker: string, onMessage: (q: Quote) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/prices/${ticker}`)
  ws.onmessage = (event) => onMessage(JSON.parse(event.data))
  return ws
}
export async function fetchTrendingTickers() {
  const { data } = await api.get('/trending-tickers')
  return data.trending as Record<string, string[]>
}