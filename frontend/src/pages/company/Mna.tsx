import { useMemo, useState } from 'react'
import { Ring, Waterfall } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconClose, IconGlobe, IconReset, IconSearch } from '../../components/icons'
import { MixBar } from '../../components/MixBar'
import { NumberField } from '../../components/NumberField'
import { AnimatedNumber, Flags, Gate, KeyValues, Meter, PageTitle, Panel, StatusPill } from '../../components/ui'
import type { Meta, MnaResult, SearchResult } from '../../lib/api-types'
import { isINR, money, multiple, pct } from '../../lib/format'
import { ok, problem, useBaseline, useCompany, useComps, useMeta, useMna, useSearch } from '../../lib/queries'
import { useScenario } from '../../lib/scenario'
import { cn, useDebounced } from '../../lib/utils'

const DEFAULT_PREMIUM = 0.25

/** Units per USD for a currency, from the dated FX rates the API serves (USD = 1). */
function perUsd(meta: Meta | undefined, currency: string): number | null {
  if (currency.toUpperCase() === 'USD') return 1
  const quote = meta?.fx.find((f) => f.pair === `USD${currency.toUpperCase()}`)
  return quote?.rate ?? null
}

export function Mna() {
  const { ticker, company } = useCompanyContext()
  const { scenario, setMna } = useScenario(ticker)
  const acquirer = scenario.mna?.acquirer_ticker ?? null
  return (
    <div className="page">
      <PageTitle eyebrow="Merger model · accretion / dilution"
                 title={<>What happens if <em>someone buys</em> {company.company_name}?</>}
                 lede="Pick an acquirer, set the price and how it is paid for, and see the effect on the buyer's earnings per share, ownership and leverage. Cross-border deals are restated at a stored, dated FX rate." />
      {acquirer ? <DealRoom ticker={ticker} acquirer={acquirer} onClear={() => setMna(null)} />
        : <AcquirerPicker ticker={ticker} onPick={(t) => setMna({ acquirer_ticker: t })} />}
    </div>
  )
}

function AcquirerPicker({ ticker, onPick }: { ticker: string; onPick: (ticker: string) => void }) {
  const { company } = useCompanyContext()
  const meta = ok(useMeta().data)
  const comps = ok(useComps(ticker).data)
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query.trim(), 180)
  const search = ok(useSearch(debounced).data)
  const rate = perUsd(meta, company.currency)
  const targetUsd = rate && company.market_cap ? company.market_cap / rate : null
  // Prefer peers big enough to buy the target; the largest companies fall back to their biggest peers.
  const { suggestions, larger } = useMemo(() => {
    const peers = (comps?.peers ?? []).filter((p) => p.ticker !== ticker)
      .sort((a, b) => (b.market_cap_usd ?? 0) - (a.market_cap_usd ?? 0))
    const bigger = peers.filter((p) => targetUsd === null || (p.market_cap_usd ?? 0) > targetUsd)
    return { suggestions: (bigger.length ? bigger : peers).slice(0, 6), larger: bigger.length > 0 }
  }, [comps, ticker, targetUsd])
  const results = (search?.results ?? []).filter((r) => r.ticker !== ticker)

  return (
    <div className="deal-picker reveal">
      <Panel className="deal-picker-panel">
        <div className="deal-picker-visual" aria-hidden="true">
          <span className="orb a" /><span className="orb b" /><span className="beam" />
        </div>
        <h3 className="display">Choose the <em>acquirer</em></h3>
        <p className="muted">Search the {meta?.company_count ?? ''} companies in the dataset, or start from a larger peer.</p>
        <label className="deal-search">
          <IconSearch size={17} />
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Company name or ticker" aria-label="Search acquirer" />
        </label>
        {debounced && (
          <ul className="deal-results">
            {results.length ? results.slice(0, 8).map((r) => <ResultRow key={r.ticker} r={r} onPick={onPick} />)
              : <li className="muted">No companies match “{debounced}”.</li>}
          </ul>
        )}
        {!debounced && suggestions.length > 0 && (
          <>
            <div className="eyebrow muted">{larger ? 'Larger peers that could plausibly buy' : 'No larger peer exists · the biggest in the sector'}</div>
            <div className="deal-suggestions">
              {suggestions.map((p) => (
                <button key={p.ticker} type="button" onClick={() => onPick(p.ticker)}>
                  <span className="mono">{p.ticker}</span>
                  <b>{p.company_name}</b>
                  <em className="num">{money(p.market_cap_usd, 'USD')}</em>
                </button>
              ))}
            </div>
          </>
        )}
      </Panel>
    </div>
  )
}

