import { describe, expect, it } from 'vitest'
import { money, pct } from './ui'

describe('financial display formatters', () => {
  it('formats an available financial value without fabricating missing data', () => {
    expect(money(3_420_000_000_000)).toContain('$3.4T')
    expect(money(undefined)).toBe('UNAVAILABLE')
  })

  it('formats percentage values consistently', () => {
    expect(pct(0.124)).toBe('12.4%')
    expect(pct(undefined)).toBe('UNAVAILABLE')
  })
})
