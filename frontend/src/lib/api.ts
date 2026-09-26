import type * as T from './api-types'

export type { Envelope } from './api-types'
export type DataMode = 'local' | 'live'
export type Scenario = Omit<T.ScenarioRequest, 'ticker' | 'mode'>

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
const TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  if (TOKEN) h.Authorization = `Bearer ${TOKEN}`
  return h
}

function failure<D>(message: string, status: T.Status = 'ERROR'): T.Envelope<D> {
  return { status, data: null, warnings: [], errors: [message], provenance: null }
}

async function call<D>(path: string, init?: RequestInit): Promise<T.Envelope<D>> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers: { ...headers(Boolean(init?.body)), ...init?.headers } })
  } catch {
    return failure('Cannot reach the ValuEngine API. Is the backend running on port 8000?')
  }
  try {
    const payload = (await response.json()) as T.Envelope<D>
    if (payload && typeof payload === 'object' && 'status' in payload) return payload
  } catch {
    /* fall through */
  }
  return failure(`Unexpected response (HTTP ${response.status}).`)
}

const get = <D>(path: string) => call<D>(path)
const post = <D>(path: string, body: unknown) => call<D>(path, { method: 'POST', body: JSON.stringify(body) })
const q = (mode: DataMode) => `?mode=${mode}`
const enc = encodeURIComponent

export function scenarioBody(ticker: string, mode: DataMode, scenario: Scenario): T.ScenarioRequest {
  return { ticker, mode, ...scenario }
}

export const api = {
  meta: () => get<T.Meta>('/api/meta'),
  search: (query: string, limit = 12) => get<T.SearchData>(`/api/companies/search?q=${enc(query)}&limit=${limit}`),
  company: (ticker: string, mode: DataMode) => get<T.Company>(`/api/company/${enc(ticker)}${q(mode)}`),
  baseline: (ticker: string, mode: DataMode) => get<T.Baseline>(`/api/company/${enc(ticker)}/baseline${q(mode)}`),
  history: (ticker: string) => get<T.HistoryResult>(`/api/company/${enc(ticker)}/history`),
  quality: (ticker: string, mode: DataMode) => get<T.DataQualityResult>(`/api/data-quality/${enc(ticker)}${q(mode)}`),
  intrinsic: (body: T.ScenarioRequest) => post<T.IntrinsicResult>('/api/valuation/intrinsic', body),
  sensitivity: (body: T.ScenarioRequest) => post<T.SensitivityResult>('/api/valuation/sensitivity', body),
  mna: (body: T.ScenarioRequest) => post<T.MnaResult>('/api/mna/run', body),
  lbo: (body: T.ScenarioRequest) => post<T.LboResult>('/api/lbo/run', body),
  stress: (body: T.ScenarioRequest) => post<T.StressResult>('/api/lbo/stress', body),
  comps: (ticker: string, mode: DataMode) => get<T.CompsResult>(`/api/comps/${enc(ticker)}${q(mode)}`),
  monteCarlo: (body: T.ScenarioRequest, iterations = 5000) =>
    post<T.MonteCarloResult>('/api/risk/monte-carlo', { ...body, iterations }),
  valueAtRisk: (ticker: string, mode: DataMode) => get<T.VarResult>(`/api/risk/var/${enc(ticker)}${q(mode)}`),
  tailRisk: (ticker: string, mode: DataMode) => get<T.EvtResult>(`/api/risk/evt/${enc(ticker)}${q(mode)}`),
  regime: (ticker: string, mode: DataMode) => get<T.RegimeResult>(`/api/risk/regime/${enc(ticker)}${q(mode)}`),
  factors: (ticker: string, mode: DataMode) => get<T.FactorResult>(`/api/risk/factors/${enc(ticker)}${q(mode)}`),
  merton: (ticker: string, mode: DataMode) => get<T.MertonResult>(`/api/risk/merton/${enc(ticker)}${q(mode)}`),
  copula: (a: string, b: string, mode: DataMode) => get<T.CopulaResult>(`/api/risk/copula/${enc(a)}/${enc(b)}${q(mode)}`),
  confidence: (body: T.ScenarioRequest) => post<T.ConfidenceResult>('/api/risk/confidence', body),
  expectations: (body: T.ScenarioRequest) => post<T.ExpectationsResult>('/api/expectations', body),
  universe: () => get<T.RadarResult>('/api/expectations/universe'),
  health: (body: T.ScenarioRequest) => post<T.HealthResult>('/api/model-health', body),
  memo: (body: T.ScenarioRequest) => post<T.MemoResult>('/api/ai/memo', body),

  async excel(body: T.ScenarioRequest): Promise<{ blob: Blob; filename: string } | { error: string }> {
    try {
      const response = await fetch(`${BASE}/api/reports/excel`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        return { error: payload?.errors?.[0] ?? `Export failed (HTTP ${response.status}).` }
      }
      const disposition = response.headers.get('content-disposition') ?? ''
      const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `ValuEngine_${body.ticker}.xlsx`
      return { blob: await response.blob(), filename }
    } catch {
      return { error: 'Cannot reach the ValuEngine API.' }
    }
  },
}

export interface CopilotEvent {
  event: 'meta' | 'delta' | 'done' | 'error'
  data: Record<string, unknown>
}

/** Parse a text/event-stream body into events; exported for tests. */
export function parseSseChunk(buffer: string): { events: CopilotEvent[]; rest: string } {
  const events: CopilotEvent[] = []
  const blocks = buffer.split('\n\n')
  const rest = blocks.pop() ?? ''
  for (const block of blocks) {
    let event = 'message'
    let data = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (data) {
      try {
        events.push({ event: event as CopilotEvent['event'], data: JSON.parse(data) })
      } catch {
        /* ignore malformed frames */
      }
    }
  }
  return { events, rest }
}

export async function* streamCopilot(body: T.CopilotRequest, signal?: AbortSignal): AsyncGenerator<CopilotEvent> {
  let response: Response
  try {
    response = await fetch(`${BASE}/api/ai/copilot/stream`, { method: 'POST', headers: headers(), body: JSON.stringify(body), signal })
  } catch {
    yield { event: 'error', data: { message: 'Cannot reach the ValuEngine API.' } }
    return
  }
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null)
    yield { event: 'error', data: { message: payload?.errors?.[0] ?? `Copilot unavailable (HTTP ${response.status}).` } }
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseChunk(buffer)
    buffer = parsed.rest
    for (const event of parsed.events) yield event
  }
}
