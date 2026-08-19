import { describe, expect, it } from 'vitest'
import { getConsiderationValidation } from './MnaPage'

describe('M&A Consideration Validation', () => {
  it('validates 50% cash and 50% stock as valid', () => {
    const res = getConsiderationValidation(50, 50)
    expect(res.isValid).toBe(true)
    expect(res.sum).toBe(100)
    expect(res.warning).toBeNull()
  })

  it('detects intermediate state (60% cash + 50% stock) as invalid without throwing', () => {
    const res = getConsiderationValidation(60, 50)
    expect(res.isValid).toBe(false)
    expect(res.sum).toBe(110)
    expect(res.warning).toContain('must equal 100%')
    expect(res.warning).toContain('110%')
  })

  it('validates 60% cash + 40% stock as valid', () => {
    const res = getConsiderationValidation(60, 40)
    expect(res.isValid).toBe(true)
    expect(res.sum).toBe(100)
    expect(res.warning).toBeNull()
  })

  it('handles fractional percentages correctly (e.g. 33.3% + 66.7%)', () => {
    const res = getConsiderationValidation(33.3, 66.7)
    expect(res.isValid).toBe(true)
    expect(res.sum).toBe(100)
  })

  it('safely handles non-numeric / NaN input without crashing', () => {
    const res = getConsiderationValidation(NaN, 50)
    expect(res.isValid).toBe(false)
    expect(res.warning).toContain('valid numerical consideration')
  })

  it('disallows negative percentages', () => {
    const res = getConsiderationValidation(-10, 110)
    expect(res.isValid).toBe(false)
  })
})