function ResultRow({ r, onPick }: { r: SearchResult; onPick: (ticker: string) => void }) {
  return (
    <li>
      <button type="button" onClick={() => onPick(r.ticker)}>
        <span className="mono">{r.ticker}</span>
        <b>{r.company_name}</b>
        <span className="muted">{r.country === 'India' ? 'IN' : 'US'} · {r.industry}</span>
        <em className="num">{money(r.market_cap, r.currency)}</em>
      </button>
    </li>
  )
}

function DealRoom({ ticker, acquirer, onClear }: { ticker: string; acquirer: string; onClear: () => void }) {
  const { company } = useCompanyContext()
  const { scenario, setMna } = useScenario(ticker)
  const m = scenario.mna!
  const acq = ok(useCompany(acquirer).data)
  const acqBaseline = ok(useBaseline(acquirer).data)
  const meta = ok(useMeta().data)
  const q = useMna(ticker)
  const result = ok(q.data)
  const acqCcy = acq?.currency ?? 'USD'
  const scale = isINR(acqCcy) ? 1e7 : 1e6
  const scaleLabel = isINR(acqCcy) ? '₹ Cr' : '$M'
  const market = acqBaseline?.market
  const toAcq = (() => {
    const from = perUsd(meta, company.currency)
    const to = perUsd(meta, acqCcy)
    return from && to ? to / from : 1
  })()
  const targetRevenue = (company.revenue ?? 0) * toAcq
  const synergyMax = Math.max(1, Math.round((targetRevenue * 0.25) / scale))
  const mix = { stock: m.pct_stock ?? 0.5, cash: m.pct_cash ?? 0, debt: m.pct_debt ?? 0.5 }
  const money$ = (key: 'revenue_synergies' | 'cost_synergies' | 'integration_costs') => ((m[key] ?? 0) / scale)
  const setMoney = (key: 'revenue_synergies' | 'cost_synergies' | 'integration_costs') => (v: number | null) =>
    setMna({ [key]: v === null ? null : v * scale })

  return (
    <div className="workbench">
      <aside className="console">
        <div className="deal-parties">
          <div className="party">
            <span className="eyebrow muted">Acquirer</span>
            <b>{acq?.company_name ?? acquirer}</b>
            <span className="mono muted">{acquirer} · {money(acq?.market_cap, acqCcy)}</span>
          </div>
          <span className="deal-arrow" aria-hidden="true">→</span>
          <div className="party">
            <span className="eyebrow muted">Target</span>
            <b>{company.company_name}</b>
            <span className="mono muted">{ticker} · {money(company.market_cap, company.currency)}</span>
          </div>
          <button type="button" className="icon-btn" title="Choose another acquirer" onClick={onClear}><IconClose size={14} /></button>
        </div>
        <div className="console-group">
          <h4>Price</h4>
          <NumberField label="Offer premium" value={m.offer_premium_pct} baseline={DEFAULT_PREMIUM} min={-0.2} max={1.0} step={0.005}
                       onChange={(v) => setMna({ offer_premium_pct: v })}
                       hint={`Offer ${money((company.current_price ?? 0) * (1 + (m.offer_premium_pct ?? DEFAULT_PREMIUM)), company.currency, { precise: true })} per share`} />
        </div>
        <div className="console-group">
          <h4>Consideration</h4>
          <MixBar value={mix} onChange={(next) => setMna({ pct_stock: next.stock, pct_cash: next.cash, pct_debt: next.debt })} />
          <NumberField label="Interest on new debt" value={m.debt_interest_rate} baseline={market ? market.risk_free_rate + market.credit_spread : null}
                       min={0} max={0.2} step={0.0005} digits={2} onChange={(v) => setMna({ debt_interest_rate: v })} />
          <NumberField label="Yield forgone on cash" value={m.cash_yield} baseline={market ? Math.max(market.risk_free_rate - 0.01, 0) : null}
                       min={0} max={0.15} step={0.0005} digits={2} onChange={(v) => setMna({ cash_yield: v })} />
          <NumberField label="Acquirer tax rate" value={m.tax_rate} baseline={market?.tax_rate ?? null} min={0} max={0.45} step={0.0025}
                       onChange={(v) => setMna({ tax_rate: v })} />
        </div>
        <div className="console-group">
          <h4>Synergies <span className="muted">({scaleLabel} a year)</span></h4>
          <NumberField label="Cost synergies" unit="number" value={money$('cost_synergies')} baseline={0} min={0} max={synergyMax} step={isINR(acqCcy) ? 10 : 5} digits={0}
                       onChange={setMoney('cost_synergies')} />
          <NumberField label="Revenue synergies" unit="number" value={money$('revenue_synergies')} baseline={0} min={0} max={synergyMax * 2} step={isINR(acqCcy) ? 10 : 5} digits={0}
                       onChange={setMoney('revenue_synergies')} />
          <NumberField label="Margin on new revenue" value={m.incremental_margin} baseline={0.2} min={0} max={0.8} step={0.01}
                       onChange={(v) => setMna({ incremental_margin: v })} />
          <NumberField label="One-off integration cost" unit="number" value={money$('integration_costs')} baseline={0} min={0} max={synergyMax * 2} step={isINR(acqCcy) ? 10 : 5} digits={0}
                       onChange={setMoney('integration_costs')} hint="Charged in year 1 only" />
        </div>
        <button type="button" className="link-quiet" onClick={() => setMna({ acquirer_ticker: acquirer, offer_premium_pct: null, pct_stock: null, pct_cash: null, pct_debt: null,
          debt_interest_rate: null, cash_yield: null, tax_rate: null, revenue_synergies: null, cost_synergies: null, incremental_margin: null, integration_costs: null })}>
          <IconReset size={12} /> Reset deal terms
        </button>
      </aside>
      <div className="results">
        <Gate loading={q.isLoading && !result} error={problem(q.data)} minHeight={320} label="Combining the two companies">
          {result && <DealResults result={result} status={q.data?.status} />}
        </Gate>
      </div>
    </div>
  )
}

