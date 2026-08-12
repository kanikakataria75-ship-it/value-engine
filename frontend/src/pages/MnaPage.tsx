import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { DataState, MetricCard, Panel, money, pct } from '../components/ui'
import type { Mna } from '../types/api'

export function MnaPage({ ticker }: { ticker: string }) {
  const [input, setInput] = useState({ target_ticker: ticker, acquirer_ticker: ticker === 'MSFT' ? 'AAPL' : 'MSFT', offer_premium_pct: .25, pct_cash: .5, pct_stock: .5, debt_interest_rate: .08, revenue_synergies: 0, incremental_margin: .20, cost_synergies: 0, integration_costs: 0, tax_rate: .21 })
  if (input.target_ticker !== ticker) setInput({ ...input, target_ticker: ticker })
  const q = useQuery({ queryKey: ['mna', input], queryFn: () => api.mna(input) })
  const m = q.data?.data as Mna | undefined
  const provenance = q.data?.provenance || {}
  const sourceNote = String(provenance.provenance || provenance.source_type) === 'LIVE' ? 'Live Alpha Vantage source data' : 'Demonstration source data'
  const update = (key: string, value: string) => setInput(p => ({ ...p, [key]: Number(value) }))

  return <>
    <div className="page-title"><div><p className="eyebrow">TRANSACTION INTELLIGENCE</p><h1>{input.target_ticker} x {input.acquirer_ticker} Deal Room</h1></div><span className="model-note">{sourceNote}</span></div>
    <DataState status={q.data?.status || 'LOADING'} errors={q.data?.errors}>
      <div className="metrics-grid four"><MetricCard label="Offer Price" value={money(m?.offer_price, true)} /><MetricCard label="Purchase Price" value={money(m?.total_purchase_price)} /><MetricCard label="Pro Forma EPS" value={money(m?.post_deal_eps, true)} /><MetricCard label="Accretion / Dilution" value={pct((m?.eps_change_pct || 0) / 100)} tone={m?.is_accretive ? 'positive' : 'negative'} /></div>
      <div className="workspace-grid"><Panel eyebrow="DEAL TERMS" title="Consideration & Synergies" className="assumptions"><Select label="Acquirer" value={input.acquirer_ticker} onChange={v => setInput(p => ({ ...p, acquirer_ticker: v }))} /><Term label="Offer Premium" value={input.offer_premium_pct} update={v => update('offer_premium_pct', v)} suffix="%" scale={100} /><Term label="Cash Consideration" value={input.pct_cash} update={v => update('pct_cash', v)} suffix="%" scale={100} /><Term label="Stock Consideration" value={input.pct_stock} update={v => update('pct_stock', v)} suffix="%" scale={100} /><Term label="Revenue Synergies" value={input.revenue_synergies} update={v => update('revenue_synergies', v)} suffix="$" scale={1} /><Term label="Cost Synergies" value={input.cost_synergies} update={v => update('cost_synergies', v)} suffix="$" scale={1} /><Term label="Integration Costs" value={input.integration_costs} update={v => update('integration_costs', v)} suffix="$" scale={1} /></Panel><div className="stack"><Panel eyebrow="OUTCOME" title={m?.is_accretive ? 'Accretive Transaction' : 'Dilutive Transaction'}><div className="bridge"><Bridge label="Pre-Tax Synergies" value={m?.pre_tax_synergies} /><Bridge label="After-Tax Integration" value={m?.after_tax_integration === undefined ? undefined : -m.after_tax_integration} /><Bridge label="EPS Change" value={m?.eps_change_pct} percentage /></div></Panel><Panel eyebrow="BREAK-EVEN" title="Synergy Requirement"><div className="large-output">{money(m?.break_even_pre_tax_synergy)}<span>pre-tax synergy required for accretion</span></div></Panel></div></div>
    </DataState>
  </>
}

function Term({ label, value, update, suffix, scale }: { label: string; value: number; update: (v: string) => void; suffix: string; scale: number }) { return <label className="input-row"><span>{label}</span><div><input type="number" step={scale === 100 ? .5 : 1000000} value={(value * scale).toFixed(scale === 100 ? 1 : 0)} onChange={e => update(String(Number(e.target.value) / scale))} /><b>{suffix}</b></div></label> }
function Select({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) { return <label className="input-row"><span>{label}</span><select value={value} onChange={e => onChange(e.target.value)}><option>AAPL</option><option>MSFT</option><option>NVDA</option></select></label> }
function Bridge({ label, value, percentage = false }: { label: string; value?: number; percentage?: boolean }) { const unavailable = value === undefined; return <div className="bridge-row"><span>{label}</span><i className={unavailable || (value || 0) >= 0 ? 'positive' : 'negative'} style={{ width: `${unavailable ? 8 : Math.min(100, Math.max(8, Math.abs(value || 0) / (percentage ? 10 : 1e10) * 100))}%` }} /><strong>{unavailable ? 'UNAVAILABLE' : percentage ? `${value.toFixed(1)}%` : money(value)}</strong></div> }
