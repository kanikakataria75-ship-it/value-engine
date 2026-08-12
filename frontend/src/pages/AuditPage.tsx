import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, Panel, StatusBadge } from '../components/ui'
import type { Company } from '../types/api'

export function AuditPage({ ticker }: { ticker: string }) {
  const company = useQuery({ queryKey: ['company', ticker], queryFn: () => api.company(ticker) })
  const health = useQuery({ queryKey: ['health', ticker], queryFn: () => api.health(ticker) })
  const quality = useQuery({ queryKey: ['quality', ticker], queryFn: () => api.quality(ticker) })
  const c = company.data?.data as Company | undefined
  const provenance = company.data?.provenance || {}
  const flags = health.data?.data.flags as string[] | undefined
  const issues = quality.data?.data.issues as Record<string, unknown>[] | undefined
  const isLive = company.data?.status === 'LIVE'
  const auditRows = [
    { Item: 'Data Source', Status: String(provenance.source || 'UNAVAILABLE'), Detail: String(provenance.source_name || 'UNAVAILABLE') },
    { Item: 'Provider', Status: isLive ? 'CONFIGURED' : 'UNAVAILABLE', Detail: isLive ? 'Alpha Vantage live provider returned normalized data' : String(provenance.notice || 'Alpha Vantage unavailable') },
    { Item: 'Ticker', Status: c?.ticker || 'UNAVAILABLE', Detail: c?.company_name || 'UNAVAILABLE' },
    { Item: 'Period', Status: String(provenance.period || 'UNAVAILABLE'), Detail: String(provenance.retrieved_at || provenance.retrieved_date || 'UNAVAILABLE') },
    { Item: 'Data Quality', Status: quality.data?.status || 'LOADING', Detail: `${issues?.length ?? '—'} recorded validation findings` },
    { Item: 'Model Health', Status: health.data?.status || 'LOADING', Detail: `${flags?.length ?? '—'} diagnostic flags returned` },
  ]
  return <>
    <CompanyHeader company={c} modelStatus={health.data?.status || 'LOADING'} />
    <div className="page-title"><div><p className="eyebrow">OUTPUTS / AUDIT</p><h1>Provenance & Model Audit</h1></div><StatusBadge status={company.data?.status || 'LOADING'} /></div>
    <div className="audit-banner"><div className="audit-seal">✓</div><div><span>AUDIT STATUS</span><strong>{isLive ? 'LIVE DATA' : 'DEMONSTRATION DATA'}</strong><p>{isLive ? 'Live Alpha Vantage inputs have been normalized, labelled with provenance, and passed through the existing data-quality gate before reaching the financial engines.' : 'Alpha Vantage unavailable. All displayed outputs originate from the existing local financial engines and their labelled demonstration inputs.'}</p></div><a href="/data">Open Data Workspace →</a></div>
    <div className="double-panel"><Panel eyebrow="AUDIT TRAIL" title="Source & Validation Register"><FinancialTable rows={auditRows} /></Panel><Panel eyebrow="ENGINE STATUS" title="Model Diagnostics"><DataState status={health.data?.status || 'LOADING'} errors={health.data?.errors}><ul className="flags audit-flags">{flags?.map(flag => <li key={flag}>{flag}</li>) || <li>No model diagnostics returned.</li>}</ul></DataState></Panel></div>
    <Panel eyebrow="DATA QUALITY" title="Validation Findings"><DataState status={quality.data?.status || 'LOADING'} errors={quality.data?.errors}><FinancialTable rows={issues || [{ Severity: 'INFORMATION', Message: 'No data-quality issues returned.' }]} /></DataState></Panel>
  </>
}
