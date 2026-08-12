import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, Panel, StatusBadge } from '../components/ui'
import type { Company } from '../types/api'

export function DataPage({ ticker }: { ticker: string }) {
  const company = useQuery({ queryKey: ['company', ticker], queryFn: () => api.company(ticker) })
  const quality = useQuery({ queryKey: ['quality', ticker], queryFn: () => api.quality(ticker) })
  const c = company.data?.data as Company | undefined
  const provenance = company.data?.provenance || {}
  const issues = quality.data?.data.issues as Record<string, unknown>[] | undefined
  const isLive = company.data?.status === 'LIVE'
  const statusLabel = isLive ? 'LIVE DATA' : 'DEMONSTRATION DATA'
  const sourceLabel = String(provenance.source_name || (isLive ? 'Alpha Vantage' : 'ValuEngine Preset'))
  const providerStatus = isLive ? 'CONFIGURED' : 'UNAVAILABLE'
  return <>
    <CompanyHeader company={c} modelStatus={company.data?.status || 'LOADING'} />
    <div className="page-title"><div><p className="eyebrow">RESEARCH / DATA</p><h1>Data Workspace</h1></div><StatusBadge status={company.data?.status || 'LOADING'} /></div>
    <div className="data-hero"><div><span>DATA STATUS</span><strong>{statusLabel}</strong><p>{isLive ? `Source: ${sourceLabel}. Provider data has passed through the existing normalization and data-quality gate.` : 'Alpha Vantage unavailable. This workspace is backed by the labelled local preset used by the existing financial engines.'}</p></div><div className="data-hero-meta"><Meta label="Source" value={sourceLabel} /><Meta label="Period" value={String(provenance.period || 'UNAVAILABLE')} /><Meta label="Currency" value={String(provenance.currency || 'UNAVAILABLE')} /><Meta label="Updated" value={String(provenance.retrieved_at || provenance.retrieved_date || 'UNAVAILABLE')} /></div></div>
    <div className="double-panel"><Panel eyebrow="DATASET" title="Company Source Financials"><FinancialTable rows={c ? Object.entries(c).filter(([, value]) => typeof value === 'number').map(([Metric, Value]) => ({ Metric, Value })) : []} /></Panel><Panel eyebrow="VALIDATION" title="Completeness & Checks"><div className="validation-stack"><div><span>Provider</span><strong>{String(provenance.source_name || 'UNAVAILABLE')}</strong></div><div><span>Validation status</span><StatusBadge status={quality.data?.status || 'LOADING'} /></div><div><span>Completeness</span><strong>UNAVAILABLE</strong><small>Current backend contract does not return a completeness score.</small></div><div><span>Live provider</span><strong>{providerStatus}</strong></div></div></Panel></div>
    <Panel eyebrow="DATA QUALITY" title="Validation Findings"><DataState status={quality.data?.status || 'LOADING'} errors={quality.data?.errors}><FinancialTable rows={issues || [{ Severity: 'INFORMATION', Message: 'No data-quality issues returned.' }]} /></DataState></Panel>
  </>
}

function Meta({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div> }
