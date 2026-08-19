import type { Envelope, Company, Dcf, Lbo, Mna, SearchResult, DataMode, CopilotResponse } from '../types/api'

const request = async <T>(path: string, options?: RequestInit): Promise<Envelope<T>> => {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30s timeout for AI requests
  try {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, signal: controller.signal, ...options })
    if (!response.ok) throw new Error(`API request failed (${response.status})`)
    return await response.json()
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return { status: 'UNAVAILABLE', data: {} as T, warnings: [], errors: ['Request timed out. Data unavailable.'], provenance: { notice: 'Timeout' } }
    }
    return { status: 'ERROR', data: {} as T, warnings: [], errors: [err.message || 'Network error'], provenance: {} }
  } finally {
    clearTimeout(timeoutId)
  }
}

export const api = {
  searchCompanies: (q: string, mode: DataMode = 'local', limit: number = 15) =>
    request<{ results: SearchResult[]; count: number }>(`/api/companies/search?q=${encodeURIComponent(q)}&mode=${mode}&limit=${limit}`),
  company: (ticker: string, mode: DataMode = 'local') =>
    request<Company>(`/api/company/${encodeURIComponent(ticker)}?mode=${mode}`),
  dcf: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Dcf>('/api/dcf/run', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  sensitivity: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Record<string, unknown>>('/api/dcf/sensitivity', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  mna: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Mna>('/api/mna/run', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  lbo: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Lbo>('/api/lbo/run', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  tradingComps: (ticker: string, mode: DataMode = 'local') =>
    request<Record<string, unknown>>(`/api/comps/trading/${encodeURIComponent(ticker)}?mode=${mode}`),
  transactionComps: (ticker: string, mode: DataMode = 'local') =>
    request<Record<string, unknown>>(`/api/comps/transactions/${encodeURIComponent(ticker)}?mode=${mode}`),
  monteCarlo: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Record<string, unknown>>('/api/analytics/monte-carlo', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  risk: (body: Record<string, unknown>, mode: DataMode = 'local') =>
    request<Record<string, unknown>>('/api/analytics/risk', { method: 'POST', body: JSON.stringify({ mode, ...body }) }),
  health: (ticker: string, acquirer: string = 'MSFT', mode: DataMode = 'local') =>
    request<Record<string, unknown>>(`/api/model-health/${encodeURIComponent(ticker)}?acquirer_ticker=${encodeURIComponent(acquirer)}&mode=${mode}`),
  quality: (ticker: string, mode: DataMode = 'local') =>
    request<Record<string, unknown>>(`/api/data-quality/${encodeURIComponent(ticker)}?mode=${mode}`),
  exportExcel: async (target_ticker: string, acquirer_ticker: string, mode: DataMode = 'local') => {
    const response = await fetch('/api/reports/excel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_ticker, acquirer_ticker, mode }),
    })
    if (!response.ok) throw new Error('Excel export could not be generated.')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `ValuEngine_${target_ticker}_Report.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  },
  riskLab: {
    monteCarlo: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/monte-carlo/${encodeURIComponent(ticker)}?mode=${mode}`),
    sensitivity: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/sensitivity/${encodeURIComponent(ticker)}?mode=${mode}`),
    var: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/var/${encodeURIComponent(ticker)}?mode=${mode}`),
    cvar: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/cvar/${encodeURIComponent(ticker)}?mode=${mode}`),
    merton: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/merton/${encodeURIComponent(ticker)}?mode=${mode}`),
    regime: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/regime/${encodeURIComponent(ticker)}?mode=${mode}`),
    famaFrench: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/fama-french/${encodeURIComponent(ticker)}?mode=${mode}`),
    evt: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/evt/${encodeURIComponent(ticker)}?mode=${mode}`),
    copula: (acquirer: string, target: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/copula/${encodeURIComponent(acquirer)}/${encodeURIComponent(target)}?mode=${mode}`),
    valuationConfidence: (ticker: string, mode: DataMode = 'local') =>
      request<Record<string, unknown>>(`/api/risk/valuation-confidence/${encodeURIComponent(ticker)}?mode=${mode}`),
  },
  copilot: (message: string, ticker: string, context_scope: string, page_context: string) =>
    request<CopilotResponse>('/api/ai/copilot', { 
      method: 'POST', 
      body: JSON.stringify({ message, ticker, context_scope, page_context }) 
    }),
}
