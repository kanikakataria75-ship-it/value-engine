import { Fragment, useState, type ReactNode } from 'react'
import type { Company, Status, DataMode } from '../types/api'

export const money = (value?: number, precise = false, currency: string = 'USD'): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'UNAVAILABLE'
  const isINR = currency?.toUpperCase() === 'INR'
  const sym = isINR ? '₹' : '$'
  const abs = Math.abs(value)

  if (isINR) {
    if (precise) {
      return `${sym}${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    }
    if (abs >= 1e7) {
      const cr = value / 1e7
      return `${sym}${cr >= 1000 ? Math.round(cr).toLocaleString('en-IN') : cr.toFixed(1)} Cr`
    }
    if (abs >= 1e5) {
      return `${sym}${(value / 1e5).toFixed(1)} L`
    }
    return `${sym}${value.toLocaleString('en-IN', { maximumFractionDigits: 1 })}`
  }

  if (precise) {
    return `${sym}${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  if (abs >= 1e12) return `${sym}${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sym}${(value / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sym}${(value / 1e6).toFixed(1)}M`
  return `${sym}${value.toLocaleString('en-US', { maximumFractionDigits: 1 })}`
}

export const pct = (value?: number, digits = 1): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'UNAVAILABLE'
  return `${(value * 100).toFixed(digits)}%`
}

export const multiple = (value?: number, digits = 2): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'UNAVAILABLE'
  return `${value.toFixed(digits)}x`
}

export const num = (value?: number, compact = true): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'UNAVAILABLE'
  const abs = Math.abs(value)
  if (compact) {
    if (abs >= 1e9) return `${(value / 1e9).toFixed(1)}B`
    if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  }
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

export function StatusBadge({ status }: { status: string }) {
  const norm = (status || 'UNAVAILABLE').replace(/\s+/g, '_').toLowerCase()
  const display = status === 'LOCAL' ? 'LOCAL DB' : status.replace(/_/g, ' ')
  return <span className={`badge ${norm}`}>{display}</span>
}

