import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Gauge, Histogram, Lines, Scatter, Tornado } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { Gate, KeyValues, PageTitle, Panel, Segmented, Stat } from '../../components/ui'
import type { CopulaResult, EvtResult, FactorResult, MertonResult, MonteCarloResult, RegimeResult, ReturnBin, VarResult } from '../../lib/api-types'
import { fixed, money, multiple, pct, priceTag, shortDate } from '../../lib/format'
import { ok, problem, useComps, useCopula, useFactors, useMerton, useMonteCarlo, useRegime, useSearch, useTailRisk, useValueAtRisk } from '../../lib/queries'
import { clamp, cn, extent, niceTicks, scaleLinear, useDebounced, useElementSize } from '../../lib/utils'

const TABS = [
  { value: 'valuation', label: 'Valuation risk' },
  { value: 'market', label: 'Market risk' },
  { value: 'regimes', label: 'Regimes' },
  { value: 'factors', label: 'Factors' },
  { value: 'credit', label: 'Credit' },
  { value: 'dependence', label: 'Dependence' },
] as const
type Tab = (typeof TABS)[number]['value']

export function Risk() {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find((t) => t.value === params.get('tab'))?.value ?? 'valuation') as Tab
  return (
    <div className="page">
      <PageTitle eyebrow="Risk lab · six independent lenses"
                 title={<>How wrong could this <em>go</em>?</>}
                 lede="Uncertainty in the valuation itself, the tails of the return distribution, hidden volatility regimes, systematic factor exposure, distance to default and how the stock crashes together with another." />
      <div className="tabbar">
        <Segmented id="risk-tab" value={tab} onChange={(v) => setParams(v === 'valuation' ? {} : { tab: v }, { replace: true })} options={TABS.map((t) => ({ ...t }))} />
      </div>
      {tab === 'valuation' && <ValuationRisk />}
      {tab === 'market' && <MarketRisk />}
      {tab === 'regimes' && <Regimes />}
      {tab === 'factors' && <Factors />}
      {tab === 'credit' && <Credit />}
      {tab === 'dependence' && <Dependence />}
    </div>
  )
}

/* ------------------------------------------------------------------ Monte Carlo */

function ValuationRisk() {
  const { ticker, company } = useCompanyContext()
  const [iterations, setIterations] = useState<'2000' | '5000' | '10000'>('5000')
  const q = useMonteCarlo(ticker, Number(iterations))
  const mc = ok(q.data)
  return (
    <Gate loading={q.isLoading && !mc} error={problem(q.data)} minHeight={360} label={`Simulating ${Number(iterations).toLocaleString()} futures`}>
      {mc && <MonteCarlo mc={mc} price={company.current_price ?? null} iterations={iterations} onIterations={setIterations} fetching={q.isFetching} />}
    </Gate>
  )
}

