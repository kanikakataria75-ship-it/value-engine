import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FootballField } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { Gate, PageTitle, Panel, Stat } from '../../components/ui'
import type { CompsResult, MultipleStats, PeerRow } from '../../lib/api-types'
import { money, multiple, pct, priceTag } from '../../lib/format'
import { ok, problem, useComps } from '../../lib/queries'
import { cn } from '../../lib/utils'

const MULTIPLES = ['ev_ebitda', 'ev_revenue', 'pe', 'pb'] as const
type MultipleKey = (typeof MULTIPLES)[number]
const COLUMNS = ['ev_revenue', 'ev_ebitda', 'pe', 'pb'] as const
const COLUMN_LABELS: Record<MultipleKey, string> = { ev_revenue: 'EV / Rev', ev_ebitda: 'EV / EBITDA', pe: 'P / E', pb: 'P / B' }
const TONES = ['gold', 'aurora', 'violet', 'ivory'] as const

export function Comps() {
  const { ticker, company } = useCompanyContext()
  const q = useComps(ticker)
  const data = ok(q.data)
  return (
    <div className="page">
      <PageTitle eyebrow="Trading comparables · relative value"
                 title={<>What <em>similar companies</em> say it is worth</>}
                 lede={`Up to twelve same-sector peers are scored on industry, country and size (log distance in USD market cap). Negative or extreme multiples are set aside, and the peer median ${company.balance_sheet_financial ? 'price-to-book' : 'EV / EBITDA'} is the primary anchor.`} />
      <Gate loading={q.isLoading} error={problem(q.data)} minHeight={360} label="Assembling the peer set">
        {data && <CompsBody data={data} />}
      </Gate>
    </div>
  )
}

function CompsBody({ data }: { data: CompsResult }) {
  const { company } = useCompanyContext()
  const ccy = data.currency
  const primary = data.primary_multiple as MultipleKey
  const own = data.target_multiples[primary]
  const median = data.distribution[primary]?.median
  const premium = own !== null && own !== undefined && median ? own / median - 1 : null

  const ranges = useMemo(() => Object.entries(data.implied_by_multiple)
    .filter(([, r]) => r.low !== null && r.low !== undefined && r.high !== null && r.high !== undefined)
    .map(([key, r], i) => ({ key, label: r.label, low: r.low as number, high: r.high as number, mid: r.mid, tone: key === primary ? 'gold' : TONES[(i % 3) + 1] })), [data, primary])

  return (
    <>
      <div className="stat-row">
        <Panel><Stat size="lg" label={`Implied value · ${data.primary_label} median`} value={money(data.implied_share_price_median, ccy, { precise: true })}
                     sub={<span className={cn(data.upside !== null && data.upside !== undefined && data.upside >= 0 ? 'pos' : 'neg')}>{pct(data.upside, 1, { signed: true })} vs market</span>} /></Panel>
        <Panel><Stat size="lg" label="Interquartile value range" value={`${priceTag(data.implied_range.low, ccy)} – ${priceTag(data.implied_range.high, ccy)}`}
                     sub={`25th to 75th percentile peer ${data.primary_label}`} /></Panel>
        <Panel><Stat size="lg" label={`${company.company_name.split(' ')[0]} trades at`} value={multiple(own)}
                     sub={premium === null ? 'no comparable multiple' : <span className={premium > 0 ? 'neg' : 'pos'}>{pct(Math.abs(premium), 0)} {premium > 0 ? 'premium to' : 'discount to'} the peer median</span>} /></Panel>
        <Panel><Stat size="lg" label="Peer set" value={`${data.peer_count} companies`} sub={`${data.same_industry_count} in the same industry`} /></Panel>
      </div>

      <div className="grid">
        <Panel className="span-7" eyebrow="Relative position" title="Where it sits inside the peer distribution">
          <div className="boxstrips">
            {MULTIPLES.filter((k) => data.distribution[k]).map((key) => (
              <BoxStrip key={key} stats={data.distribution[key]} own={data.target_multiples[key]} primary={key === primary} />
            ))}
          </div>
          <p className="footnote muted">Whiskers span the peer minimum to maximum once negative or extreme multiples are set aside, the box is the interquartile range and the line is the median. The gold diamond is the company itself.</p>
        </Panel>
        <Panel className="span-5" eyebrow="Implied share value" title="Each multiple, applied to the company">
          {ranges.length ? <FootballField ranges={ranges} market={company.current_price ?? 0} format={(v) => money(v, ccy)} />
            : <p className="muted">No multiple produced a usable range.</p>}
        </Panel>
      </div>

      <Panel eyebrow="Peer set" title="Closest comparables, ranked by similarity" flush>
        <PeerTable peers={data.peers} primary={primary} target={data.target_multiples} />
      </Panel>
      <p className="footnote muted">{data.methodology}</p>
    </>
  )
}

