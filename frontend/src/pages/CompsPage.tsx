import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, MetricCard, Panel, money } from '../components/ui'
import type { Company, DataMode } from '../types/api'

export function CompsPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const company = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const trading = useQuery({
    queryKey: ['trading-comps', ticker, dataMode],
    queryFn: () => api.tradingComps(ticker, dataMode),
  })

  const transaction = useQuery({
    queryKey: ['transaction-comps', ticker, dataMode],
    queryFn: () => api.transactionComps(ticker, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const td = trading.data?.data || {}
  const xd = transaction.data?.data || {}
  const curr = c?.currency || (ticker.endsWith('.NSE') ? 'INR' : 'USD')

  const peerList = (td.peer_multiples_df as Record<string, unknown>[]) || []
  const dist = td.distribution_df as Record<string, Record<string, unknown>> | undefined

  return (
    <>
      <CompanyHeader company={c} modelStatus={trading.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">MARKET BENCHMARKING</p>
          <h1>Comparable Companies Analysis (Trading Comps)</h1>
        </div>
        <span className="model-note">
          {dataMode === 'local'
            ? `Sector Peer Universe (${c?.sector || 'All Sectors'}) from 389-stock institutional database.`
            : 'Live Market Comps from configured provider.'}
        </span>
      </div>

      <DataState status={trading.data?.status || 'LOADING'} errors={trading.data?.errors} dataMode={dataMode}>
        <div className="metrics-grid four">
          <MetricCard
            label="Median Implied Share Price"
            value={money(td.implied_share_price_median as number, true, curr)}
            detail="Implied by sector EV/EBITDA median"
          />
          <MetricCard
            label="Active Peer Universe"
            value={`${peerList.length} Companies`}
            detail={`${c?.sector || 'Sector'} peers`}
          />
          <MetricCard
            label="Benchmark Source"
            value={dataMode === 'local' ? 'Local DB (389)' : 'Live Provider'}
            detail="Peer fundamentals database"
          />
          <MetricCard
            label="Precedent Transactions"
            value="UNAVAILABLE"
            detail="No verified M&A deal database"
          />
        </div>

        <Panel eyebrow="PEER MULTIPLES" title={`Peer Universe Multiples (${c?.sector || 'Sector'} Benchmarking)`}>
          <FinancialTable rows={peerList} currency={curr} />
        </Panel>

        <Panel eyebrow="STATISTICAL DISTRIBUTION" title="Multiples Distribution Quartiles">
          <FinancialTable rows={statsRows(dist)} currency={curr} />
        </Panel>
      </DataState>

      <Panel eyebrow="PRECEDENT TRANSACTIONS" title="Transaction Comparables">
        <DataState status={transaction.data?.status || 'LOADING'} errors={transaction.data?.errors} dataMode={dataMode}>
          <FinancialTable rows={(xd.transaction_multiples_df as Record<string, unknown>[]) || []} currency={curr} />
        </DataState>
      </Panel>
    </>
  )
}

function statsRows(stats?: Record<string, Record<string, unknown>>) {
  if (!stats) return []
  return Object.entries(stats).map(([metric, values]) => ({
    Metric: metric,
    ...values,
  }))
}
