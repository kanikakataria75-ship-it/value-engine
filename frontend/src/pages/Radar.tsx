import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Scatter, type ScatterPoint } from '../components/charts'
import { Gate, PageTitle, Panel, Segmented, Stat } from '../components/ui'
import type { RadarRow } from '../lib/api-types'
import { money, pct, points, shortDate } from '../lib/format'
import { ok, problem, useUniverse } from '../lib/queries'
import { clamp, cn } from '../lib/utils'

type Country = 'all' | 'United States' | 'India'
type Model = 'all' | 'dcf' | 'excess_return'
type SortKey = 'expectations_gap' | 'implied_growth' | 'historical_cagr' | 'implied_return' | 'scenario_upside' | 'market_cap_usd'

export function Radar() {
  const q = useUniverse()
  const data = ok(q.data)
  const navigate = useNavigate()
  const [country, setCountry] = useState<Country>('all')
  const [model, setModel] = useState<Model>('dcf')
  const [sector, setSector] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'expectations_gap', dir: -1 })
  const [highlight, setHighlight] = useState<string | null>(null)

  const sectors = useMemo(() => [...new Set((data?.rows ?? []).map((r) => r.sector).filter(Boolean) as string[])].sort(), [data])
  const rows = useMemo(() => {
    const needle = text.trim().toLowerCase()
    return (data?.rows ?? []).filter((r) =>
      (country === 'all' || r.country === country) && (model === 'all' || r.model === model) && (!sector || r.sector === sector) &&
      (!needle || r.ticker.toLowerCase().includes(needle) || (r.company_name ?? '').toLowerCase().includes(needle)))
  }, [data, country, model, sector, text])
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    const av = a[sort.key] ?? -Infinity
    const bv = b[sort.key] ?? -Infinity
    return (av > bv ? 1 : av < bv ? -1 : 0) * sort.dir
  }), [rows, sort])

  const scatter: ScatterPoint[] = rows
    .filter((r) => r.model === 'dcf' && r.implied_growth !== null && r.implied_growth !== undefined && r.historical_cagr !== null && r.historical_cagr !== undefined)
    .map((r) => {
      const gap = r.expectations_gap ?? 0
      return {
        id: r.ticker, label: `${r.ticker} · ${r.company_name}`,
        x: clamp(r.historical_cagr as number, -0.2, 0.5), y: clamp(r.implied_growth as number, -0.2, 0.5),
        tone: gap > 0.05 ? 'gold' : gap < -0.05 ? 'aurora' : 'ivory', size: 2.4 + Math.min(4, Math.log10(Math.max(r.market_cap_usd ?? 1e9, 1e9) / 1e9) * 1.3),
      }
    })

  const header = (key: SortKey, label: string) => (
    <th key={key} className={cn('num sortable', sort.key === key && 'sorted')} onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : -1 }))}>
      {label}{sort.key === key ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''}
    </th>
  )

  return (
    <div className="page radar-page">
      <PageTitle eyebrow="Expectations radar · the whole universe"
                 title={<>What is the market <em>pricing in</em>, everywhere?</>}
                 lede="The reverse DCF from the Expectations Lab, run on every company at its baseline assumptions. Above the diagonal, the price needs faster growth than the company has delivered; below it, the market expects a slowdown." />
      <Gate loading={q.isLoading} error={problem(q.data)} minHeight={420} label="Solving every company">
        {data && (
          <>
            <div className="stat-row">
              <Panel><Stat size="lg" label="Companies solved" value={`${data.summary.companies}`} sub={`${data.summary.dcf_companies} operating · ${data.summary.financial_companies} financial`} /></Panel>
              <Panel><Stat size="lg" label="Median growth priced in" value={pct(data.summary.median_implied_growth)} tone="gold" /></Panel>
              <Panel><Stat size="lg" label="Median historical CAGR" value={pct(data.summary.median_historical_cagr)} /></Panel>
              <Panel><Stat size="lg" label="Price out of reach" value={`${data.summary.not_reachable}`} sub="no growth rate between −30% and +60% fits" /></Panel>
            </div>
            <div className="radar-filters">
              <Segmented id="radar-country" size="sm" value={country} onChange={setCountry}
                         options={[{ value: 'all', label: 'All' }, { value: 'United States', label: 'United States' }, { value: 'India', label: 'India' }]} />
              <Segmented id="radar-model" size="sm" value={model} onChange={setModel}
                         options={[{ value: 'dcf', label: 'Operating (DCF)' }, { value: 'excess_return', label: 'Financials' }, { value: 'all', label: 'Both' }]} />
              <input className="radar-search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Filter by name or ticker" aria-label="Filter companies" />
              <div className="chip-row">
                <button type="button" className={cn('chip', !sector && 'on')} onClick={() => setSector(null)}>All sectors</button>
                {sectors.map((s) => <button key={s} type="button" className={cn('chip', sector === s && 'on')} onClick={() => setSector(sector === s ? null : s)}>{s}</button>)}
              </div>
            </div>
            <div className="grid">
              <Panel className="span-8" eyebrow={`${scatter.length} operating companies`} title="Priced-in growth against delivered growth">
                {scatter.length ? (
                  <Scatter points={scatter} xLabel="Historical revenue CAGR" yLabel="Growth priced in" format={(v) => pct(v, 0)} height={440} diagonal
                           highlight={highlight} onPick={(p) => p.id && navigate(`/c/${p.id}/expectations`)} />
                ) : <p className="muted">No operating companies match the filters.</p>}
                <div className="legend-inline">
                  <span><i className="sw sw-gold" /> Priced for acceleration (&gt; +5 pts)</span>
                  <span><i className="sw sw-aurora" /> Priced for slowdown (&lt; −5 pts)</span>
                  <span><i className="sw sw-ivory" /> In line with history</span>
                  <span className="muted">Dot size follows market cap; values beyond −20% / 50% are pinned to the edge.</span>
                </div>
              </Panel>
              <Panel className="span-4" eyebrow="By sector" title="Median growth priced in">
                <SectorBars medians={data.summary.sector_median_implied_growth} active={sector} onPick={setSector} />
              </Panel>
            </div>
            <Panel eyebrow={`${sorted.length} companies · computed ${shortDate(data.computed_at)}`} title="Every company, ranked" flush>
              <div className="table-wrap radar-table">
                <table className="fin-table">
                  <thead>
                    <tr>
                      <th>Company</th><th>Sector</th>
                      {header('implied_growth', model === 'excess_return' ? 'ROE priced in' : 'Growth priced in')}
                      {header('historical_cagr', model === 'excess_return' ? 'Current ROE' : 'Historical CAGR')}
                      {header('expectations_gap', 'Gap')}
                      {header('implied_return', 'Implied return')}
                      {header('scenario_upside', 'Baseline upside')}
                      {header('market_cap_usd', 'Mkt cap (USD)')}
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.slice(0, 400).map((r) => <RadarTableRow key={r.ticker} r={r} onHover={setHighlight} />)}
                  </tbody>
                </table>
              </div>
            </Panel>
            <p className="footnote muted">{data.methodology}</p>
          </>
        )}
      </Gate>
    </div>
  )
}

