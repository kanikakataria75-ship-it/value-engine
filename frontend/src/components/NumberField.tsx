import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { clamp, cn } from '../lib/utils'
import { IconReset } from './icons'

/* Precision input for model assumptions.
   - drag the label horizontally to scrub (hold Shift for fine steps)
   - drag or click the track; the gold tick marks the company baseline
   - arrow keys nudge (Shift x10); type an exact value and press Enter
   - a value that differs from the baseline shows a reset control */

export type Unit = 'pct' | 'x' | 'years' | 'money' | 'number'

const toDisplay = (value: number, unit: Unit) => (unit === 'pct' ? value * 100 : value)
const fromDisplay = (value: number, unit: Unit) => (unit === 'pct' ? value / 100 : value)
const suffix = (unit: Unit) => (unit === 'pct' ? '%' : unit === 'x' ? '×' : unit === 'years' ? 'yrs' : '')

export function NumberField({ label, value, baseline, onChange, unit = 'pct', min, max, step, digits, hint, disabled }: {
  label: string
  value: number | null | undefined
  baseline?: number | null
  onChange: (value: number | null) => void
  unit?: Unit
  min: number
  max: number
  step: number
  digits?: number
  hint?: string
  disabled?: boolean
}) {
  const current = value ?? baseline ?? min
  const precision = digits ?? (unit === 'pct' ? 1 : unit === 'years' ? 0 : 2)
  const [draft, setDraft] = useState<string | null>(null)
  const scrub = useRef<{ x: number; start: number } | null>(null)
  const track = useRef<HTMLDivElement>(null)
  const modified = value !== null && value !== undefined && baseline !== null && baseline !== undefined &&
    Math.abs(value - baseline) > step / 20

  useEffect(() => setDraft(null), [value])

  const commit = (next: number) => {
    const snapped = Math.round(clamp(next, min, max) / step) * step
    const rounded = Number(snapped.toFixed(10))
    onChange(baseline !== null && baseline !== undefined && Math.abs(rounded - baseline) < step / 20 ? null : rounded)
  }

  const onLabelDown = (event: PointerEvent<HTMLSpanElement>) => {
    if (disabled) return
    event.currentTarget.setPointerCapture(event.pointerId)
    scrub.current = { x: event.clientX, start: current }
    document.body.classList.add('scrubbing')
  }
  const onLabelMove = (event: PointerEvent<HTMLSpanElement>) => {
    if (!scrub.current) return
    const dx = event.clientX - scrub.current.x
    const perPixel = step / (event.shiftKey ? 12 : 3)
    commit(scrub.current.start + dx * perPixel)
  }
  const onLabelUp = () => {
    scrub.current = null
    document.body.classList.remove('scrubbing')
  }

  const fromTrack = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect()
    if (!rect) return
    commit(min + ((clientX - rect.left) / rect.width) * (max - min))
  }

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault()
      commit(current + (event.key === 'ArrowUp' ? 1 : -1) * step * (event.shiftKey ? 10 : 1))
    } else if (event.key === 'Enter') {
      event.currentTarget.blur()
    } else if (event.key === 'Escape') {
      setDraft(null)
      event.currentTarget.blur()
    }
  }

  const position = (v: number) => `${clamp((v - min) / (max - min), 0, 1) * 100}%`

  return (
    <div className={cn('field', modified && 'modified', disabled && 'disabled')} title={hint}>
      <div className="field-top">
        <span className="field-label" onPointerDown={onLabelDown} onPointerMove={onLabelMove} onPointerUp={onLabelUp}
              onPointerCancel={onLabelUp}>
          {label}
        </span>
        {modified && (
          <button type="button" className="field-reset" onClick={() => onChange(null)} title="Reset to company baseline">
            <IconReset size={12} />
          </button>
        )}
        <label className="field-input">
          <input
            type="text"
            inputMode="decimal"
            disabled={disabled}
            value={draft ?? toDisplay(current, unit).toFixed(precision)}
            onChange={(e) => setDraft(e.target.value)}
            onFocus={(e) => e.currentTarget.select()}
            onBlur={() => {
              if (draft !== null) {
                const parsed = Number(draft.replace(/[,%x×\s]/g, ''))
                if (Number.isFinite(parsed)) commit(fromDisplay(parsed, unit))
                setDraft(null)
              }
            }}
            onKeyDown={onKey}
            aria-label={label}
          />
          <span className="field-suffix">{suffix(unit)}</span>
        </label>
      </div>
      <div
        ref={track}
        className="field-track"
        onPointerDown={(e) => {
          if (disabled) return
          e.currentTarget.setPointerCapture(e.pointerId)
          fromTrack(e.clientX)
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1 && !disabled) fromTrack(e.clientX)
        }}
      >
        <div className="field-fill" style={{ width: position(current) }} />
        {baseline !== null && baseline !== undefined && <div className="field-base" style={{ left: position(baseline) }} title="Company baseline" />}
        <div className="field-thumb" style={{ left: position(current) }} />
      </div>
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  )
}

export function Toggle({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (value: boolean) => void; hint?: string }) {
  return (
    <label className="toggle" title={hint}>
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <i className="toggle-switch" aria-hidden="true" />
    </label>
  )
}