function BoxStrip({ stats, own, primary }: { stats: MultipleStats; own: number | null | undefined; primary: boolean }) {
  const hasOwn = own !== null && own !== undefined && Number.isFinite(own)
  const lo = Math.min(stats.min, hasOwn ? own : stats.min)
  const hi = Math.max(stats.max, hasOwn ? own : stats.max)
  const pad = (hi - lo) * 0.06 || 1
  const pos = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100
  return (
    <div className={cn('boxstrip', primary && 'primary')}>
      <div className="boxstrip-label">
        <b>{stats.label}</b>
        <span className="muted">n = {stats.n}{stats.excluded_outliers ? ` · ${stats.excluded_outliers} outlier${stats.excluded_outliers > 1 ? 's' : ''} excluded` : ''}</span>
      </div>
      <div className="boxstrip-track">
        <i className="whisker" style={{ left: `${pos(stats.min)}%`, width: `${pos(stats.max) - pos(stats.min)}%` }} />
        <i className="box" style={{ left: `${pos(stats.p25)}%`, width: `${Math.max(0.5, pos(stats.p75) - pos(stats.p25))}%` }} />
        <i className="median" style={{ left: `${pos(stats.median)}%` }}><span className="num">{multiple(stats.median)}</span></i>
        {hasOwn && <i className="own" style={{ left: `${pos(own)}%` }}><span className="num">{multiple(own)}</span></i>}
      </div>
    </div>
  )
}

type SortKey = 'similarity' | 'market_cap_usd' | MultipleKey

function PeerTable({ peers, primary, target }: { peers: PeerRow[]; primary: MultipleKey; target: Record<string, number | null> }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'similarity', dir: -1 })
  const rows = useMemo(() => [...peers].sort((a, b) => {
    const av = a[sort.key] ?? -Infinity
    const bv = b[sort.key] ?? -Infinity
    return (av > bv ? 1 : av < bv ? -1 : 0) * sort.dir
  }), [peers, sort])
  const maxSim = Math.max(...peers.map((p) => p.similarity ?? 0), 1e-9)
  const minSim = Math.min(...peers.map((p) => p.similarity ?? 0))
  const header = (key: SortKey, label: string, className = 'num') => (
    <th key={key} className={cn(className, 'sortable', sort.key === key && 'sorted', key === primary && 'primary')}
        onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : -1 }))}
        aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      {label}{sort.key === key ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''}
    </th>
  )
  return (
    <div className="table-wrap">
      <table className="fin-table peers">
        <thead>
          <tr>
            <th>Company</th>
            {header('similarity', 'Similarity', '')}
            {header('market_cap_usd', 'Mkt cap (USD)')}
            {COLUMNS.map((k) => header(k, COLUMN_LABELS[k]))}
          </tr>
        </thead>
        <tbody>
          <tr className="target-row">
            <td><span className="pill pill-gold">This company</span></td>
            <td />
            <td />
            {COLUMNS.map((k) => (
              <td key={k} className={cn('num', k === primary && 'primary')}>{multiple(target[k], k === 'pb' ? 2 : 1)}</td>
            ))}
          </tr>
          {rows.map((p) => {
            const sim = p.similarity === null || p.similarity === undefined ? 0 : (p.similarity - minSim) / (maxSim - minSim || 1)
            return (
              <tr key={p.ticker}>
                <td>
                  <Link to={`/c/${p.ticker}`} className="peer-link">
                    <span className="mono">{p.ticker}</span>
                    <span className="peer-name">{p.company_name}</span>
                    <span className="peer-meta muted">{p.country === 'India' ? 'IN' : 'US'} · {p.industry}{p.same_industry ? '' : ' · adjacent'}</span>
                  </Link>
                </td>
                <td><div className="sim-bar"><i style={{ width: `${12 + sim * 88}%` }} /></div></td>
                <td className="num">{money(p.market_cap_usd, 'USD')}</td>
                {COLUMNS.map((k) => (
                  <td key={k} className={cn('num', k === primary && 'primary')}>{multiple(p[k], k === 'pb' ? 2 : 1)}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
