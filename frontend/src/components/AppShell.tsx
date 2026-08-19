import { useState, useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { StatusBadge, money } from './ui'
import { useTheme } from '../context/ThemeContext'
import { CopilotPanel } from './CopilotPanel'
import type { DataMode, SearchResult } from '../types/api'

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
      ['Risk Lab', '/risk-lab'],
    ],
  },
  { section: 'RESEARCH', links: [['Company', '/company'], ['Data', '/data']] },
  { section: 'OUTPUTS', links: [['Reports', '/reports'], ['Excel', '/reports'], ['Audit', '/audit']] },
]

export function AppShell({
  ticker,
  setTicker,
  dataMode,
  setDataMode,
  children,
}: {
  ticker: string
  setTicker: (value: string) => void
  dataMode: DataMode
  setDataMode: (mode: DataMode) => void
  children: React.ReactNode
}) {
  const { theme, setTheme } = useTheme()
  const { pathname } = useLocation()
  const [isThemeOpen, setIsThemeOpen] = useState(false)
  const themeRef = useRef<HTMLDivElement>(null)

  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const [isCopilotOpen, setIsCopilotOpen] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  // Debounce search query 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Fetch company search suggestions
  const searchResults = useQuery({
    queryKey: ['search', debouncedSearch, dataMode],
    queryFn: () => api.searchCompanies(debouncedSearch, dataMode, 10),
    enabled: debouncedSearch.length >= 1,
    staleTime: 60000,
  })

  // Fetch active company details
  const context = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const status = context.data?.status || 'LOADING'
  const companyData = context.data?.data
  const provenance = context.data?.provenance || {}

  // Click outside listener for search & theme dropdowns
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
      if (themeRef.current && !themeRef.current.contains(event.target as Node)) {
        setIsThemeOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelectCompany = (item: SearchResult) => {
    setTicker(item.ticker)
    setSearchInput('')
    setIsDropdownOpen(false)
    setSelectedIdx(-1)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const results = searchResults.data?.data?.results || []
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIsDropdownOpen(true)
      setSelectedIdx((prev) => (prev < results.length - 1 ? prev + 1 : prev))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx((prev) => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectedIdx >= 0 && results[selectedIdx]) {
        handleSelectCompany(results[selectedIdx])
      } else if (searchInput.trim()) {
        setTicker(searchInput.trim().toUpperCase())
        setSearchInput('')
        setIsDropdownOpen(false)
      }
    } else if (e.key === 'Escape') {
      setIsDropdownOpen(false)
    }
  }

  const isLocal = dataMode === 'local'
  const isLive = dataMode === 'live' && (status === 'LIVE' || status === 'VALID')
  const isRateLimited = status === 'RATE_LIMITED'

  const resultsList = searchResults.data?.data?.results || []

  return (
    <div className={`app-shell ${isCopilotOpen ? 'copilot-open' : ''}`}>
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
        <button className="copilot-entry" type="button" onClick={() => setIsCopilotOpen(true)}>
          <span className="copilot-spark">✦</span>
          <span>
            AI COPILOT
          </span>
          <b>›</b>
        </button>
      </aside>

      <main>
        <header className="topbar">
          {/* GLOBAL DATA MODE SWITCH */}
          <div className="data-mode-control" role="group" aria-label="Global Data Source Mode">
            <span className="data-mode-label">DATA SOURCE:</span>
            <div className="mode-toggle-group">
              <button
                type="button"
                className={`mode-btn ${dataMode === 'live' ? 'active live' : ''}`}
                onClick={() => setDataMode('live')}
                title="Fetch live market data from configured external provider"
              >
                <span className="mode-icon">⚡</span>
                <span className="mode-text">LIVE API</span>
              </button>
              <button
                type="button"
                className={`mode-btn ${dataMode === 'local' ? 'active local' : ''}`}
                onClick={() => setDataMode('local')}
                title="Use local verified dataset containing 389 stocks"
              >
                <span className="mode-icon">🏛</span>
                <span className="mode-text">400+ STOCKS</span>
                <span className="badge-count">389</span>
              </button>
            </div>
          </div>

          {/* GLOBAL DEBOUNCED SEARCH BAR */}
          <div className="search-wrapper" ref={searchRef}>
            <div className="search-input-box">
              <span className="search-icon" aria-hidden="true">⌕</span>
              <input
                type="text"
                placeholder={isLocal ? "Search 389 stocks (e.g. Reliance, TCS, Apple, NVDA)..." : "Search ticker (e.g. AAPL, MSFT, TSLA)..."}
                aria-label="Global search companies"
                value={searchInput}
                onChange={(e) => {
                  setSearchInput(e.target.value)
                  setIsDropdownOpen(true)
                  setSelectedIdx(-1)
                }}
                onFocus={() => {
                  if (searchInput.trim().length >= 1) setIsDropdownOpen(true)
                }}
                onKeyDown={handleKeyDown}
              />
              {searchInput && (
                <button
                  type="button"
                  className="clear-search-btn"
                  onClick={() => {
                    setSearchInput('')
                    setIsDropdownOpen(false)
                  }}
                  aria-label="Clear search"
                >
                  ✕
                </button>
              )}
            </div>

            {/* SEARCH SUGGESTIONS DROPDOWN */}
            {isDropdownOpen && debouncedSearch.length >= 1 && (
              <div className="search-dropdown-menu">
                {searchResults.isLoading ? (
                  <div className="dropdown-loading">
                    <span className="spinner" />
                    <span>Searching {isLocal ? '389 local stocks' : 'market universe'}…</span>
                  </div>
                ) : resultsList.length > 0 ? (
                  <ul className="dropdown-results-list" role="listbox">
                    {resultsList.map((item, idx) => (
                      <li
                        key={item.ticker}
                        className={`dropdown-item ${idx === selectedIdx ? 'highlighted' : ''}`}
                        role="option"
                        aria-selected={idx === selectedIdx}
                        onClick={() => handleSelectCompany(item)}
                        onMouseEnter={() => setSelectedIdx(idx)}
                      >
                        <div className="item-main">
                          <div className="item-title-row">
                            <strong className="item-ticker">{item.ticker}</strong>
                            <span className="item-country-badge">
                              {item.country === 'India' ? '🇮🇳 India · NSE' : '🇺🇸 USA · NASDAQ'}
                            </span>
                            <span className="item-sector">{item.sector}</span>
                          </div>
                          <span className="item-name">{item.company_name}</span>
                        </div>
                        {item.current_price !== undefined && (
                          <div className="item-price">
                            <strong>{money(item.current_price, true, item.currency)}</strong>
                            {item.market_cap && <small>{money(item.market_cap, false, item.currency)}</small>}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : searchResults.isError ? (
                  <div className="dropdown-empty error">Search unavailable. Please try again.</div>
                ) : (
                  <div className="dropdown-empty">
                    <span>No matching company found in {isLocal ? '389-stock local database' : 'live provider'}.</span>
                    <small>Press Enter to query raw ticker &quot;{debouncedSearch.toUpperCase()}&quot;</small>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* TOP RIGHT STATUS & CONTEXT */}
          <div className="top-status">
            <div className="active-ticker-pill">
              <span className="active-dot" />
              <span className="active-ticker-name">{ticker}</span>
              {companyData?.currency && <span className="active-curr">({companyData.currency})</span>}
            </div>

            {/* THEME SELECTOR DROPDOWN */}
            <div className="theme-selector-container" ref={themeRef}>
              <button
                type="button"
                className="theme-toggle-btn"
                onClick={() => setIsThemeOpen((prev) => !prev)}
                aria-label="Select Color Theme"
                title="Change UI Theme (Purple / White / Dark / Amber)"
              >
                <span className="theme-btn-dot">
                  {theme === 'purple' ? '🟣' : theme === 'white' ? '☀' : theme === 'dark' ? '⚫' : '🟡'}
                </span>
                <span className="theme-btn-label">
                  {theme === 'purple' ? 'Purple' : theme === 'white' ? 'White' : theme === 'dark' ? 'Dark' : 'Amber'}
                </span>
                <span className="theme-btn-arrow">▾</span>
              </button>

              {isThemeOpen && (
                <div className="theme-dropdown-menu" role="menu">
                  <div
                    className={`theme-menu-item ${theme === 'purple' ? 'selected' : ''}`}
                    role="menuitem"
                    onClick={() => {
                      setTheme('purple')
                      setIsThemeOpen(false)
                    }}
                  >
                    <span className="theme-item-icon">🟣</span>
                    <div className="theme-item-text">
                      <strong>Purple (Default)</strong>
                      <small>Signature Institutional</small>
                    </div>
                    {theme === 'purple' && <span className="theme-check">✓</span>}
                  </div>

                  <div
                    className={`theme-menu-item ${theme === 'white' ? 'selected' : ''}`}
                    role="menuitem"
                    onClick={() => {
                      setTheme('white')
                      setIsThemeOpen(false)
                    }}
                  >
                    <span className="theme-item-icon">☀</span>
                    <div className="theme-item-text">
                      <strong>White Mode</strong>
                      <small>Light IB / Bloomberg</small>
                    </div>
                    {theme === 'white' && <span className="theme-check">✓</span>}
                  </div>

                  <div
                    className={`theme-menu-item ${theme === 'dark' ? 'selected' : ''}`}
                    role="menuitem"
                    onClick={() => {
                      setTheme('dark')
                      setIsThemeOpen(false)
                    }}
                  >
                    <span className="theme-item-icon">⚫</span>
                    <div className="theme-item-text">
                      <strong>Dark Mode</strong>
                      <small>Neutral Charcoal / Slate</small>
                    </div>
                    {theme === 'dark' && <span className="theme-check">✓</span>}
                  </div>

                  <div
                    className={`theme-menu-item ${theme === 'amber' ? 'selected' : ''}`}
                    role="menuitem"
                    onClick={() => {
                      setTheme('amber')
                      setIsThemeOpen(false)
                    }}
                  >
                    <span className="theme-item-icon">🟡</span>
                    <div className="theme-item-text">
                      <strong>Amber Dark</strong>
                      <small>Gold Financial Terminal</small>
                    </div>
                    {theme === 'amber' && <span className="theme-check">✓</span>}
                  </div>
                </div>
              )}
            </div>

            <StatusBadge status={isLocal ? 'LOCAL' : status} />
            <span className="status-dot">
              {isLocal
                ? 'Local Store (389 Stocks)'
                : isLive
                ? 'Alpha Vantage (Live)'
                : isRateLimited
                ? 'Circuit Breaker Active'
                : 'Alpha Vantage Unavailable'}
            </span>
            <button aria-label="Help" className="top-icon">?</button>
            <button aria-label="Notifications" className="top-icon">◦</button>
            <button aria-label="Settings" className="avatar">VE</button>
          </div>
        </header>

        {/* DATA PROVENANCE BANNER */}
        <div className={isLocal ? 'demo-banner local-banner' : isLive ? 'demo-banner live-banner' : isRateLimited ? 'demo-banner rate-limited-banner' : 'demo-banner'}>
          <span className="status-light" />
          <strong>
            {isLocal ? 'LOCAL DATASET (389 STOCKS)' : isLive ? 'LIVE DATA' : isRateLimited ? 'RATE LIMITED (CIRCUIT BREAKER ACTIVE)' : 'DEMONSTRATION DATA'}
          </strong>
          <span>
            {isLocal
              ? 'Institutional SQLite Repository · 389 Ingested Equities · 97k+ Price Records · Zero External Latency'
              : isLive
              ? `Source: ${provenance.source_name || 'Alpha Vantage'}${provenance.retrieved_at ? ` · Updated: ${provenance.retrieved_at}` : ''}`
              : isRateLimited
              ? 'Alpha Vantage rate limit reached. Circuit breaker active; local preset or cached fallback in use.'
              : 'Alpha Vantage unavailable. Outputs generated from validated local financial engines.'}
          </span>
          <a href="/audit">Review provenance →</a>
        </div>

        <div className="workspace">{children}</div>
      </main>

      <CopilotPanel
        ticker={ticker}
        mode={dataMode}
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        pageContext={pathname.replace('/', '') || 'dashboard'}
      />
    </div>
  )
}

