import { idToken } from './firebase'

const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, { method = 'GET', body } = {}) {
  const token = await idToken()
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`)
  return data
}

const qs = (params) => {
  const p = Object.entries(params).filter(([, v]) => v !== '' && v != null)
  return p.length ? '?' + new URLSearchParams(p).toString() : ''
}

export const api = {
  balance: () => request('/get-balance'),
  settings: () => request('/get-settings'),
  saveSettings: (settings) => request('/save-settings', { method: 'POST', body: { settings } }),
  parseStrategy: (description) => request('/parse-custom-strategy', { method: 'POST', body: { description } }),
  trades: (filters = {}) => request('/api/trades' + qs(filters)),
  positions: () => request('/api/positions'),
  signals: () => request('/api/signals'),
  analytics: (filters = {}) => request('/api/analytics' + qs(filters)),
  closePosition: (symbol) => request('/api/close-position', { method: 'POST', body: { symbol } }),
  tickers: () => request('/api/market/tickers'),
  aiChat: (message, mode) => request('/api/ai/chat', { method: 'POST', body: { message, mode } }),
}
