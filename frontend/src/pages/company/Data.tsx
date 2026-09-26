import { Ring, Sparkline } from '../../components/charts'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconAlert, IconCheck, IconInfo } from '../../components/icons'
import { KeyValues, PageTitle, Panel, StatusPill } from '../../components/ui'
import type { Company, HistoryRow } from '../../lib/api-types'
import { fiscalLabel, fixed, integer, money, pct, shortDate } from '../../lib/format'
import { ok, useHistory } from '../../lib/queries'
import { cn } from '../../lib/utils'

type Field = keyof Company
const GROUPS: { title: string; fields: [Field, string, 'money' | 'price' | 'count' | 'ratio'][] }[] = [
  { title: 'Income statement', fields: [['revenue', 'Revenue', 'money'], ['ebitda', 'EBITDA', 'money'], ['ebit', 'EBIT', 'money'], ['d_and_a', 'Depreciation & amortisation', 'money'], ['net_income', 'Net income', 'money'], ['eps', 'Earnings per share', 'price']] },
  { title: 'Cash flow', fields: [['operating_cash_flow', 'Operating cash flow', 'money'], ['capex', 'Capital expenditure', 'money']] },
  { title: 'Balance sheet', fields: [['total_assets', 'Total assets', 'money'], ['total_liabilities', 'Total liabilities', 'money'], ['book_equity', 'Book equity', 'money'], ['total_debt', 'Total debt', 'money'], ['cash_and_equivalents', 'Cash & equivalents', 'money']] },
  { title: 'Market', fields: [['current_price', 'Share price', 'price'], ['shares_outstanding', 'Shares outstanding', 'count'], ['market_cap', 'Market capitalisation', 'money'], ['beta', 'Provider beta', 'ratio']] },
]

const HISTORY_FIELDS: [keyof HistoryRow, string][] = [
  ['revenue', 'Revenue'], ['ebitda', 'EBITDA'], ['ebit', 'EBIT'], ['net_income', 'Net income'],
  ['operating_cash_flow', 'Operating cash flow'], ['capex', 'CapEx'], ['d_and_a', 'D&A'],
]

export function Data() {
  const { ticker, company } = useCompanyContext()
  const history = ok(useHistory(ticker).data)
  const ccy = company.currency
  const quality = company.quality
  const prov = company.provenance
  const derived = new Set(prov.derived_fields ?? [])
  const rows = history?.rows ?? []

  const show = (field: Field, kind: string) => {
    const value = company[field] as number | null | undefined
    if (kind === 'money') return money(value, ccy)
    if (kind === 'price') return money(value, ccy, { precise: true })
    if (kind === 'count') return integer(value)
    return fixed(value, 2)
  }

  return (
    <div className="page">
      <PageTitle eyebrow="Data room · provenance and quality"
                 title={<>Where every number <em>comes from</em></>}
                 lede="Each figure is stored locally with its source, fiscal period and currency. Values the pipeline had to derive are marked, and every company passes a rule-based quality check before any model runs." />
      <div className="grid">
        <Panel className="span-4 quality-card" eyebrow="Quality score" title="Rule-based data check">
          <div className="quality-ring">
            <Ring value={quality.score / 100} size={132} tone={quality.score >= 80 ? 'pos' : quality.score >= 60 ? 'gold' : 'neg'}>
              <b className="num">{Math.round(quality.score)}</b><span>/ 100</span>
            </Ring>
            <div>
              <StatusPill status={quality.status} />
              <p className="muted">{quality.fields_present} of {quality.fields_total} core fields ({pct(quality.completeness, 0)}) · {integer(quality.price_records)} daily prices</p>
              <p className="muted small">100 − 40 per error − 8 per warning</p>
            </div>
          </div>
          {quality.missing_fields.length > 0 && <p className="muted small">Missing: {quality.missing_fields.join(', ').replace(/_/g, ' ')}</p>}
        </Panel>
        <Panel className="span-8" eyebrow="Provenance" title={`${prov.source_type === 'LOCAL' ? 'Local store' : prov.source_type} · ${prov.origin ?? prov.source_name ?? 'unknown origin'}`}>
          <div className="grid-2 tight">
            <KeyValues rows={[
              ['Fiscal period', `${fiscalLabel(prov.period_end ?? company.period)} (${prov.period_type ?? 'FY'})`],
              ['Reporting currency', prov.currency ?? ccy],
              ['Retrieved', shortDate(prov.retrieved_at ?? company.retrieved_at)],
              ['Source', prov.source_name ?? '—'],
            ]} />
            <div>
              <div className="eyebrow muted">Derived by the pipeline</div>
              <div className="chip-row">
                {derived.size ? [...derived].map((f) => <span key={f} className="chip static">{f.replace(/_/g, ' ')}</span>) : <span className="muted">Nothing derived: every field is as reported.</span>}
              </div>
              {(prov.repairs ?? []).length > 0 && (
                <>
                  <div className="eyebrow muted">Repairs</div>
                  <ul className="plain-list">{prov.repairs!.map((r) => <li key={r}>{r}</li>)}</ul>
                </>
              )}
              {prov.notice && <p className="footnote">{prov.notice}</p>}
            </div>
          </div>
        </Panel>

        <Panel className="span-7" eyebrow={`Latest fiscal year · ${ccy}`} title="Fundamentals as stored" flush>
          <div className="fund-groups">
            {GROUPS.map((g) => (
              <div key={g.title} className="fund-group">
                <div className="eyebrow muted">{g.title}</div>
                <dl className="kv">
                  {g.fields.map(([field, label, kind]) => (
                    <div key={field} className="kv-row">
                      <dt>{label}{derived.has(field) && <span className="tag">derived</span>}</dt>
                      <dd className="num">{show(field, kind)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </Panel>
        <Panel className="span-5" eyebrow="Quality findings" title={`${company.issues.length} check${company.issues.length === 1 ? '' : 's'} reported`}>
          <ul className="issues">
            {company.issues.length === 0 && <li className="issue ok"><IconCheck size={14} /> No findings.</li>}
            {company.issues.map((issue, i) => (
              <li key={`${issue.rule}-${i}`} className={cn('issue', issue.severity.toLowerCase())}>
                <span className="issue-icon">{issue.severity === 'INFO' ? <IconInfo size={14} /> : <IconAlert size={14} />}</span>
                <span><b className="mono">{issue.rule}</b>{issue.message}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel className="span-12" eyebrow="Statement history" title={rows.length ? `${rows.length} fiscal years` : 'No history stored'} flush>
          {rows.length > 0 && (
            <div className="table-wrap">
              <table className="fin-table">
                <thead>
                  <tr><th />{rows.map((r) => <th key={r.period_end} className="num">{fiscalLabel(r.period_end)}</th>)}<th className="num">Trend</th></tr>
                </thead>
                <tbody>
                  {HISTORY_FIELDS.map(([key, label]) => {
                    const values = rows.map((r) => r[key] as number | null | undefined)
                    return (
                      <tr key={key}>
                        <td>{label}</td>
                        {values.map((v, i) => <td key={i} className="num">{money(v, rows[i].currency ?? ccy)}</td>)}
                        <td className="num"><Sparkline values={values.filter((v): v is number => typeof v === 'number')} width={80} height={22} /></td>
                      </tr>
                    )
                  })}
                  <tr className="emph">
                    <td>EBITDA margin</td>
                    {rows.map((r) => <td key={r.period_end} className="num">{pct(r.ebitda && r.revenue ? r.ebitda / r.revenue : null)}</td>)}
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
