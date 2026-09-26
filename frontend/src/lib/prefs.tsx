import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import type { DataMode } from './api'
import { readStorage, usePrefersReducedMotion, writeStorage } from './utils'

export type Theme = 'observatory' | 'paper'

interface Prefs {
  theme: Theme
  setTheme: (theme: Theme, origin?: { x: number; y: number }) => void
  mode: DataMode
  setMode: (mode: DataMode) => void
  reducedMotion: boolean
}

const PrefsContext = createContext<Prefs | null>(null)

type ViewTransitionDocument = Document & {
  startViewTransition?: (callback: () => void) => { ready: Promise<void> }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStorage<Theme>('ve.theme', 'observatory'))
  const [mode, setModeState] = useState<DataMode>(() => readStorage<DataMode>('ve.mode', 'local'))
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'paper' ? '#efe9dd' : '#04050a')
  }, [theme])

  const setTheme = useCallback((next: Theme, origin?: { x: number; y: number }) => {
    writeStorage('ve.theme', next)
    const doc = document as ViewTransitionDocument
    if (!doc.startViewTransition || reducedMotion) {
      setThemeState(next)
      return
    }
    const x = origin?.x ?? window.innerWidth - 120
    const y = origin?.y ?? 32
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const transition = doc.startViewTransition(() => {
      flushSync(() => setThemeState(next))
      document.documentElement.dataset.theme = next
    })
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 820, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', pseudoElement: '::view-transition-new(root)' },
      )
    })
  }, [reducedMotion])

  const setMode = useCallback((next: DataMode) => {
    writeStorage('ve.mode', next)
    setModeState(next)
  }, [])

  const value = useMemo(() => ({ theme, setTheme, mode, setMode, reducedMotion }), [theme, setTheme, mode, setMode, reducedMotion])
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs(): Prefs {
  const context = useContext(PrefsContext)
  if (!context) throw new Error('usePrefs must be used inside PrefsProvider')
  return context
}
