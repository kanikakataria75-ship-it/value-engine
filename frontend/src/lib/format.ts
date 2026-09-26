/* Number formatting. Indian amounts use lakh / crore conventions; US amounts use B / T. */

export const DASH = '—'

type Maybe = number | null | undefined

const finite = (value: Maybe): value is number => typeof value === 'number' && Number.isFinite(value)

export const isINR = (currency?: string | null) => (currency ?? '').toUpperCase() === 'INR'
export const symbolFor = (currency?: string | null) => (isINR(currency) ? '₹' : '$')

export function money(value: Maybe, currency?: string | null, options: { precise?: boolean; signed?: boolean } = {}): string {
  if (!finite(value)) return DASH
  const symbol = symbolFor(currency)
  const sign = value < 0 ? '−' : options.signed && value > 0 ? '+' : ''
  const abs = Math.abs(value)
  if (options.precise) {
    const locale = isINR(currency) ? 'en-IN' : 'en-US'
    return `${sign}${symbol}${abs.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  if (isINR(currency)) {
    if (abs >= 1e12) return `${sign}${symbol}${(abs / 1e12).toFixed(2)} L Cr`
    if (abs >= 1e7) return `${sign}${symbol}${Math.round(abs / 1e7).toLocaleString('en-IN')} Cr`
    if (abs >= 1e5) return `${sign}${symbol}${(abs / 1e5).toFixed(1)} L`
    return `${sign}${symbol}${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
  }
  if (abs >= 1e12) return `${sign}${symbol}${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}${symbol}${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sign}${symbol}${(abs / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${sign}${symbol}${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  return `${sign}${symbol}${abs.toFixed(2)}`
}

/** Share price for dense grids: whole units from 100 upward, cents below. */
export function priceTag(value: Maybe, currency?: string | null): string {
  if (!finite(value)) return DASH
  const digits = Math.abs(value) >= 100 ? 0 : 2
  const locale = isINR(currency) ? 'en-IN' : 'en-US'
  const sign = value < 0 ? '−' : ''
  return `${sign}${symbolFor(currency)}${Math.abs(value).toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
}

export function pct(value: Maybe, digits = 1, options: { signed?: boolean } = {}): string {
  if (!finite(value)) return DASH
  const sign = value < 0 ? '−' : options.signed && value > 0 ? '+' : ''
  return `${sign}${Math.abs(value * 100).toFixed(digits)}%`
}

export function points(value: Maybe, digits = 1): string {
  if (!finite(value)) return DASH
  const sign = value < 0 ? '−' : value > 0 ? '+' : ''
  return `${sign}${Math.abs(value * 100).toFixed(digits)} pts`
}

export function multiple(value: Maybe, digits = 1): string {
  if (!finite(value)) return DASH
  return `${value.toFixed(digits)}×`
}

export function compact(value: Maybe, digits = 1): string {
  if (!finite(value)) return DASH
  const abs = Math.abs(value)
  const sign = value < 0 ? '−' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(digits)}T`
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(digits)}B`
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(digits)}M`
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(digits)}K`
  return `${sign}${abs.toFixed(digits)}`
}

export function fixed(value: Maybe, digits = 2): string {
  return finite(value) ? value.toFixed(digits) : DASH
}

export function integer(value: Maybe): string {
  return finite(value) ? Math.round(value).toLocaleString('en-US') : DASH
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function shortDate(iso?: string | null): string {
  if (!iso) return DASH
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  if (!y || !m) return iso
  return d ? `${MONTHS[m - 1]} ${d}, ${y}` : `${MONTHS[m - 1]} ${y}`
}

/** Fiscal year named by the calendar year it ends in, with the month when it is not December. */
export function fiscalLabel(iso?: string | null): string {
  if (!iso) return DASH
  const [y, m] = iso.slice(0, 10).split('-').map(Number)
  if (!y || !m) return iso
  return `FY${y}${m !== 12 ? ` · ${MONTHS[m - 1]}` : ''}`
}

export function tone(value: Maybe, neutralBand = 0): 'pos' | 'neg' | '' {
  if (!finite(value)) return ''
  if (value > neutralBand) return 'pos'
  if (value < -neutralBand) return 'neg'
  return ''
}
