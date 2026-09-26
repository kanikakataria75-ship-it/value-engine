import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AreaChart, FootballField, Gauge, Sparkline } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconArrowRight, IconCube, IconLayers } from '../../components/icons'
import { AnimatedNumber, Flags, Gate, KeyValues, Panel, Segmented, StatusPill } from '../../components/ui'
import { money, multiple, pct } from '../../lib/format'
import { usePrefs } from '../../lib/prefs'
import { ok, problem, useComps, useConfidence, useExpectations, useHealth, useHistory, useIntrinsic, useMonteCarlo, useRegime } from '../../lib/queries'
import { webglAvailable } from '../../lib/utils'
import type { HorizonRange } from '../../three/ValuationHorizon'

const ValuationHorizon = lazy(() => import('../../three/ValuationHorizon'))

export function Overview() {
  const { ticker, company, baseline } = useCompanyContext()
  const { reducedMotion } = usePrefs()
  const currency = company.currency
  const intrinsicQ = useIntrinsic(ticker)
  const intrinsic = ok(intrinsicQ.data)
  const comps = ok(useComps(ticker).data)
  const mc = ok(useMonteCarlo(ticker, 3000).data)
  const expectations = ok(useExpectations(ticker).data)
  const healthQ = useHealth(ticker)
  const health = ok(healthQ.data)
  const confidence = ok(useConfidence(ticker).data)
  const regime = ok(useRegime(ticker).data)
  const history = ok(useHistory(ticker).data)
  // The 3D horizon needs room for its row labels; narrow screens start on the 2D chart.
  const [view, setView] = useState<'3d' | '2d'>(() => (webglAvailable() && !reducedMotion && window.innerWidth >= 1100 ? '3d' : '2d'))
  const price = company.current_price ?? 0

  const ranges = useMemo<HorizonRange[]>(() => {
    const list: HorizonRange[] = []
    const closes = company.historical_prices.slice(-252).map((p) => p.close)
    if (closes.length) list.push({ key: 'range', label: '52-week trading range', sublabel: 'Observed closes', low: Math.min(...closes), high: Math.max(...closes), tone: 'ivory' })
    if (comps?.implied_range.low != null && comps.implied_range.high != null) {
      list.push({ key: 'comps', label: 'Trading comparables', sublabel: `${comps.primary_label} · interquartile`, low: comps.implied_range.low,
                  high: comps.implied_range.high, mid: comps.implied_range.mid, tone: 'violet' })
    }
    if (mc) list.push({ key: 'mc', label: 'Intrinsic value', sublabel: 'Monte Carlo 10th–90th pct.', low: mc.metrics.p10, high: mc.metrics.p90, mid: mc.base_price, tone: 'gold' })
    else if (intrinsic) {
      const v = intrinsic.implied_share_price
      list.push({ key: 'er', label: 'Intrinsic value', sublabel: 'Excess-return model', low: v * 0.995, high: v * 1.005, mid: v, tone: 'gold' })
    }
    return list
  }, [company, comps, mc, intrinsic])

  const regimeStrip = useMemo(() => {
    if (!regime) return undefined
    const byDate = new Map(regime.sequence.map((p) => [p.date, p.p_high_vol]))
    return company.historical_prices.map((p) => byDate.get(p.date) ?? 0)
  }, [regime, company])

  const revenueSeries = history?.rows.map((r) => r.revenue ?? 0) ?? []
  const marginSeries = history?.rows.map((r) => (r.ebitda && r.revenue ? r.ebitda / r.revenue : 0)) ?? []
  const actuals = baseline?.actuals
  const upside = intrinsic?.upside ?? null
  const bank = company.balance_sheet_financial

  return (
    <div className="page">
      <div className="grid grid-overview">
        <Panel className="span-8 horizon-panel" eyebrow="Valuation horizon" title="Where the value lies"
               action={<Segmented id="horizon" size="sm" value={view} onChange={setView}
                                  options={[{ value: '3d', label: <><IconCube size={13} /> 3D</> }, { value: '2d', label: <><IconLayers size={13} /> 2D</> }]} />}>
          <div className="horizon-stage">
            {ranges.length === 0 ? <Gate loading label="Assembling valuation ranges"><span /></Gate>
              : view === '3d' ? (
                <Suspense fallback={<Gate loading label="Rendering"><span /></Gate>}>
                  <ValuationHorizon ranges={ranges} marketPrice={price} currency={currency} />
                </Suspense>
              ) : (
                <FootballField ranges={ranges} market={price} format={(v) => money(v, currency)} />
              )}
          </div>
        </Panel>

        <Panel className="span-4 verdict" eyebrow="Verdict" title={bank ? 'Excess-return value' : 'Intrinsic value (DCF)'}>
          <Gate loading={intrinsicQ.isLoading} error={problem(intrinsicQ.data)}>
            <div className="verdict-value num"><AnimatedNumber value={intrinsic?.implied_share_price} format={(v) => money(v, currency, { precise: true })} /></div>
            <div className={`verdict-upside num ${upside !== null && upside >= 0 ? 'pos' : 'neg'}`}>
              {upside === null ? '—' : `${upside >= 0 ? '+' : '−'}${pct(Math.abs(upside))}`} <span className="muted">vs market {money(price, currency, { precise: true })}</span>
            </div>
            <div className="hairline" />
            {expectations?.method === 'dcf' ? (
              <div className="priced-in">
                <div className="eyebrow muted">What today's price assumes</div>
                <p>
                  <b className="num gold">{pct(expectations.implied.revenue_growth)}</b> revenue growth a year for {expectations.scenario.projection_years} years,
                  versus <b className="num">{pct(expectations.historical.revenue_cagr)}</b> over the last {Math.max(0, expectations.historical.years - 1)} years.
                </p>
                <span className={`pill ${expectations.stance?.includes('acceleration') ? 'pill-gold' : expectations.stance?.includes('slowdown') ? 'pill-info' : 'pill-off'}`}>{expectations.stance ?? 'not reachable'}</span>
              </div>
            ) : expectations?.method === 'excess_return' ? (
              <div className="priced-in">
                <div className="eyebrow muted">What today's price assumes</div>
                <p>A sustainable ROE of <b className="num gold">{pct(expectations.implied_steady_state_roe)}</b> against a current {pct(expectations.current_roe)} and a {pct(expectations.cost_of_equity)} cost of equity.</p>
              </div>
            ) : null}
            <Link to={`/c/${ticker}/expectations`} className="link-arrow">Explore the Expectations Lab <IconArrowRight size={14} /></Link>
          </Gate>
        </Panel>

        <Panel className="span-4" eyebrow="Confidence" title="How much to trust it">
          {confidence ? (
            <div className="confidence">
              <Gauge value={(confidence.score ?? 0) / 100} label={`${Math.round(confidence.score ?? 0)}`} sub={confidence.label ?? ''} size={128}
                     tone={(confidence.score ?? 0) >= 75 ? 'pos' : (confidence.score ?? 0) >= 50 ? 'gold' : 'neg'} />
              <ul className="confidence-list">
                {confidence.components.map((c) => (
                  <li key={c.key} title={c.detail}>
                    <span>{c.label}</span>
                    <em className="num">{c.score === null || c.score === undefined ? 'n/a' : Math.round(c.score)}</em>
                    <i><b style={{ width: `${c.score ?? 0}%` }} /></i>
                  </li>
                ))}
              </ul>
            </div>
          ) : <Gate loading label="Scoring"><span /></Gate>}
        </Panel>

        <Panel className="span-4" eyebrow="Model health" title="What needs a second look"
               action={<StatusPill status={healthQ.data?.status} />}>
          <Gate loading={healthQ.isLoading}>
            <Flags flags={(health?.flags ?? []).filter((f) => f.severity !== 'INFO').slice(0, 4)} empty="No assumptions or data points need review." />
            {health?.scorecard.score != null && (
              <div className="scorecard" title={health.scorecard.note}>
                <div className="scorecard-line">Opportunity score <b className="num">{Math.round(health.scorecard.score)}/100</b></div>
                <ul>
                  {health.scorecard.components.map((c) => (
                    <li key={c.label} title={c.detail}><span>{c.label}</span><b className="num">{c.points}/{c.max}</b></li>
                  ))}
                </ul>
              </div>
            )}
          </Gate>
        </Panel>

        <Panel className="span-4" eyebrow="Fundamentals" title={`Latest fiscal year · ${currency}`}>
          <div className="fund-sparks">
            <div><span>Revenue</span><b className="num">{money(company.revenue, currency)}</b><Sparkline values={revenueSeries} /></div>
            <div><span>EBITDA margin</span><b className="num">{pct(actuals?.ebitda_margin)}</b><Sparkline values={marginSeries} color="var(--aurora)" /></div>
          </div>
          <KeyValues rows={[
            [bank ? 'Return on equity' : 'Return on invested capital', pct(bank ? actuals?.roe : actuals?.roic)],
            ['Net debt / EBITDA', multiple(actuals?.net_debt_to_ebitda)],
            [bank ? 'Price / book' : 'EV / EBITDA', multiple(bank ? actuals?.pb : actuals?.ev_ebitda)],
            ['Price / earnings', multiple(actuals?.pe)],
            ['Beta used in CAPM', `${baseline?.wacc_build.beta.toFixed(2) ?? '—'}`],
          ]} />
        </Panel>

        <Panel className="span-12" eyebrow="Market" title="One year of prices, with the volatility regime beneath"
               action={regime ? <span className="muted">Now: <b className={regime.current_regime.startsWith('High') ? 'neg' : 'pos'}>{regime.current_regime}</b> · {pct(regime.current_probabilities[regime.current_regime], 0)} probability</span> : null}>
          <AreaChart data={company.historical_prices.map((p) => ({ date: p.date, value: p.close }))} height={260}
                     format={(v) => money(v, currency)} strip={regimeStrip} stripLabel="Regime"
                     markers={intrinsic ? [{ value: intrinsic.implied_share_price, label: `Intrinsic ${money(intrinsic.implied_share_price, currency)}`, color: 'var(--gold)' }] : []} />
        </Panel>
      </div>
    </div>
  )
}
