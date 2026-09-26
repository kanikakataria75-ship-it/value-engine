import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, scenarioBody, type DataMode } from './api'
import type * as T from './api-types'
import { usePrefs } from './prefs'
import { useScenario } from './scenario'
import { stableHash, useDebounced } from './utils'

type Env<D> = T.Envelope<D>

const smooth = { placeholderData: keepPreviousData, staleTime: 60_000 } as const

function useModeKey(): DataMode {
  return usePrefs().mode
}

/** Debounced scenario request body for the current company. */
export function useScenarioBody(ticker: string): { body: T.ScenarioRequest; hash: string } {
  const mode = useModeKey()
  const { scenario } = useScenario(ticker)
  const debounced = useDebounced(scenario, 220)
  const body = scenarioBody(ticker, mode, debounced)
  return { body, hash: stableHash(body) }
}

export const useMeta = () => useQuery<Env<T.Meta>>({ queryKey: ['meta'], queryFn: api.meta, staleTime: 300_000 })

export const useSearch = (query: string) =>
  useQuery<Env<T.SearchData>>({ queryKey: ['search', query], queryFn: () => api.search(query), ...smooth })

export function useCompany(ticker: string) {
  const mode = useModeKey()
  return useQuery<Env<T.Company>>({ queryKey: ['company', ticker, mode], queryFn: () => api.company(ticker, mode), staleTime: 120_000 })
}

export function useBaseline(ticker: string) {
  const mode = useModeKey()
  return useQuery<Env<T.Baseline>>({ queryKey: ['baseline', ticker, mode], queryFn: () => api.baseline(ticker, mode), staleTime: 300_000 })
}

export const useHistory = (ticker: string) =>
  useQuery<Env<T.HistoryResult>>({ queryKey: ['history', ticker], queryFn: () => api.history(ticker), staleTime: 300_000 })

export function useQuality(ticker: string) {
  const mode = useModeKey()
  return useQuery<Env<T.DataQualityResult>>({ queryKey: ['quality', ticker, mode], queryFn: () => api.quality(ticker, mode) })
}

function useScenarioQuery<D>(name: string, ticker: string, fn: (body: T.ScenarioRequest) => Promise<Env<D>>, enabled = true) {
  const { body, hash } = useScenarioBody(ticker)
  return useQuery<Env<D>>({ queryKey: [name, hash], queryFn: () => fn(body), enabled, ...smooth })
}

export const useIntrinsic = (ticker: string) => useScenarioQuery('intrinsic', ticker, api.intrinsic)
export const useSensitivity = (ticker: string) => useScenarioQuery('sensitivity', ticker, api.sensitivity)
export const useExpectations = (ticker: string) => useScenarioQuery('expectations', ticker, api.expectations)
export const useHealth = (ticker: string) => useScenarioQuery('health', ticker, api.health)
export const useConfidence = (ticker: string) => useScenarioQuery('confidence', ticker, api.confidence)
export const useLbo = (ticker: string) => useScenarioQuery('lbo', ticker, api.lbo)
export const useStress = (ticker: string) => useScenarioQuery('stress', ticker, api.stress)

export function useMna(ticker: string) {
  const { scenario } = useScenario(ticker)
  return useScenarioQuery('mna', ticker, api.mna, Boolean(scenario.mna?.acquirer_ticker))
}

export function useMonteCarlo(ticker: string, iterations = 5000) {
  const { body, hash } = useScenarioBody(ticker)
  return useQuery<Env<T.MonteCarloResult>>({
    queryKey: ['monte-carlo', hash, iterations], queryFn: () => api.monteCarlo(body, iterations), ...smooth,
  })
}

export function useComps(ticker: string) {
  const mode = useModeKey()
  return useQuery<Env<T.CompsResult>>({ queryKey: ['comps', ticker, mode], queryFn: () => api.comps(ticker, mode), staleTime: 300_000 })
}

function usePriceModel<D>(name: string, ticker: string, fn: (t: string, m: DataMode) => Promise<Env<D>>) {
  const mode = useModeKey()
  return useQuery<Env<D>>({ queryKey: [name, ticker, mode], queryFn: () => fn(ticker, mode), staleTime: 300_000 })
}

export const useValueAtRisk = (ticker: string) => usePriceModel('var', ticker, api.valueAtRisk)
export const useTailRisk = (ticker: string) => usePriceModel('evt', ticker, api.tailRisk)
export const useRegime = (ticker: string) => usePriceModel('regime', ticker, api.regime)
export const useFactors = (ticker: string) => usePriceModel('factors', ticker, api.factors)
export const useMerton = (ticker: string) => usePriceModel('merton', ticker, api.merton)

export function useCopula(a: string, b: string) {
  const mode = useModeKey()
  return useQuery<Env<T.CopulaResult>>({
    queryKey: ['copula', a, b, mode], queryFn: () => api.copula(a, b, mode), enabled: Boolean(a && b && a !== b), staleTime: 300_000,
  })
}

export const useUniverse = () =>
  useQuery<Env<T.RadarResult>>({ queryKey: ['universe'], queryFn: api.universe, staleTime: 600_000 })

export function ok<D>(envelope: Env<D> | undefined): D | undefined {
  return envelope && envelope.data && !['INVALID', 'UNAVAILABLE', 'ERROR'].includes(envelope.status) ? envelope.data : undefined
}

/** Message for a Gate when an envelope carries no usable data (null while loading or when data is usable). */
export function problem<D>(envelope: Env<D> | undefined): string | null {
  if (!envelope || ok(envelope)) return null
  return envelope.errors[0] ?? envelope.warnings[0] ?? 'Not available for this company.'
}
