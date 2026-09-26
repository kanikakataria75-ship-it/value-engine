import { useMemo, useState, type ReactNode } from 'react'
import { clamp, cn, extent, niceTicks, scaleLinear, useElementSize } from '../../lib/utils'

/* Custom SVG charts. Colours come from CSS variables so every chart follows the theme. */

const PAD = { top: 14, right: 16, bottom: 26, left: 52 }
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-03-14" -> "Mar ’26". */
export function monthLabel(iso: string): string {
  const month = Number(iso.slice(5, 7))
  return month ? `${MONTHS[month - 1]} ’${iso.slice(2, 4)}` : iso
}

function Frame({ height, children, className }: { height: number; className?: string; children: (width: number) => ReactNode }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  return (
    <div ref={ref} className={cn('chart', className)} style={{ height }}>
      {size.width > 0 && children(size.width)}
    </div>
  )
}

function Tip({ x, y, children, width }: { x: number; y: number; children: ReactNode; width: number }) {
  const left = clamp(x + 12, 4, Math.max(4, width - 180))
  return (
    <div className="chart-tip" style={{ left, top: Math.max(0, y - 8) }}>
      {children}
    </div>
  )
}

/* ---------- Area / line over time, with an optional heat strip (e.g. regime probability) ---------- */
export interface TimePoint { date: string; value: number }

export function AreaChart({ data, height = 240, format, strip, stripLabel, markers = [], color = 'var(--gold)' }: {
  data: TimePoint[]; height?: number; format: (v: number) => string; strip?: number[]; stripLabel?: string
  markers?: { value: number; label: string; color?: string }[]; color?: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  return (
    <Frame height={height}>
      {(width) => {
        const stripH = strip ? 14 : 0
        const innerH = height - PAD.top - PAD.bottom - stripH - (strip ? 8 : 0)
        const values = data.map((d) => d.value).concat(markers.map((m) => m.value))
        const [lo, hi] = extent(values)
        const pad = (hi - lo) * 0.08
        const y = scaleLinear([lo - pad, hi + pad], [PAD.top + innerH, PAD.top])
        const x = scaleLinear([0, Math.max(1, data.length - 1)], [PAD.left, width - PAD.right])
        const line = data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join('')
        const area = `${line}L${x(data.length - 1)},${PAD.top + innerH}L${x(0)},${PAD.top + innerH}Z`
        const ticks = niceTicks(lo - pad, hi + pad, 4)
        const gid = `area-${Math.round(width)}-${data.length}`
        const labelEvery = Math.max(1, Math.round(data.length / 5))
        return (
          <>
            <svg width={width} height={height}
                 onPointerMove={(e) => {
                   const rect = e.currentTarget.getBoundingClientRect()
                   setHover(Math.round(clamp(x.invert(e.clientX - rect.left), 0, data.length - 1)))
                 }}
                 onPointerLeave={() => setHover(null)}>
              <defs>
                <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity="0.28" />
                  <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
              </defs>
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
                  <text x={PAD.left - 8} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">{format(t)}</text>
                </g>
              ))}
              <path d={area} fill={`url(#${gid})`} />
              <path d={line} fill="none" stroke={color} strokeWidth={1.6} className="draw" />
              {markers.map((m) => (
                <g key={m.label}>
                  <line x1={PAD.left} x2={width - PAD.right} y1={y(m.value)} y2={y(m.value)} stroke={m.color ?? 'var(--text-2)'} strokeDasharray="4 4" strokeWidth={1} />
                  <text x={width - PAD.right} y={y(m.value) - 5} textAnchor="end" className="marker-label" fill={m.color ?? 'var(--text-2)'}>{m.label}</text>
                </g>
              ))}
              {data.map((d, i) => (i % labelEvery === 0 ? (
                <text key={d.date} x={x(i)} y={height - 6} className="tick" textAnchor="middle">{monthLabel(d.date)}</text>
              ) : null))}
              {strip && (
                <g>
                  {strip.map((p, i) => (
                    <rect key={i} x={x(i) - (width - PAD.left - PAD.right) / strip.length / 2} y={PAD.top + innerH + 8}
                          width={(width - PAD.left - PAD.right) / strip.length + 0.5} height={stripH}
                          fill="var(--ember)" opacity={0.08 + p * 0.8} />
                  ))}
                  <text x={PAD.left - 8} y={PAD.top + innerH + 8 + stripH / 2} className="tick" textAnchor="end" dominantBaseline="middle">{stripLabel}</text>
                </g>
              )}
              {hover !== null && data[hover] && (
                <g>
                  <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} className="crosshair" />
                  <circle cx={x(hover)} cy={y(data[hover].value)} r={4} fill={color} className="glow-dot" />
                </g>
              )}
            </svg>
            {hover !== null && data[hover] && (
              <Tip x={x(hover)} y={y(data[hover].value)} width={width}>
                <b className="num">{format(data[hover].value)}</b>
                <span>{data[hover].date}{strip ? ` · high-vol ${Math.round((strip[hover] ?? 0) * 100)}%` : ''}</span>
              </Tip>
            )}
          </>
        )
      }}
    </Frame>
  )
}