function RadarTableRow({ r, onHover }: { r: RadarRow; onHover: (ticker: string | null) => void }) {
  const financial = r.model === 'excess_return'
  const implied = financial ? r.implied_roe : r.implied_growth
  const history = financial ? r.current_roe : r.historical_cagr
  const reachable = r.status !== 'NOT_REACHABLE'
  return (
    <tr onPointerEnter={() => onHover(r.ticker)} onPointerLeave={() => onHover(null)}>
      <td>
        <Link to={`/c/${r.ticker}/expectations`} className="peer-link">
          <span className="mono">{r.ticker}</span>
          <span className="peer-name">{r.company_name}</span>
          <span className="peer-meta muted">{r.country === 'India' ? 'IN' : 'US'}</span>
        </Link>
      </td>
      <td className="muted">{r.sector}</td>
      <td className="num gold">{reachable ? pct(implied) : <span className="muted">out of reach</span>}</td>
      <td className="num">{pct(history)}</td>
      <td className={cn('num', (r.expectations_gap ?? 0) > 0.05 ? 'gold' : (r.expectations_gap ?? 0) < -0.05 ? 'aurora' : '')}>{points(r.expectations_gap)}</td>
      <td className="num">{pct(r.implied_return)}</td>
      <td className={cn('num', (r.scenario_upside ?? 0) >= 0 ? 'pos' : 'neg')}>{pct(r.scenario_upside, 0, { signed: true })}</td>
      <td className="num">{money(r.market_cap_usd, 'USD')}</td>
    </tr>
  )
}

function SectorBars({ medians, active, onPick }: { medians: Record<string, number>; active: string | null; onPick: (sector: string | null) => void }) {
  const entries = Object.entries(medians).sort((a, b) => b[1] - a[1])
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01)
  return (
    <ul className="sector-bars">
      {entries.map(([name, value]) => (
        <li key={name} className={cn(active === name && 'on')}>
          <button type="button" onClick={() => onPick(active === name ? null : name)}>
            <span>{name}</span>
            <i><b className={value < 0 ? 'neg' : ''} style={{ width: `${(Math.abs(value) / max) * 100}%` }} /></i>
            <em className="num">{pct(value)}</em>
          </button>
        </li>
      ))}
    </ul>
  )
}
