import { Heatmap, Waterfall } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconReset } from '../../components/icons'
import { NumberField, Toggle } from '../../components/NumberField'
import { AnimatedNumber, Flags, Gate, KeyValues, Meter, PageTitle, Panel, Segmented, StatusPill } from '../../components/ui'
import type { DcfResult, ExcessReturnResult } from '../../lib/api-types'
import { money, multiple, pct, priceTag } from '../../lib/format'
import { ok, problem, useIntrinsic, useSensitivity } from '../../lib/queries'
import { useScenario } from '../../lib/scenario'

export function Valuation() {
  const { ticker, company, baseline } = useCompanyContext()
  const bank = company.balance_sheet_financial
  return (
    <div className="page">
      <PageTitle eyebrow={bank ? 'Excess-return model · banks & insurers' : 'Discounted cash flow · free cash flow to the firm'}
                 title={bank ? <>Value from <em>returns above</em> the cost of equity</> : <>What the business is <em>worth</em> on your assumptions</>}
                 lede={bank ? 'For balance-sheet businesses, debt is raw material rather than financing, so value is book equity plus the present value of returns above the cost of equity.'
                   : 'Every assumption starts at the company baseline (gold tick). Drag a label to scrub, drag the track, or type a value; the model recomputes instantly.'} />
      {bank ? <ExcessReturnWorkbench ticker={ticker} /> : <DcfWorkbench ticker={ticker} />}
      {!baseline && <div className="muted">Loading company baseline…</div>}
    </div>
  )
}

