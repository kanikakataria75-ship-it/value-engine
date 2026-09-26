import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { money } from '../lib/format'
import { usePrefs } from '../lib/prefs'
import { useMeta, useSearch } from '../lib/queries'
import { readStorage, useDebounced } from '../lib/utils'
import { IconArrowRight, IconGlobe, IconMoon, IconPlay, IconSearch, IconSpark, IconSun, NavIcons } from './icons'

export const COMPANY_PAGES = [
  { path: '', label: 'Overview', icon: NavIcons.overview, blurb: 'Verdict, valuation horizon, health' },
  { path: 'valuation', label: 'Valuation', icon: NavIcons.valuation, blurb: 'DCF or excess-return model' },
  { path: 'expectations', label: 'Expectations Lab', icon: NavIcons.expectations, blurb: 'What the price implies' },
  { path: 'comps', label: 'Comparables', icon: NavIcons.comps, blurb: 'Peer multiples' },
  { path: 'mna', label: 'M&A Deal Room', icon: NavIcons.mna, blurb: 'Accretion / dilution' },
  { path: 'lbo', label: 'LBO', icon: NavIcons.lbo, blurb: 'Sponsor returns' },
  { path: 'risk', label: 'Risk Lab', icon: NavIcons.risk, blurb: 'Distributions, tails, regimes' },
  { path: 'data', label: 'Data & Provenance', icon: NavIcons.data, blurb: 'Fundamentals and quality' },
  { path: 'report', label: 'Report', icon: NavIcons.report, blurb: 'IC memo and Excel model' },
] as const

export function recentTickers(): string[] {
  return readStorage<string[]>('ve.recent', [])
}

export function CommandPalette({ open, onOpenChange, ticker, onAskCopilot, onReplayIntro }: {
  open: boolean; onOpenChange: (open: boolean) => void; ticker: string | null
  onAskCopilot: () => void; onReplayIntro: () => void
}) {
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query, 150)
  const search = useSearch(debounced)
  const navigate = useNavigate()
  const { theme, setTheme, mode, setMode } = usePrefs()
  const results = search.data?.data?.results ?? []
  const count = useMeta().data?.data?.company_count
  const recents = recentTickers()
  // Filtering is done by the API, so cmdk never re-selects on its own: keep the first row highlighted
  // whenever the rows change, so Enter always opens the top match.
  const [selected, setSelected] = useState('')
  const first = results.length ? `company-${results[0].ticker}`
    : !query && recents.length ? `recent-${recents[0]}`
      : !query && ticker ? 'page-' : 'nav-home'

  useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  useEffect(() => {
    setSelected(first)
  }, [first, open])

  const go = (path: string) => {
    onOpenChange(false)
    navigate(path)
  }

  return (
    <Command.Dialog open={open} onOpenChange={onOpenChange} label="Command menu" className="cmdk" overlayClassName="cmdk-overlay"
                    shouldFilter={false} value={selected} onValueChange={setSelected}>
      <div className="cmdk-input-wrap">
        <IconSearch size={18} />
        <Command.Input value={query} onValueChange={setQuery} placeholder={`Search ${count ? `${count} ` : ""}companies, jump to a page, or run a command…`} />
        <kbd>esc</kbd>
      </div>
      <Command.List className="cmdk-list">
        <Command.Empty className="cmdk-empty">No matches. Try a ticker like AAPL or a name like Reliance.</Command.Empty>
        {results.length > 0 && (
          <Command.Group heading="Companies">
            {results.map((r) => (
              <Command.Item key={r.ticker} value={`company-${r.ticker}`} onSelect={() => go(`/c/${r.ticker}`)} className="cmdk-item">
                <span className="cmdk-mono">{r.ticker.replace('.NSE', '').slice(0, 2)}</span>
                <span className="cmdk-main"><b>{r.company_name}</b><small>{r.ticker} · {r.exchange} · {r.sector}</small></span>
                <span className="cmdk-meta num">{money(r.current_price, r.currency, { precise: true })}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {!query && recents.length > 0 && (
          <Command.Group heading="Recent">
            {recents.slice(0, 5).map((t) => (
              <Command.Item key={t} value={`recent-${t}`} onSelect={() => go(`/c/${t}`)} className="cmdk-item">
                <span className="cmdk-mono">{t.replace('.NSE', '').slice(0, 2)}</span>
                <span className="cmdk-main"><b>{t}</b></span>
                <IconArrowRight size={14} />
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {ticker && !query && (
          <Command.Group heading={ticker}>
            {COMPANY_PAGES.map((page) => (
              <Command.Item key={page.path} value={`page-${page.path}`} onSelect={() => go(`/c/${ticker}${page.path ? `/${page.path}` : ''}`)} className="cmdk-item">
                <span className="cmdk-icon"><page.icon size={16} /></span>
                <span className="cmdk-main"><b>{page.label}</b><small>{page.blurb}</small></span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {!query && (
          <>
            <Command.Group heading="Navigate">
              <Command.Item value="nav-home" onSelect={() => go('/')} className="cmdk-item">
                <span className="cmdk-icon"><IconGlobe size={16} /></span><span className="cmdk-main"><b>The Observatory</b><small>Expectations galaxy</small></span>
              </Command.Item>
              <Command.Item value="nav-radar" onSelect={() => go('/radar')} className="cmdk-item">
                <span className="cmdk-icon"><NavIcons.expectations size={16} /></span><span className="cmdk-main"><b>Expectations Radar</b><small>All companies, ranked</small></span>
              </Command.Item>
              <Command.Item value="nav-method" onSelect={() => go('/methodology')} className="cmdk-item">
                <span className="cmdk-icon"><NavIcons.report size={16} /></span><span className="cmdk-main"><b>Methodology</b><small>How every number is made</small></span>
              </Command.Item>
            </Command.Group>
            <Command.Group heading="Actions">
              <Command.Item value="act-copilot" onSelect={() => { onOpenChange(false); onAskCopilot() }} className="cmdk-item">
                <span className="cmdk-icon"><IconSpark size={16} /></span><span className="cmdk-main"><b>Ask ValuAI</b></span>
              </Command.Item>
              <Command.Item value="act-theme" onSelect={() => { onOpenChange(false); setTheme(theme === 'observatory' ? 'paper' : 'observatory') }} className="cmdk-item">
                <span className="cmdk-icon">{theme === 'observatory' ? <IconSun size={16} /> : <IconMoon size={16} />}</span>
                <span className="cmdk-main"><b>Switch to {theme === 'observatory' ? 'Paper' : 'Observatory'} theme</b></span>
              </Command.Item>
              <Command.Item value="act-mode" onSelect={() => { onOpenChange(false); setMode(mode === 'local' ? 'live' : 'local') }} className="cmdk-item">
                <span className="cmdk-icon"><IconGlobe size={16} /></span>
                <span className="cmdk-main"><b>Use {mode === 'local' ? 'live provider data' : 'the local dataset'}</b><small>{mode === 'local' ? 'Alpha Vantage, falling back to local' : 'Offline, instant'}</small></span>
              </Command.Item>
              <Command.Item value="act-intro" onSelect={() => { onOpenChange(false); onReplayIntro() }} className="cmdk-item">
                <span className="cmdk-icon"><IconPlay size={16} /></span><span className="cmdk-main"><b>Replay the intro</b></span>
              </Command.Item>
            </Command.Group>
          </>
        )}
      </Command.List>
    </Command.Dialog>
  )
}
