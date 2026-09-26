import { Suspense, useEffect, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Navigate, NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api, scenarioBody } from '../lib/api'
import type { Baseline, Company } from '../lib/api-types'
import { fiscalLabel, money, pct, shortDate } from '../lib/format'
import { usePrefs } from '../lib/prefs'
import { useBaseline, useCompany } from '../lib/queries'
import { useScenario } from '../lib/scenario'
import type { Scenario } from '../lib/api'
import { decodeScenario, encodeScenario, readStorage, writeStorage } from '../lib/utils'
import { COMPANY_PAGES } from './CommandPalette'
import { IconDownload, IconLink, IconReset, IconSpark } from './icons'
import type { ShellContext } from './Shell'
import { useToast } from './Toast'
import { Button, Empty, Orbit, StatusPill } from './ui'

export interface CompanyContext extends ShellContext {
  ticker: string
  company: Company
  baseline: Baseline | undefined
}

export const useCompanyContext = () => useOutletContext<CompanyContext>()

function dayChange(company: Company): number | null {
  const prices = company.historical_prices
  if (prices.length < 2) return null
  return prices[prices.length - 1].close / prices[prices.length - 2].close - 1
}

export function exchangeLabel(company: Company): string {
  if (company.country === 'India') return 'NSE · India'
  const code = (company.exchange ?? '').toUpperCase()
  const venue = ['NYQ', 'NYSE'].includes(code) ? 'NYSE' : ['NMS', 'NGS', 'NCM', 'NGM', 'NASDAQ', 'NASDAQGS'].includes(code) ? 'NASDAQ' : code || 'US'
  return `${venue} · United States`
}

const LEGAL = new Set(['inc', 'inc.', 'ltd', 'ltd.', 'limited', 'corporation', 'corp', 'corp.', 'co', 'co.', 'company', 'plc', 'the', '&', 'and', 'holdings', 'group'])

/** Up to two initials from the company name, skipping legal suffixes ("HDFC Bank Limited" -> "HB"). */
export function monogram(name: string): string {
  const words = name.replace(/[^A-Za-z0-9&.\s-]/g, ' ').split(/[\s-]+/).filter((w) => w && !LEGAL.has(w.toLowerCase()))
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join('') || name.slice(0, 1).toUpperCase()
}

function yearRange(company: Company): [number, number] | null {
  const closes = company.historical_prices.slice(-252).map((p) => p.close)
  return closes.length ? [Math.min(...closes), Math.max(...closes)] : null
}

