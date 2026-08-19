import { useQuery } from '@tanstack/react-query'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { api } from '../services/api'
import {
  CompanyHeader,
  DataState,
  Heatmap,
  MetricCard,
  Panel,
  StatusBadge,
  money,
  num,
  pct,
} from '../components/ui'
import type { Company, Dcf, Lbo, Mna, DataMode } from '../types/api'

type ModelStatus = { label: string; status?: string; value: string; detail: string; href: string }

export function Dashboard({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const company = useQuery({ queryKey: ['company', ticker, dataMode], queryFn: () => api.company(ticker, dataMode) })
  const dcf = useQuery({ queryKey: ['dashboard-dcf', ticker, dataMode], queryFn: () => api.dcf({ ticker }, dataMode) })
  const mna = useQuery({
    queryKey: ['dashboard-mna', ticker, dataMode],
    queryFn: () => api.mna({ target_ticker: ticker, acquirer_ticker: ticker === 'MSFT' ? 'AAPL' : 'MSFT' }, dataMode),
  })
  const lbo = useQuery({ queryKey: ['dashboard-lbo', ticker, dataMode], queryFn: () => api.lbo({ ticker }, dataMode) })
  const comps = useQuery({ queryKey: ['dashboard-comps', ticker, dataMode], queryFn: () => api.tradingComps(ticker, dataMode) })
  const transactions = useQuery({ queryKey: ['dashboard-transaction-comps', ticker, dataMode], queryFn: () => api.transactionComps(ticker, dataMode) })
  const health = useQuery({ queryKey: ['health', ticker, dataMode], queryFn: () => api.health(ticker, 'MSFT', dataMode) })
  const quality = useQuery({ queryKey: ['quality', ticker, dataMode], queryFn: () => api.quality(ticker, dataMode) })
  const sensitivity = useQuery({
    queryKey: ['dashboard-sensitivity', ticker, dataMode],
    queryFn: () => api.sensitivity({ ticker, revenue_growth_rate: 0.07, ebitda_margin: 0.25, wacc: 0.085, terminal_growth_rate: 0.025 }, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const d = dcf.data?.data as Dcf | undefined
  const m = mna.data?.data as Mna | undefined
  const l = lbo.data?.data as Lbo | undefined
  const dealQuality = health.data?.data?.deal_quality as { score?: number | string } | undefined
  const flags = health.data?.data?.flags as string[] | undefined
  const issues = quality.data?.data?.issues as { severity: string }[] | undefined
  const curr = c?.currency || (ticker?.endsWith?.('.NSE') ? 'INR' : 'USD')

  const prices = c?.historical_prices || []
  const chartData = prices.slice(-120).map((p) => ({
    date: p.date.length > 5 ? p.date.slice(5) : p.date,
    close: p.close,
  }))

  const football = [
    { label: 'DCF Intrinsic Value', value: d?.implied_share_price, type: 'indigo', status: dcf.data?.status },
    { label: 'Trading Comps Median', value: comps.data?.data?.implied_share_price_median as number | undefined, type: 'violet', status: comps.data?.status },
    { label: 'Transaction Comps', value: transactions.data?.data?.implied_share_price_median as number | undefined, type: 'muted', status: transactions.data?.status || 'UNAVAILABLE' },
    { label: 'Current Market Price', value: c?.current_price, type: 'market', status: company.data?.status || 'VALID' },
  ]
  const availableValues = football.flatMap((item) => (item.value === undefined || item.value === null ? [] : [item.value]))
  const maximum = Math.max(...availableValues, 1)

  const modelCards: ModelStatus[] = [
    {
      label: 'DCF Model',
      status: dcf.data?.status,
      value: money(d?.implied_share_price, true, curr),
      detail: d && typeof d.upside_downside_pct === 'number' ? `${pct(d.upside_downside_pct / 100)} upside/downside` : 'Intrinsic cash flow valuation',
      href: '/dcf',
    },
    {
      label: 'M&A Model',
      status: mna.data?.status,
      value: m && typeof m.eps_change_pct === 'number' ? pct(m.eps_change_pct / 100) : 'UNAVAILABLE',
      detail: m?.is_accretive ? 'Accretive transaction' : 'Accretion / Dilution',
      href: '/mna',
    },
    {
      label: 'LBO Model',
      status: lbo.data?.status,
      value: l && typeof l.irr === 'number' ? pct(l.irr) : 'UNAVAILABLE',
      detail: l && typeof l.moic === 'number' ? `${l.moic.toFixed(2)}x MoIC · 5Y Exit` : 'Leveraged buyout returns',
      href: '/lbo',
    },
    {
      label: 'Trading Comps',
      status: comps.data?.status,
      value: money(comps.data?.data?.implied_share_price_median as number | undefined, true, curr),
      detail: `${dataMode === 'local' ? 'Sector peers (Local)' : 'Preset peers'}`,
      href: '/comps',
    },
    {
      label: 'Risk Lab',
      status: 'VALID',
      value: 'Monte Carlo / VaR',
      detail: 'Tail risk & structural stress',
      href: '/risk-lab',
    },
  ]

  return (
    <>
      <CompanyHeader company={c} modelStatus={company.data?.status || 'LOADING'} dataMode={dataMode} />

      <section className="dashboard-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">KEY FINANCIALS</p>
            <h2>Operating Snapshot</h2>
          </div>
          <span>{`LTM · ${curr} · ${dataMode === 'local' ? 'Local SQLite Dataset (389 Companies)' : 'Live Market Provider'}`}</span>
        </div>
        <div className="metrics-grid financial-grid">
          <MetricCard label="Revenue" value={money(c?.revenue, false, curr)} detail="LTM source revenue" />
          <MetricCard label="EBITDA" value={money(c?.ebitda, false, curr)} detail="Operating cash profitability" />
          <MetricCard label="EBIT" value={money(c?.ebit, false, curr)} detail="Operating earnings" />
          <MetricCard label="Net Income" value={money(c?.net_income, false, curr)} detail="Bottom line GAAP earnings" />
          <MetricCard label="Cash & Equivalents" value={money(c?.cash_and_equivalents, false, curr)} detail="Balance sheet liquid assets" />
          <MetricCard label="Total Debt" value={money(c?.total_debt, false, curr)} detail="Short + long-term debt" />
          <MetricCard label="Shares Outstanding" value={num(c?.shares_outstanding)} detail="Total shares (diluted)" />
          <MetricCard label="Market Cap" value={money(c?.market_cap, false, curr)} detail="Implied equity market cap" />
        </div>
      </section>

      <div className="dashboard-grid hero-grid">
        <Panel
          eyebrow="VALUATION TRIANGULATION"
          title="Implied Value vs. Market"
          className="football"
          action={<span className="panel-meta">{curr} / share</span>}
        >
          <DataState status={dcf.data?.status || 'LOADING'} errors={dcf.data?.errors} dataMode={dataMode}>
            {football.map((item) => (
              <div className="field-row" key={item.label}>
                <span className="field-label">{item.label}</span>
                {item.value === undefined || item.value === null ? (
                  <div className="field-unavailable">
                    <StatusBadge status={item.status || 'UNAVAILABLE'} />
                  </div>
                ) : (
                  <div className="field-track">
                    <i className={item.type} style={{ width: `${Math.min(100, Math.max(8, (item.value / maximum) * 92))}%` }} />
                  </div>
                )}
                <strong className="field-value">
                  {item.value === undefined || item.value === null ? 'UNAVAILABLE' : money(item.value, true, curr)}
                </strong>
              </div>
            ))}
            <p className="caption">
              Transaction comps remain unavailable until a verified precedent-transactions dataset is configured.
            </p>
          </DataState>
        </Panel>

        <Panel eyebrow="MODEL HEALTH" title="Validation Control Center" action={<StatusBadge status={health.data?.status || 'LOADING'} />}>
          <div className="health-overview">
            <div className="health-score">
              <strong>
                {dealQuality?.score === 'UNAVAILABLE'
                  ? 'UNAVAILABLE'
                  : dealQuality?.score === undefined
                  ? '—'
                  : String(Math.round(Number(dealQuality.score)))}
              </strong>
              <span>Deal / Model Quality</span>
            </div>
            <div className="health-grid">
              <HealthItem label="Data Quality" value={quality.data?.status || 'LOADING'} />
              <HealthItem label="Model Logic" value={health.data?.status || 'LOADING'} />
              <HealthItem label="Completeness" value={issues?.length === 0 ? 'VALID' : issues ? 'REVIEW_REQUIRED' : 'LOADING'} />
              <HealthItem label="Assumptions" value={flags?.length ? health.data?.status || 'LOADING' : 'VALID'} />
            </div>
          </div>
          <ul className="flags">
            {flags?.slice(0, 2).map((flag) => (
              <li key={flag}>{flag}</li>
            )) || <li>Checking model diagnostics…</li>}
          </ul>
        </Panel>
      </div>

      <div className="dashboard-grid lower-grid">
        <Panel eyebrow="MARKET PERFORMANCE" title={`Price History (${prices.length} Days)`}>
          {chartData.length > 0 ? (
            <div style={{ height: 230, width: '100%' }}>
              <ResponsiveContainer>
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={11} minTickGap={25} />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    domain={['auto', 'auto']}
                    tickFormatter={(v) => money(v, false, curr)}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 6 }}
                    formatter={(val: number) => [money(val, true, curr), 'Close Price']}
                    labelFormatter={(lbl) => `Date: ${lbl}`}
                  />
                  <Area type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#priceGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="unavailable-art">
              <span className="badge unavailable">HISTORICAL DATA UNAVAILABLE</span>
              <p>Historical price records unavailable for this asset.</p>
            </div>
          )}
        </Panel>

        <Panel eyebrow="SENSITIVITY SNAPSHOT" title="WACC × Terminal Growth" action={<a className="inline-link" href="/dcf">Open DCF →</a>}>
          <DataState status={sensitivity.data?.status || 'LOADING'} errors={sensitivity.data?.errors} dataMode={dataMode}>
            <div className="mini-heatmap">
              <Heatmap
                rows={(sensitivity.data?.data?.terminal_growth_values as number[]) || []}
                cols={(sensitivity.data?.data?.wacc_values as number[]) || []}
                values={(sensitivity.data?.data?.wacc_terminal as (number | null)[][]) || []}
                format="price"
                currency={curr}
              />
            </div>
          </DataState>
        </Panel>
      </div>

      <section className="dashboard-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">MODELS</p>
            <h2>Active Valuation & Risk Engines</h2>
          </div>
          <span>Institutional Python & R calculations</span>
        </div>
        <div className="model-grid model-grid-five">
          {modelCards.map((card) => (
            <ModelCard key={card.label} {...card} />
          ))}
        </div>
      </section>
    </>
  )
}

function HealthItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <StatusBadge status={value} />
    </div>
  )
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
