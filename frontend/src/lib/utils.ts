import { useEffect, useRef, useState } from 'react'

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export function extent(values: number[]): [number, number] {
  let min = Infinity
  let max = -Infinity
  for (const v of values) {
    if (Number.isFinite(v)) {
      if (v < min) min = v
      if (v > max) max = v
    }
  }
  if (min === Infinity) return [0, 1]
  if (min === max) return [min - 1, max + 1]
  return [min, max]
}

export function scaleLinear(domain: [number, number], range: [number, number]) {
  const [d0, d1] = domain
  const [r0, r1] = range
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  const scale = (v: number) => r0 + (v - d0) * k
  scale.invert = (px: number) => (k === 0 ? d0 : d0 + (px - r0) / k)
  return scale
}

/** "Nice" tick values between min and max. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min]
  const span = max - min
  const raw = span / count
  const power = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => span / s <= count) ?? 10 * power
  const start = Math.ceil(min / step) * step
  const ticks: number[] = []
  for (let v = start; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toFixed(12)))
  return ticks
}

export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, size] as const
}

export function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(id)
  }, [value, delay])
  return debounced
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!query) return
    const listener = () => setReduced(query.matches)
    query.addEventListener('change', listener)
    return () => query.removeEventListener('change', listener)
  }, [])
  return reduced
}

export function readStorage<T>(key: string, fallback: T, storage: Storage = window.localStorage): T {
  try {
    const raw = storage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeStorage(key: string, value: unknown, storage: Storage = window.localStorage): void {
  try {
    if (value === undefined) storage.removeItem(key)
    else storage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage can be unavailable (private mode); preferences simply won't persist */
  }
}

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

/** Deterministic JSON (object keys sorted at every level), used for query keys. */
export function stableHash(value: unknown): string {
  return JSON.stringify(value, (_key, v) =>
    v && typeof v === 'object' && !Array.isArray(v)
      ? Object.fromEntries(Object.entries(v as Record<string, unknown>).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
      : v,
  )
}

/** URL-safe anchor id for a heading. */
export const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

export type PatchOf<S> = { [K in keyof S]?: S[K] | null }

/** Apply a patch of overrides: null or undefined removes a field; an empty result collapses to undefined. */
export function mergeOverrides<S extends object>(section: S | undefined, patch: PatchOf<S>): S | undefined {
  const next: Record<string, unknown> = { ...(section ?? {}) }
  for (const [field, value] of Object.entries(patch)) {
    if (value === null || value === undefined) delete next[field]
    else next[field] = value
  }
  return Object.keys(next).length ? (next as S) : undefined
}

const SCENARIO_SECTIONS = ['dcf', 'excess_return', 'lbo', 'mna'] as const

/** Encode scenario overrides for a shareable link (base64url of JSON). */
export function encodeScenario(scenario: object): string {
  const bytes = new TextEncoder().encode(JSON.stringify(scenario))
  let binary = ''
  bytes.forEach((b) => { binary += String.fromCharCode(b) })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Decode a shared scenario, keeping only known sections of scalar overrides; null if malformed. */
export function decodeScenario(token: string): Record<string, Record<string, number | string | boolean>> | null {
  try {
    const base64 = token.replace(/-/g, '+').replace(/_/g, '/')
    const binary = atob(base64 + '='.repeat((4 - (base64.length % 4)) % 4))
    const parsed: unknown = JSON.parse(new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0))))
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    const clean: Record<string, Record<string, number | string | boolean>> = {}
    for (const section of SCENARIO_SECTIONS) {
      const value = (parsed as Record<string, unknown>)[section]
      if (!value || typeof value !== 'object' || Array.isArray(value)) continue
      const fields = Object.entries(value as Record<string, unknown>)
        .filter(([, v]) => (typeof v === 'number' && Number.isFinite(v)) || typeof v === 'string' || typeof v === 'boolean')
      if (fields.length) clean[section] = Object.fromEntries(fields) as Record<string, number | string | boolean>
    }
    // A deal needs an acquirer; without one the API would reject every scenario request.
    if (clean.mna && typeof clean.mna.acquirer_ticker !== 'string') delete clean.mna
    return clean
  } catch {
    return null
  }
}