function MonteCarlo({ mc, price, iterations, onIterations, fetching }: {
  mc: MonteCarloResult; price: number | null; iterations: '2000' | '5000' | '10000'; onIterations: (v: '2000' | '5000' | '10000') => void; fetching: boolean
}) {
  const ccy = mc.currency
  const m = mc.metrics
  const fmt = (v: number) => money(v, ccy)
  return (
    <>
      <div className="stat-row">
        <Panel><Stat size="lg" label="Median value" value={money(m.median, ccy, { precise: true })} sub={`base case ${money(mc.base_price, ccy, { precise: true })}`} /></Panel>
        <Panel><Stat size="lg" label="80% of outcomes between" value={`${priceTag(m.p10, ccy)} – ${priceTag(m.p90, ccy)}`} sub={`σ ${fmt(m.std)}`} /></Panel>
        <Panel><Stat size="lg" label="Chance value is below the price" value={pct(m.prob_below_market, 0)} tone={(m.prob_below_market ?? 0) > 0.5 ? 'neg' : 'pos'}
                     sub={price ? `market ${money(price, ccy, { precise: true })}` : undefined} /></Panel>
        <Panel><Stat size="lg" label="Valid scenarios" value={`${mc.valid_scenarios.toLocaleString()} / ${mc.iterations.toLocaleString()}`}
                     sub={mc.adjusted_terminal_growth_draws ? `${mc.adjusted_terminal_growth_draws} terminal draws capped below WACC` : `seed ${mc.seed}`} /></Panel>
      </div>
      <Panel eyebrow="Distribution" title="Intrinsic value across correlated input draws"
             action={<Segmented id="mc-iter" size="sm" value={iterations} onChange={onIterations}
                                options={[{ value: '2000', label: '2k' }, { value: '5000', label: '5k' }, { value: '10000', label: '10k' }]} />}>
        <div className={cn(fetching && 'refreshing')}>
          <Histogram bins={mc.histogram} format={fmt} height={280} splitAt={price}
                     markers={[
                       ...(price ? [{ value: price, label: `Market ${fmt(price)}`, tone: 'var(--text-0)' }] : []),
                       { value: mc.base_price, label: `Base ${fmt(mc.base_price)}`, tone: 'var(--gold)' },
                       { value: m.p10, label: 'P10' },
                       { value: m.p90, label: 'P90' },
                     ]} />
        </div>
      </Panel>
      <div className="grid-2">
        <Panel eyebrow="Sensitivity" title="Tornado: one input at a time, P10 → P90">
          <Tornado base={mc.base_price} format={fmt} inputFormat={(v) => pct(v, 1)}
                   rows={mc.tornado.map((r) => ({ label: r.label, low: r.price_at_low, high: r.price_at_high, lowInput: r.low_input, highInput: r.high_input }))} />
          <p className="footnote muted">Bars show the value when each input moves to its own 10th and 90th percentile with all others at the base case.</p>
        </Panel>
        <Panel eyebrow="Attribution" title="Which inputs drive the spread">
          <ul className="attribution">
            {mc.attribution.map((r) => (
              <li key={r.variable}>
                <span>{r.label}</span>
                <i><b style={{ width: `${clamp(r.variance_share, 0, 1) * 100}%` }} className={r.standardized_coefficient >= 0 ? 'up' : 'down'} /></i>
                <em className="num">{pct(r.variance_share, 0)}</em>
              </li>
            ))}
          </ul>
          <p className="footnote muted">Share of value variance explained by each input (standardised regression, R² {pct(mc.attribution_r_squared, 0)}). Colour shows the direction of the effect.</p>
          <KeyValues rows={Object.entries(mc.input_volatility).map(([k, v]) => [`σ ${k.replace(/_/g, ' ')}`, pct(v, 2)])} />
        </Panel>
      </div>
      <p className="footnote muted">{mc.methodology}</p>
    </>
  )
}

/* ------------------------------------------------------------------ VaR + EVT */

function MarketRisk() {
  const { ticker } = useCompanyContext()
  const varQ = useValueAtRisk(ticker)
  const evtQ = useTailRisk(ticker)
  const v = ok(varQ.data)
  const evt = ok(evtQ.data)
  return (
    <>
      <Gate loading={varQ.isLoading} error={problem(varQ.data)} minHeight={300} label="Measuring the tails">
        {v && <VarView v={v} />}
      </Gate>
      <Gate loading={evtQ.isLoading} error={problem(evtQ.data)} minHeight={240} label="Fitting the tail">
        {evt && <EvtView evt={evt} />}
      </Gate>
    </>
  )
}

