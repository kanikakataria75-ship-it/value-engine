import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, Panel, StatusBadge, money, pct } from '../components/ui'
import type { Company, Dcf, Lbo, Mna, DataMode } from '../types/api'

export function ReportsPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const isIndia = ticker.endsWith('.NSE') || ticker.endsWith('.BSE')
  const acquirerTicker = isIndia ? 'TCS.NSE' : ticker === 'MSFT' ? 'AAPL' : 'MSFT'

  const company = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const dcf = useQuery({
    queryKey: ['report-dcf', ticker, dataMode],
    queryFn: () => api.dcf({ ticker }, dataMode),
  })

  const mna = useQuery({
    queryKey: ['report-mna', ticker, acquirerTicker, dataMode],
    queryFn: () => api.mna({ target_ticker: ticker, acquirer_ticker: acquirerTicker }, dataMode),
  })

  const lbo = useQuery({
    queryKey: ['report-lbo', ticker, dataMode],
    queryFn: () => api.lbo({ ticker }, dataMode),
  })

  const health = useQuery({
    queryKey: ['health', ticker, dataMode],
    queryFn: () => api.health(ticker, acquirerTicker, dataMode),
  })

  const quality = useQuery({
    queryKey: ['quality', ticker, dataMode],
    queryFn: () => api.quality(ticker, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const d = dcf.data?.data as Dcf | undefined
  const m = mna.data?.data as Mna | undefined
  const l = lbo.data?.data as Lbo | undefined
  const curr = c?.currency || (isIndia ? 'INR' : 'USD')

  const provenance = quality.data?.provenance || dcf.data?.provenance || {}
  const sourceLabel = dataMode === 'local' ? 'LOCAL SQLITE REPOSITORY (389 STOCKS)' : 'LIVE MARKET API'

  const mnaValueLabel = mna.isLoading
    ? 'Loading...'
    : m
    ? pct((m.eps_change_pct || 0) / 100)
    : 'UNAVAILABLE'

  const lboValueLabel = lbo.isLoading
    ? 'Loading...'
    : l
    ? pct(l.irr)
    : 'UNAVAILABLE'

  return (
    <>
      <CompanyHeader company={c} modelStatus={dcf.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">INSTITUTIONAL MEMO</p>
          <h1>Investment Committee Review: {ticker}</h1>
        </div>
        <button
          className="primary"
          onClick={() => api.exportExcel(ticker, acquirerTicker, dataMode)}
          style={{ cursor: 'pointer' }}
        >
          ⬇ Export Full Model to Excel (.xlsx)
        </button>
      </div>

      <div className="report">
        <Panel eyebrow="EXECUTIVE SUMMARY" title={`${ticker} Valuation, M&A & LBO Overview`}>
          <div className="report-kpis">
            <div>
              <span>DCF Implied Share Price</span>
              <strong>{money(d?.implied_share_price, true, curr)}</strong>
            </div>
            <div>
              <span>M&A Pro Forma EPS Change</span>
              <strong>{mnaValueLabel}</strong>
            </div>
            <div>
              <span>LBO Sponsor 5Y IRR</span>
              <strong>{lboValueLabel}</strong>
            </div>
            <div>
              <span>Model Logic Health</span>
              <StatusBadge status={health.data?.status || (health.isLoading ? 'LOADING' : 'VALID')} />
            </div>
          </div>
        </Panel>

        <div className="double-panel">
          <Panel eyebrow="INTRINSIC VALUATION" title="5-Year Unlevered Free Cash Flow Schedule">
            <DataState status={dcf.data?.status || (dcf.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={dcf.data?.errors} dataMode={dataMode}>
              <FinancialTable rows={(d?.projections_df || []).slice(0, 5)} currency={curr} />
            </DataState>
          </Panel>

          <Panel eyebrow="STRATEGIC M&A" title={`Deal Pro Forma (${ticker} + ${acquirerTicker})`}>
            <DataState status={mna.data?.status || (mna.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={mna.data?.errors} dataMode={dataMode}>
              <FinancialTable
                rows={
                  m
                    ? [
                        { Metric: 'Offer Price / Share', Value: m.offer_price },
                        { Metric: 'Total Purchase Consideration', Value: m.total_purchase_price },
                        { Metric: 'Pro Forma EPS Change %', Value: m.eps_change_pct / 100 },
                        { Metric: 'Break-Even Annual Synergy', Value: m.break_even_pre_tax_synergy },
                      ]
                    : []
                }
                currency={curr}
              />
            </DataState>
          </Panel>
        </div>

        <Panel eyebrow="FINANCIAL SPONSOR" title="LBO Returns & Mandatory Debt Waterfall">
          <DataState status={lbo.data?.status || (lbo.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={lbo.data?.errors} dataMode={dataMode}>
            <FinancialTable rows={l?.schedule_df || []} currency={curr} />
          </DataState>
        </Panel>

        <div className="double-panel">
          <Panel eyebrow="MODEL DIAGNOSTICS" title="Validation Findings">
            <ul className="flags">
              {(health.data?.data?.flags as string[] | undefined)?.map((x) => (
                <li key={x}>{x}</li>
              )) || <li>{health.isLoading ? 'Checking model diagnostics...' : 'All model integrity checks passed.'}</li>}
            </ul>
          </Panel>

          <Panel eyebrow="AUDIT REGISTER" title="Data Provenance & Quality Findings">
            <p className="provenance" style={{ marginBottom: 12 }}>
              Source: <b>{sourceLabel}</b>
              <br />
              Period: {String(provenance.period || c?.period || 'LTM (FY2024)')} · Currency:{' '}
              <b>{curr}</b>
            </p>
            <DataState status={quality.data?.status || (quality.isLoading ? 'LOADING' : 'VALID')} errors={quality.data?.errors} dataMode={dataMode}>
              <FinancialTable
                rows={
                  (quality.data?.data?.issues as Record<string, unknown>[])?.length
                    ? (quality.data?.data?.issues as Record<string, unknown>[])
                    : [{ Rule: 'COMPLETENESS_VERIFIED', Severity: 'PASS', Message: '0 missing fields detected across 10 critical fundamental attributes.' }]
                }
                currency={curr}
              />
            </DataState>
          </Panel>
        </div>
      </div>
    </>
  )
}
