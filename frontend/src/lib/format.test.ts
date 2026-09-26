import { describe, expect, it } from 'vitest'
import { fiscalLabel, money, multiple, pct, points, priceTag, shortDate, tone } from './format'

describe('money', () => {
  it('uses lakh / crore conventions for rupees', () => {
    expect(money(2.5e12, 'INR')).toBe('₹2.50 L Cr')
    expect(money(4.2e9, 'INR')).toBe('₹420 Cr')
    expect(money(3.5e5, 'INR')).toBe('₹3.5 L')
  })

  it('uses B / T / M for dollars', () => {
    expect(money(3.1e12, 'USD')).toBe('$3.10T')
    expect(money(45.6e9, 'USD')).toBe('$45.6B')
    expect(money(7.25e6, 'USD')).toBe('$7.3M')
  })

  it('formats precise prices with the right grouping and a true minus sign', () => {
    expect(money(123456.789, 'INR', { precise: true })).toBe('₹1,23,456.79')
    expect(money(-12.5, 'USD', { precise: true })).toBe('−$12.50')
    expect(money(5, 'USD', { precise: true, signed: true })).toBe('+$5.00')
  })

  it('returns a dash for missing values', () => {
    expect(money(null, 'USD')).toBe('—')
    expect(money(Number.NaN, 'USD')).toBe('—')
  })
})

describe('percentages and multiples', () => {
  it('formats percentages with optional sign', () => {
    expect(pct(0.1234)).toBe('12.3%')
    expect(pct(-0.05, 0)).toBe('−5%')
    expect(pct(0.02, 1, { signed: true })).toBe('+2.0%')
  })

  it('formats percentage-point gaps', () => {
    expect(points(0.034)).toBe('+3.4 pts')
    expect(points(-0.1, 0)).toBe('−10 pts')
    expect(points(0)).toBe('0.0 pts')
  })

  it('formats multiples', () => {
    expect(multiple(12.345)).toBe('12.3×')
    expect(multiple(undefined)).toBe('—')
  })

  it('classifies tone with a neutral band', () => {
    expect(tone(0.02)).toBe('pos')
    expect(tone(-0.02)).toBe('neg')
    expect(tone(0.004, 0.005)).toBe('')
  })
})

describe('dates', () => {
  it('names fiscal years by the calendar year they end in', () => {
    expect(fiscalLabel('2026-03-31')).toBe('FY2026 · Mar')
    expect(fiscalLabel('2025-12-31')).toBe('FY2025')
  })

  it('formats short dates', () => {
    expect(shortDate('2026-09-25')).toBe('Sep 25, 2026')
    expect(shortDate(null)).toBe('—')
  })
})

describe('priceTag', () => {
  it('drops cents from 100 upward and keeps them below', () => {
    expect(priceTag(341.07, 'USD')).toBe('$341')
    expect(priceTag(95.874, 'USD')).toBe('$95.87')
    expect(priceTag(123456.7, 'INR')).toBe('₹1,23,457')
  })
})