function VarView({ v }: { v: VarResult }) {
  const methods = ['historical', 'normal', 'cornish_fisher'] as const
  const names = { historical: 'Historical', normal: 'Normal', cornish_fisher: 'Cornish-Fisher' }
  return (
    <>
      <div className="stat-row">
        <Panel><Stat size="lg" label="Annualised volatility" value={pct(v.annualized_volatility)} sub={`${pct(v.daily_volatility, 2)} a day · ${v.observations} days`} /></Panel>
        <Panel><Stat size="lg" label="Skew · excess kurtosis" value={`${fixed(v.skewness)} · ${fixed(v.excess_kurtosis)}`}
                     sub={v.normality_rejected ? `Not normal (Jarque-Bera p ${v.jarque_bera_p_value < 0.001 ? '< 0.001' : fixed(v.jarque_bera_p_value, 3)})` : 'Normality not rejected'} /></Panel>
        <Panel><Stat size="lg" label="Maximum drawdown" value={pct(v.max_drawdown)} tone="neg" sub={v.peak_date ? `${shortDate(v.peak_date)} → ${shortDate(v.trough_date)}` : undefined} /></Panel>
        <Panel><Stat size="lg" label="Worst · best day" value={`${pct(v.worst_day, 1)} · ${pct(v.best_day, 1, { signed: true })}`} /></Panel>
      </div>
      <div className="grid">
        <Panel className="span-7" eyebrow="Return distribution" title="Daily returns against a normal curve">
          <ReturnDistribution bins={v.histogram} marks={v.table.filter((r) => r.method === 'historical').map((r) => ({ value: -r.var_1d, label: `VaR ${pct(r.confidence, 0)}` }))} />
        </Panel>
        <Panel className="span-5" eyebrow="Value at risk" title="One-day and ten-day losses" flush>
          <div className="table-wrap">
            <table className="fin-table compact">
              <thead><tr><th>Method</th><th className="num">Conf.</th><th className="num">VaR 1d</th><th className="num">ES 1d</th><th className="num">VaR 10d</th><th className="num">ES 10d</th></tr></thead>
              <tbody>
                {methods.flatMap((method) => v.table.filter((r) => r.method === method).map((r, i) => (
                  <tr key={`${method}-${r.confidence}`}>
                    <td>{i === 0 ? names[method] : ''}</td>
                    <td className="num">{pct(r.confidence, 0)}</td>
                    <td className="num neg">{pct(r.var_1d, 2)}</td>
                    <td className="num neg">{pct(r.es_1d, 2)}</td>
                    <td className="num">{pct(r.var_10d, 1)}</td>
                    <td className="num">{pct(r.es_10d, 1)}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
          <p className="footnote muted pad">Losses are shown as positive numbers. Ten-day figures scale by √10. Cornish-Fisher adjusts the normal quantile for skew and fat tails.</p>
        </Panel>
      </div>
    </>
  )
}

function ReturnDistribution({ bins, marks }: { bins: ReturnBin[]; marks: { value: number; label: string }[] }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const height = 260
  const pad = { l: 40, r: 12, t: 22, b: 26 }
  if (!bins.length) return null
  const width = size.width
  const step = bins.length > 1 ? bins[1].value - bins[0].value : 0.01
  const [x0, x1] = [bins[0].value - step / 2, bins[bins.length - 1].value + step / 2]
  const x = scaleLinear([x0, x1], [pad.l, Math.max(pad.l + 1, width - pad.r)])
  const top = Math.max(...bins.map((b) => Math.max(b.count, b.normal)), 1)
  const y = scaleLinear([0, top], [height - pad.b, pad.t])
  const curve = bins.map((b, i) => `${i ? 'L' : 'M'}${x(b.value).toFixed(1)},${y(b.normal).toFixed(1)}`).join('')
  return (
    <div ref={ref} className="chart" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height}>
          <line x1={pad.l} x2={width - pad.r} y1={height - pad.b} y2={height - pad.b} className="axis" />
          {niceTicks(x0, x1, 6).map((t) => <text key={t} x={x(t)} y={height - 8} className="tick" textAnchor="middle">{pct(t, 0)}</text>)}
          {bins.map((b) => (
            <rect key={b.value} x={x(b.value - step / 2) + 0.6} width={Math.max(1, x(b.value + step / 2) - x(b.value - step / 2) - 1.2)}
                  y={y(b.count)} height={height - pad.b - y(b.count)} rx={1.5} className={cn('bar', b.value < 0 ? 'bar-neg' : 'bar-pos')} />
          ))}
          <path d={curve} fill="none" stroke="var(--text-1)" strokeWidth={1.4} strokeDasharray="4 3" />
          {marks.map((m, i) => (
            <g key={m.label}>
              <line x1={x(m.value)} x2={x(m.value)} y1={pad.t - 4} y2={height - pad.b} stroke="var(--ember)" strokeWidth={1.2} />
              <text x={x(m.value) - 4} y={pad.t - 8 + i * 12} className="marker-label" textAnchor="end" fill="var(--ember)">{m.label}</text>
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}

function EvtView({ evt }: { evt: EvtResult }) {
  return (
    <div className="grid">
      <Panel className="span-7" eyebrow="Extreme value theory" title="Generalised Pareto fit to the worst days">
        <div className="evt-head">
          <Stat label="Tail shape ξ" value={fixed(evt.shape_xi, 3)} sub={evt.tail_interpretation} />
          <Stat label="Scale β" value={fixed(evt.scale_beta, 4)} />
          <Stat label="Threshold" value={pct(evt.threshold, 2)} sub={`${evt.exceedances} exceedances of ${evt.observations}`} />
          <Stat label="Goodness of fit" value={`KS p ${fixed(evt.ks_p_value, 2)}`} sub={evt.ks_p_value > 0.05 ? 'fit not rejected' : 'fit rejected at 5%'} />
        </div>
        <table className="fin-table compact">
          <thead><tr><th>Confidence</th><th className="num">EVT VaR 1d</th><th className="num">EVT ES 1d</th><th className="num">Empirical VaR</th></tr></thead>
          <tbody>
            {evt.levels.map((l) => (
              <tr key={l.confidence}>
                <td className="num">{pct(l.confidence, 1)}</td>
                <td className="num neg">{pct(l.var_1d, 2)}</td>
                <td className="num neg">{pct(l.es_1d, 2)}</td>
                <td className="num">{pct(l.empirical_var_1d, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {evt.low_sample_warning && <p className="footnote warn-text">Few exceedances: treat the tail estimates as indicative.</p>}
      </Panel>
      <Panel className="span-5" eyebrow="Fit check" title="Quantile-quantile plot">
        <Scatter points={evt.qq.map((p) => ({ x: p.model, y: p.empirical, tone: 'gold' as const, size: 3.4 }))} xLabel="Model" yLabel="Empirical"
                 format={(v) => pct(v, 1)} height={280} diagonal />
      </Panel>
      <p className="footnote muted span-12">{evt.methodology}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ Regimes */

function Regimes() {
  const { ticker } = useCompanyContext()
  const q = useRegime(ticker)
  const r = ok(q.data)
  return (
    <Gate loading={q.isLoading} error={problem(q.data)} minHeight={360} label="Decoding hidden regimes">
      {r && <RegimeView r={r} />}
    </Gate>
  )
}

function RegimeView({ r }: { r: RegimeResult }) {
  return (
    <>
      <Panel eyebrow="Hidden Markov model" title={`Now: ${r.current_regime} · ${pct(r.current_probabilities[r.current_regime], 0)} probability`}
             action={<span className={cn('pill', r.regimes_supported ? 'pill-ok' : 'pill-warn')}>{r.regimes_supported ? 'Two regimes supported by BIC' : 'BIC prefers one regime'}</span>}>
        <RegimeRibbon r={r} />
        <div className="legend-inline"><span><i className="sw sw-aurora" /> Calm</span><span><i className="sw sw-ember" /> Turbulent</span><span className="muted">Bar height is the daily return; colour is the smoothed probability of the turbulent state.</span></div>
      </Panel>
      <div className="grid-3">
        {r.states.map((s) => (
          <Panel key={s.label} eyebrow="State" title={s.label}>
            <KeyValues rows={[
              ['Annualised return', pct(s.annualized_return)],
              ['Annualised volatility', pct(s.annualized_volatility)],
              ['Persistence (stay probability)', pct(s.persistence, 1)],
              ['Expected duration', s.expected_duration_days ? `${Math.round(s.expected_duration_days)} days` : '—'],
              ['Share of days', pct(s.share_of_days, 0)],
            ]} />
          </Panel>
        ))}
        <Panel eyebrow="Dynamics" title="Transition matrix">
          <div className="matrix">
            <span />{r.states.map((s) => <b key={s.label}>{s.label.split(' ')[0]}</b>)}
            {r.transition_matrix.map((row, i) => (
              <div key={i} className="matrix-row">
                <b>{r.states[i]?.label.split(' ')[0]}</b>
                {row.map((p, j) => <span key={j} className="num" style={{ background: `color-mix(in srgb, var(--gold) ${Math.round(p * 55)}%, transparent)` }}>{pct(p, 1)}</span>)}
              </div>
            ))}
          </div>
          <KeyValues rows={[
            ['Volatility ratio', multiple(r.volatility_ratio, 2)],
            ['BIC · two regimes', fixed(r.bic_hmm, 1)],
            ['BIC · one regime', fixed(r.bic_single_regime, 1)],
          ]} />
        </Panel>
      </div>
      <p className="footnote muted">{r.methodology}</p>
    </>
  )
}

function RegimeRibbon({ r }: { r: RegimeResult }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const height = 220
  const width = size.width
  const n = r.sequence.length
  const maxAbs = Math.max(...r.sequence.map((p) => Math.abs(p.value)), 1e-6)
  const mid = height / 2
  const bw = n ? width / n : 0
  const labels = useMemo(() => {
    const out: { i: number; text: string }[] = []
    let last = ''
    r.sequence.forEach((p, i) => {
      const key = p.date.slice(0, 7)
      if (key !== last && Number(p.date.slice(5, 7)) % 3 === 1) out.push({ i, text: shortDate(`${key}-01`).replace(/ \d+,/, '') })
      last = key
    })
    return out
  }, [r.sequence])
  return (
    <div ref={ref} className="chart" style={{ height: height + 20 }}>
      {width > 0 && (
        <svg width={width} height={height + 20}>
          <line x1={0} x2={width} y1={mid} y2={mid} className="axis" />
          {r.sequence.map((p, i) => {
            const h = (Math.abs(p.value) / maxAbs) * (mid - 6)
            return (
              <rect key={p.date} x={i * bw} width={Math.max(0.8, bw - 0.4)} y={p.value >= 0 ? mid - h : mid} height={Math.max(0.6, h)}
                    fill={`color-mix(in srgb, var(--ember) ${Math.round(p.p_high_vol * 100)}%, var(--aurora))`} opacity={0.85} />
            )
          })}
          {labels.map((l) => <text key={l.i} x={l.i * bw} y={height + 14} className="tick">{l.text}</text>)}
        </svg>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ Factors */

function Factors() {
  const { ticker } = useCompanyContext()
  const q = useFactors(ticker)
  const f = ok(q.data)
  return (
    <Gate loading={q.isLoading} error={problem(q.data)} minHeight={360} label="Regressing on factors">
      {f && <FactorView f={f} />}
    </Gate>
  )
}

function FactorView({ f }: { f: FactorResult }) {
  const every = Math.max(1, Math.floor(f.cumulative.length / 6))
  return (
    <>
      <div className="stat-row">
        <Panel><Stat size="lg" label="CAPM beta (regression)" value={fixed(f.capm_beta, 2)} sub={`± ${fixed(f.capm_beta_std_error, 2)} · R² ${pct(f.capm_r_squared, 0)}`} /></Panel>
        <Panel><Stat size="lg" label="Provider beta" value={fixed(f.provider_beta, 2)} sub="Yahoo Finance · 5Y monthly vs S&P 500" /></Panel>
        <Panel><Stat size="lg" label="Alpha (annualised)" value={pct(f.alpha_annualized, 1, { signed: true })} tone={f.alpha_annualized >= 0 ? 'pos' : 'neg'} /></Panel>
        <Panel><Stat size="lg" label="Three-factor R²" value={pct(f.r_squared, 0)} sub={`idiosyncratic vol ${pct(f.residual_volatility_annualized)}`} /></Panel>
      </div>
      <div className="grid">
        <Panel className="span-5" eyebrow="Loadings" title="Market, size and value exposure" flush>
          <table className="fin-table compact">
            <thead><tr><th>Factor</th><th className="num">Loading</th><th className="num">t-stat</th><th className="num">p-value</th></tr></thead>
            <tbody>
              {f.coefficients.map((c) => (
                <tr key={c.factor}>
                  <td>{c.label}</td>
                  <td className="num">
                    <span className="coef"><i style={{ width: `${clamp(Math.abs(c.coefficient) / 2, 0, 1) * 100}%` }} className={c.coefficient >= 0 ? 'up' : 'down'} />{fixed(c.coefficient, 2)}</span>
                  </td>
                  <td className={cn('num', Math.abs(c.t_stat) >= 2 ? 'gold' : 'muted')}>{fixed(c.t_stat, 2)}</td>
                  <td className="num">{c.p_value < 0.001 ? '< 0.001' : fixed(c.p_value, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="footnote muted pad">Factors are built from the {f.universe.constituents} companies in the {f.market} universe (size and value portfolios, stock excluded). Newey-West standard errors.</p>
        </Panel>
        <Panel className="span-7" eyebrow="Performance" title="Cumulative return against the market factor">
          <Lines labels={f.cumulative.map((p, i) => (i % every === 0 ? shortDate(p.date).replace(/ \d+,/, '') : ''))} format={(v) => pct(v, 0)} zero series={[
            { name: 'Stock', color: 'var(--gold)', values: f.cumulative.map((p) => p.stock) },
            { name: 'Market', color: 'var(--aurora)', values: f.cumulative.map((p) => p.market), dashed: true },
          ]} />
          <div className="legend-inline"><span><i className="sw sw-gold" /> Stock</span><span><i className="sw sw-aurora" /> Market factor</span></div>
        </Panel>
      </div>
      <p className="footnote muted">{f.methodology} {f.limitations}</p>
    </>
  )
}

/* ------------------------------------------------------------------ Merton */

function Credit() {
  const { ticker } = useCompanyContext()
  const q = useMerton(ticker)
  const m = ok(q.data)
  return (
    <Gate loading={q.isLoading} error={problem(q.data)} minHeight={320} label="Solving the Merton model">
      {m && <MertonView m={m} />}
    </Gate>
  )
}

function MertonView({ m }: { m: MertonResult }) {
  const { company } = useCompanyContext()
  const ccy = company.currency
  const dd = m.distance_to_default
  return (
    <>
      <div className="grid">
        <Panel className="span-4" eyebrow="Structural credit model" title="Distance to default">
          <Gauge value={dd === null || dd === undefined ? null : clamp(dd / 8, 0, 1)} label={dd === null || dd === undefined ? 'n/a' : `${dd.toFixed(2)}σ`}
                 sub={`${pct(m.probability_of_default, m.probability_of_default < 0.001 ? 3 : 2)} one-year PD`} tone={(dd ?? 0) >= 3 ? 'pos' : (dd ?? 0) >= 1.5 ? 'gold' : 'neg'} size={180} />
          {m.note && <p className="footnote muted">{m.note}</p>}
        </Panel>
        <Panel className="span-8" eyebrow="Inputs and solution" title="Equity as a call option on the firm's assets">
          <div className="grid-2 tight">
            <KeyValues rows={[
              ['Equity value', money(m.inputs.equity_value, ccy)],
              ['Default point (debt)', money(m.inputs.default_point, ccy)],
              ['Equity volatility', pct(m.inputs.equity_volatility)],
              ['Risk-free rate', pct(m.inputs.risk_free_rate, 2)],
              ['Horizon', `${m.inputs.horizon_years} year · ${m.inputs.volatility_window_days}-day vol window`],
            ]} />
            <KeyValues rows={[
              ['Implied asset value', money(m.asset_value, ccy), 'gold'],
              ['Implied asset volatility', pct(m.asset_volatility), 'gold'],
              ['Market leverage', pct(m.market_leverage)],
              ['Implied credit spread', m.implied_credit_spread === null || m.implied_credit_spread === undefined ? '—'
                : m.implied_credit_spread * 10000 < 0.5 ? '< 1 bp' : `${(m.implied_credit_spread * 10000).toFixed(0)} bp`],
            ]} />
          </div>
          <div className="hairline" />
          <div className="eyebrow muted">If equity volatility were different</div>
          <Lines labels={m.sensitivity.map((s) => pct(s.equity_volatility, 0))} format={(v) => `${v.toFixed(1)}σ`} series={[
            { name: 'Distance to default', color: 'var(--gold)', values: m.sensitivity.map((s) => s.distance_to_default) },
          ]} height={180} />
        </Panel>
      </div>
      <p className="footnote muted">{m.methodology}</p>
    </>
  )
}

/* ------------------------------------------------------------------ Copulas */

function Dependence() {
  const { ticker } = useCompanyContext()
  const peers = ok(useComps(ticker).data)?.peers ?? []
  const [pair, setPair] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query.trim(), 180)
  const results = ok(useSearch(debounced).data)?.results.filter((r) => r.ticker !== ticker) ?? []
  const other = pair ?? peers[0]?.ticker ?? ''
  const q = useCopula(ticker, other)
  const c = ok(q.data)
  return (
    <>
      <Panel eyebrow="Pair" title={`${ticker} and ${other || '…'}`}
             action={
               <div className="pair-picker">
                 {peers.slice(0, 5).map((p) => (
                   <button key={p.ticker} type="button" className={cn('chip', other === p.ticker && 'on')} onClick={() => setPair(p.ticker)}>{p.ticker}</button>
                 ))}
                 <div className="pair-search">
                   <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Any ticker…" aria-label="Pair with another company" />
                   {debounced && results.length > 0 && (
                     <ul>{results.slice(0, 6).map((r) => (
                       <li key={r.ticker}><button type="button" onClick={() => { setPair(r.ticker); setQuery('') }}><span className="mono">{r.ticker}</span> {r.company_name}</button></li>
                     ))}</ul>
                   )}
                 </div>
               </div>
             }>
        <Gate loading={q.isLoading} error={other ? problem(q.data) : 'Choose a second company.'} minHeight={280} label="Fitting copulas">
          {c && <CopulaView c={c} />}
        </Gate>
      </Panel>
      {c && <p className="footnote muted">{c.methodology}</p>}
    </>
  )
}

function CopulaView({ c }: { c: CopulaResult }) {
  const bestAic = Math.min(...c.fits.map((f) => f.aic))
  const every = Math.max(1, Math.floor(c.rolling_correlation.length / 6))
  const [lo, hi] = extent(c.rolling_correlation.map((p) => p.correlation))
  return (
    <div className="grid">
      <div className="span-5">
        <Scatter points={c.pseudo_observations.map((p) => ({ x: p.u, y: p.v, tone: p.u < c.joint_crash.quantile && p.v < c.joint_crash.quantile ? 'ember' as const : 'ivory' as const, size: 2.4 }))}
                 xLabel={c.pair.a ?? 'A'} yLabel={c.pair.b ?? 'B'} format={(v) => v.toFixed(1)} height={300} />
        <p className="footnote muted">Rank-transformed daily returns. Ember points are days when both stocks fell into their worst {pct(c.joint_crash.quantile, 0)}.</p>
      </div>
      <div className="span-7">
        <div className="stat-row compact">
          <Stat label="Selected copula" value={c.selected_copula} sub={Object.entries(c.selected_params).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(' · ')} />
          <Stat label="Kendall τ · Spearman ρ" value={`${fixed(c.kendall_tau, 2)} · ${fixed(c.spearman_rho, 2)}`} sub={`Pearson ${fixed(c.pearson_correlation, 2)} · ${c.observations} days`} />
          <Stat label="Lower-tail dependence" value={pct(c.lower_tail_dependence, 0)} tone={c.lower_tail_dependence > 0.2 ? 'neg' : ''} sub={`upper ${pct(c.upper_tail_dependence, 0)}`} />
        </div>
        <div className="crash-callout">
          <b className="num">{multiple(c.joint_crash.multiple_of_independence, 1)}</b>
          <span>
            as likely to crash together as independent stocks: both in their worst {pct(c.joint_crash.quantile, 0)} on
            {' '}{pct(c.joint_crash.model_probability, 2)} of days under the copula ({pct(c.joint_crash.empirical_probability, 2)} observed, {pct(c.joint_crash.independence_probability, 2)} if independent).
          </span>
        </div>
        <table className="fin-table compact">
          <thead><tr><th>Family</th><th className="num">Log-likelihood</th><th className="num">AIC</th><th className="num">λ lower</th><th className="num">λ upper</th></tr></thead>
          <tbody>
            {c.fits.map((f) => (
              <tr key={f.family} className={f.aic === bestAic ? 'emph' : ''}>
                <td>{f.name}{f.aic === bestAic && <span className="pill pill-gold tiny">best</span>}</td>
                <td className="num">{fixed(f.log_likelihood, 1)}</td>
                <td className="num">{fixed(f.aic, 1)}</td>
                <td className="num">{pct(f.lower_tail, 0)}</td>
                <td className="num">{pct(f.upper_tail, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="span-12">
        <div className="eyebrow muted">Rolling 60-day correlation ({fixed(lo, 2)} to {fixed(hi, 2)})</div>
        <Lines labels={c.rolling_correlation.map((p, i) => (i % every === 0 ? shortDate(p.date).replace(/ \d+,/, '') : ''))} format={(v) => v.toFixed(2)} height={170} zero series={[
          { name: 'Correlation', color: 'var(--violet)', values: c.rolling_correlation.map((p) => p.correlation) },
        ]} />
      </div>
    </div>
  )
}