export function CompanyLayout() {
  const { ticker: raw = '' } = useParams()
  const ticker = raw.toUpperCase()
  const shell = useOutletContext<ShellContext>()
  const location = useLocation()
  const company = useCompany(ticker)
  const baseline = useBaseline(ticker)
  const scenario = useScenario(ticker)
  const { mode } = usePrefs()
  const toast = useToast()
  const navigate = useNavigate()

  // A shared link carries the sender's scenario in ?s=; adopt it once, then tidy the address bar.
  useEffect(() => {
    const token = new URLSearchParams(location.search).get('s')
    if (!token) return
    const shared = decodeScenario(token)
    if (shared) {
      scenario.load(shared as Scenario)
      toast(Object.keys(shared).length ? 'Opened the shared scenario' : 'The shared link uses the company baseline')
    } else {
      toast('That link carries an unreadable scenario', 'bad')
    }
    navigate(location.pathname, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search])

  useEffect(() => {
    if (!company.data?.data) return
    const recent = readStorage<string[]>('ve.recent', []).filter((t) => t !== ticker)
    writeStorage('ve.recent', [ticker, ...recent].slice(0, 8))
    document.title = `${company.data.data.company_name} · ValuEngine`
    return () => { document.title = 'ValuEngine' }
  }, [company.data, ticker])

  const c = company.data?.data
  const range = useMemo(() => (c ? yearRange(c) : null), [c])
  if (raw !== ticker) return <Navigate to={location.pathname.replace(raw, ticker)} replace />

  if (company.isLoading) return <div className="page-center"><Orbit label={`Loading ${ticker}`} /></div>
  if (!c) {
    return (
      <div className="page-center">
        <Empty title={`${ticker} is not in the dataset`} message={company.data?.errors?.[0] ?? 'Try searching for another company.'} />
      </div>
    )
  }

  const change = dayChange(c)
  const bank = c.balance_sheet_financial
  const page = location.pathname.split('/')[3] ?? ''
  const prov = c.provenance

  const exportModel = async () => {
    toast('Building your Excel model…')
    const result = await api.excel(scenarioBody(ticker, mode, scenario.scenario))
    if ('error' in result) {
      toast(result.error, 'bad')
      return
    }
    const url = URL.createObjectURL(result.blob)
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 2000)
    toast(`Downloaded ${result.filename}`)
  }

  const share = async () => {
    const url = new URL(window.location.href)
    url.search = ''
    const custom = Object.keys(scenario.scenario).length > 0
    if (custom) url.searchParams.set('s', encodeScenario(scenario.scenario))
    try {
      await navigator.clipboard.writeText(url.toString())
      toast(custom ? 'Link copied, with your scenario' : 'Link copied')
    } catch {
      toast('Could not copy the link', 'bad')
    }
  }

  return (
    <div className="company">
      <header className="masthead reveal">
        <div className="masthead-id">
          <div className="monogram" aria-hidden="true">
            <span>{monogram(c.company_name)}</span>
          </div>
          <div>
            <div className="eyebrow muted">{exchangeLabel(c)} · {c.sector}</div>
            <h1 className="display masthead-name">{c.company_name}</h1>
            <div className="masthead-meta">
              <span className="pill pill-gold mono">{ticker}</span>
              <span className="muted">{c.industry}</span>
              <StatusPill status={company.data?.status} label={`${prov.source_type === 'LOCAL' ? 'Local' : prov.source_type} · ${prov.origin ?? prov.source_name ?? ''}`} />
              <span className="muted mono">{fiscalLabel(c.period)} · retrieved {shortDate(c.retrieved_at)}</span>
            </div>
          </div>
        </div>
        <div className="masthead-quote">
          <div className="quote-price num">{money(c.current_price, c.currency, { precise: true })}</div>
          <div className={`quote-change num ${change === null ? '' : change >= 0 ? 'pos' : 'neg'}`}>
            {change === null ? '—' : `${change >= 0 ? '▲' : '▼'} ${pct(Math.abs(change), 2)}`} <span className="muted">last session</span>
          </div>
          {range && (
            <div className="range52" title="52-week closing range">
              <span className="num">{money(range[0], c.currency)}</span>
              <div className="range52-track">
                <i style={{ left: `${((c.current_price ?? range[0]) - range[0]) / Math.max(1e-9, range[1] - range[0]) * 100}%` }} />
              </div>
              <span className="num">{money(range[1], c.currency)}</span>
            </div>
          )}
          <div className="quote-cap muted">Market cap <b className="num">{money(c.market_cap, c.currency)}</b></div>
        </div>
      </header>

      <div className="company-toolbar reveal">
        <div className={`scenario-chip ${scenario.modified ? 'on' : ''}`}>
          <i />
          {scenario.modified ? 'Custom scenario' : 'Company baseline'}
          {scenario.modified && (
            <button type="button" onClick={() => { scenario.reset(); toast('Scenario reset to the company baseline') }} title="Reset all assumptions">
              <IconReset size={13} /> Reset
            </button>
          )}
        </div>
        <div className="company-actions">
          <Button icon={<IconSpark size={15} />} onClick={shell.openCopilot}>Ask ValuAI</Button>
          <Button icon={<IconDownload size={15} />} onClick={exportModel}>Excel model</Button>
          <Button icon={<IconLink size={15} />} onClick={share}>Share</Button>
        </div>
      </div>

      <div className="company-body">
        <nav className="rail" aria-label={`${ticker} workspace`}>
          {COMPANY_PAGES.map((item) => {
            const disabled = bank && item.path === 'lbo'
            const to = `/c/${ticker}${item.path ? `/${item.path}` : ''}`
            return disabled ? (
              <span key={item.path} className="rail-link disabled" title="LBOs are not modelled for banks and insurers">
                <item.icon size={17} /><span>{item.label}</span>
              </span>
            ) : (
              <NavLink key={item.path} to={to} end={!item.path} className={({ isActive }) => `rail-link ${isActive ? 'on' : ''}`}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="rail-active" className="rail-active" transition={{ type: 'spring', stiffness: 420, damping: 36 }} />}
                    <item.icon size={17} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            )
          })}
          <div className="rail-foot">
            <span className="eyebrow muted">Shortcuts</span>
            <span className="muted"><kbd>⌘K</kbd> search · <kbd>⌘.</kbd> ValuAI</span>
          </div>
        </nav>
        <section className="company-content">
          <AnimatePresence mode="wait">
            <motion.div key={page} initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}>
              <Suspense fallback={<div className="page-center"><Orbit label="Opening" /></div>}>
                <Outlet context={{ ...shell, ticker, company: c, baseline: baseline.data?.data ?? undefined } satisfies CompanyContext} />
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </section>
      </div>
    </div>
  )
}