export function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string
  value: string
  detail?: string
  tone?: 'positive' | 'negative' | 'neutral'
}) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className={`metric-value ${tone || ''}`}>{value}</strong>
      {detail && <small className="metric-detail">{detail}</small>}
    </div>
  )
}

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = '',
}: {
  title?: string
  eyebrow?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || eyebrow || action) && (
        <header className="panel-head">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function DataState({
  status,
  errors,
  children,
  dataMode = 'local',
}: {
  status: Status | string
  errors?: string[]
  children: ReactNode
  dataMode?: DataMode
}) {
  if (status === 'INVALID' || status === 'UNAVAILABLE' || status === 'ERROR') {
    const errorMsg = errors?.[0] || 'This model output is currently unavailable.'
    return (
      <div className="empty-state">
        <StatusBadge status={status} />
        <p className="empty-state-title">{errorMsg}</p>
        {status === 'UNAVAILABLE' && dataMode === 'local' && (
          <small className="empty-state-hint">
            Tip: 389 companies are pre-loaded in the Local Dataset. Switch to Live API if looking for other global tickers.
          </small>
        )}
      </div>
    )
  }
  return <>{children}</>
}

export function CompanyHeader({
  company,
  modelStatus = 'VALID',
  dataMode = 'local',
}: {
  company?: Partial<Company> | null
  modelStatus?: string
  dataMode?: DataMode
}) {
  if (!company || !company.ticker) {
    return (
      <div className="company-header skeleton">
        <div className="company-identity">
          <div className="company-mark">VE</div>
          <div>
            <p className="eyebrow">COMPANY CONTEXT</p>
            <h1>LOADING ASSET...</h1>
          </div>
        </div>
      </div>
    )
  }

  const isIndia = Boolean(company.ticker?.endsWith('.NSE') || company.ticker?.endsWith('.BSE') || company.currency === 'INR')
  const countryFlag = isIndia ? '🇮🇳 India' : '🇺🇸 United States'
  const curr = company.currency || (isIndia ? 'INR' : 'USD')

  return (
    <div className="company-header">
      <div className="company-identity">
        <div className="company-mark" aria-hidden="true">
          {company.ticker.replace(/\..*$/, '').slice(0, 2)}
        </div>
        <div>
          <div className="company-tagline">
            <p className="eyebrow">ACTIVE CONTEXT</p>
            <span className="source-tag">{dataMode === 'local' ? '🏛 LOCAL DATASET (389)' : '⚡ LIVE API'}</span>
          </div>
          <h1>{company.company_name}</h1>
          <p className="company-sub">
            <span className="ticker-badge">{company.ticker}</span>
            <span>·</span>
            <span>{company.exchange}</span>
            <span>·</span>
            <span>{countryFlag}</span>
            <span>·</span>
            <span>{company.sector}</span>
            {company.industry && (
              <>
                <span>·</span>
                <span className="industry-text">{company.industry}</span>
              </>
            )}
          </p>
        </div>
      </div>
      <div className="company-values">
        <div>
          <span>Current Price</span>
          <strong>{money(company.current_price, true, curr)}</strong>
        </div>
        <div>
          <span>Market Cap</span>
          <strong>{money(company.market_cap, false, curr)}</strong>
        </div>
        {typeof company.beta === 'number' && Number.isFinite(company.beta) && (
          <div>
            <span>Beta</span>
            <strong>{company.beta.toFixed(2)}</strong>
          </div>
        )}
        <StatusBadge status={modelStatus} />
      </div>
    </div>
  )
}

export function FinancialTable({
  rows,
  currency = 'USD',
}: {
  rows: Record<string, unknown>[]
  currency?: string
}) {
  if (!rows || !rows.length) {
    return (
      <div className="empty-state compact">
        <p>NO RECORDS AVAILABLE</p>
      </div>
    )
  }

  const columns = Object.keys(rows[0])

  const formatCell = (colName: string, val: unknown) => {
    if (val === null || val === undefined) return '—'
    if (typeof val === 'number') {
      const lower = colName.toLowerCase()
      if (lower.includes('pct') || lower.includes('margin') || lower.includes('growth') || lower.includes('irr') || lower.includes('rate') || lower.includes('p_value')) {
        return pct(val)
      }
      if (lower.includes('multiple') || lower.includes('moic') || lower.includes('ev /') || lower.includes('p / e')) {
        return `${val.toFixed(2)}x`
      }
      if (lower === 'year' || lower === 'horizon' || lower === 'observations' || lower === 'count') {
        return String(val)
      }
      if (lower.includes('price') || lower.includes('revenue') || lower.includes('ebit') || lower.includes('income') || lower.includes('debt') || lower.includes('cash') || lower.includes('capex') || lower.includes('ufcf') || lower.includes('taxes') || lower.includes('equity') || lower.includes('value')) {
        return money(val, lower.includes('price'), currency)
      }
      return num(val)
    }
    return String(val)
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c.replace(/_/g, ' ').toUpperCase()}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((c) => {
                const val = row[c]
                const isNum = typeof val === 'number'
                return (
                  <td className={isNum ? 'numeric' : ''} key={c}>
                    {formatCell(c, val)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Heatmap({
  rows,
  cols,
  values,
  format = 'price',
  rowLabel = 'Terminal Growth',
  colLabel = 'WACC',
  currency = 'USD',
  baseRowIdx = 2,
  baseColIdx = 2,
}: {
  rows: number[]
  cols: number[]
  values: (number | null)[][]
  format?: 'pct' | 'price'
  rowLabel?: string
  colLabel?: string
  currency?: string
  baseRowIdx?: number
  baseColIdx?: number
}) {
  const [hovered, setHovered] = useState<{ r: number; c: number; val: number | null } | null>(null)

  const valid = values.flat().filter((v): v is number => v !== null && Number.isFinite(v))
  if (!valid.length) {
    return (
      <div className="empty-state compact">
        <p>SENSITIVITY MATRIX UNAVAILABLE</p>
      </div>
    )
  }

  const low = Math.min(...valid)
  const high = Math.max(...valid)

  return (
    <div className="heatmap-container">
      <div className="heatmap-header-labels">
        <span className="axis-title-col">{colLabel} →</span>
      </div>
      <div className="heatmap-with-axes">
        <div className="heatmap-row-axis-title">
          <span>{rowLabel}</span>
        </div>
        <div className="heatmap" style={{ gridTemplateColumns: `80px repeat(${cols.length}, 1fr)` }}>
          <div className="heat-corner-label">Growth \ WACC</div>
          {cols.map((c, i) => (
            <span className={`heat-label col-header ${i === baseColIdx ? 'base-axis' : ''}`} key={`col-${i}`}>
              {pct(c)}
            </span>
          ))}
          {rows.map((rowVal, r) => (
            <Fragment key={`row-${r}`}>
              <span className={`heat-label row-header ${r === baseRowIdx ? 'base-axis' : ''}`}>{pct(rowVal)}</span>
              {values[r]?.map((value, c) => {
                const isBase = r === baseRowIdx && c === baseColIdx
                const intensity = value === null || high === low ? 0.35 : 0.15 + 0.75 * ((value - low) / (high - low))
                const formattedVal = value === null ? '—' : format === 'price' ? money(value, true, currency) : pct(value)

                return (
                  <span
                    key={`${r}-${c}`}
                    className={`heat-cell ${isBase ? 'base-case' : ''}`}
                    style={{
                      backgroundColor: value === null ? '#131e33' : `rgba(79, 70, 229, ${intensity})`,
                    }}
                    onMouseEnter={() => setHovered({ r, c, val: value })}
                    onMouseLeave={() => setHovered(null)}
                  >
                    {isBase && <span className="base-tag">BASE</span>}
                    {formattedVal}
                  </span>
                )
              })}
            </Fragment>
          ))}
        </div>
      </div>
      {hovered && (
        <div className="heatmap-tooltip">
          <span>
            {rowLabel}: <strong>{pct(rows[hovered.r])}</strong>
          </span>
          <span>·</span>
          <span>
            {colLabel}: <strong>{pct(cols[hovered.c])}</strong>
          </span>
          <span>·</span>
          <span>
            Implied Value: <strong>{hovered.val !== null ? (format === 'price' ? money(hovered.val, true, currency) : pct(hovered.val)) : '—'}</strong>
          </span>
        </div>
      )}
    </div>
  )
}
