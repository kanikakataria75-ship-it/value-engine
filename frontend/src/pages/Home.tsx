import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { Scatter } from '../components/charts'
import { IconArrowRight, IconArrowUpRight, IconSearch } from '../components/icons'
import { AnimatedNumber, Orbit, Segmented } from '../components/ui'
import type { RadarRow } from '../lib/api-types'
import { compact, money, pct, points, shortDate } from '../lib/format'
import { usePrefs } from '../lib/prefs'
import { useMeta, useSearch, useUniverse } from '../lib/queries'
import { cn, useDebounced, webglAvailable } from '../lib/utils'
import type { GalaxyFilter } from '../three/Galaxy'

const Galaxy = lazy(() => import('../three/Galaxy'))

const EXAMPLES = ['Reliance Industries', 'NVIDIA', 'HDFC Bank', 'Walmart', 'Infosys', 'JPMorgan', 'Titan', 'Microsoft']

function HeroSearch() {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const [example, setExample] = useState(0)
  const debounced = useDebounced(query, 140)
  const search = useSearch(debounced)
  const navigate = useNavigate()
  const results = debounced ? search.data?.data?.results?.slice(0, 6) ?? [] : []

  useEffect(() => {
    const id = window.setInterval(() => setExample((i) => (i + 1) % EXAMPLES.length), 2600)
    return () => window.clearInterval(id)
  }, [])

  return (
    <div className={cn('hero-search', focused && 'focused')}>
      <IconSearch size={18} />
      <input value={query} onChange={(e) => setQuery(e.target.value)} onFocus={() => setFocused(true)}
             onBlur={() => window.setTimeout(() => setFocused(false), 150)}
             onKeyDown={(e) => { if (e.key === 'Enter' && results[0]) navigate(`/c/${results[0].ticker}`) }}
             aria-label="Search companies" />
      {!query && (
        <span className="hero-search-placeholder">
          Search a company — try{' '}
          <AnimatePresence mode="wait">
            <motion.em key={example} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35 }}>
              {EXAMPLES[example]}
            </motion.em>
          </AnimatePresence>
        </span>
      )}
      <kbd>↵</kbd>
      {focused && results.length > 0 && (
        <div className="hero-results">
          {results.map((r) => (
            <button key={r.ticker} type="button" onMouseDown={() => navigate(`/c/${r.ticker}`)}>
              <span className="mono">{r.ticker}</span>
              <span>{r.company_name}</span>
              <span className="num muted">{money(r.current_price, r.currency, { precise: true })}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function GapBars({ row }: { row: RadarRow }) {
  if (row.model === 'excess_return') {
    const max = Math.max(row.implied_roe ?? 0, row.current_roe ?? 0, 0.01)
    return (
      <div className="gapbars">
        <div><span>ROE priced in</span><i className="gold" style={{ width: `${(Math.max(0, row.implied_roe ?? 0) / max) * 100}%` }} /><b className="num">{pct(row.implied_roe)}</b></div>
        <div><span>Current ROE</span><i className="ivory" style={{ width: `${(Math.max(0, row.current_roe ?? 0) / max) * 100}%` }} /><b className="num">{pct(row.current_roe)}</b></div>
      </div>
    )
  }
  const values = [row.implied_growth ?? 0, row.historical_cagr ?? 0]
  const max = Math.max(...values.map(Math.abs), 0.01)
  return (
    <div className="gapbars">
      <div><span>Priced in</span><i className="gold" style={{ width: `${(Math.abs(values[0]) / max) * 100}%` }} /><b className="num">{pct(row.implied_growth)}</b></div>
      <div><span>History</span><i className={values[1] < 0 ? 'ember' : 'ivory'} style={{ width: `${(Math.abs(values[1]) / max) * 100}%` }} /><b className="num">{pct(row.historical_cagr)}</b></div>
    </div>
  )
}

function Legend() {
  return (
    <div className="legend">
      <div className="eyebrow muted">Reading the galaxy</div>
      <div className="legend-scale">
        <span>Priced for slowdown</span>
        <i />
        <span>Priced for acceleration</span>
      </div>
      <ul>
        <li><b>Height</b> above the disc = growth the price assumes beyond the last three years' record.</li>
        <li><b>Arms</b> are sectors; the largest companies sit nearest the core.</li>
        <li><b>Violet</b> stars are priced beyond the model's range.</li>
      </ul>
    </div>
  )
}

export function Home() {
  const universe = useUniverse()
  const meta = useMeta().data?.data
  const { reducedMotion } = usePrefs()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<GalaxyFilter>({ country: 'all', sector: null })
  const [selected, setSelected] = useState<RadarRow | null>(null)
  const webgl = useMemo(webglAvailable, [])
  const data = universe.data?.data
  const rows = useMemo(() => data?.rows ?? [], [data])
  const sectors = useMemo(() => {
    const counts = new Map<string, number>()
    rows.forEach((r) => counts.set(r.sector ?? 'Unclassified', (counts.get(r.sector ?? 'Unclassified') ?? 0) + 1))
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [rows])
  const usdinr = meta?.fx.find((f) => f.pair === 'USDINR')

  return (
    <div className="home">
      <section className={cn('hero', selected && 'has-focus')}>
        <div className="hero-canvas">
          {webgl ? (
            <Suspense fallback={<div className="galaxy-fallback" />}>
              {rows.length > 0 && (
                <Galaxy rows={rows} filter={filter} selected={selected?.ticker ?? null} reducedMotion={reducedMotion}
                        onSelect={setSelected} onOpen={(row) => navigate(`/c/${row.ticker}/expectations`)} />
              )}
            </Suspense>
          ) : (
            <div className="galaxy-flat">
              <Scatter height={520} diagonal xLabel="Historical growth" yLabel="Growth priced in" format={(v) => pct(v, 0)}
                       points={rows.filter((r) => r.implied_growth != null && r.historical_cagr != null)
                         .map((r) => ({ x: r.historical_cagr!, y: r.implied_growth!, id: r.ticker, label: r.company_name ?? r.ticker, tone: (r.expectations_gap ?? 0) > 0 ? 'gold' : 'aurora' }))}
                       onPick={(p) => navigate(`/c/${p.id}`)} />
            </div>
          )}
          {universe.isLoading && <div className="hero-loading"><Orbit label="Charting the universe" /></div>}
        </div>

        <div className="hero-copy">
          <div className="eyebrow reveal">The market observatory</div>
          <h1 className="display hero-title reveal" style={{ animationDelay: '80ms' }}>
            What is the market <em>pricing&nbsp;in</em>?
          </h1>
          <p className="hero-lede reveal" style={{ animationDelay: '160ms' }}>
            {meta?.company_count ?? 'Hundreds of'} companies across the US and India. For each one, ValuEngine runs the cash-flow
            model in reverse to find the growth hidden inside today's share price, and measures it against what the business has actually delivered.
          </p>
          <div className="reveal" style={{ animationDelay: '240ms' }}><HeroSearch /></div>
          <div className="hero-hints reveal" style={{ animationDelay: '320ms' }}>
            <span><i className="mouse" /> drag to orbit</span><span><kbd>Ctrl</kbd> + scroll to zoom</span><span>click a star to focus</span>
          </div>
        </div>

        <aside className="hero-hud reveal" style={{ animationDelay: '380ms' }}>
          <Legend />
          <div className="hud-block">
            <Segmented id="country" size="sm" value={filter.country}
                       onChange={(country) => setFilter((f) => ({ ...f, country }))}
                       options={[{ value: 'all', label: 'All' }, { value: 'United States', label: 'US' }, { value: 'India', label: 'India' }]} />
            <div className="sector-chips">
              {sectors.map(([name, count]) => (
                <button key={name} type="button" className={cn('chip', filter.sector === name && 'on')}
                        onClick={() => setFilter((f) => ({ ...f, sector: f.sector === name ? null : name }))}>
                  {name}<span>{count}</span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <AnimatePresence>
          {selected && (
            <motion.div className="focus-card" initial={{ opacity: 0, y: 20, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10 }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}>
              <div className="eyebrow">{selected.sector} · {selected.country}</div>
              <h3 className="display">{selected.company_name}</h3>
              <div className="focus-price num">{money(selected.price, selected.currency, { precise: true })}</div>
              <GapBars row={selected} />
              <p className="muted">
                {selected.status === 'NOT_REACHABLE' ? 'The price implies more growth than the model can represent at today\'s margin.'
                  : selected.model === 'excess_return' ? `Priced for a sustainable ROE of ${pct(selected.implied_roe)}.`
                    : `Gap to history ${points(selected.expectations_gap)} · implied return ${pct(selected.implied_return)} a year.`}
              </p>
              <div className="focus-actions">
                <Link className="btn btn-primary" to={`/c/${selected.ticker}/expectations`}>Open the Expectations Lab <IconArrowRight size={15} /></Link>
                <Link className="btn btn-ghost" to={`/c/${selected.ticker}`}>Overview</Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="hero-stats">
          <div><b className="num"><AnimatedNumber value={meta?.company_count} format={(v) => Math.round(v).toString()} /></b><span>companies</span></div>
          <div><b className="num"><AnimatedNumber value={meta?.price_rows} format={(v) => compact(v, 0)} /></b><span>daily prices</span></div>
          <div><b className="num"><AnimatedNumber value={meta?.history_companies} format={(v) => Math.round(v).toString()} /></b><span>4-year histories</span></div>
          <div><b className="num">{usdinr ? `₹${usdinr.rate.toFixed(2)}` : '—'}</b><span>USD/INR · {shortDate(usdinr?.date)}</span></div>
          <div><b className="num">{shortDate(meta?.price_end)}</b><span>prices through</span></div>
        </div>
      </section>

      {data && (
        <section className="home-section">
          <div className="section-head">
            <div>
              <div className="eyebrow">Across the universe</div>
              <h2 className="display">The widest gaps between <em>price</em> and <em>history</em></h2>
            </div>
            <Link to="/radar" className="btn btn-ghost">Open the full radar <IconArrowUpRight size={15} /></Link>
          </div>
          <div className="extremes">
            {[['Priced for acceleration', data.summary.most_optimistic, 'gold'], ['Priced for slowdown', data.summary.most_pessimistic, 'aurora']].map(([title, list, tone]) => (
              <div key={title as string} className="extreme-col">
                <h3 className={`extreme-title ${tone}`}>{title as string}</h3>
                {(list as RadarRow[]).slice(0, 6).map((row, i) => (
                  <Link key={row.ticker} to={`/c/${row.ticker}/expectations`} className="extreme-row" style={{ animationDelay: `${i * 60}ms` }}>
                    <span className="extreme-rank num">{String(i + 1).padStart(2, '0')}</span>
                    <span className="extreme-name"><b>{row.company_name}</b><small className="mono">{row.ticker}</small></span>
                    <GapBars row={row} />
                    <span className={`extreme-gap num ${tone}`}>{points(row.expectations_gap, 0)}</span>
                  </Link>
                ))}
              </div>
            ))}
          </div>
          <p className="section-note muted">
            Median growth priced in: <b className="num">{pct(data.summary.median_implied_growth)}</b> a year versus a median three-year record of{' '}
            <b className="num">{pct(data.summary.median_historical_cagr)}</b>, using each company's own baseline WACC. {data.summary.not_reachable} companies are priced beyond the model's growth range.
          </p>
        </section>
      )}

      <section className="home-section how">
        <div className="section-head">
          <div>
            <div className="eyebrow">How the engine reads a price</div>
            <h2 className="display">Three instruments, <em>one</em> honest answer</h2>
          </div>
        </div>
        <div className="how-grid">
          {[
            ['01', 'Reverse the DCF', 'Hold every assumption but one at the company baseline and solve for the growth, margin or return that reproduces today\'s price exactly.'],
            ['02', 'Weigh the odds', 'Draw thousands of futures from the company\'s own historical volatility and count how many are worth more than the market is paying.'],
            ['03', 'Ask why', 'ValuAI explains every number from the same engine outputs you see, grounded in your scenario, never in generic defaults.'],
          ].map(([n, title, body]) => (
            <div key={n} className="how-card">
              <span className="how-n num">{n}</span>
              <h3 className="display">{title}</h3>
              <p className="muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="footer">
        <div className="footer-brand display">ValuEngine</div>
        <div className="muted">Data: Yahoo Finance fundamentals and prices, stored locally · FX: Yahoo Finance · Not investment advice.</div>
        <div className="footer-links"><Link to="/methodology">Methodology</Link><Link to="/radar">Radar</Link></div>
      </footer>
    </div>
  )
}
