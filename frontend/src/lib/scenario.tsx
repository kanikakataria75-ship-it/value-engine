import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type * as T from './api-types'
import type { Scenario } from './api'
import { mergeOverrides, readStorage, writeStorage, type PatchOf } from './utils'

/* The analyst's assumptions per company. Only overrides are stored: any field that is absent falls
   back to the company baseline on the server, so every endpoint (valuation, Excel, copilot, risk)
   sees exactly the same scenario. */

type Section = 'dcf' | 'excess_return' | 'lbo'
type Patch<S> = PatchOf<S>

interface ScenarioContextValue {
  scenarios: Record<string, Scenario>
  update: (ticker: string, updater: (current: Scenario) => Scenario) => void
}

const ScenarioContext = createContext<ScenarioContextValue | null>(null)
const key = (ticker: string) => `ve.scenario.v2.${ticker.toUpperCase()}`

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [scenarios, setScenarios] = useState<Record<string, Scenario>>({})

  const update = useCallback((ticker: string, updater: (current: Scenario) => Scenario) => {
    const symbol = ticker.toUpperCase()
    setScenarios((all) => {
      const current = all[symbol] ?? readStorage<Scenario>(key(symbol), {})
      const next = updater(current)
      writeStorage(key(symbol), Object.keys(next).length ? next : undefined)
      return { ...all, [symbol]: next }
    })
  }, [])

  const value = useMemo(() => ({ scenarios, update }), [scenarios, update])
  return <ScenarioContext.Provider value={value}>{children}</ScenarioContext.Provider>
}

export interface ScenarioApi {
  scenario: Scenario
  modified: boolean
  setDcf: (patch: Patch<T.DcfAssumptions>) => void
  setExcessReturn: (patch: Patch<T.ExcessReturnAssumptions>) => void
  setLbo: (patch: Patch<T.LboAssumptions>) => void
  setMna: (patch: Patch<T.MnaAssumptions> | null) => void
  reset: (section?: Section | 'mna') => void
  /** Replace the whole scenario, e.g. one opened from a shared link. */
  load: (scenario: Scenario) => void
}

export function useScenario(ticker: string): ScenarioApi {
  const context = useContext(ScenarioContext)
  if (!context) throw new Error('useScenario must be used inside ScenarioProvider')
  const symbol = ticker.toUpperCase()
  const scenario = context.scenarios[symbol] ?? readStorage<Scenario>(key(symbol), {})
  const { update } = context

  return useMemo(() => {
    const setSection = <S extends object>(section: Section) => (patch: Patch<S>) =>
      update(symbol, (current) => {
        const next = { ...current, [section]: mergeOverrides(current[section] as S | undefined, patch) }
        if (!next[section]) delete next[section]
        return next
      })
    return {
      scenario,
      modified: Boolean(scenario.dcf || scenario.excess_return || scenario.lbo),
      setDcf: setSection<T.DcfAssumptions>('dcf'),
      setExcessReturn: setSection<T.ExcessReturnAssumptions>('excess_return'),
      setLbo: setSection<T.LboAssumptions>('lbo'),
      setMna: (patch) =>
        update(symbol, (current) => {
          if (patch === null) {
            const { mna: _removed, ...rest } = current
            return rest
          }
          const merged = mergeOverrides(current.mna ?? undefined, patch) as T.MnaAssumptions | undefined
          return merged?.acquirer_ticker ? { ...current, mna: merged } : current
        }),
      reset: (section) =>
        update(symbol, (current) => {
          if (!section) return current.mna ? { mna: current.mna } : {}
          const { [section]: _removed, ...rest } = current
          return rest
        }),
      load: (next) => update(symbol, () => next),
    }
  }, [scenario, symbol, update])
}
