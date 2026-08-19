import { describe, expect, it } from 'vitest'
import { createHistogramFromRaw } from './RiskLabPage'

describe('Monte Carlo Histogram Binning Helper', () => {
  it('handles empty or undefined simulation values gracefully', () => {
    expect(createHistogramFromRaw(undefined)).toEqual([])
    expect(createHistogramFromRaw([])).toEqual([])
  })

  it('correctly creates 24 histogram bins from raw simulated prices', () => {
    const rawSimulations = [
      1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350, 1400, 1450,
      1500, 1550, 1600, 1650, 1700, 1750, 1800, 1850, 1900, 1950,
      2000, 2050, 2100, 2150, 2200, 2250, 2300, 2350, 2400, 2450,
    ]
    const bins = createHistogramFromRaw(rawSimulations, 10, 1500)
    expect(bins.length).toBe(10)

    const totalCount = bins.reduce((sum, b) => sum + b.count, 0)
    expect(totalCount).toBe(rawSimulations.length)

    // Check downside flag
    const downsideBins = bins.filter((b) => b.isDownside)
    const normalBins = bins.filter((b) => !b.isDownside)
    expect(downsideBins.length).toBeGreaterThan(0)
    expect(normalBins.length).toBeGreaterThan(0)
  })

  it('handles single value array without division by zero', () => {
    const single = [1200, 1200, 1200]
    const bins = createHistogramFromRaw(single, 10, 1300)
    expect(bins.length).toBe(1)
    expect(bins[0].count).toBe(3)
    expect(bins[0].isDownside).toBe(true)
  })

  it('filters out non-numeric values safely', () => {
    const mixed = [1000, NaN, 2000, Infinity, 1500] as number[]
    const bins = createHistogramFromRaw(mixed, 5)
    expect(bins.length).toBe(5)
    const totalCount = bins.reduce((sum, b) => sum + b.count, 0)
    expect(totalCount).toBe(3)
  })
})
