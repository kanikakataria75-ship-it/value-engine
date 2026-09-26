import { Lines, StackedArea, Waterfall } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconReset } from '../../components/icons'
import { NumberField } from '../../components/NumberField'
import { AnimatedNumber, Empty, Flags, Gate, KeyValues, PageTitle, Panel, StatusPill } from '../../components/ui'
import type { LboResult, StressScenario } from '../../lib/api-types'
import { money, multiple, pct } from '../../lib/format'
import { ok, problem, useLbo, useStress } from '../../lib/queries'
import { useScenario } from '../../lib/scenario'
import { cn } from '../../lib/utils'

export function Lbo() {
  const { ticker, company, baseline } = useCompanyContext()
  const { scenario, setLbo, reset } = useScenario(ticker)
  const q = useLbo(ticker)
  const result = ok(q.data)
  const stress = ok(useStress(ticker).data)
  const base = baseline?.lbo
  const l = scenario.lbo ?? {}
  // Richly valued companies can sit above 40x EBITDA; keep their baseline inside the slider's range.
  const multipleMax = Math.max(40, Math.ceil(Math.max(base?.entry_multiple ?? 0, base?.exit_multiple ?? 0) * 1.4))

  if (company.balance_sheet_financial) {
    return (
      <div className="page page-center">
        <Empty title="LBOs are not modelled for banks and insurers"
               message="Their debt is operating funding rather than acquisition financing, so leverage-based returns are not meaningful." />
      </div>
    )
  }

  return (
    <div className="page">
      <PageTitle eyebrow="Leveraged buyout · sponsor returns"
                 title={<>Could a <em>private equity</em> buyer make it work?</>}
                 lede="Debt is sized in turns of EBITDA, cash flow sweeps senior then subordinated debt, a revolver covers shortfalls, and the value created is split exactly into growth, multiple and deleveraging." />
      <div className="workbench">
        <aside className="console">
          <div className="console-head">
            <span className="eyebrow">Assumptions</span>
            {scenario.lbo && <button type="button" className="link-quiet" onClick={() => reset('lbo')}><IconReset size={12} /> Baseline</button>}
          </div>
          <div className="console-group">
            <h4>Entry & exit</h4>
            <NumberField label="Entry EV / EBITDA" unit="x" value={l.entry_multiple} baseline={base?.entry_multiple} min={3} max={multipleMax} step={0.25}
                         onChange={(v) => setLbo({ entry_multiple: v })} hint="Baseline: today's multiple plus a take-private premium" />
            <NumberField label="Exit EV / EBITDA" unit="x" value={l.exit_multiple} baseline={base?.exit_multiple} min={3} max={multipleMax} step={0.25}
                         onChange={(v) => setLbo({ exit_multiple: v })} />
            <NumberField label="Holding period" unit="years" value={l.projection_years} baseline={base?.projection_years} min={3} max={10} step={1}
                         onChange={(v) => setLbo({ projection_years: v })} />
            <NumberField label="Transaction fees" value={l.fees_pct} baseline={base?.fees_pct} min={0} max={0.06} step={0.0025}
                         onChange={(v) => setLbo({ fees_pct: v })} hint="Share of entry enterprise value" />
          </div>
          <div className="console-group">
            <h4>Debt package</h4>
            <NumberField label="Senior debt" unit="x" value={l.senior_debt_turns} baseline={base?.senior_debt_turns} min={0} max={7} step={0.25}
                         onChange={(v) => setLbo({ senior_debt_turns: v })} hint="Turns of entry EBITDA" />
            <NumberField label="Senior rate" value={l.senior_rate} baseline={base?.senior_rate} min={0.02} max={0.2} step={0.0025} digits={2}
                         onChange={(v) => setLbo({ senior_rate: v })} />
            <NumberField label="Subordinated debt" unit="x" value={l.sub_debt_turns} baseline={base?.sub_debt_turns} min={0} max={4} step={0.25}
                         onChange={(v) => setLbo({ sub_debt_turns: v })} />
            <NumberField label="Subordinated rate" value={l.sub_rate} baseline={base?.sub_rate} min={0.03} max={0.25} step={0.0025} digits={2}
                         onChange={(v) => setLbo({ sub_rate: v })} />
          </div>
          <div className="console-group">
            <h4>Operations</h4>
            <NumberField label="Revenue growth / yr" value={l.revenue_growth} baseline={base?.revenue_growth} min={-0.1} max={0.35} step={0.0025}
                         onChange={(v) => setLbo({ revenue_growth: v })} />
            <NumberField label="Target EBITDA margin" value={l.target_ebitda_margin} baseline={base?.target_ebitda_margin} min={0.02} max={0.8} step={0.005}
                         onChange={(v) => setLbo({ target_ebitda_margin: v })} />
            <NumberField label="Tax rate" value={l.tax_rate} baseline={base?.tax_rate} min={0} max={0.4} step={0.0025}
                         onChange={(v) => setLbo({ tax_rate: v })} />
          </div>
        </aside>
        <div className="results">
          <Gate loading={q.isLoading && !result} error={problem(q.data)} minHeight={320} label="Running the debt schedule">
            {result && <LboResults result={result} status={q.data?.status} />}
          </Gate>
          {stress && (
            <Panel eyebrow="Stress test" title="How the deal holds up when things go wrong">
              <div className="stress-grid">
                {stress.scenarios.map((s) => <StressCard key={s.name} s={s} currency={stress.currency} />)}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}

function LboResults({ result, status }: { result: LboResult; status?: string }) {
  const ccy = result.currency
  const years = result.schedule.map((r) => `Y${r.year}`)
  const a = result.attribution
  const uses = [
    { label: 'Enterprise value', value: result.entry_ev, cls: 'u-ev' },
    { label: 'Fees', value: result.fees, cls: 'u-fees' },
  ]
  const sources = [
    { label: 'Senior debt', value: result.senior_debt, cls: 's-senior' },
    { label: 'Subordinated', value: result.sub_debt, cls: 's-sub' },
    { label: 'Sponsor equity', value: result.sponsor_initial_equity, cls: 's-equity' },
  ]
  return (
    <>
      <Panel className="result-hero" flush>
        <div className="result-hero-grid">
          <div>
            <div className="eyebrow">Sponsor IRR</div>
            <div className={cn('hero-number num', result.irr >= 0.2 ? 'pos' : result.irr < 0.1 ? 'neg' : '')}>
              <AnimatedNumber value={result.irr} format={(v) => pct(v, 1)} />
            </div>
            <div className="num">{multiple(result.moic, 2)} money multiple over {result.inputs.projection_years} years</div>
            <div className="eps-line num">{money(result.sponsor_initial_equity, ccy)} <span>→</span> {money(result.exit_equity, ccy)} <span className="muted">equity</span></div>
          </div>
          <div className="result-hero-side">
            <StatusPill status={status} />
            <KeyValues rows={[
              ['Entry leverage', multiple(result.entry_leverage)],
              ['Equity cheque', pct(result.equity_contribution_pct, 0)],
              ['Lowest interest cover', multiple(result.min_interest_coverage)],
              ['Peak revolver draw', money(result.peak_revolver, ccy)],
            ]} />
          </div>
        </div>
      </Panel>

      <div className="grid-2">
        <Panel eyebrow="Sources & uses" title={`Funding a ${money(result.total_uses, ccy)} purchase`}>
          <div className="su">
            {[{ title: 'Uses', rows: uses }, { title: 'Sources', rows: sources }].map((side) => (
              <div key={side.title} className="su-side">
                <div className="eyebrow muted">{side.title}</div>
                <div className="su-bar">
                  {side.rows.map((r) => <i key={r.label} className={r.cls} style={{ flex: Math.max(r.value, 0) }} title={`${r.label}: ${money(r.value, ccy)}`} />)}
                </div>
                <ul>
                  {side.rows.map((r) => (
                    <li key={r.label}><i className={cn('sw', r.cls)} />{r.label}<b className="num">{money(r.value, ccy)}</b><em className="num">{pct(r.value / result.total_uses, 0)}</em></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Panel>
        <Panel eyebrow="Value creation" title={`Where the ${money(result.value_creation, ccy)} gain comes from`}>
          <Waterfall height={230} format={(v) => money(v, ccy)} steps={[
            { label: 'EBITDA growth', value: a.ebitda_growth },
            { label: 'Multiple', value: a.multiple_expansion },
            { label: 'Debt paydown', value: a.deleveraging },
            { label: 'Fees', value: a.fees_and_leakage },
            ...(Math.abs(a.equity_floor) > 1e-6 ? [{ label: 'Equity floor', value: a.equity_floor }] : []),
            { label: 'Total', value: result.value_creation, total: true },
          ]} />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel eyebrow="Deleveraging" title="Debt outstanding at each year end">
          <StackedArea labels={['Entry', ...years]} format={(v) => money(v, ccy)} layers={[
            { name: 'Senior', color: 'var(--gold)', values: [result.senior_debt, ...result.schedule.map((r) => r.ending_senior)] },
            { name: 'Subordinated', color: 'var(--violet)', values: [result.sub_debt, ...result.schedule.map((r) => r.ending_sub)] },
            { name: 'Revolver', color: 'var(--ember)', values: [0, ...result.schedule.map((r) => r.revolver_balance)] },
          ]} />
        </Panel>
        <Panel eyebrow="Credit" title="Leverage and interest cover">
          <Lines labels={years} format={(v) => `${v.toFixed(1)}×`} zero series={[
            { name: 'Net debt / EBITDA', color: 'var(--gold)', values: result.schedule.map((r) => r.leverage ?? 0) },
            { name: 'EBITDA / interest', color: 'var(--aurora)', values: result.schedule.map((r) => Math.min(r.interest_coverage ?? 0, 25)), dashed: true },
          ]} />
          <div className="legend-inline"><span><i className="sw sw-gold" /> Net debt / EBITDA</span><span><i className="sw sw-aurora" /> EBITDA / interest (capped at 25×)</span></div>
        </Panel>
      </div>

      <Panel eyebrow="Schedule" title="Operating model and debt waterfall" flush>
        <div className="table-wrap">
          <table className="fin-table">
            <thead><tr><th />{result.schedule.map((r) => <th key={r.year} className="num">Year {r.year}</th>)}</tr></thead>
            <tbody>
              {([
                ['Revenue', 'revenue'], ['EBITDA', 'ebitda'], ['Interest', 'interest'], ['Taxes', 'taxes'], ['CapEx', 'capex'],
                ['Change in NWC', 'delta_nwc'], ['Levered free cash flow', 'levered_fcf'], ['Mandatory amortisation', 'mandatory_amortization'],
                ['Senior sweep', 'senior_sweep'], ['Subordinated sweep', 'sub_sweep'], ['Revolver draw', 'revolver_draw'],
                ['Ending senior', 'ending_senior'], ['Ending subordinated', 'ending_sub'], ['Revolver balance', 'revolver_balance'], ['Net debt', 'net_debt'],
              ] as const).map(([label, key]) => (
                <tr key={key} className={key === 'levered_fcf' || key === 'net_debt' ? 'emph' : ''}>
                  <td>{label}</td>
                  {result.schedule.map((r) => <td key={r.year} className="num">{money(r[key], ccy)}</td>)}
                </tr>
              ))}
              <tr>
                <td>EBITDA margin</td>
                {result.schedule.map((r) => <td key={r.year} className="num">{pct(r.ebitda_margin)}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel eyebrow="Diagnostics" title="What the model is telling you"><Flags flags={result.flags} /></Panel>
    </>
  )
}

function StressCard({ s, currency }: { s: StressScenario; currency: string }) {
  const failed = s.status && !['VALID', 'REVIEW_REQUIRED'].includes(s.status)
  const tone = failed ? 'bad' : (s.irr ?? 0) >= 0.15 ? 'ok' : (s.irr ?? 0) >= 0.05 ? 'warn' : 'bad'
  return (
    <div className={cn('stress-card', `tone-${tone}`)}>
      <div className="stress-name">{s.name}</div>
      <div className="stress-desc muted">{s.description}</div>
      {failed ? <div className="stress-fail">{s.message ?? 'The structure breaks.'}</div> : (
        <div className="stress-stats">
          <div><span>IRR</span><b className="num">{pct(s.irr, 1)}</b></div>
          <div><span>MOIC</span><b className="num">{multiple(s.moic, 2)}</b></div>
          <div><span>Min cover</span><b className="num">{multiple(s.min_interest_coverage)}</b></div>
          <div><span>Revolver</span><b className="num">{money(s.peak_revolver, currency)}</b></div>
        </div>
      )}
    </div>
  )
}
