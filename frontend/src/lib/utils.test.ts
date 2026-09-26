import { describe, expect, it } from 'vitest'
import { decodeScenario, encodeScenario, extent, mergeOverrides, niceTicks, scaleLinear, slug, stableHash } from './utils'

describe('stableHash', () => {
  it('ignores key order at every level', () => {
    const a = { ticker: 'AAPL', dcf: { wacc: 0.08, revenue_growth: 0.05 }, list: [1, 2] }
    const b = { list: [1, 2], dcf: { revenue_growth: 0.05, wacc: 0.08 }, ticker: 'AAPL' }
    expect(stableHash(a)).toBe(stableHash(b))
  })

  it('keeps nested values (regression: a key allow-list once dropped them)', () => {
    expect(stableHash({ dcf: { wacc: 0.08 } })).not.toBe(stableHash({ dcf: { wacc: 0.09 } }))
  })

  it('preserves array order', () => {
    expect(stableHash([1, 2])).not.toBe(stableHash([2, 1]))
  })
})

describe('mergeOverrides', () => {
  it('adds, replaces and removes overrides', () => {
    const start = { wacc: 0.08, revenue_growth: 0.05 }
    expect(mergeOverrides(start, { wacc: 0.09 })).toEqual({ wacc: 0.09, revenue_growth: 0.05 })
    expect(mergeOverrides(start, { wacc: null })).toEqual({ revenue_growth: 0.05 })
  })

  it('collapses to undefined when nothing is overridden', () => {
    expect(mergeOverrides({ wacc: 0.08 }, { wacc: null })).toBeUndefined()
    expect(mergeOverrides(undefined, {})).toBeUndefined()
  })

  it('keeps legitimate zeros and false values', () => {
    expect(mergeOverrides(undefined, { pct_cash: 0, mid_year_convention: false })).toEqual({ pct_cash: 0, mid_year_convention: false })
  })
})

describe('scales and ticks', () => {
  it('maps and inverts linearly', () => {
    const x = scaleLinear([0, 10], [100, 200])
    expect(x(5)).toBe(150)
    expect(x.invert(175)).toBe(7.5)
  })

  it('produces round tick values inside the range', () => {
    expect(niceTicks(0, 1, 5)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
    const ticks = niceTicks(-0.034, 0.121, 5)
    expect(ticks.every((t) => t >= -0.034 && t <= 0.121)).toBe(true)
    expect(ticks).toContain(0)
  })

  it('pads a degenerate extent and ignores non-finite values', () => {
    expect(extent([3, 3])).toEqual([2, 4])
    expect(extent([1, Number.NaN, 5])).toEqual([1, 5])
    expect(extent([])).toEqual([0, 1])
  })

  it('slugs headings for anchors', () => {
    expect(slug('M&A accretion and dilution')).toBe('m-a-accretion-and-dilution')
  })
})

describe('shared scenario links', () => {
  it('round-trips overrides through a URL-safe token', () => {
    const scenario = { dcf: { wacc: 0.091, terminal_method: 'exit_multiple', mid_year_convention: false }, mna: { acquirer_ticker: 'XOM', pct_stock: 0.4 } }
    const token = encodeScenario(scenario)
    expect(token).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(decodeScenario(token)).toEqual(scenario)
  })

  it('handles non-ASCII text', () => {
    expect(decodeScenario(encodeScenario({ mna: { acquirer_ticker: 'RELIANCE.NSE', note: '₹ crore' } }))).toEqual({ mna: { acquirer_ticker: 'RELIANCE.NSE', note: '₹ crore' } })
  })

  it('drops unknown sections, nested objects and deals without an acquirer', () => {
    const token = encodeScenario({ dcf: { wacc: 0.08, nested: { x: 1 } }, hack: { y: 1 }, mna: { pct_stock: 1 } })
    expect(decodeScenario(token)).toEqual({ dcf: { wacc: 0.08 } })
  })

  it('rejects malformed tokens', () => {
    expect(decodeScenario('%%%')).toBeNull()
    expect(decodeScenario(encodeScenario([1, 2]))).toBeNull()
  })
})
