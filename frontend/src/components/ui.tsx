import { useEffect, useRef, useState, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import type { Flag, Status } from '../lib/api-types'
import { cn } from '../lib/utils'
import { IconAlert, IconCheck, IconInfo } from './icons'

/* ---------- Panel: glass surface with a cursor-following spotlight ---------- */
export function Panel({ title, eyebrow, action, children, className, style, flush }: {
  title?: ReactNode; eyebrow?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string
  style?: CSSProperties; flush?: boolean
}) {
  const ref = useRef<HTMLElement>(null)
  return (
    <section
      ref={ref}
      className={cn('panel', flush && 'flush', className)}
      style={style}
      onPointerMove={(e) => {
        const el = ref.current
        if (!el) return
        const rect = el.getBoundingClientRect()
        el.style.setProperty('--mx', `${e.clientX - rect.left}px`)
        el.style.setProperty('--my', `${e.clientY - rect.top}px`)
      }}
    >
      {(title || eyebrow || action) && (
        <header className="panel-head">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h3 className="panel-title">{title}</h3>}
          </div>
          {action && <div className="panel-action">{action}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

/* ---------- Animated number: tweens between values ---------- */
export function AnimatedNumber({ value, format, duration = 700 }: { value: number | null | undefined; format: (v: number) => string; duration?: number }) {
  const [display, setDisplay] = useState<number | null>(value ?? null)
  const from = useRef<number | null>(value ?? null)
  useEffect(() => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      setDisplay(null)
      return
    }
    const start = from.current ?? value
    const begin = performance.now()
    let frame = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - begin) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const current = start + (value - start) * eased
      setDisplay(current)
      if (t < 1) frame = requestAnimationFrame(step)
      else from.current = value
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])
  return <>{display === null ? '—' : format(display)}</>
}

/* ---------- Stat ---------- */
export function Stat({ label, value, sub, tone, size = 'md', hint }: {
  label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: 'pos' | 'neg' | 'gold' | ''; size?: 'sm' | 'md' | 'lg' | 'xl'; hint?: string
}) {
  return (
    <div className={cn('stat', `stat-${size}`)} title={hint}>
      <div className="stat-label">{label}</div>
      <div className={cn('stat-value num', tone)}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

/* ---------- Status pill ---------- */
const STATUS_TEXT: Partial<Record<Status | string, [string, string]>> = {
  VALID: ['Valid', 'ok'],
  REVIEW_REQUIRED: ['Review', 'warn'],
  INVALID: ['Invalid', 'bad'],
  UNAVAILABLE: ['Unavailable', 'off'],
  LOCAL: ['Local data', 'info'],
  LIVE: ['Live', 'live'],
  CACHED: ['Cached', 'info'],
  LOCAL_FALLBACK: ['Local fallback', 'warn'],
  RATE_LIMITED: ['Rate limited', 'warn'],
  ERROR: ['Error', 'bad'],
}

export function StatusPill({ status, label }: { status?: string | null; label?: string }) {
  const [text, tone] = STATUS_TEXT[status ?? ''] ?? [status ?? '…', 'off']
  return (
    <span className={cn('pill', `pill-${tone}`)}>
      <i className="pill-dot" />
      {label ?? text}
    </span>
  )
}

export function Pill({ children, tone = 'off', className }: { children: ReactNode; tone?: 'ok' | 'warn' | 'bad' | 'info' | 'gold' | 'off'; className?: string }) {
  return <span className={cn('pill', `pill-${tone}`, className)}>{children}</span>
}

/* ---------- Buttons ---------- */
export function Button({ variant = 'ghost', icon, children, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'quiet'; icon?: ReactNode
}) {
  return (
    <button type="button" className={cn('btn', `btn-${variant}`, className)} {...props}>
      {icon}
      {children && <span>{children}</span>}
    </button>
  )
}

/* ---------- Segmented control with a sliding indicator ---------- */
export function Segmented<V extends string>({ options, value, onChange, id, size = 'md' }: {
  options: { value: V; label: ReactNode }[]; value: V; onChange: (value: V) => void; id: string; size?: 'sm' | 'md'
}) {
  return (
    <div className={cn('segmented', `segmented-${size}`)} role="tablist">
      {options.map((option) => (
        <button key={option.value} type="button" role="tab" aria-selected={option.value === value}
                className={cn('segmented-item', option.value === value && 'on')} onClick={() => onChange(option.value)}>
          {option.value === value && <motion.span layoutId={`seg-${id}`} className="segmented-indicator" transition={{ type: 'spring', stiffness: 480, damping: 38 }} />}
          <span className="segmented-label">{option.label}</span>
        </button>
      ))}
    </div>
  )
}

/* ---------- Loading / empty ---------- */
export function Skeleton({ height = 18, width = '100%', radius = 8, className }: { height?: number | string; width?: number | string; radius?: number; className?: string }) {
  return <div className={cn('skeleton', className)} style={{ height, width, borderRadius: radius }} />
}

export function Orbit({ label }: { label?: string }) {
  return (
    <div className="orbit-loader" role="status">
      <span className="orbit-ring a" />
      <span className="orbit-ring b" />
      <span className="orbit-core" />
      {label && <span className="orbit-label">{label}</span>}
    </div>
  )
}

export function Empty({ title, message, action }: { title: string; message?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true"><span /><span /><span /></div>
      <h4>{title}</h4>
      {message && <p>{message}</p>}
      {action}
    </div>
  )
}

/** Loading / error / empty handling for an envelope-backed block. */
export function Gate({ loading, error, children, minHeight = 160, label }: {
  loading: boolean; error?: string | null; children: ReactNode; minHeight?: number; label?: string
}) {
  if (loading) return <div className="gate" style={{ minHeight }}><Orbit label={label ?? 'Computing'} /></div>
  if (error) return <div className="gate" style={{ minHeight }}><Empty title="Not available" message={error} /></div>
  return <>{children}</>
}

/* ---------- Flags ---------- */
export function Flags({ flags, empty = 'Nothing to review.' }: { flags: Flag[]; empty?: string }) {
  if (!flags.length) {
    return <div className="flags-empty"><IconCheck size={15} /> {empty}</div>
  }
  return (
    <ul className="flags">
      {flags.map((flag, i) => (
        <li key={`${flag.code}-${i}`} className={cn('flag', `flag-${flag.severity.toLowerCase()}`)}>
          <span className="flag-icon">{flag.severity === 'INFO' ? <IconInfo size={14} /> : <IconAlert size={14} />}</span>
          <span className="flag-body">
            <b>{flag.module}</b>
            {flag.message}
          </span>
        </li>
      ))}
    </ul>
  )
}

/* ---------- Key/value list ---------- */
export function KeyValues({ rows }: { rows: [ReactNode, ReactNode, string?][] }) {
  return (
    <dl className="kv">
      {rows.map(([k, v, tone], i) => (
        <div key={i} className="kv-row">
          <dt>{k}</dt>
          <dd className={cn('num', tone)}>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Meter({ value, tone = 'gold', label }: { value: number; tone?: 'gold' | 'pos' | 'neg'; label?: string }) {
  return (
    <div className="meter" aria-label={label}>
      <div className={cn('meter-fill', tone)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  )
}

export function PageTitle({ eyebrow, title, lede, actions }: { eyebrow: string; title: ReactNode; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-title reveal">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="display page-h1">{title}</h1>
        {lede && <p className="page-lede">{lede}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}