function DcfWorkbench({ ticker }: { ticker: string }) {
  const { company, baseline } = useCompanyContext()
  const { scenario, setDcf, reset } = useScenario(ticker)
  const q = useIntrinsic(ticker)
  const result = ok(q.data) as DcfResult | undefined
  const sens = ok(useSensitivity(ticker).data)
  const base = baseline?.dcf
  const d = scenario.dcf ?? {}
  const ccy = company.currency
  const w = baseline?.wacc_build
  const method = d.terminal_method ?? base?.terminal_method ?? 'perpetuity'

  return (
    <div className="workbench">
      <aside className="console">
        <div className="console-head">
          <span className="eyebrow">Assumptions</span>
          {scenario.dcf && <button type="button" className="link-quiet" onClick={() => reset('dcf')}><IconReset size={12} /> Baseline</button>}
        </div>
        <div className="console-group">
          <h4>Growth & margins</h4>
          <NumberField label="Revenue growth / yr" value={d.revenue_growth} baseline={base?.revenue_growth} min={-0.1} max={0.4} step={0.0025}
                       onChange={(v) => setDcf({ revenue_growth: v })} />
          <NumberField label="Target EBITDA margin" value={d.ebitda_margin} baseline={base?.ebitda_margin} min={-0.1} max={0.85} step={0.005}
                       onChange={(v) => setDcf({ ebitda_margin: v })} hint={`Latest actual ${pct(result?.current_margin ?? base?.ebitda_margin)} · ramps linearly to the target`} />
          <NumberField label="Projection years" unit="years" value={d.projection_years} baseline={base?.projection_years} min={3} max={10} step={1}
                       onChange={(v) => setDcf({ projection_years: v })} />
        </div>
        <div className="console-group">
          <h4>Discounting</h4>
          <NumberField label="WACC" value={d.wacc} baseline={base?.wacc} min={0.03} max={0.2} step={0.0005} digits={2}
                       onChange={(v) => setDcf({ wacc: v })} />
          <Segmented id="tv-method" size="sm" value={method} onChange={(v) => setDcf({ terminal_method: v === base?.terminal_method ? null : v })}
                     options={[{ value: 'perpetuity', label: 'Perpetuity' }, { value: 'exit_multiple', label: 'Exit multiple' }]} />
          {method === 'perpetuity' ? (
            <>
              <NumberField label="Terminal growth" value={d.terminal_growth} baseline={base?.terminal_growth} min={-0.01} max={0.07} step={0.0005} digits={2}
                           onChange={(v) => setDcf({ terminal_growth: v })} />
              <NumberField label="RONIC (terminal)" value={d.ronic} baseline={base?.ronic} min={0.03} max={0.6} step={0.005}
                           onChange={(v) => setDcf({ ronic: v })} hint="Return on new capital: sets how much growth must be reinvested" />
            </>
          ) : (
            <NumberField label="Exit EV / EBITDA" unit="x" value={d.exit_multiple} baseline={base?.exit_multiple} min={2} max={40} step={0.25}
                         onChange={(v) => setDcf({ exit_multiple: v })} />
          )}
          <Toggle label="Mid-year discounting" checked={d.mid_year_convention ?? base?.mid_year_convention ?? true}
                  onChange={(v) => setDcf({ mid_year_convention: v === base?.mid_year_convention ? null : v })} />
        </div>
        <div className="console-group">
          <h4>Reinvestment & tax</h4>
          <NumberField label="CapEx / revenue" value={d.capex_pct} baseline={base?.capex_pct} min={0} max={0.4} step={0.0025} onChange={(v) => setDcf({ capex_pct: v })} />
          <NumberField label="D&A / revenue" value={d.da_pct} baseline={base?.da_pct} min={0} max={0.3} step={0.0025} onChange={(v) => setDcf({ da_pct: v })} />
          <NumberField label="NWC / Δ revenue" value={d.nwc_pct} baseline={base?.nwc_pct} min={-0.2} max={0.4} step={0.005} onChange={(v) => setDcf({ nwc_pct: v })} />
          <NumberField label="Tax rate" value={d.tax_rate} baseline={base?.tax_rate} min={0} max={0.4} step={0.0025} onChange={(v) => setDcf({ tax_rate: v })} />
        </div>
        {w && (
          <div className="wacc-build">
            <div className="eyebrow muted">Baseline WACC build</div>
            <div className="wacc-stack">
              <i className="eq" style={{ flex: w.weight_equity }} title="Equity weight" />
              <i className="dt" style={{ flex: Math.max(0.001, w.weight_debt) }} title="Debt weight" />
            </div>
            <KeyValues rows={[
              ['Risk-free rate', pct(w.risk_free_rate, 2)],
              [`Beta (${w.beta_source.split(' (')[0]})`, w.beta.toFixed(2)],
              ['Equity risk premium', pct(w.equity_risk_premium, 1)],
              ['Cost of equity', pct(w.cost_of_equity, 2), 'gold'],
              ['After-tax cost of debt', pct(w.after_tax_cost_of_debt, 2)],
              ['Debt weight', pct(w.weight_debt, 0)],
            ]} />
          </div>
        )}
      </aside>

      <div className="results">
        <Gate loading={q.isLoading && !result} error={problem(q.data)} minHeight={300}>
          {result && (
            <>
              <Panel className="result-hero" flush>
                <div className="result-hero-grid">
                  <div>
                    <div className="eyebrow">Implied value per share</div>
                    <div className="hero-number num"><AnimatedNumber value={result.implied_share_price} format={(v) => money(v, ccy, { precise: true })} /></div>
                    <div className={`num ${(result.upside ?? 0) >= 0 ? 'pos' : 'neg'}`}>{pct(result.upside, 1, { signed: true })} versus {money(result.current_price, ccy, { precise: true })}</div>
                  </div>
                  <div className="result-hero-side">
                    <StatusPill status={q.data?.status} />
                    <div className="tv-share">
                      <span>Terminal value share of EV</span>
                      <Meter value={result.terminal_share_of_ev ?? 0} tone={(result.terminal_share_of_ev ?? 0) > 0.85 ? 'neg' : 'gold'} />
                      <b className="num">{pct(result.terminal_share_of_ev, 0)}</b>
                    </div>
                    <KeyValues rows={[
                      ['Enterprise value', money(result.enterprise_value, ccy)],
                      ['Implied EV / EBITDA', multiple(result.implied_ev_ebitda)],
                      ['ROIC vs WACC', `${pct(result.roic)} vs ${pct(result.inputs.wacc)}`],
                    ]} />
                  </div>
                </div>
              </Panel>
              <Panel eyebrow="Bridge" title="From cash flows to equity value">
                <Waterfall height={230} format={(v) => money(v, ccy)} steps={[
                  { label: 'PV of FCF', value: result.pv_ufcf_sum },
                  { label: 'PV of terminal', value: result.pv_terminal_value },
                  { label: 'Enterprise value', value: result.enterprise_value, total: true },
                  { label: 'Less debt', value: -result.total_debt },
                  { label: 'Plus cash', value: result.cash },
                  { label: 'Equity value', value: result.equity_value, total: true },
                ]} />
              </Panel>
              <Panel eyebrow="Diagnostics" title="What the model is telling you">
                <Flags flags={result.flags} empty="No assumptions look stretched." />
              </Panel>
              <Panel eyebrow="Projection" title={`${result.inputs.projection_years}-year free cash flow build`} flush>
                <div className="table-wrap">
                  <table className="fin-table">
                    <thead>
                      <tr><th />{result.projections.map((p) => <th key={p.year} className="num">Year {p.year}</th>)}</tr>
                    </thead>
                    <tbody>
                      {([
                        ['Revenue', 'revenue', 'money'], ['EBITDA margin', 'ebitda_margin', 'pct'], ['EBITDA', 'ebitda', 'money'],
                        ['D&A', 'd_and_a', 'money'], ['EBIT', 'ebit', 'money'], ['Taxes', 'taxes', 'money'], ['NOPAT', 'nopat', 'money'],
                        ['CapEx', 'capex', 'money'], ['Change in NWC', 'delta_nwc', 'money'], ['Unlevered FCF', 'ufcf', 'money'],
                        ['Discount factor', 'discount_factor', 'fixed'], ['PV of FCF', 'pv_ufcf', 'money'],
                      ] as const).map(([label, key, kind]) => (
                        <tr key={key} className={key === 'ufcf' ? 'emph' : ''}>
                          <td>{label}</td>
                          {result.projections.map((p) => (
                            <td key={p.year} className="num">
                              {kind === 'pct' ? pct(p[key]) : kind === 'fixed' ? p[key].toFixed(3) : money(p[key], ccy)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </>
          )}
        </Gate>
        {sens && sens.method === 'dcf' && (
          <div className="grid-2">
            <Panel eyebrow="Sensitivity" title="Terminal growth × WACC">
              <Heatmap rows={sens.terminal_growth_values} cols={sens.wacc_values} values={sens.wacc_terminal} rowLabel="g" colLabel="WACC"
                       format={(v) => priceTag(v, ccy)} axisFormat={(v) => pct(v, 2)} reference={company.current_price} />
            </Panel>
            <Panel eyebrow="Sensitivity" title="Target margin × revenue growth">
              <Heatmap rows={sens.ebitda_margin_values} cols={sens.revenue_growth_values} values={sens.growth_margin} rowLabel="Margin" colLabel="Growth"
                       format={(v) => priceTag(v, ccy)} axisFormat={(v) => pct(v, 1)} reference={company.current_price} />
            </Panel>
          </div>
        )}
        <p className="footnote muted">Heatmap colours diverge around the market price: gold cells are worth more than today's price, ember cells less.</p>
      </div>
    </div>
  )
}

function ExcessReturnWorkbench({ ticker }: { ticker: string }) {
  const { company, baseline } = useCompanyContext()
  const { scenario, setExcessReturn, reset } = useScenario(ticker)
  const q = useIntrinsic(ticker)
  const result = ok(q.data) as ExcessReturnResult | undefined
  const sens = ok(useSensitivity(ticker).data)
  const base = baseline?.excess_return
  const e = scenario.excess_return ?? {}
  const ccy = company.currency

  return (
    <div className="workbench">
      <aside className="console">
        <div className="console-head">
          <span className="eyebrow">Assumptions</span>
          {scenario.excess_return && <button type="button" className="link-quiet" onClick={() => reset('excess_return')}><IconReset size={12} /> Baseline</button>}
        </div>
        <div className="console-group">
          <h4>Returns</h4>
          <NumberField label="Current ROE" value={e.roe} baseline={base?.roe} min={-0.05} max={0.4} step={0.0025} onChange={(v) => setExcessReturn({ roe: v })} />
          <NumberField label="Terminal ROE" value={e.terminal_roe} baseline={base?.terminal_roe} min={0} max={0.4} step={0.0025}
                       onChange={(v) => setExcessReturn({ terminal_roe: v })} hint="ROE fades linearly to this level" />
          <NumberField label="Cost of equity" value={e.cost_of_equity} baseline={base?.cost_of_equity} min={0.05} max={0.2} step={0.0005} digits={2}
                       onChange={(v) => setExcessReturn({ cost_of_equity: v })} />
        </div>
        <div className="console-group">
          <h4>Growth</h4>
          <NumberField label="Book value growth" value={e.book_growth} baseline={base?.book_growth} min={-0.05} max={0.25} step={0.0025}
                       onChange={(v) => setExcessReturn({ book_growth: v })} />
          <NumberField label="Terminal growth" value={e.terminal_growth} baseline={base?.terminal_growth} min={0} max={0.08} step={0.0005} digits={2}
                       onChange={(v) => setExcessReturn({ terminal_growth: v })} />
          <NumberField label="Projection years" unit="years" value={e.projection_years} baseline={base?.projection_years} min={3} max={10} step={1}
                       onChange={(v) => setExcessReturn({ projection_years: v })} />
        </div>
      </aside>
      <div className="results">
        <Gate loading={q.isLoading && !result} error={problem(q.data)} minHeight={300}>
          {result && (
            <>
              <Panel className="result-hero" flush>
                <div className="result-hero-grid">
                  <div>
                    <div className="eyebrow">Implied value per share</div>
                    <div className="hero-number num"><AnimatedNumber value={result.implied_share_price} format={(v) => money(v, ccy, { precise: true })} /></div>
                    <div className={`num ${(result.upside ?? 0) >= 0 ? 'pos' : 'neg'}`}>{pct(result.upside, 1, { signed: true })} versus {money(result.current_price, ccy, { precise: true })}</div>
                  </div>
                  <div className="result-hero-side">
                    <StatusPill status={q.data?.status} />
                    <KeyValues rows={[
                      ['Justified price / book', multiple(result.justified_pb, 2), 'gold'],
                      ['Market price / book', multiple(result.market_pb, 2)],
                      ['ROE the market implies', pct(result.market_implied_roe)],
                      ['Book value per share', money(result.book_value_per_share, ccy, { precise: true })],
                    ]} />
                  </div>
                </div>
              </Panel>
              <Panel eyebrow="Bridge" title="Book equity plus the value of excess returns">
                <Waterfall height={220} format={(v) => money(v, ccy)} steps={[
                  { label: 'Book equity', value: result.book_equity, total: true },
                  { label: 'PV excess returns', value: result.pv_residual_income_sum },
                  { label: 'PV terminal', value: result.pv_terminal_value },
                  { label: 'Equity value', value: result.equity_value, total: true },
                ]} />
              </Panel>
              <Panel eyebrow="Schedule" title="Residual income, year by year" flush>
                <div className="table-wrap">
                  <table className="fin-table">
                    <thead><tr><th />{result.schedule.map((r) => <th key={r.year} className="num">Year {r.year}</th>)}</tr></thead>
                    <tbody>
                      {([['Opening book', 'opening_book', 'money'], ['ROE', 'roe', 'pct'], ['Net income', 'net_income', 'money'],
                         ['Equity charge', 'equity_charge', 'money'], ['Residual income', 'residual_income', 'money'],
                         ['Implied payout', 'implied_payout', 'money'], ['PV of residual income', 'pv_residual_income', 'money']] as const).map(([label, key, kind]) => (
                        <tr key={key} className={key === 'residual_income' ? 'emph' : ''}>
                          <td>{label}</td>
                          {result.schedule.map((r) => <td key={r.year} className="num">{kind === 'pct' ? pct(r[key]) : money(r[key], ccy)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              <Panel eyebrow="Diagnostics" title="What the model is telling you"><Flags flags={result.flags} /></Panel>
            </>
          )}
        </Gate>
        {sens && sens.method === 'excess_return' && (
          <div className="grid-2">
            <Panel eyebrow="Sensitivity" title="Terminal growth × cost of equity">
              <Heatmap rows={sens.terminal_growth_values} cols={sens.cost_of_equity_values} values={sens.ke_growth} rowLabel="g" colLabel="Ke"
                       format={(v) => priceTag(v, ccy)} axisFormat={(v) => pct(v, 2)} reference={company.current_price} />
            </Panel>
            <Panel eyebrow="Sensitivity" title="Terminal ROE × cost of equity">
              <Heatmap rows={sens.terminal_roe_values} cols={sens.cost_of_equity_values} values={sens.ke_roe} rowLabel="ROE" colLabel="Ke"
                       format={(v) => priceTag(v, ccy)} axisFormat={(v) => pct(v, 1)} reference={company.current_price} />
            </Panel>
          </div>
        )}
      </div>
    </div>
  )
}
