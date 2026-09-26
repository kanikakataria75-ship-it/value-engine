import { lazy, Suspense, useMemo, useState } from 'react'
import { Gauge } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconCube, IconLayers, IconPlay, IconStop } from '../../components/icons'
import { Gate, PageTitle, Panel, Segmented } from '../../components/ui'
import type { DcfExpectations, FinancialExpectations } from '../../lib/api-types'
import { money, multiple, pct, points } from '../../lib/format'
import { usePrefs } from '../../lib/prefs'
import { ok, problem, useExpectations } from '../../lib/queries'
import { clamp, cn, extent, niceTicks, scaleLinear, useElementSize, webglAvailable } from '../../lib/utils'
import type { SurfaceLayers } from '../../three/ValueSurface'

const ValueSurface = lazy(() => import('../../three/ValueSurface'))

export function Expectations() {
  const { ticker } = useCompanyContext()
  const q = useExpectations(ticker)
  const data = ok(q.data)
  return (
    <div className="page">
      <PageTitle eyebrow="Expectations Lab · reverse valuation"
                 title={<>What is the market <em>pricing in</em>?</>}
                 lede="Instead of asking what the company is worth, the lab solves for the future that today's share price already assumes, then asks how plausible that future is against the company's own history." />
      <Gate loading={q.isLoading && !data} error={problem(q.data)} minHeight={420} label="Reverse-engineering the price">
        {data?.method === 'dcf' && <DcfLab data={data} />}
        {data?.method === 'excess_return' && <FinancialLab data={data} />}
      </Gate>
    </div>
  )
}

/* ------------------------------------------------------------------ operating companies */