/* ---------- Histogram with vertical markers ---------- */
export function Histogram({ bins, markers = [], format, height = 240, splitAt }: {
  bins: { start: number; end: number; count: number }[]; markers?: { value: number; label: string; tone?: string }[]
  format: (v: number) => string; height?: number; splitAt?: number | null
}) {
  const [hover, setHover] = useState<number | null>(null)
  return (
    <Frame height={height}>
      {(width) => {
        if (!bins.length) return null
        const lo = Math.min(bins[0].start, ...markers.map((m) => m.value))
        const hi = Math.max(bins[bins.length - 1].end, ...markers.map((m) => m.value))
        const x = scaleLinear([lo, hi], [PAD.left, width - PAD.right])
        const maxCount = Math.max(...bins.map((b) => b.count), 1)
        const y = scaleLinear([0, maxCount], [height - PAD.bottom, PAD.top + 18])
        const ticks = niceTicks(lo, hi, 5)
        return (
          <>
            <svg width={width} height={height} onPointerLeave={() => setHover(null)}>
              <line x1={PAD.left} x2={width - PAD.right} y1={height - PAD.bottom} y2={height - PAD.bottom} className="axis" />
              {ticks.map((t) => <text key={t} x={x(t)} y={height - 8} className="tick" textAnchor="middle">{format(t)}</text>)}
              {bins.map((b, i) => {
                const below = splitAt !== null && splitAt !== undefined && (b.start + b.end) / 2 < splitAt
                return (
                  <rect key={i} x={x(b.start) + 0.8} y={y(b.count)} width={Math.max(1, x(b.end) - x(b.start) - 1.6)}
                        height={height - PAD.bottom - y(b.count)} rx={2}
                        className={cn('bar', below ? 'bar-neg' : 'bar-pos', hover === i && 'hover')}
                        onPointerEnter={() => setHover(i)} />
                )
              })}
              {markers.map((m, i) => (
                <g key={m.label}>
                  <line x1={x(m.value)} x2={x(m.value)} y1={PAD.top + 4} y2={height - PAD.bottom} stroke={m.tone ?? 'var(--text-1)'}
                        strokeWidth={m.tone ? 1.6 : 1} strokeDasharray={m.tone ? undefined : '3 4'} />
                  <text x={x(m.value)} y={PAD.top + (i % 2) * 12} className="marker-label" textAnchor="middle" fill={m.tone ?? 'var(--text-1)'}>{m.label}</text>
                </g>
              ))}
            </svg>
            {hover !== null && bins[hover] && (
              <Tip x={x(bins[hover].start)} y={y(bins[hover].count)} width={width}>
                <b className="num">{format(bins[hover].start)} – {format(bins[hover].end)}</b>
                <span>{bins[hover].count} scenarios</span>
              </Tip>
            )}
          </>
        )
      }}
    </Frame>
  )
}

