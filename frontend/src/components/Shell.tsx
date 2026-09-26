import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Link, NavLink, Outlet, useLocation, useMatch } from 'react-router-dom'
import { usePrefs } from '../lib/prefs'
import { useMeta } from '../lib/queries'
import { webglAvailable } from '../lib/utils'
import { CommandPalette } from './CommandPalette'
import { Copilot, CopilotOrb } from './Copilot'
import { EngineMark, Wordmark } from './EngineMark'
import { IconCommand, IconMoon, IconSun } from './icons'
import { Orbit, Segmented } from './ui'

const IntroExperience = lazy(() => import('../three/IntroExperience'))

const NAV = [
  { to: '/', label: 'Observatory', end: true },
  { to: '/radar', label: 'Radar' },
  { to: '/methodology', label: 'Methodology' },
]

function shouldPlayIntro(reduced: boolean): boolean {
  try {
    if (reduced || !webglAvailable()) return false
    return window.sessionStorage.getItem('ve.intro') !== 'seen'
  } catch {
    return false
  }
}

export function Shell() {
  const { theme, setTheme, mode, setMode, reducedMotion } = usePrefs()
  const location = useLocation()
  const companyMatch = useMatch('/c/:ticker/*')
  const ticker = companyMatch?.params.ticker?.toUpperCase() ?? null
  const page = ticker ? (location.pathname.split('/')[3] ?? '') : ''
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const [intro, setIntro] = useState(() => shouldPlayIntro(reducedMotion))
  const meta = useMeta().data?.data

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLElement && /input|textarea/i.test(event.target.tagName)
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((v) => !v)
      } else if (event.key === '/' && !typing) {
        event.preventDefault()
        setPaletteOpen(true)
      } else if (event.key === '.' && (event.metaKey || event.ctrlKey)) {
        setCopilotOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }, [location.pathname])

  const finishIntro = useCallback(() => {
    try { window.sessionStorage.setItem('ve.intro', 'seen') } catch { /* ignore */ }
    setIntro(false)
  }, [])

  return (
    <div className={`app ${copilotOpen ? 'with-copilot' : ''}`}>
      <AnimatePresence>
        {intro && (
          <motion.div key="intro" className="intro-host" initial={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.9 }}>
            <Suspense fallback={<div className="intro-fallback" />}>
              <IntroExperience onDone={finishIntro} companyCount={meta?.company_count} />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>

      <header className="topbar">
        <Link to="/" className="brand" aria-label="ValuEngine home">
          <EngineMark />
          <Wordmark />
        </Link>
        <nav className="topnav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `topnav-link ${isActive ? 'on' : ''}`}>
              {({ isActive }) => (
                <>
                  {item.label}
                  {isActive && <motion.span layoutId="nav-underline" className="topnav-underline" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-right">
          <button type="button" className="search-trigger" onClick={() => setPaletteOpen(true)}>
            <span>Search companies</span>
            <kbd><IconCommand size={11} /> K</kbd>
          </button>
          <Segmented id="mode" size="sm" value={mode} onChange={setMode}
                     options={[{ value: 'local', label: 'Local' }, { value: 'live', label: 'Live' }]} />
          <button type="button" className="icon-btn theme-toggle" aria-label="Toggle theme"
                  title={theme === 'observatory' ? 'Paper theme' : 'Observatory theme'}
                  onClick={(e) => setTheme(theme === 'observatory' ? 'paper' : 'observatory', { x: e.clientX, y: e.clientY })}>
            {theme === 'observatory' ? <IconSun size={17} /> : <IconMoon size={17} />}
          </button>
        </div>
      </header>

      <main className="main">
        <AnimatePresence mode="wait">
          <motion.div key={ticker ? `c-${ticker}` : location.pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
            <Suspense fallback={<div className="page-center"><Orbit label="Loading" /></div>}>
              <Outlet context={{ openCopilot: () => setCopilotOpen(true) }} />
            </Suspense>
          </motion.div>
        </AnimatePresence>
      </main>

      <CopilotOrb open={copilotOpen} onClick={() => setCopilotOpen((v) => !v)} />
      <Copilot open={copilotOpen} onClose={() => setCopilotOpen(false)} ticker={ticker} page={page} />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} ticker={ticker}
                      onAskCopilot={() => setCopilotOpen(true)} onReplayIntro={() => setIntro(true)} />
      {mode === 'live' && !meta?.live_provider_configured && (
        <div className="live-note">Live mode without an Alpha Vantage key serves the local snapshot, labelled as a fallback.</div>
      )}
    </div>
  )
}

export interface ShellContext {
  openCopilot: () => void
}
