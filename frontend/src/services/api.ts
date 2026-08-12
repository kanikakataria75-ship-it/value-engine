import type { Envelope, Company, Dcf, Lbo, Mna } from '../types/api'

const request = async <T>(path: string, options?: RequestInit): Promise<Envelope<T>> => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!response.ok) throw new Error(`API request failed (${response.status})`)
  return response.json()
}
export const api = {
  company: (ticker: string) => request<Company>(`/api/company/${ticker}`),
  dcf: (body: Record<string, unknown>) => request<Dcf>('/api/dcf/run', { method: 'POST', body: JSON.stringify(body) }),
  sensitivity: (body: Record<string, unknown>) => request<Record<string, unknown>>('/api/dcf/sensitivity', { method: 'POST', body: JSON.stringify(body) }),
  mna: (body: Record<string, unknown>) => request<Mna>('/api/mna/run', { method: 'POST', body: JSON.stringify(body) }),
  lbo: (body: Record<string, unknown>) => request<Lbo>('/api/lbo/run', { method: 'POST', body: JSON.stringify(body) }),
  tradingComps: (ticker: string) => request<Record<string, unknown>>(`/api/comps/trading/${ticker}`),
  transactionComps: (ticker: string) => request<Record<string, unknown>>(`/api/comps/transactions/${ticker}`),
  monteCarlo: (body: Record<string, unknown>) => request<Record<string, unknown>>('/api/analytics/monte-carlo', { method: 'POST', body: JSON.stringify(body) }),
  risk: (body: Record<string, unknown>) => request<Record<string, unknown>>('/api/analytics/risk', { method: 'POST', body: JSON.stringify(body) }),
  health: (ticker: string) => request<Record<string, unknown>>(`/api/model-health/${ticker}`),
  quality: (ticker: string) => request<Record<string, unknown>>(`/api/data-quality/${ticker}`),
  exportExcel: async (target_ticker: string, acquirer_ticker: string) => {
    const response = await fetch('/api/reports/excel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_ticker, acquirer_ticker }) })
    if (!response.ok) throw new Error('Excel export could not be generated.')
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `ValuEngine_${target_ticker}_Report.xlsx`; link.click(); URL.revokeObjectURL(url)
  },
}
