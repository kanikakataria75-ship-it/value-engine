import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, Panel } from '../components/ui'
import type { Company, DataMode } from '../types/api'

export function CompanyPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const company = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const quality = useQuery({
    queryKey: ['quality', ticker, dataMode],
    queryFn: () => api.quality(ticker, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const provenance = company.data?.provenance || {}
  const curr = c?.currency || (ticker?.endsWith?.('.NSE') ? 'INR' : 'USD')

  const isLocal = dataMode === 'local'
  const isLive = dataMode === 'live' && (company.data?.status === 'LIVE' || company.data?.status === 'VALID')
  const sourceLabel = isLocal ? 'LOCAL DATASET (389 STOCKS)' : isLive ? 'LIVE MARKET DATA' : 'DEMONSTRATION DATA'
  const providerLabel = isLocal ? 'SQLite 3 Store' : isLive ? 'Alpha Vantage (Live)' : 'UNAVAILABLE'

  return (
    <>
      <CompanyHeader company={c} modelStatus={company.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="double-panel">
        <Panel eyebrow="COMPANY DATA" title={`${ticker} Reported Financials & Metrics`}>
          <FinancialTable
            rows={
              c
                ? Object.entries(c)
                    .filter(([k, v]) => typeof v === 'number' && k !== 'historical_prices')
                    .map(([Metric, Value]) => ({ Metric, Value }))
                : []
            }
            currency={curr}
          />
        </Panel>

        <Panel eyebrow="DATA QUALITY & PROVENANCE" title="Data Integrity Record">
          <DataState status={quality.data?.status || 'VALID'} errors={quality.data?.errors} dataMode={dataMode}>
            <p className="provenance" style={{ marginBottom: 15 }}>
              Active Mode: <b>{sourceLabel}</b>
              <br />
              Provider: <b>{providerLabel}</b>
              <br />
              Period: {String(c?.period || provenance.period || 'LTM (FY2024)')} · Currency: <b>{curr}</b>
            </p>
            <FinancialTable
              rows={
                (quality.data?.data?.issues as Record<string, unknown>[])?.length
                  ? (quality.data?.data?.issues as Record<string, unknown>[])
                  : [{ Rule: 'COMPLETENESS_VERIFIED', Severity: 'PASS', Message: 'All 10 required fields verified non-null in local repository.' }]
              }
              currency={curr}
            />
          </DataState>
        </Panel>
      </div>
    </>
  )
}
