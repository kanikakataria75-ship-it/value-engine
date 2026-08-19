import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
  Cell,
} from 'recharts'
import { api } from '../services/api'
import { CompanyHeader, DataState, MetricCard, Panel, money, pct } from '../components/ui'
import type { Company, DataMode } from '../types/api'

export function AnalyticsPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const company = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const input = {
    ticker,
    revenue_growth_rate: 0.07,
    ebitda_margin: 0.25,
    wacc: 0.085,
    terminal_growth_rate: 0.025,
    iterations: 500,
  }

  const monte = useQuery({
    queryKey: ['monte', ticker, dataMode],
    queryFn: () => api.monteCarlo(input, dataMode),
  })

  const risk = useQuery({
    queryKey: ['risk', ticker, dataMode],
    queryFn: () => api.risk(input, dataMode),
  })

  const c = company.data?.data as Company | undefined
  const d = monte.data?.data || {}
  const curr = c?.currency || (ticker.endsWith('.NSE') ? 'INR' : 'USD')
  const currentPrice = c?.current_price || 0

  const distribution = (d.distribution as number[] | undefined) || []
  const chartBins = createHistogramBins(distribution, 24)

  const p10 = d.p10 as number | undefined
  const median = d.median as number | undefined
  const p90 = d.p90 as number | undefined
  const mean = d.mean as number | undefined
  const stdDev = d.std_dev as number | undefined

  return (
    <>
      <CompanyHeader company={c} modelStatus={monte.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">STATISTICAL SIMULATION</p>
          <h1>Analytics & Monte Carlo Distribution</h1>
        </div>
        <span className="model-note">
          500 iterations of stochastic Gaussian parameter variation evaluated through the DCF model.
        </span>
      </div>

      <DataState status={monte.data?.status || 'LOADING'} errors={monte.data?.errors} dataMode={dataMode}>
        <div className="metrics-grid five">
          <MetricCard
            label="10th Percentile (P10)"
            value={money(p10, true, curr)}
            detail="Bearish downside threshold"
          />
          <MetricCard
            label="Median Valuation (P50)"
            value={money(median, true, curr)}
            detail="Central simulated value"
          />
          <MetricCard
            label="90th Percentile (P90)"
            value={money(p90, true, curr)}
            detail="Bullish upside threshold"
          />
          <MetricCard
            label="Standard Deviation"
            value={money(stdDev, true, curr)}
            detail="Valuation dispersion"
          />
          <MetricCard
            label="Market Share Price"
            value={money(currentPrice, true, curr)}
            detail="Observed market quote"
          />
        </div>

        <Panel eyebrow="MONTE CARLO SIMULATION" title="DCF Implied Valuation Probability Distribution">
          {chartBins.length > 0 ? (
            <div style={{ height: 320, width: '100%', marginTop: 10 }}>
              <ResponsiveContainer>
                <BarChart data={chartBins} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="label"
                    stroke="#64748b"
                    fontSize={11}
                    minTickGap={20}
                    tickFormatter={(v) => money(Number(v), false, curr)}
                  />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 6 }}
                    formatter={(count: number) => [`${count} simulations`, 'Frequency']}
                    labelFormatter={(lbl) => `Valuation Range: ~${money(Number(lbl), true, curr)}`}
                  />
                  {median !== undefined && (
                    <ReferenceLine
                      x={getClosestBinLabel(chartBins, median)}
                      stroke="#10b981"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      label={{ value: 'MEDIAN', fill: '#10b981', fontSize: 11, position: 'top' }}
                    />
                  )}
                  {currentPrice > 0 && (
                    <ReferenceLine
                      x={getClosestBinLabel(chartBins, currentPrice)}
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      label={{ value: 'CURRENT PRICE', fill: '#f59e0b', fontSize: 11, position: 'top' }}
                    />
                  )}
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {chartBins.map((entry, index) => {
                      const isDownside = currentPrice > 0 && entry.mid < currentPrice
                      return (
                        <Cell
                          key={`cell-${index}`}
                          fill={isDownside ? 'rgba(239, 68, 68, 0.7)' : 'rgba(99, 102, 241, 0.75)'}
                        />
                      )
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state compact">
              <p>No distribution data available</p>
            </div>
          )}
          <div className="chart-legend-row">
            <span className="legend-item"><i className="legend-dot central" /> Normal Simulation Zone</span>
            <span className="legend-item"><i className="legend-dot downside" /> Below Current Price (Downside Risk)</span>
            <span className="legend-item"><i className="legend-dot median" /> Median Simulation</span>
            <span className="legend-item"><i className="legend-dot market" /> Market Price</span>
          </div>
        </Panel>
      </DataState>

      <Panel eyebrow="STRESS TESTING" title="LBO Macro & Operating Scenario Comparison">
        <DataState status={risk.data?.status || 'LOADING'} errors={risk.data?.errors} dataMode={dataMode}>
          <div className="scenario-grid">
            {Object.entries((risk.data?.data?.scenarios as Record<string, { IRR: number; MoIC: number }>) || {}).map(
              ([name, result]) => (
                <div className="scenario-card" key={name}>
                  <div className="scenario-header">
                    <span className="scenario-name">{name}</span>
                    <span className={`scenario-pill ${(result?.IRR || 0) >= 0.2 ? 'high' : (result?.IRR || 0) >= 0.1 ? 'med' : 'low'}`}>
                      {(result?.IRR || 0) >= 0.2 ? 'Strong' : (result?.IRR || 0) >= 0.1 ? 'Target' : 'Underperforming'}
                    </span>
                  </div>
                  <strong className="scenario-irr">{pct(result?.IRR)}</strong>
                  <span className="scenario-irr-label">Projected Sponsor IRR</span>
                  <div className="scenario-moic-row">
                    <span>Exit Multiple on Invested Capital</span>
                    <strong>{typeof result?.MoIC === 'number' ? `${result.MoIC.toFixed(2)}x MoIC` : '—'}</strong>
                  </div>
                </div>
              )
            )}
          </div>
        </DataState>
      </Panel>
    </>
  )
}

function createHistogramBins(values: number[], numBins = 20) {
  if (!values.length) return []
  const min = Math.min(...values)
  const max = Math.max(...values)
  const width = (max - min) / numBins || 1
  const bins = Array.from({ length: numBins }, (_, i) => {
    const bMin = min + i * width
    const bMax = min + (i + 1) * width
    const mid = (bMin + bMax) / 2
    return {
      min: bMin,
      max: bMax,
      mid,
      label: String(Math.round(mid)),
      count: 0,
    }
  })

  values.forEach((v) => {
    const idx = Math.min(numBins - 1, Math.max(0, Math.floor((v - min) / width)))
    bins[idx].count++
  })

  return bins
}

function getClosestBinLabel(bins: { label: string; mid: number }[], target: number) {
  if (!bins.length) return ''
  let closest = bins[0]
  let minDiff = Math.abs(bins[0].mid - target)
  for (let i = 1; i < bins.length; i++) {
    const diff = Math.abs(bins[i].mid - target)
    if (diff < minDiff) {
      minDiff = diff
      closest = bins[i]
    }
  }
  return closest.label
}
