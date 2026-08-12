import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { StatusBadge } from './ui'

const nav = [
  { section: 'OVERVIEW', links: [['Dashboard', '/']] },
  {
    section: 'MODELING',
    links: [
      ['DCF', '/dcf'],
      ['M&A', '/mna'],
      ['LBO', '/lbo'],
      ['Trading Comps', '/comps'],
      ['Transaction Comps', '/comps'],
    ],
  },
  {
    section: 'ANALYTICS',
    links: [
      ['Sensitivity', '/analytics'],
      ['Monte Carlo', '/analytics'],
      ['Risk', '/analytics'],
    ],
  },
  { section: 'RESEARCH', links: [['Company', '/company'], ['Data', '/data']] },
  { section: 'OUTPUTS', links: [['Reports', '/reports'], ['Excel', '/reports'], ['Audit', '/audit']] },
]

export function AppShell({
  ticker,
  setTicker,
  children,
}: {
  ticker: string
  setTicker: (value: string) => void
  children: React.ReactNode
}) {
  const context = useQuery({ queryKey: ['company', ticker], queryFn: () => api.company(ticker) })
  const status = context.data?.status || 'LOADING'
  const provenance = context.data?.provenance || {}

  const isLive = status === 'LIVE'
  const isCached = status === 'CACHED'
  const isRateLimited = status === 'RATE_LIMITED'

  const sourceName = String(
    provenance.source_name ||
      (isLive || isCached ? 'Alpha Vantage' : 'ValuEngine Preset')
  )
  const updated = String(provenance.retrieved_at || provenance.retrieved_date || '')

  let bannerClass = 'demo-banner'
  let bannerTitle = 'DEMONSTRATION DATA'
  let bannerDetail = 'Alpha Vantage unavailable. Outputs generated from validated local financial engines.'

  if (isLive) {
    bannerClass = 'demo-banner live-banner'
    bannerTitle = 'LIVE DATA'
    bannerDetail = `Source: ${sourceName}${updated ? ` · Updated: ${updated}` : ''}`
  } else if (isCached) {
    bannerClass = 'demo-banner cached-banner'
    bannerTitle = 'CACHED PROVIDER DATA'
    bannerDetail = `Source: ${sourceName} (Local Cache)${updated ? ` · Cached: ${updated}` : ''}`
  } else if (isRateLimited) {
    bannerClass = 'demo-banner rate-limited-banner'
    bannerTitle = 'RATE LIMITED (CIRCUIT BREAKER ACTIVE)'
    bannerDetail = `Alpha Vantage rate limit reached. Circuit breaker active; local preset or cached fallback in use.`
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="wordmark">
          <span className="wordmark-mark">V</span>VALU<span>ENGINE</span>
          <small>INSTITUTIONAL INTELLIGENCE</small>
        </div>
        <nav>
          {nav.map((group) => (
            <div className="nav-group" key={group.section}>
              <p>{group.section}</p>
              {group.links.map(([label, to]) => (
                <NavLink key={label} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <button className="copilot-entry" type="button">
          <span className="copilot-spark">✦</span>
          <span>
            AI COPILOT<small>Coming Soon</small>
          </span>
          <b>›</b>
        </button>
      </aside>
      <main>
        <header className="topbar">
          <div className="context">
            <span>ACTIVE COMPANY</span>
            <select
              aria-label="Active company"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
            >
              <option>AAPL</option>
              <option>MSFT</option>
              <option>NVDA</option>
            </select>
          </div>
          <label className="search">
            <span>⌕</span>
            <input placeholder="Search companies, models, reports..." aria-label="Global search" />
          </label>
          <div className="top-status">
            <StatusBadge status={status} />
            <span className="status-dot">
              {isLive
                ? `${sourceName} (Live)`
                : isCached
                ? `${sourceName} (Cached)`
                : isRateLimited
                ? 'Circuit Breaker Active'
                : 'Alpha Vantage Unavailable'}
            </span>
            <button aria-label="Help" className="top-icon">
              ?
            </button>
            <button aria-label="Notifications" className="top-icon">
              ◦
            </button>
            <button aria-label="Settings" className="avatar">
              VE
            </button>
          </div>
        </header>
        <div className={bannerClass}>
          <span className="status-light" />
          <strong>{bannerTitle}</strong>
          <span>{bannerDetail}</span>
          <a href="/audit">Review provenance →</a>
        </div>
        <div className="workspace">{children}</div>
      </main>
    </div>
  )
}