function DealResults({ result, status }: { result: MnaResult; status?: string }) {
  const ccy = result.currency
  const y1 = result.eps_change_pct
  const rr = result.eps_change_pct_run_rate
  const breakEven = result.break_even_pre_tax_synergy ?? 0
  const synergyCover = breakEven > 0 ? Math.min(1, result.pre_tax_synergies / breakEven) : 1
  return (
    <>
      <Panel className={cn('result-hero deal-hero', result.is_accretive ? 'accretive' : 'dilutive')} flush>
        <div className="result-hero-grid">
          <div>
            <div className="eyebrow">Year-1 EPS impact for {result.acquirer_ticker}</div>
            <div className={cn('hero-number num', (y1 ?? 0) >= 0 ? 'pos' : 'neg')}>
              <AnimatedNumber value={y1} format={(v) => pct(v, 1, { signed: true })} />
            </div>
            <div className="deal-verdict">{result.is_accretive ? 'Accretive' : 'Dilutive'} · run-rate <b className={cn('num', (rr ?? 0) >= 0 ? 'pos' : 'neg')}>{pct(rr, 1, { signed: true })}</b></div>
            <div className="eps-line num">{money(result.acquirer_standalone_eps, ccy, { precise: true })} <span>→</span> {money(result.post_deal_eps, ccy, { precise: true })} <span className="muted">EPS</span></div>
          </div>
          <div className="result-hero-side">
            <StatusPill status={status} />
            {result.fx && (
              <span className="pill pill-info"><IconGlobe size={12} /> {result.fx.from_currency}→{result.fx.to_currency} at {result.fx.rate.toPrecision(5)} · {result.fx.date ?? 'latest'}</span>
            )}
            <KeyValues rows={[
              ['Offer per share', money(result.offer_price_target_currency, result.target_currency, { precise: true })],
              ['Equity purchase price', money(result.total_purchase_price, ccy)],
              ['Offer enterprise value', money(result.offer_enterprise_value, ccy)],
              ['EV / EBITDA paid', multiple(result.implied_ev_ebitda)],
              ['P/E paid vs acquirer P/E', `${multiple(result.implied_pe)} vs ${multiple(result.acquirer_pe)}`],
            ]} />
          </div>
        </div>
      </Panel>

      <Panel eyebrow="Earnings bridge" title="Pro forma net income, year 1">
        <Waterfall height={240} format={(v) => money(v, ccy)} steps={[
          { label: 'Acquirer NI', value: result.acquirer_net_income, total: true },
          { label: 'Target NI', value: result.target_net_income },
          { label: 'Financing', value: -result.after_tax_financing_cost },
          { label: 'Synergies', value: result.after_tax_synergies },
          { label: 'Integration', value: -result.after_tax_integration },
          { label: 'Pro forma NI', value: result.pro_forma_net_income, total: true },
        ]} />
        <p className="footnote muted">
          Pro forma shares {Math.round(result.pro_forma_shares).toLocaleString()} after issuing {Math.round(result.new_shares_issued).toLocaleString()} new shares.
          Financing cost is after tax: interest on {money(result.new_debt, ccy)} of new debt plus the yield forgone on {money(result.cash_consideration, ccy)} of cash.
        </p>
      </Panel>

      <div className="grid-3">
        <Panel eyebrow="Break-even" title="Synergies needed">
          <div className="big-figure num">{breakEven > 0 ? money(breakEven, ccy) : 'None'}</div>
          <p className="muted">{breakEven > 0 ? 'of pre-tax synergies a year make year-1 EPS neutral.' : 'The deal is accretive before synergies.'}</p>
          {breakEven > 0 && (
            <>
              <Meter value={synergyCover} tone={synergyCover >= 1 ? 'pos' : 'gold'} />
              <p className="muted small">{money(result.pre_tax_synergies, ccy)} entered · {pct(synergyCover, 0)} of break-even</p>
            </>
          )}
        </Panel>
        <Panel eyebrow="Ownership" title="Who owns the combined company">
          <div className="ownership">
            <Ring value={result.ownership_acquirer} size={96}>
              <b className="num">{pct(result.ownership_acquirer, 0)}</b>
            </Ring>
            <ul>
              <li><i className="sw sw-gold" /><span>{result.acquirer_ticker.replace('.NSE', '')} holders</span><b className="num">{pct(result.ownership_acquirer, 1)}</b></li>
              <li><i className="sw sw-aurora" /><span>{result.target_ticker.replace('.NSE', '')} holders</span><b className="num">{pct(result.ownership_target, 1)}</b></li>
            </ul>
          </div>
        </Panel>
        <Panel eyebrow="Balance sheet" title="Pro forma leverage">
          <div className={cn('big-figure num', (result.pro_forma_net_debt_to_ebitda ?? 0) > 4 ? 'neg' : '')}>{multiple(result.pro_forma_net_debt_to_ebitda)}</div>
          <p className="muted">net debt / combined EBITDA</p>
          <KeyValues rows={[
            ['Pro forma debt', money(result.pro_forma_debt, ccy)],
            ['Cash used', `${money(result.cash_consideration, ccy)} of ${money(result.acquirer_cash, ccy)}`],
          ]} />
        </Panel>
      </div>
      <Panel eyebrow="Diagnostics" title="What the model is telling you"><Flags flags={result.flags} /></Panel>
    </>
  )
}
