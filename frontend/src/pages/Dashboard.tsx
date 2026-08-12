import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, Heatmap, MetricCard, Panel, StatusBadge, money, num, pct } from '../components/ui'
import type { Company, Dcf, Lbo, Mna } from '../types/api'

type ModelStatus = { label: string; status?: string; value: string; detail: string; href: string }

export function Dashboard({ ticker }: { ticker: string }) {
  const company = useQuery({ queryKey: ['company', ticker], queryFn: () => api.company(ticker) })
  const dcf = useQuery({ queryKey: ['dashboard-dcf', ticker], queryFn: () => api.dcf({ ticker }) })
  const mna = useQuery({ queryKey: ['dashboard-mna', ticker], queryFn: () => api.mna({ target_ticker: ticker, acquirer_ticker: ticker === 'MSFT' ? 'AAPL' : 'MSFT' }) })
  const lbo = useQuery({ queryKey: ['dashboard-lbo', ticker], queryFn: () => api.lbo({ ticker }) })
  const comps = useQuery({ queryKey: ['dashboard-comps', ticker], queryFn: () => api.tradingComps(ticker) })
  const transactions = useQuery({ queryKey: ['dashboard-transaction-comps', ticker], queryFn: () => api.transactionComps(ticker) })
  const health = useQuery({ queryKey: ['health', ticker], queryFn: () => api.health(ticker) })
  const quality = useQuery({ queryKey: ['quality', ticker], queryFn: () => api.quality(ticker) })
  const sensitivity = useQuery({ queryKey: ['dashboard-sensitivity', ticker], queryFn: () => api.sensitivity({ ticker, revenue_growth_rate: 0.07, ebitda_margin: 0.25, wacc: 0.085, terminal_growth_rate: 0.025 }) })

  const c = company.data?.data as Company | undefined
  const d = dcf.data?.data as Dcf | undefined
  const m = mna.data?.data as Mna | undefined
  const l = lbo.data?.data as Lbo | undefined
  const dealQuality = health.data?.data.deal_quality as { score?: number | string } | undefined
  const flags = health.data?.data.flags as string[] | undefined
  const issues = quality.data?.data.issues as { severity: string }[] | undefined
  const provenance = (company.data?.provenance as Record<string, unknown>) || {}

  const football = [
    { label: 'DCF', value: d?.implied_share_price, type: 'indigo', status: dcf.data?.status },
    { label: 'Trading Comps', value: comps.data?.data.implied_share_price_median as number | undefined, type: 'violet', status: comps.data?.status },
    { label: 'Transaction Comps', value: transactions.data?.data.implied_share_price_median as number | undefined, type: 'muted', status: transactions.data?.status || 'UNAVAILABLE' },
    { label: 'Current Price', value: c?.current_price, type: 'market', status: company.data?.status || 'DEMO' },
  ]
  const availableValues = football.flatMap(item => (item.value === undefined || item.value === null ? [] : [item.value]))
  const maximum = Math.max(...availableValues, 1)

  const modelCards: ModelStatus[] = [
    { label: 'DCF', status: dcf.data?.status, value: money(d?.implied_share_price, true), detail: d ? pct(d.upside_downside_pct / 100) : 'Intrinsic value', href: '/dcf' },
    { label: 'M&A', status: mna.data?.status, value: m ? pct(m.eps_change_pct / 100) : 'UNAVAILABLE', detail: m?.is_accretive ? 'Accretive transaction' : 'Accretion / dilution', href: '/mna' },
    { label: 'LBO', status: lbo.data?.status, value: l ? pct(l.irr) : 'UNAVAILABLE', detail: l ? `${l.moic.toFixed(2)}x MoIC` : 'Leveraged underwriting', href: '/lbo' },
    { label: 'Trading Comps', status: comps.data?.status, value: money(comps.data?.data.implied_share_price_median as number | undefined, true), detail: 'Peer median valuation', href: '/comps' },
    { label: 'Transaction Comps', status: transactions.data?.status || 'UNAVAILABLE', value: 'UNAVAILABLE', detail: 'No verified transaction dataset', href: '/comps' },
  ]

  return (
    <>
      <CompanyHeader company={c} modelStatus={company.data?.status || 'LOADING'} />
      <section className="dashboard-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">KEY FINANCIALS</p>
            <h2>Operating Snapshot</h2>
          </div>
          <span>{`LTM · ${String(provenance.currency || 'USD')} · ${company.data?.status === 'LIVE' ? 'Live data' : 'Demonstration data'}`}</span>
        </div>
        <div className="metrics-grid financial-grid">
          <MetricCard label="Revenue" value={money(c?.revenue)} detail="LTM source financials" />
          <MetricCard label="EBITDA" value={money(c?.ebitda)} detail="LTM source financials" />
          <MetricCard label="EBIT" value={money(c?.ebit)} detail="LTM source financials" />
          <MetricCard label="Net Income" value={money(c?.net_income)} detail="LTM source financials" />
          <MetricCard label="Free Cash Flow" value="UNAVAILABLE" detail="Not supplied by current API" />
          <MetricCard label="Cash" value={money(c?.cash_and_equivalents)} detail="Balance sheet" />
          <MetricCard label="Total Debt" value={money(c?.total_debt)} detail="Balance sheet" />
          <MetricCard label="Shares Outstanding" value={num(c?.shares_outstanding)} detail="Basic shares" />
        </div>
      </section>

      <div className="dashboard-grid hero-grid">
        <Panel eyebrow="VALUATION TRIANGULATION" title="Implied Value vs. Market" className="football" action={<span className="panel-meta">USD / share</span>}>
          <DataState status={dcf.data?.status || 'LOADING'} errors={dcf.data?.errors}>
            {football.map(item => (
              <div className="field-row" key={item.label}>
                <span>{item.label}</span>
                {item.value === undefined || item.value === null ? (
                  <div className="field-unavailable">
                    <StatusBadge status={item.status || 'UNAVAILABLE'} />
                  </div>
                ) : (
                  <div className="field-track">
                    <i className={item.type} style={{ width: `${Math.min(100, (item.value / maximum) * 90)}%` }} />
                  </div>
                )}
                <strong>{item.value === undefined || item.value === null ? 'UNAVAILABLE' : money(item.value, true)}</strong>
              </div>
            ))}
            <p className="caption">Transaction comps remain unavailable because the backend has not been supplied a verified precedent-transactions dataset.</p>
          </DataState>
        </Panel>
        <Panel eyebrow="MODEL HEALTH" title="Validation Control Center" action={<StatusBadge status={health.data?.status || 'LOADING'} />}>
          <div className="health-overview">
            <div className="health-score">
              <strong>{dealQuality?.score === 'UNAVAILABLE' ? 'UNAVAILABLE' : dealQuality?.score === undefined ? '—' : String(Math.round(Number(dealQuality.score)))}</strong>
              <span>Deal / Model Quality</span>
            </div>
            <div className="health-grid">
              <HealthItem label="Data Quality" value={quality.data?.status || 'LOADING'} />
              <HealthItem label="Model Logic" value={health.data?.status || 'LOADING'} />
              <HealthItem label="Completeness" value={issues?.length === 0 ? 'VALID' : issues ? 'REVIEW_REQUIRED' : 'LOADING'} />
              <HealthItem label="Assumptions" value={flags?.length ? health.data?.status || 'LOADING' : 'VALID'} />
            </div>
          </div>
          <ul className="flags">{flags?.slice(0, 2).map(flag => <li key={flag}>{flag}</li>) || <li>Checking model diagnostics…</li>}</ul>
        </Panel>
      </div>

      <div className="dashboard-grid lower-grid">
        <Panel eyebrow="MARKET PERFORMANCE" title="Historical Price" className="unavailable-panel">
          <div className="unavailable-art">
            <div className="ghost-line" />
            <div className="ghost-line short" />
            <span className="badge unavailable">HISTORICAL DATA UNAVAILABLE</span>
            <p>Live historical market data is not configured. No chart has been generated.</p>
          </div>
        </Panel>
        <Panel eyebrow="SENSITIVITY SNAPSHOT" title="WACC × Terminal Growth" action={<a className="inline-link" href="/dcf">Open DCF →</a>}>
          <DataState status={sensitivity.data?.status || 'LOADING'} errors={sensitivity.data?.errors}>
            <div className="mini-heatmap">
              <Heatmap rows={(sensitivity.data?.data.terminal_growth_values as number[]) || []} cols={(sensitivity.data?.data.wacc_values as number[]) || []} values={(sensitivity.data?.data.wacc_terminal as (number | null)[][]) || []} format="price" />
            </div>
          </DataState>
        </Panel>
      </div>

      <section className="dashboard-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">MODELS</p>
            <h2>Active Analysis</h2>
          </div>
          <span>Validated engine outputs</span>
        </div>
        <div className="model-grid model-grid-five">{modelCards.map(card => <ModelCard key={card.label} {...card} />)}</div>
      </section>

      <div className="dashboard-grid lower-grid">
        <Panel eyebrow="SCENARIO ANALYSIS" title="Base · Bull · Bear">
          <div className="empty-state compact">
            <StatusBadge status="UNAVAILABLE" />
            <p>Scenario outputs are not available from the current backend contract. No values have been inferred.</p>
          </div>
        </Panel>
        <Panel eyebrow="RECENT MODELS / REPORTS" title="Current Workspace">
          <div className="recent-list">
            {modelCards.slice(0, 4).map(model => (
              <a href={model.href} key={model.label}>
                <span>{model.label}</span>
                <StatusBadge status={model.status || 'LOADING'} />
                <small>Open model →</small>
              </a>
            ))}
          </div>
        </Panel>
      </div>
    </>
  )
}

function HealthItem({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><StatusBadge status={value} /></div>
}

function ModelCard({ label, value, detail, href, status }: ModelStatus) {
  return (
    <a className="model-card" href={href}>
      <div className="model-card-top">
        <p>{label}</p>
        <StatusBadge status={status || 'LOADING'} />
      </div>
      <span>{detail}</span>
      <strong>{value}</strong>
      <small>Open Model →</small>
    </a>
  )
}
