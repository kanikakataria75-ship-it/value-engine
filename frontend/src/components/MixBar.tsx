import { useRef, type PointerEvent } from 'react'
import { clamp } from '../lib/utils'

/* Consideration mix as one bar with two draggable dividers: stock | cash on hand | new debt.
   The three shares always sum to 100%, so the mix can never be invalid. */

export interface Mix {
  stock: number
  cash: number
  debt: number
}

const SEGMENTS: { key: keyof Mix; label: string; className: string }[] = [
  { key: 'stock', label: 'New shares', className: 'mix-stock' },
  { key: 'cash', label: 'Cash on hand', className: 'mix-cash' },
  { key: 'debt', label: 'New debt', className: 'mix-debt' },
]

export function MixBar({ value, onChange }: { value: Mix; onChange: (mix: Mix) => void }) {
  const bar = useRef<HTMLDivElement>(null)
  const dragging = useRef<0 | 1 | null>(null)
  const first = value.stock
  const second = value.stock + value.cash

  const move = (event: PointerEvent<HTMLDivElement>) => {
    if (dragging.current === null || !bar.current) return
    const rect = bar.current.getBoundingClientRect()
    const at = Math.round(clamp((event.clientX - rect.left) / rect.width, 0, 1) * 200) / 200
    if (dragging.current === 0) {
      const stock = Math.min(at, second)
      onChange({ stock, cash: second - stock, debt: 1 - second })
    } else {
      const edge = Math.max(at, first)
      onChange({ stock: first, cash: edge - first, debt: 1 - edge })
    }
  }

  return (
    <div className="mix">
      <div ref={bar} className="mix-bar" onPointerMove={move} onPointerUp={() => (dragging.current = null)}
           onPointerLeave={() => (dragging.current = null)}>
        {SEGMENTS.map((segment) => (
          <div key={segment.key} className={`mix-seg ${segment.className}`} style={{ width: `${value[segment.key] * 100}%` }}>
            {value[segment.key] >= 0.12 && <span className="num">{Math.round(value[segment.key] * 100)}%</span>}
          </div>
        ))}
        {[first, second].map((at, index) => (
          <div key={index} className="mix-handle" style={{ left: `${at * 100}%` }} role="slider" tabIndex={0}
               aria-valuenow={Math.round(at * 100)} aria-valuemin={0} aria-valuemax={100}
               aria-label={index === 0 ? 'Share of new shares' : 'Share of cash plus shares'}
               onPointerDown={(e) => {
                 e.currentTarget.parentElement?.setPointerCapture(e.pointerId)
                 dragging.current = index as 0 | 1
               }}
               onKeyDown={(e) => {
                 if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
                 const delta = e.key === 'ArrowLeft' ? -0.05 : 0.05
                 if (index === 0) {
                   const stock = clamp(first + delta, 0, second)
                   onChange({ stock, cash: second - stock, debt: 1 - second })
                 } else {
                   const edge = clamp(second + delta, first, 1)
                   onChange({ stock: first, cash: edge - first, debt: 1 - edge })
                 }
               }} />
        ))}
      </div>
      <div className="mix-legend">
        {SEGMENTS.map((segment) => (
          <span key={segment.key}><i className={segment.className} />{segment.label} <b className="num">{Math.round(value[segment.key] * 100)}%</b></span>
        ))}
      </div>
    </div>
  )
}