/* ---------- Heatmap: diverging around a reference value (e.g. market price) ---------- */
export function Heatmap({ rows, cols, values, rowLabel, colLabel, format, axisFormat, reference, baseRow = 2, baseCol = 2 }: {
  rows: number[]; cols: number[]; values: (number | null)[][]; rowLabel: string; colLabel: string
  format: (v: number) => string; axisFormat: (v: number) => string; reference?: number | null; baseRow?: number; baseCol?: number
}) {
  const flat = values.flat().filter((v): v is number => v !== null)
  const ref = reference ?? (flat.length ? flat.reduce((a, b) => a + b, 0) / flat.length : 0)
  const span = Math.max(...flat.map((v) => Math.abs(v - ref)), 1e-9)
  return (
    <div className="heatmap" style={{ gridTemplateColumns: `64px repeat(${cols.length}, minmax(0, 1fr))` }}>
      <div className="heatmap-corner"><span>{rowLabel}</span><i>↓</i><span>{colLabel}</span><i>→</i></div>
      {cols.map((c, j) => <div key={`c${j}`} className={cn('heatmap-col', j === baseCol && 'base')}>{axisFormat(c)}</div>)}
      {rows.map((r, i) => (
        <div key={`r${i}`} className="heatmap-row">
          <div className={cn('heatmap-rowlabel', i === baseRow && 'base')}>{axisFormat(r)}</div>
          {values[i]?.map((v, j) => {
            const d = v === null ? 0 : (v - ref) / span
            const bg = v === null ? 'transparent'
              : d >= 0 ? `color-mix(in srgb, var(--gold) ${Math.round(8 + d * 52)}%, transparent)`
                : `color-mix(in srgb, var(--ember) ${Math.round(8 - d * 48)}%, transparent)`
            return (
              <div key={j} className={cn('heatmap-cell num', i === baseRow && j === baseCol && 'base')} style={{ background: bg }}
                   title={v === null ? 'Not defined (WACC ≤ g)' : format(v)}>
                {v === null ? '—' : format(v)}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

/* ---------- Tornado ---------- */
export function Tornado({ rows, base, format, inputFormat }: {
  rows: { label: string; low: number; high: number; lowInput: number; highInput: number }[]
  base: number; format: (v: number) => string; inputFormat: (v: number) => string
}) {
  const all = rows.flatMap((r) => [r.low, r.high]).concat(base)
  const [lo, hi] = extent(all)
  return (
    <div className="tornado">
      {rows.map((r) => {
        const pos = (v: number) => ((v - lo) / (hi - lo)) * 100
        const left = Math.min(pos(r.low), pos(r.high))
        const right = Math.max(pos(r.low), pos(r.high))
        return (
          <div key={r.label} className="tornado-row">
            <div className="tornado-label">{r.label}<span>{inputFormat(r.lowInput)} → {inputFormat(r.highInput)}</span></div>
            <div className="tornado-track">
              <div className="tornado-base" style={{ left: `${pos(base)}%` }} />
              <div className="tornado-bar neg" style={{ left: `${left}%`, width: `${Math.max(0.4, pos(base) - left)}%` }} />
              <div className="tornado-bar pos" style={{ left: `${pos(base)}%`, width: `${Math.max(0.4, right - pos(base))}%` }} />
              <span className="tornado-value lo num" style={{ left: `${left}%` }}>{format(Math.min(r.low, r.high))}</span>
              <span className="tornado-value hi num" style={{ left: `${right}%` }}>{format(Math.max(r.low, r.high))}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ---------- Waterfall (bridge) ---------- */
/** Split a tick label over two lines when it is wider than its band (about 6 px per character). */
function wrap(label: string, band: number): string[] {
  if (label.length * 6 <= band - 4 || !label.includes(' ')) return [label]
  const words = label.split(' ')
  let best = [label]
  let bestWidth = Infinity
  for (let i = 1; i < words.length; i++) {
    const lines = [words.slice(0, i).join(' '), words.slice(i).join(' ')]
    const width = Math.max(...lines.map((l) => l.length))
    if (width < bestWidth) {
      best = lines
      bestWidth = width
    }
  }
  return best
}

export function Waterfall({ steps, format, height = 220 }: {
  steps: { label: string; value: number; total?: boolean }[]; format: (v: number) => string; height?: number
}) {
  return (
    <Frame height={height}>
      {(width) => {
        let running = 0
        const bars = steps.map((s) => {
          const start = s.total ? 0 : running
          const end = s.total ? s.value : running + s.value
          running = s.total ? s.value : end
          return { ...s, start, end }
        })
        const [lo, hi] = extent(bars.flatMap((b) => [b.start, b.end]).concat(0))
        const y = scaleLinear([Math.min(0, lo), hi * 1.08], [height - PAD.bottom - 10, PAD.top + 14])
        const band = (width - PAD.left - PAD.right) / steps.length
        return (
          <svg width={width} height={height}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} className="axis" />
            {bars.map((b, i) => {
              const top = y(Math.max(b.start, b.end))
              const h = Math.max(1.5, Math.abs(y(b.start) - y(b.end)))
              const cls = b.total ? 'wf-total' : b.value >= 0 ? 'wf-up' : 'wf-down'
              const cx = PAD.left + band * i + band / 2
              return (
                <g key={b.label}>
                  <rect x={cx - band * 0.32} y={top} width={band * 0.64} height={h} rx={3} className={cls} />
                  {i < bars.length - 1 && (
                    <line x1={cx + band * 0.32} x2={cx + band * 0.68} y1={y(b.end)} y2={y(b.end)} className="wf-link" />
                  )}
                  <text x={cx} y={top - 6} textAnchor="middle" className="wf-value">{b.total ? format(b.value) : `${b.value >= 0 ? '+' : ''}${format(b.value)}`}</text>
                  <text x={cx} y={height - (wrap(b.label, band).length > 1 ? 18 : 8)} textAnchor="middle" className="tick">
                    {wrap(b.label, band).map((line, li) => <tspan key={li} x={cx} dy={li ? 11 : 0}>{line}</tspan>)}
                  </text>
                </g>
              )
            })}
          </svg>
        )
      }}
    </Frame>
  )
}

/* ---------- Scatter ---------- */
export interface ScatterPoint { x: number; y: number; id?: string; label?: string; tone?: 'gold' | 'aurora' | 'ember' | 'violet' | 'ivory'; size?: number }

export function Scatter({ points, xLabel, yLabel, format, height = 320, diagonal, onPick, highlight }: {
  points: ScatterPoint[]; xLabel: string; yLabel: string; format: (v: number) => string; height?: number
  diagonal?: boolean; onPick?: (point: ScatterPoint) => void; highlight?: string | null
}) {
  const [hover, setHover] = useState<ScatterPoint | null>(null)
  return (
    <Frame height={height}>
      {(width) => {
        const [x0, x1] = extent(points.map((p) => p.x))
        const [y0, y1] = extent(points.map((p) => p.y))
        const lo = diagonal ? Math.min(x0, y0) : x0
        const hiX = diagonal ? Math.max(x1, y1) : x1
        const x = scaleLinear([lo, hiX], [PAD.left, width - PAD.right])
        const y = scaleLinear([diagonal ? lo : y0, diagonal ? hiX : y1], [height - PAD.bottom - 8, PAD.top])
        return (
          <>
            <svg width={width} height={height}>
              {niceTicks(lo, hiX, 5).map((t) => (
                <g key={`x${t}`}>
                  <line x1={x(t)} x2={x(t)} y1={PAD.top} y2={height - PAD.bottom - 8} className="grid" />
                  <text x={x(t)} y={height - 10} textAnchor="middle" className="tick">{format(t)}</text>
                </g>
              ))}
              {niceTicks(diagonal ? lo : y0, diagonal ? hiX : y1, 5).map((t) => (
                <g key={`y${t}`}>
                  <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
                  <text x={PAD.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle" className="tick">{format(t)}</text>
                </g>
              ))}
              {diagonal && (
                <line x1={x(lo)} y1={y(lo)} x2={x(hiX)} y2={y(hiX)} stroke="var(--gold)" strokeDasharray="5 5" strokeWidth={1} opacity={0.6} />
              )}
              {points.map((p, i) => (
                <circle key={p.id ?? i} cx={x(p.x)} cy={y(p.y)} r={(p.size ?? 3.2) * (highlight && p.id === highlight ? 2 : 1)}
                        className={cn('dot', `dot-${p.tone ?? 'ivory'}`, highlight && p.id === highlight && 'dot-hi', onPick && 'pickable')}
                        onPointerEnter={() => setHover(p)} onPointerLeave={() => setHover(null)} onClick={() => onPick?.(p)} />
              ))}
              <text x={width - PAD.right} y={height - 26} textAnchor="end" className="axis-title">{xLabel} →</text>
              <text x={PAD.left + 4} y={PAD.top + 4} className="axis-title">↑ {yLabel}</text>
            </svg>
            {hover && (
              <Tip x={x(hover.x)} y={y(hover.y)} width={width}>
                <b>{hover.label ?? hover.id}</b>
                <span className="num">{xLabel}: {format(hover.x)} · {yLabel}: {format(hover.y)}</span>
              </Tip>
            )}
          </>
        )
      }}
    </Frame>
  )
}

/* ---------- Radial gauge ---------- */
export function Gauge({ value, label, sub, tone = 'gold', size = 150 }: { value: number | null; label: string; sub?: string; tone?: 'gold' | 'pos' | 'neg'; size?: number }) {
  const r = size / 2 - 10
  const circumference = Math.PI * r * 1.5
  const v = value === null ? 0 : clamp(value, 0, 1)
  return (
    <div className="gauge" style={{ width: size, height: size * 0.82 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g transform={`rotate(135 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} className="gauge-track" strokeDasharray={`${circumference} ${circumference * 4}`} />
          <circle cx={size / 2} cy={size / 2} r={r} className={cn('gauge-fill', tone)} strokeDasharray={`${circumference * v} ${circumference * 4}`} />
        </g>
      </svg>
      <div className="gauge-center">
        <b className="num">{label}</b>
        {sub && <span>{sub}</span>}
      </div>
    </div>
  )
}

export function Ring({ value, size = 64, tone = 'gold', children }: { value: number; size?: number; tone?: 'gold' | 'pos' | 'neg'; children?: ReactNode }) {
  const r = size / 2 - 5
  const c = 2 * Math.PI * r
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} className="gauge-track" />
        <circle cx={size / 2} cy={size / 2} r={r} className={cn('gauge-fill', tone)} strokeDasharray={`${c * clamp(value, 0, 1)} ${c}`}
                transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-center">{children}</div>
    </div>
  )
}

/* ---------- Multi-line chart ---------- */
export function Lines({ series, height = 220, format, labels, zero }: {
  series: { name: string; color: string; values: number[]; dashed?: boolean }[]; height?: number
  format: (v: number) => string; labels: string[]; zero?: boolean
}) {
  return (
    <Frame height={height}>
      {(width) => {
        const all = series.flatMap((s) => s.values).concat(zero ? [0] : [])
        const [lo, hi] = extent(all)
        const y = scaleLinear([lo, hi], [height - PAD.bottom, PAD.top])
        const n = Math.max(...series.map((s) => s.values.length), 2)
        const x = scaleLinear([0, n - 1], [PAD.left, width - PAD.right])
        const every = Math.max(1, Math.round(n / 5))
        return (
          <svg width={width} height={height}>
            {niceTicks(lo, hi, 4).map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className={t === 0 ? 'axis' : 'grid'} />
                <text x={PAD.left - 8} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">{format(t)}</text>
              </g>
            ))}
            {labels.map((l, i) => (i % every === 0 ? <text key={l + i} x={x(i)} y={height - 8} className="tick" textAnchor="middle">{l}</text> : null))}
            {series.map((s) => (
              <path key={s.name} d={s.values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')}
                    fill="none" stroke={s.color} strokeWidth={1.6} strokeDasharray={s.dashed ? '4 4' : undefined} className="draw" />
            ))}
          </svg>
        )
      }}
    </Frame>
  )
}

/* ---------- Stacked area (e.g. LBO debt paydown) ---------- */
export function StackedArea({ layers, labels, format, height = 240 }: {
  layers: { name: string; color: string; values: number[] }[]; labels: string[]; format: (v: number) => string; height?: number
}) {
  return (
    <Frame height={height}>
      {(width) => {
        const n = labels.length
        const totals = labels.map((_, i) => layers.reduce((sum, l) => sum + Math.max(0, l.values[i] ?? 0), 0))
        const y = scaleLinear([0, Math.max(...totals, 1) * 1.1], [height - PAD.bottom, PAD.top])
        const x = scaleLinear([0, Math.max(1, n - 1)], [PAD.left, width - PAD.right])
        const stacks: number[][] = []
        layers.forEach((layer, li) => {
          stacks[li] = labels.map((_, i) => (li ? stacks[li - 1][i] : 0) + Math.max(0, layer.values[i] ?? 0))
        })
        return (
          <svg width={width} height={height}>
            {niceTicks(0, Math.max(...totals, 1) * 1.1, 4).map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
                <text x={PAD.left - 8} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">{format(t)}</text>
              </g>
            ))}
            {layers.map((layer, li) => {
              const top = stacks[li].map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join('')
              const bottom = (li ? stacks[li - 1] : labels.map(() => 0)).map((v, i) => `L${x(i)},${y(v)}`).reverse().join('')
              return <path key={layer.name} d={`${top}${bottom}Z`} fill={layer.color} opacity={0.72} stroke={layer.color} strokeWidth={1} />
            })}
            {labels.map((l, i) => <text key={l} x={x(i)} y={height - 8} className="tick" textAnchor="middle">{l}</text>)}
          </svg>
        )
      }}
    </Frame>
  )
}

/* ---------- Sparkline ---------- */
export function Sparkline({ values, width = 96, height = 28, color = 'var(--gold)' }: { values: number[]; width?: number; height?: number; color?: string }) {
  const path = useMemo(() => {
    if (values.length < 2) return ''
    const [lo, hi] = extent(values)
    const x = scaleLinear([0, values.length - 1], [2, width - 2])
    const y = scaleLinear([lo, hi], [height - 3, 3])
    return values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  }, [values, width, height])
  return (
    <svg width={width} height={height} className="sparkline">
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} />
      {values.length > 1 && <circle cx={width - 2} cy={(() => { const [lo, hi] = extent(values); return scaleLinear([lo, hi], [height - 3, 3])(values[values.length - 1]) })()} r={2.2} fill={color} />}
    </svg>
  )
}

/* ---------- 2D football field (fallback for the 3D horizon) ---------- */
export function FootballField({ ranges, market, format }: {
  ranges: { key: string; label: string; low: number; high: number; mid?: number | null; tone: string }[]; market: number; format: (v: number) => string
}) {
  const [lo, hi] = extent(ranges.flatMap((r) => [r.low, r.high]).concat(market))
  const pad = (hi - lo) * 0.08
  const pos = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100
  return (
    <div className="ff">
      {ranges.map((r) => (
        <div key={r.key} className="ff-row">
          <div className="ff-label">{r.label}</div>
          <div className="ff-track">
            <div className={`ff-bar tone-${r.tone}`} style={{ left: `${pos(r.low)}%`, width: `${Math.max(0.6, pos(r.high) - pos(r.low))}%` }} />
            {r.mid != null && <div className="ff-mid" style={{ left: `${pos(r.mid)}%` }} />}
            <span className="ff-val num" style={{ left: `${pos(r.high)}%` }}>{format(r.low)} – {format(r.high)}</span>
          </div>
        </div>
      ))}
      <div className="ff-market" style={{ left: `calc(var(--ff-label) + (100% - var(--ff-label)) * ${pos(market) / 100})` }}>
        <span>Market {format(market)}</span>
      </div>
    </div>
  )
}
