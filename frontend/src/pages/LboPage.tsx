import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, FinancialTable, MetricCard, Panel, money, pct } from '../components/ui'
import type { Company, Lbo, DataMode } from '../types/api'

export function LboPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const [input, setInput] = useState({
    ticker,
    entry_multiple: 10,
    senior_debt_pct: 0.4,
    sub_debt_pct: 0.2,
    senior_rate: 0.08,
    sub_rate: 0.1,
    exit_multiple: 11,
    revenue_growth: 0.07,
    ebitda_margin: 0.25,
  })

  if (input.ticker !== ticker) {
    setInput((prev) => ({ ...prev, ticker }))
  }

  const company = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const q = useQuery({
    queryKey: ['lbo', input, dataMode],
    queryFn: () => api.lbo(input, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const l = q.data?.data as Lbo | undefined
  const curr = c?.currency || (ticker.endsWith('.NSE') ? 'INR' : 'USD')

  const set = (key: string, value: string, scale = 1) =>
    setInput((p) => ({ ...p, [key]: Number(value) / scale }))

  const maxBridgeVal = Math.max(
    Math.abs(l?.attr_ebitda_growth || 0),
    Math.abs(l?.attr_multiple_expansion || 0),
    Math.abs(l?.attr_debt_paydown || 0),
    Math.abs(l?.attr_cash_generation || 0),
    1
  )

  return (
    <>
      <CompanyHeader company={c} modelStatus={q.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">PRIVATE EQUITY RETURNS</p>
          <h1>LBO Leveraged Buyout Model</h1>
        </div>
        <span className="model-note">
          Debt waterfall, mandatory amortization, and 100% cash sweep calculated by the Python LBO engine.
        </span>
      </div>

      <DataState status={q.data?.status || 'LOADING'} errors={q.data?.errors} dataMode={dataMode}>
        <div className="metrics-grid four">
          <MetricCard
            label="Sponsor 5Y IRR"
            value={pct(l?.irr)}
            tone={(l?.irr || 0) >= 0.2 ? 'positive' : 'neutral'}
            detail="Annualized equity return"
          />
          <MetricCard
            label="Exit MOIC"
            value={l && typeof l.moic === 'number' ? `${l.moic.toFixed(2)}x` : '—'}
            detail="Multiple on invested capital"
          />
          <MetricCard
            label="Entry Enterprise Value"
            value={money(l?.entry_ev, false, curr)}
            detail="Sponsor entry valuation"
          />
          <MetricCard
            label="Exit Equity Value"
            value={money(l?.exit_equity, false, curr)}
            detail="Exit EV minus residual debt"
          />
        </div>

        <div className="workspace-grid">
          <Panel eyebrow="UNDERWRITING" title="Entry & Exit Assumptions" className="assumptions">
            <LboInput
              label="Entry EV / EBITDA"
              value={input.entry_multiple}
              suffix="x"
              update={(v) => set('entry_multiple', v)}
            />
            <LboInput
              label="Senior Debt Share"
              value={input.senior_debt_pct}
              suffix="%"
              scale={100}
              update={(v) => set('senior_debt_pct', v, 100)}
            />
            <LboInput
              label="Subordinated Debt"
              value={input.sub_debt_pct}
              suffix="%"
              scale={100}
              update={(v) => set('sub_debt_pct', v, 100)}
            />
            <LboInput
              label="Exit EV / EBITDA"
              value={input.exit_multiple}
              suffix="x"
              update={(v) => set('exit_multiple', v)}
            />
            <LboInput
              label="Revenue Growth"
              value={input.revenue_growth}
              suffix="%"
              scale={100}
              update={(v) => set('revenue_growth', v, 100)}
            />
            <LboInput
              label="EBITDA Margin"
              value={input.ebitda_margin}
              suffix="%"
              scale={100}
              update={(v) => set('ebitda_margin', v, 100)}
            />
          </Panel>

          <Panel eyebrow="VALUE CREATION" title="Returns Attribution Bridge">
            <div className="attribution">
              <Bridge label="EBITDA Growth" value={l?.attr_ebitda_growth} maxVal={maxBridgeVal} currency={curr} />
              <Bridge label="Multiple Expansion" value={l?.attr_multiple_expansion} maxVal={maxBridgeVal} currency={curr} />
              <Bridge label="Debt Paydown" value={l?.attr_debt_paydown} maxVal={maxBridgeVal} currency={curr} />
              <Bridge label="Cash Generation" value={l?.attr_cash_generation} maxVal={maxBridgeVal} currency={curr} />
            </div>
          </Panel>
        </div>

        <Panel eyebrow="DEBT SCHEDULE" title="5-Year Mandatory Paydown & Cash Sweep Waterfall">
          <FinancialTable rows={l?.schedule_df || []} currency={curr} />
        </Panel>
      </DataState>
    </>
  )
}

function LboInput({
  label,
  value,
  suffix,
  scale = 1,
  update,
}: {
  label: string
  value: number
  suffix: string
  scale?: number
  update: (v: string) => void
}) {
  return (
    <label className="input-row">
      <span>{label}</span>
      <div className="input-with-unit">
        <input
          type="number"
          step={scale === 100 ? 0.5 : 0.25}
          value={isNaN(value) ? '' : (value * scale).toFixed(scale === 100 ? 1 : 2)}
          onChange={(e) => update(e.target.value)}
        />
        <b>{suffix}</b>
      </div>
    </label>
  )
}

function Bridge({
  label,
  value,
  maxVal,
  currency = 'USD',
}: {
  label: string
  value?: number
  maxVal: number
  currency?: string
}) {
  const val = value || 0
  const widthPct = Math.min(100, Math.max(6, (Math.abs(val) / maxVal) * 100))
  return (
    <div className="bridge-row">
      <span className="bridge-label">{label}</span>
      <div className="bridge-track">
        <i
          className={val >= 0 ? 'positive' : 'negative'}
          style={{ width: `${widthPct}%` }}
        />
      </div>
      <strong className="bridge-val">{money(value, false, currency)}</strong>
    </div>
  )
}
