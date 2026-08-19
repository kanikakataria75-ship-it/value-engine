import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import {
  CompanyHeader,
  DataState,
  FinancialTable,
  Heatmap,
  MetricCard,
  Panel,
  money,
  pct,
} from '../components/ui'
import type { Company, Dcf, DataMode } from '../types/api'

export function DcfPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const [assumptions, setAssumptions] = useState({
    ticker,
    revenue_growth_rate: 0.07,
    ebitda_margin: 0.25,
    wacc: 0.085,
    terminal_growth_rate: 0.025,
    projection_years: 5,
    tax_rate: 0.21,
    mid_year_convention: false,
  })

  if (assumptions.ticker !== ticker) {
    setAssumptions((prev) => ({ ...prev, ticker }))
  }

  const c = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const result = useQuery({
    queryKey: ['dcf', assumptions, dataMode],
    queryFn: () => api.dcf(assumptions, dataMode),
  })

  const sensitivity = useQuery({
    queryKey: ['sensitivity', assumptions, dataMode],
    queryFn: () => api.sensitivity(assumptions, dataMode),
  })

  const d = result.data?.data as Dcf | undefined
  const company = c.data?.data as Company | undefined
  const curr = company?.currency || (ticker.endsWith('.NSE') ? 'INR' : 'USD')

  const set = (key: string, value: string | boolean | number) =>
    setAssumptions((prev) => ({
      ...prev,
      [key]: typeof value === 'boolean' ? value : Number(value),
    }))

  return (
    <>
      <CompanyHeader company={company} modelStatus={result.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">VALUATION MODEL</p>
          <h1>Discounted Cash Flow (DCF)</h1>
        </div>
        <span className="model-note">
          Institutional multi-stage UFCF model calculated by the Python DCF engine.
        </span>
      </div>

      <div className="workspace-grid">
        <Panel eyebrow="ASSUMPTIONS" title="Forecast Drivers" className="assumptions">
          <Input
            label="Revenue Growth"
            value={assumptions.revenue_growth_rate}
            onChange={(v) => set('revenue_growth_rate', v)}
          />
          <Input
            label="EBITDA Margin"
            value={assumptions.ebitda_margin}
            onChange={(v) => set('ebitda_margin', v)}
          />
          <Input
            label="Discount Rate (WACC)"
            value={assumptions.wacc}
            onChange={(v) => set('wacc', v)}
          />
          <Input
            label="Terminal Growth Rate"
            value={assumptions.terminal_growth_rate}
            onChange={(v) => set('terminal_growth_rate', v)}
          />
          <Input
            label="Effective Tax Rate"
            value={assumptions.tax_rate}
            onChange={(v) => set('tax_rate', v)}
          />
          <div className="input-row switch-row">
            <span>Mid-Year Convention</span>
            <label className="switch">
              <input
                type="checkbox"
                checked={assumptions.mid_year_convention}
                onChange={(e) => set('mid_year_convention', e.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>
          <p className="caption">
            Base financials are loaded from {dataMode === 'local' ? 'verified local SQLite store' : 'live provider'}.
          </p>
        </Panel>

        <div>
          <DataState status={result.data?.status || 'LOADING'} errors={result.data?.errors} dataMode={dataMode}>
            <div className="metrics-grid four">
              <MetricCard
                label="DCF Implied Share Price"
                value={money(d?.implied_share_price, true, curr)}
                detail="Intrinsic value per share"
              />
              <MetricCard
                label="Upside / Downside"
                value={pct((d?.upside_downside_pct || 0) / 100)}
                tone={(d?.upside_downside_pct || 0) >= 0 ? 'positive' : 'negative'}
                detail={`vs. ${money(company?.current_price, true, curr)} market`}
              />
              <MetricCard
                label="Enterprise Value"
                value={money(d?.enterprise_value, false, curr)}
                detail="PV of UFCF + PV of TV"
              />
              <MetricCard
                label="Equity Value"
                value={money(d?.equity_value, false, curr)}
                detail="EV - Net Debt"
              />
            </div>

            <Panel eyebrow="PROJECTIONS" title="5-Year Unlevered Free Cash Flow (UFCF) Schedule">
              <FinancialTable rows={d?.projections_df || []} currency={curr} />
            </Panel>
          </DataState>
        </div>
      </div>

      <div className="double-panel">
        <Panel eyebrow="SENSITIVITY MATRIX" title="WACC × Terminal Growth Rate">
          <DataState status={sensitivity.data?.status || 'LOADING'} errors={sensitivity.data?.errors} dataMode={dataMode}>
            <Heatmap
              rows={(sensitivity.data?.data?.terminal_growth_values as number[]) || []}
              cols={(sensitivity.data?.data?.wacc_values as number[]) || []}
              values={(sensitivity.data?.data?.wacc_terminal as (number | null)[][]) || []}
              format="price"
              rowLabel="Terminal Growth"
              colLabel="WACC"
              currency={curr}
              baseRowIdx={2}
              baseColIdx={2}
            />
          </DataState>
        </Panel>

        <Panel eyebrow="SENSITIVITY MATRIX" title="Revenue Growth × EBITDA Margin">
          <DataState status={sensitivity.data?.status || 'LOADING'} errors={sensitivity.data?.errors} dataMode={dataMode}>
            <Heatmap
              rows={(sensitivity.data?.data?.ebitda_margin_values as number[]) || []}
              cols={(sensitivity.data?.data?.revenue_growth_values as number[]) || []}
              values={(sensitivity.data?.data?.revenue_margin as (number | null)[][]) || []}
              format="price"
              rowLabel="EBITDA Margin"
              colLabel="Revenue Growth"
              currency={curr}
              baseRowIdx={2}
              baseColIdx={2}
            />
          </DataState>
        </Panel>
      </div>
    </>
  )
}

function Input({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: string) => void
}) {
  return (
    <label className="input-row">
      <span>{label}</span>
      <div className="input-with-unit">
        <input
          type="number"
          step="0.005"
          value={isNaN(value) ? '' : (value * 100).toFixed(1)}
          onChange={(e) => onChange(String(Number(e.target.value) / 100))}
        />
        <b>%</b>
      </div>
    </label>
  )
}