function DcfLab({ data }: { data: DcfExpectations }) {
  const { company } = useCompanyContext()
  const { reducedMotion } = usePrefs()
  const ccy = data.currency
  const [view, setView] = useState<'3d' | '2d'>(() => (webglAvailable() ? '3d' : '2d'))
  const [layers, setLayers] = useState<SurfaceLayers>({ cloud: true, history: true, frontier: true })
  const [spin, setSpin] = useState(!reducedMotion)
  const implied = data.implied
  const years = data.scenario.projection_years
  const histYears = Math.max(0, data.historical.years - 1)
  const toggle = (key: keyof SurfaceLayers) => setLayers((l) => ({ ...l, [key]: !l[key] }))

  return (
    <>
      <section className="xp-hero reveal">
        <div className="xp-sentence display">
          At <span className="num">{money(data.market_price, ccy, { precise: true })}</span>, the market is pricing in{' '}
          <em className="num">{implied.revenue_growth === null || implied.revenue_growth === undefined ? 'an unreachable' : pct(implied.revenue_growth)}</em>{' '}
          revenue growth a year for {years} years.
        </div>
        <div className="xp-sub">
          {data.historical.revenue_cagr !== null && data.historical.revenue_cagr !== undefined && implied.revenue_growth !== null && implied.revenue_growth !== undefined ? (
            <>That is <b className="num">{points(data.expectations_gap ?? 0)}</b> versus the {histYears}-year revenue CAGR of <b className="num">{pct(data.historical.revenue_cagr)}</b>, with margins held at your {pct(data.scenario.ebitda_margin)} target.</>
          ) : <>No growth rate between −30% and +60% reconciles the model with the price, holding your other assumptions.</>}
          {data.stance && <span className={cn('pill', data.stance.includes('acceleration') ? 'pill-gold' : data.stance.includes('slowdown') ? 'pill-info' : 'pill-off')}>{data.stance}</span>}
        </div>
        <ExpectationsTrack data={data} />
      </section>

      <div className="xp-drivers">
        <DriverCard label="Revenue growth" held="margin, WACC and terminal value held" implied={implied.revenue_growth} yours={data.scenario.revenue_growth} />
        <DriverCard label="Target EBITDA margin" held="growth, WACC and terminal value held" implied={implied.ebitda_margin} yours={data.scenario.ebitda_margin}
                    note={`today ${pct(data.current_margin)}`} />
        <DriverCard label="Terminal growth" held={data.scenario.terminal_method === 'perpetuity' ? 'everything else held' : 'not used with an exit multiple'}
                    implied={implied.terminal_growth} yours={data.scenario.terminal_method === 'perpetuity' ? data.scenario.terminal_growth : null} digits={2} />
        <DriverCard label="Expected return" held="the discount rate that equates value and price" implied={implied.expected_return} yours={data.scenario.wacc}
                    yoursLabel="your WACC" digits={2} invert />
      </div>

      <div className="grid xp-grid">
        <Panel className="span-8 xp-surface-panel" flush eyebrow="Value landscape" title="Every future, priced"
               action={
                 <div className="xp-controls">
                   {view === '3d' && (
                     <>
                       <div className="chip-row">
                         {(['frontier', 'cloud', 'history'] as const).map((key) => (
                           <button key={key} type="button" className={cn('chip', layers[key] && 'on')} onClick={() => toggle(key)}>
                             <i className={`sw sw-${key}`} />{key === 'frontier' ? 'Break-even curve' : key === 'cloud' ? 'Simulated futures' : 'Actual years'}
                           </button>
                         ))}
                       </div>
                       <button type="button" className="icon-btn" title={spin ? 'Stop rotation' : 'Rotate'} onClick={() => setSpin((v) => !v)}>
                         {spin ? <IconStop size={14} /> : <IconPlay size={14} />}
                       </button>
                     </>
                   )}
                   <Segmented id="xp-view" size="sm" value={view} onChange={setView}
                              options={[{ value: '3d', label: <><IconCube size={13} /> 3D</> }, { value: '2d', label: <><IconLayers size={13} /> Map</> }]} />
                 </div>
               }>
          <div className="xp-stage">
            {view === '3d' ? (
              <Suspense fallback={<Gate loading label="Raising the landscape"><span /></Gate>}>
                <ValueSurface data={data} layers={layers} autoRotate={spin} />
              </Suspense>
            ) : <FrontierMap data={data} />}
          </div>
          <div className="xp-legend">
            <span><i className="sw sw-above" /> Worth more than the price</span>
            <span><i className="sw sw-below" /> Worth less</span>
            <span><i className="sw sw-frontier" /> Futures that exactly justify {money(data.market_price, ccy, { precise: true })}</span>
            <span><i className="sw sw-scenario" /> Your scenario ({pct(data.scenario.revenue_growth)}, {pct(data.scenario.ebitda_margin)})</span>
          </div>
        </Panel>

        <Panel className="span-4 xp-odds" eyebrow="Plausibility" title="Odds the fundamentals beat the price">
          <Gauge value={data.odds_fundamentals_beat_price} label={pct(data.odds_fundamentals_beat_price, 0)}
                 sub="of simulated futures" tone={data.odds_fundamentals_beat_price >= 0.5 ? 'pos' : data.odds_fundamentals_beat_price >= 0.25 ? 'gold' : 'neg'} size={176} />
          <p className="muted">
            Growth and margin are drawn around your scenario with the company's own historical volatility
            (σ growth {pct(data.input_volatility.revenue_growth)}, σ margin {pct(data.input_volatility.ebitda_margin)}, correlation 0.3).
            The share of futures worth more than today's price is the odds shown.
          </p>
          <div className="xp-mini">
            <div><span>Your scenario is worth</span><b className="num">{money(data.scenario_value, ccy, { precise: true })}</b></div>
            <div><span>Versus the price</span><b className={cn('num', data.scenario_upside >= 0 ? 'pos' : 'neg')}>{pct(data.scenario_upside, 1, { signed: true })}</b></div>
          </div>
        </Panel>

        <Panel className="span-7" eyebrow="Analyst note" title="Reading the price">
          <ol className="xp-narrative">
            {data.narrative.map((line, i) => <li key={i}>{line}</li>)}
          </ol>
        </Panel>
        <Panel className="span-5" eyebrow="Track record" title="What the company has actually delivered">
          {data.history_points.length ? (
            <table className="fin-table compact">
              <thead><tr><th>FY</th><th className="num">Growth</th><th className="num">Margin</th><th className="num">Clears the bar?</th></tr></thead>
              <tbody>
                {data.history_points.map((p) => {
                  const required = requiredMargin(data, p.revenue_growth)
                  const clears = required !== null && p.ebitda_margin >= required
                  return (
                    <tr key={p.period_end}>
                      <td className="mono">{p.period_end.slice(0, 4)}</td>
                      <td className="num">{pct(p.revenue_growth)}</td>
                      <td className="num">{pct(p.ebitda_margin)}</td>
                      <td className={cn('num', clears ? 'pos' : 'neg')}>
                        {required === null ? '—' : clears ? 'Yes' : Number.isFinite(required) ? `No · needs ${pct(required)}` : 'No · no margin is enough'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : <p className="muted">Not enough statement history to plot actual operating years.</p>}
          <p className="footnote muted">"Clears the bar" asks whether a year's growth and margin, sustained for {years} years, would justify today's price of {company.company_name}.</p>
        </Panel>
      </div>
      <p className="footnote muted">{data.methodology}</p>
    </>
  )
}

/** Margin needed at a growth rate to justify the price. Outside the solved frontier the answer is
    +Infinity (no margin in range is enough) or -Infinity (any margin clears it), assuming value rises
    with growth as it does whenever margins are positive. */
function requiredMargin(data: DcfExpectations, growth: number): number | null {
  const f = data.frontier
  if (!f.length) return null
  const falling = f.length < 2 || f[f.length - 1].required_margin <= f[0].required_margin
  if (growth < f[0].revenue_growth) return falling ? Infinity : -Infinity
  if (growth > f[f.length - 1].revenue_growth) return falling ? -Infinity : Infinity
  if (f.length < 2) return f[0].required_margin
  for (let i = 1; i < f.length; i++) {
    if (growth <= f[i].revenue_growth) {
      const t = (growth - f[i - 1].revenue_growth) / (f[i].revenue_growth - f[i - 1].revenue_growth || 1)
      return f[i - 1].required_margin + t * (f[i].required_margin - f[i - 1].required_margin)
    }
  }
  return null
}

/** Three markers on one growth axis: the company's history, your scenario and the market's assumption. */
function ExpectationsTrack({ data }: { data: DcfExpectations }) {
  const marks = [
    { key: 'history', label: 'History', value: data.historical.revenue_cagr },
    { key: 'yours', label: 'Your scenario', value: data.scenario.revenue_growth },
    { key: 'market', label: 'Market-implied', value: data.implied.revenue_growth },
  ].filter((m): m is { key: string; label: string; value: number } => m.value !== null && m.value !== undefined)
  if (!marks.length) return null
  const values = marks.map((m) => m.value)
  const lo = Math.min(-0.02, ...values) - 0.02
  const hi = Math.max(0.1, ...values) + 0.02
  const pos = (v: number) => ((v - lo) / (hi - lo)) * 100
  const ticks = niceTicks(lo, hi, 6)
  const market = data.implied.revenue_growth
  const history = data.historical.revenue_cagr
  return (
    <div className="xp-track" aria-label="Growth comparison">
      <div className="xp-track-rail">
        {market !== null && market !== undefined && history !== null && history !== undefined && (
          <div className={cn('xp-track-gap', market > history ? 'up' : 'down')}
               style={{ left: `${pos(Math.min(market, history))}%`, width: `${Math.abs(pos(market) - pos(history))}%` }} />
        )}
        {ticks.map((t) => <span key={t} className="xp-track-tick" style={{ left: `${pos(t)}%` }}>{pct(t, 0)}</span>)}
        {marks.map((m, i) => (
          <div key={m.key} className={`xp-track-mark ${m.key}`} style={{ left: `${pos(m.value)}%`, animationDelay: `${0.2 + i * 0.15}s` }}>
            <i />
            <span><b>{m.label}</b><em className="num">{pct(m.value)}</em></span>
          </div>
        ))}
      </div>
    </div>
  )
}

function DriverCard({ label, held, implied, yours, yoursLabel = 'your scenario', note, digits = 1, invert }: {
  label: string; held: string; implied: number | null | undefined; yours: number | null; yoursLabel?: string; note?: string; digits?: number; invert?: boolean
}) {
  const delta = implied !== null && implied !== undefined && yours !== null ? implied - yours : null
  // For growth/margin, needing more than you assume means the price is demanding; for returns, a higher
  // implied return means the price is cheap relative to your discount rate.
  const demanding = delta !== null && (invert ? delta < 0 : delta > 0)
  return (
    <div className="xp-driver">
      <div className="eyebrow muted">{label}</div>
      <div className="xp-driver-value num">{implied === null || implied === undefined ? <span className="muted">unreachable</span> : pct(implied, digits)}</div>
      <div className="xp-driver-held">{held}</div>
      {delta !== null && (
        <div className={cn('xp-driver-delta num', demanding ? 'neg' : 'pos')}>
          {points(delta, digits)} vs {yoursLabel} {pct(yours, digits)}
        </div>
      )}
      {note && <div className="xp-driver-note muted">{note}</div>}
    </div>
  )
}

/** 2D fallback: the value surface as a heat map with the break-even curve, actual years and the scenario on top. */
function FrontierMap({ data }: { data: DcfExpectations }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const { growth, margin, values } = data.surface
  const height = 440
  const pad = { l: 56, r: 18, t: 16, b: 36 }
  const width = size.width
  const x = scaleLinear([growth[0], growth[growth.length - 1]], [pad.l, Math.max(pad.l + 1, width - pad.r)])
  const y = scaleLinear([margin[0], margin[margin.length - 1]], [height - pad.b, pad.t])
  const span = useMemo(() => {
    const flat = values.flat().filter((v): v is number => v !== null && Number.isFinite(v)).map((v) => Math.abs(Math.log(Math.max(v, 1e-6) / data.market_price)))
    const sorted = flat.sort((a, b) => a - b)
    return sorted[Math.floor(sorted.length * 0.95)] || 1
  }, [values, data.market_price])
  const frontierPath = data.frontier
    .filter((p) => p.required_margin >= margin[0] && p.required_margin <= margin[margin.length - 1])
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.revenue_growth).toFixed(1)},${y(p.required_margin).toFixed(1)}`).join('')
  const cw = (x(growth[1]) - x(growth[0])) || 1
  const ch = (y(margin[0]) - y(margin[1])) || 1
  const [gx0, gx1] = extent(growth)
  const [my0, my1] = extent(margin)
  return (
    <div ref={ref} className="frontier-map" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height}>
          {values.map((row, j) => row.map((v, i) => {
            if (v === null || !Number.isFinite(v)) return null
            const d = clamp(Math.log(Math.max(v, 1e-6) / data.market_price) / span, -1, 1)
            const fill = d >= 0 ? `color-mix(in srgb, var(--gold) ${Math.round(6 + d * 58)}%, transparent)` : `color-mix(in srgb, var(--ember) ${Math.round(6 - d * 50)}%, transparent)`
            return <rect key={`${i}-${j}`} x={x(growth[i]) - cw / 2} y={y(margin[j]) - ch / 2} width={cw + 0.5} height={ch + 0.5} fill={fill} />
          }))}
          {niceTicks(gx0, gx1, 6).map((t) => (
            <g key={`gx${t}`}>
              <line x1={x(t)} x2={x(t)} y1={pad.t} y2={height - pad.b} className="grid" />
              <text x={x(t)} y={height - 14} className="tick" textAnchor="middle">{pct(t, 0)}</text>
            </g>
          ))}
          {niceTicks(my0, my1, 6).map((t) => (
            <g key={`my${t}`}>
              <line x1={pad.l} x2={width - pad.r} y1={y(t)} y2={y(t)} className="grid" />
              <text x={pad.l - 8} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">{pct(t, 0)}</text>
            </g>
          ))}
          <path d={frontierPath} className="frontier-line" />
          {data.history_points.map((p) => (
            <g key={p.period_end} className="frontier-history">
              <circle cx={x(p.revenue_growth)} cy={y(p.ebitda_margin)} r={5} />
              <text x={x(p.revenue_growth) + 8} y={y(p.ebitda_margin) + 4} className="marker-label">FY{p.period_end.slice(2, 4)}</text>
            </g>
          ))}
          <g className="frontier-scenario">
            <circle cx={x(data.scenario.revenue_growth)} cy={y(data.scenario.ebitda_margin)} r={7} />
            <circle cx={x(data.scenario.revenue_growth)} cy={y(data.scenario.ebitda_margin)} r={13} className="halo" />
          </g>
          <text x={width - pad.r} y={height - 2} className="axis-title" textAnchor="end">Revenue growth a year →</text>
          <text x={pad.l + 4} y={pad.t + 10} className="axis-title">↑ Target EBITDA margin</text>
        </svg>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ banks & insurers */

function FinancialLab({ data }: { data: FinancialExpectations }) {
  const ccy = data.currency
  const marks = [
    { key: 'ke', label: 'Cost of equity', value: data.cost_of_equity },
    { key: 'current', label: 'Current ROE', value: data.current_roe },
    { key: 'implied', label: 'Market-implied ROE', value: data.implied_steady_state_roe },
  ]
  const hi = Math.max(...marks.map((m) => m.value), 0.05) * 1.25
  const lo = Math.min(0, ...marks.map((m) => m.value))
  const pos = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <>
      <section className="xp-hero reveal">
        <div className="xp-sentence display">
          At <span className="num">{multiple(data.market_pb, 2)}</span> book, the market is pricing in a sustainable return on equity of{' '}
          <em className="num">{pct(data.implied_steady_state_roe)}</em>.
        </div>
        <div className="xp-sub">
          That is <b className="num">{points(data.expectations_gap)}</b> versus today's ROE of <b className="num">{pct(data.current_roe)}</b>, with a {pct(data.cost_of_equity)} cost of equity.
          <span className="pill pill-gold">{data.stance}</span>
        </div>
        <div className="xp-track">
          <div className="xp-track-rail">
            {niceTicks(lo, hi, 6).map((t) => <span key={t} className="xp-track-tick" style={{ left: `${pos(t)}%` }}>{pct(t, 0)}</span>)}
            {marks.map((m, i) => (
              <div key={m.key} className={`xp-track-mark ${m.key === 'implied' ? 'market' : m.key === 'current' ? 'history' : 'yours'}`}
                   style={{ left: `${pos(m.value)}%`, animationDelay: `${0.2 + i * 0.15}s` }}>
                <i />
                <span><b>{m.label}</b><em className="num">{pct(m.value)}</em></span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <div className="xp-drivers">
        <div className="xp-driver">
          <div className="eyebrow muted">Implied steady-state ROE</div>
          <div className="xp-driver-value num">{pct(data.implied_steady_state_roe)}</div>
          <div className="xp-driver-held">P/B = (ROE − g) / (Ke − g), solved for ROE</div>
        </div>
        <div className="xp-driver">
          <div className="eyebrow muted">Implied terminal ROE</div>
          <div className="xp-driver-value num">{data.implied_terminal_roe === null || data.implied_terminal_roe === undefined ? <span className="muted">unreachable</span> : pct(data.implied_terminal_roe)}</div>
          <div className="xp-driver-held">the fade target that makes the excess-return model equal the price</div>
        </div>
        <div className="xp-driver">
          <div className="eyebrow muted">Your scenario is worth</div>
          <div className="xp-driver-value num">{money(data.scenario_value, ccy, { precise: true })}</div>
          <div className={cn('xp-driver-delta num', data.scenario_upside >= 0 ? 'pos' : 'neg')}>{pct(data.scenario_upside, 1, { signed: true })} vs {money(data.market_price, ccy, { precise: true })}</div>
        </div>
      </div>
      <Panel eyebrow="Analyst note" title="Reading the price">
        <ol className="xp-narrative">{data.narrative.map((line, i) => <li key={i}>{line}</li>)}</ol>
      </Panel>
      <p className="footnote muted">{data.methodology}</p>
    </>
  )
}
