import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { DataState, FinancialTable, Panel, StatusBadge, money } from '../components/ui'
import type { Dcf, Lbo, Mna } from '../types/api'

export function ReportsPage({ ticker }: { ticker: string }) {
  const acquirerTicker = ticker === 'MSFT' ? 'AAPL' : 'MSFT'
  const dcf = useQuery({ queryKey: ['report-dcf', ticker], queryFn: () => api.dcf({ ticker }) })
  const mna = useQuery({ queryKey: ['report-mna', ticker, acquirerTicker], queryFn: () => api.mna({ target_ticker: ticker, acquirer_ticker: acquirerTicker }) })
  const lbo = useQuery({ queryKey: ['report-lbo', ticker], queryFn: () => api.lbo({ ticker }) })
  const health = useQuery({ queryKey: ['health', ticker], queryFn: () => api.health(ticker) })
  const quality = useQuery({ queryKey: ['quality', ticker], queryFn: () => api.quality(ticker) })

  const d = dcf.data?.data as Dcf | undefined
  const m = mna.data?.data as Mna | undefined
  const l = lbo.data?.data as Lbo | undefined
  const provenance = quality.data?.provenance || dcf.data?.provenance || {}
  const isLive = String(provenance.provenance || provenance.source_type) === 'LIVE'
  const sourceLabel = isLive ? 'LIVE DATA' : 'DEMONSTRATION DATA'

  const mnaValueLabel = mna.isLoading
    ? 'Loading...'
    : m
    ? `${m.eps_change_pct.toFixed(1)}%`
    : 'UNAVAILABLE'

  const lboValueLabel = lbo.isLoading
    ? 'Loading...'
    : l
    ? `${(l.irr * 100).toFixed(1)}%`
    : 'UNAVAILABLE'

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">ANALYST OUTPUT</p>
          <h1>Investment Committee Report</h1>
        </div>
        <button
          className="primary"
          onClick={() => api.exportExcel(ticker, acquirerTicker)}
        >
          Export to Excel
        </button>
      </div>
      <div className="report">
        <Panel eyebrow="EXECUTIVE SUMMARY" title={`${ticker} Valuation & Transaction Review`}>
          <div className="report-kpis">
            <div>
              <span>DCF Implied Value</span>
              <strong>{money(d?.implied_share_price, true)}</strong>
            </div>
            <div>
              <span>M&A EPS Change</span>
              <strong>{mnaValueLabel}</strong>
            </div>
            <div>
              <span>LBO IRR</span>
              <strong>{lboValueLabel}</strong>
            </div>
            <div>
              <span>Model Health</span>
              <StatusBadge status={health.data?.status || (health.isLoading ? 'LOADING' : 'UNAVAILABLE')} />
            </div>
          </div>
        </Panel>

        <div className="double-panel">
          <Panel eyebrow="VALUATION" title="DCF">
            <DataState status={dcf.data?.status || (dcf.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={dcf.data?.errors}>
              <FinancialTable rows={(d?.projections_df || []).slice(0, 5)} />
            </DataState>
          </Panel>
          <Panel eyebrow="M&A" title="Accretion / Dilution">
            <DataState status={mna.data?.status || (mna.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={mna.data?.errors}>
              <FinancialTable
                rows={
                  m
                    ? [
                        { Metric: 'Offer Price', Value: m.offer_price },
                        { Metric: 'Purchase Price', Value: m.total_purchase_price },
                        { Metric: 'EPS Change %', Value: m.eps_change_pct },
                        { Metric: 'Break-Even Synergy', Value: m.break_even_pre_tax_synergy },
                      ]
                    : []
                }
              />
            </DataState>
          </Panel>
        </div>

        <Panel eyebrow="LBO" title="Debt Paydown & Returns">
          <DataState status={lbo.data?.status || (lbo.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={lbo.data?.errors}>
            <FinancialTable rows={l?.schedule_df || []} />
          </DataState>
        </Panel>

        <div className="double-panel">
          <Panel eyebrow="MODEL HEALTH" title="Diagnostics">
            <ul className="flags">
              {(health.data?.data.flags as string[] | undefined)?.map((x) => (
                <li key={x}>{x}</li>
              )) || <li>{health.isLoading ? 'Loading model diagnostics...' : 'No model diagnostics returned.'}</li>}
            </ul>
          </Panel>
          <Panel eyebrow="DATA QUALITY & AUDIT TRAIL" title="Provenance">
            <p className="provenance">
              Source: <b>{sourceLabel}</b>
              <br />
              Live API: <b>{isLive ? 'CONFIGURED' : 'UNAVAILABLE'}</b>
              <br />
              Period: {String(provenance.period || 'UNAVAILABLE')} · Currency:{' '}
              {String(provenance.currency || 'UNAVAILABLE')}
            </p>
            <DataState status={quality.data?.status || (quality.isLoading ? 'LOADING' : 'UNAVAILABLE')} errors={quality.data?.errors}>
              <FinancialTable
                rows={
                  (quality.data?.data.issues as Record<string, unknown>[]) || [
                    { Severity: 'INFORMATION', Message: 'No data-quality issues returned.' },
                  ]
                }
              />
            </DataState>
          </Panel>
        </div>
      </div>
    </>
  )
}
