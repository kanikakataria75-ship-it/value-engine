import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { CompanyHeader, DataState, MetricCard, Panel, money, pct } from '../components/ui'
import type { Company, Mna, DataMode, SearchResult } from '../types/api'

export function getConsiderationValidation(cashPct: number, stockPct: number) {
  if (isNaN(cashPct) || isNaN(stockPct)) {
    return {
      sum: NaN,
      isValid: false,
      warning: 'Please enter valid numerical consideration percentages.',
    }
  }
  const sum = Math.round((cashPct + stockPct) * 10) / 10
  const isValid = Math.abs(sum - 100) < 0.05 && cashPct >= 0 && stockPct >= 0
  return {
    sum,
    isValid,
    warning: isValid ? null : `Cash + Stock consideration must equal 100%. Current total: ${sum}%`,
  }
}

export function MnaPage({ ticker, dataMode = 'local' }: { ticker: string; dataMode?: DataMode }) {
  const isIndia = ticker?.endsWith?.('.NSE') || ticker?.endsWith?.('.BSE')
  const defaultAcquirer = isIndia
    ? ticker === 'TCS.NSE'
      ? 'INFY.NSE'
      : 'TCS.NSE'
    : ticker === 'MSFT'
    ? 'AAPL'
    : 'MSFT'

  // Draft inputs for consideration (percentages 0-100)
  const [cashDraft, setCashDraft] = useState('50.0')
  const [stockDraft, setStockDraft] = useState('50.0')
  const [lastEditedConsideration, setLastEditedConsideration] = useState<'cash' | 'stock'>('cash')

  // Acquirer search & selection state
  const [acquirerDraft, setAcquirerDraft] = useState(defaultAcquirer)
  const [selectedAcquirer, setSelectedAcquirer] = useState(defaultAcquirer)
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const searchRef = useRef<HTMLDivElement>(null)

  // Other model parameters
  const [dealTerms, setDealTerms] = useState({
    offer_premium_pct: 0.25,
    debt_interest_rate: 0.08,
    revenue_synergies: 0,
    incremental_margin: 0.2,
    cost_synergies: 0,
    integration_costs: 0,
    tax_rate: 0.21,
  })

  // Synchronize when global context ticker changes
  useEffect(() => {
    setAcquirerDraft(defaultAcquirer)
    setSelectedAcquirer(defaultAcquirer)
    setCashDraft('50.0')
    setStockDraft('50.0')
    setLastEditedConsideration('cash')
  }, [ticker, defaultAcquirer])

  // Debounce search query 300ms for acquirer search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(acquirerDraft.trim())
    }, 300)
    return () => clearTimeout(timer)
  }, [acquirerDraft])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Autocomplete search query for Acquirer
  const searchResults = useQuery({
    queryKey: ['acquirer-search', debouncedSearch, dataMode],
    queryFn: () => api.searchCompanies(debouncedSearch, dataMode, 8),
    enabled: debouncedSearch.length >= 2,
    staleTime: 60000,
  })

  // Validation
  const cashNum = parseFloat(cashDraft)
  const stockNum = parseFloat(stockDraft)
  const validation = getConsiderationValidation(cashNum, stockNum)

  // Balance action
  const handleBalanceTo100 = () => {
    const cNum = isNaN(cashNum) ? 0 : cashNum
    const sNum = isNaN(stockNum) ? 0 : stockNum

    if (lastEditedConsideration === 'cash') {
      const clampedCash = Math.min(100, Math.max(0, cNum))
      const balancedStock = Math.round((100 - clampedCash) * 10) / 10
      setCashDraft(clampedCash.toFixed(1))
      setStockDraft(balancedStock.toFixed(1))
    } else {
      const clampedStock = Math.min(100, Math.max(0, sNum))
      const balancedCash = Math.round((100 - clampedStock) * 10) / 10
      setStockDraft(clampedStock.toFixed(1))
      setCashDraft(balancedCash.toFixed(1))
    }
  }

  // Handle company suggestion selection
  const handleSelectCompany = (item: SearchResult) => {
    setAcquirerDraft(item.ticker)
    setSelectedAcquirer(item.ticker)
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
      } else if (results.length > 0) {
        handleSelectCompany(results[0])
      } else if (acquirerDraft.trim().length >= 2) {
        setSelectedAcquirer(acquirerDraft.trim().toUpperCase())
        setAcquirerDraft(acquirerDraft.trim().toUpperCase())
        setIsDropdownOpen(false)
      }
    } else if (e.key === 'Escape') {
      setIsDropdownOpen(false)
    }
  }

  // Active query parameters (only updated when consideration is valid and acquirer is selected)
  const [calcInput, setCalcInput] = useState({
    target_ticker: ticker,
    acquirer_ticker: defaultAcquirer,
    offer_premium_pct: 0.25,
    pct_cash: 0.5,
    pct_stock: 0.5,
    debt_interest_rate: 0.08,
    revenue_synergies: 0,
    incremental_margin: 0.2,
    cost_synergies: 0,
    integration_costs: 0,
    tax_rate: 0.21,
  })

  useEffect(() => {
    if (validation.isValid && selectedAcquirer) {
      setCalcInput({
        target_ticker: ticker,
        acquirer_ticker: selectedAcquirer,
        offer_premium_pct: dealTerms.offer_premium_pct,
        pct_cash: cashNum / 100,
        pct_stock: stockNum / 100,
        debt_interest_rate: dealTerms.debt_interest_rate,
        revenue_synergies: dealTerms.revenue_synergies,
        incremental_margin: dealTerms.incremental_margin,
        cost_synergies: dealTerms.cost_synergies,
        integration_costs: dealTerms.integration_costs,
        tax_rate: dealTerms.tax_rate,
      })
    }
  }, [validation.isValid, cashNum, stockNum, selectedAcquirer, dealTerms, ticker])

  const targetComp = useQuery({
    queryKey: ['company', ticker, dataMode],
    queryFn: () => api.company(ticker, dataMode),
  })

  const q = useQuery({
    queryKey: ['mna', calcInput, dataMode],
    queryFn: () => api.mna(calcInput, dataMode),
  })

  const m = q.data?.data as Mna | undefined
  const c = targetComp.data?.data as Company | undefined
  const curr = c?.currency || (isIndia ? 'INR' : 'USD')

  const updateTerm = (key: keyof typeof dealTerms, value: string) => {
    const num = Number(value)
    if (!isNaN(num)) {
      setDealTerms((p) => ({ ...p, [key]: num }))
    }
  }

  const resultsList = searchResults.data?.data?.results || []

  return (
    <>
      <CompanyHeader company={c} modelStatus={q.data?.status || 'LOADING'} dataMode={dataMode} />

      <div className="page-title">
        <div>
          <p className="eyebrow">TRANSACTION INTELLIGENCE</p>
          <h1>
            M&A Deal Room: {ticker} + {selectedAcquirer}
          </h1>
        </div>
        <span className="model-note">
          Accretion/dilution, consideration financing, and synergy break-even calculated by the Python M&A engine.
        </span>
      </div>

      <div className="metrics-grid four">
        <MetricCard
          label="Offer Price / Share"
          value={money(m?.offer_price, true, curr)}
          detail={`${((dealTerms.offer_premium_pct || 0) * 100).toFixed(1)}% premium over market`}
        />
        <MetricCard
          label="Total Purchase Price"
          value={money(m?.total_purchase_price, false, curr)}
          detail="Implied transaction equity value"
        />
        <MetricCard
          label="Pro Forma EPS"
          value={money(m?.post_deal_eps, true, curr)}
          detail={`Standalone: ${money(m?.acquirer_standalone_eps, true, curr)}`}
        />
        <MetricCard
          label="Accretion / Dilution"
          value={m && typeof m.eps_change_pct === 'number' ? pct(m.eps_change_pct / 100) : 'UNAVAILABLE'}
          tone={m?.is_accretive ? 'positive' : 'negative'}
          detail={m?.is_accretive ? 'Accretive transaction' : 'Dilutive transaction'}
        />
      </div>

      <div className="workspace-grid">
        <Panel eyebrow="DEAL TERMS" title="Consideration & Synergies" className="assumptions">
          {/* ACQUIRER SEARCH WITH AUTOCOMPLETE */}
          <div className="input-row" style={{ alignItems: 'flex-start' }}>
            <span style={{ paddingTop: 6 }}>Acquirer Ticker</span>
            <div className="mna-acquirer-wrapper" ref={searchRef}>
              <div className="mna-acquirer-input-box">
                <input
                  type="text"
                  placeholder="Search acquirer ticker..."
                  aria-label="Acquirer ticker search"
                  value={acquirerDraft}
                  onChange={(e) => {
                    setAcquirerDraft(e.target.value)
                    setIsDropdownOpen(true)
                    setSelectedIdx(-1)
                  }}
                  onFocus={() => {
                    if (acquirerDraft.trim().length >= 2) setIsDropdownOpen(true)
                  }}
                  onKeyDown={handleKeyDown}
                />
                {acquirerDraft && (
                  <button
                    type="button"
                    className="mna-acquirer-clear"
                    onClick={() => {
                      setAcquirerDraft('')
                      setIsDropdownOpen(false)
                    }}
                    aria-label="Clear acquirer search"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* SEARCH SUGGESTIONS DROPDOWN */}
              {isDropdownOpen && debouncedSearch.length >= 2 && (
                <div className="mna-dropdown-menu">
                  {searchResults.isLoading ? (
                    <div className="dropdown-loading">
                      <span className="spinner" />
                      <span>Searching companies…</span>
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
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : searchResults.isError ? (
                    <div className="dropdown-empty error">Search unavailable.</div>
                  ) : (
                    <div className="dropdown-empty" style={{ padding: '12px 14px', fontSize: 11, color: '#94a3b8' }}>
                      <span>No matching company found.</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <Term
            label="Offer Premium"
            value={dealTerms.offer_premium_pct}
            update={(v) => updateTerm('offer_premium_pct', v)}
            suffix="%"
            scale={100}
          />

          {/* CASH CONSIDERATION */}
          <div className="input-row">
            <span>Cash Consideration</span>
            <div className="input-with-unit">
              <input
                type="number"
                step="0.5"
                min="0"
                max="100"
                value={cashDraft}
                onChange={(e) => {
                  setCashDraft(e.target.value)
                  setLastEditedConsideration('cash')
                }}
              />
              <b>%</b>
            </div>
          </div>

          {/* STOCK CONSIDERATION */}
          <div className="input-row">
            <span>Stock Consideration</span>
            <div className="input-with-unit">
              <input
                type="number"
                step="0.5"
                min="0"
                max="100"
                value={stockDraft}
                onChange={(e) => {
                  setStockDraft(e.target.value)
                  setLastEditedConsideration('stock')
                }}
              />
              <b>%</b>
            </div>
          </div>

          {/* INLINE WARNING & BALANCE ACTION */}
          {!validation.isValid && (
            <div className="consideration-warning-box">
              <div className="warning-text">
                <span className="warning-icon">⚠</span>
                <div>
                  <strong>Cash + Stock consideration must equal 100%.</strong>
                  <p>Current total: {isNaN(validation.sum) ? '—' : `${validation.sum}%`}</p>
                </div>
              </div>
              <button
                type="button"
                className="btn-balance"
                onClick={handleBalanceTo100}
                title={`Balance consideration to 100% by adjusting ${lastEditedConsideration === 'cash' ? 'Stock' : 'Cash'}`}
              >
                Balance to 100%
              </button>
            </div>
          )}

          <Term
            label="Revenue Synergies"
            value={dealTerms.revenue_synergies}
            update={(v) => updateTerm('revenue_synergies', v)}
            suffix={curr === 'INR' ? '₹' : '$'}
            scale={1}
          />
          <Term
            label="Cost Synergies"
            value={dealTerms.cost_synergies}
            update={(v) => updateTerm('cost_synergies', v)}
            suffix={curr === 'INR' ? '₹' : '$'}
            scale={1}
          />
          <Term
            label="Integration Costs"
            value={dealTerms.integration_costs}
            update={(v) => updateTerm('integration_costs', v)}
            suffix={curr === 'INR' ? '₹' : '$'}
            scale={1}
          />
        </Panel>

        <div className="stack">
          <DataState status={q.data?.status || (validation.isValid ? 'LOADING' : 'VALID')} errors={q.data?.errors} dataMode={dataMode}>
            <Panel
              eyebrow="OUTCOME"
              title={m?.is_accretive ? 'Accretive Transaction' : 'Dilutive Transaction'}
            >
              <div className="bridge">
                <Bridge label="Pre-Tax Synergies" value={m?.pre_tax_synergies} currency={curr} />
                <Bridge
                  label="After-Tax Integration"
                  value={m?.after_tax_integration === undefined ? undefined : -m.after_tax_integration}
                  currency={curr}
                />
                <Bridge label="EPS Change %" value={m?.eps_change_pct} percentage currency={curr} />
              </div>
            </Panel>

            <Panel eyebrow="BREAK-EVEN ANALYSIS" title="Required Synergy for Accretion">
              <div className="large-output">
                <strong>{money(m?.break_even_pre_tax_synergy, false, curr)}</strong>
                <span>pre-tax annual synergies required to avoid EPS dilution</span>
              </div>
            </Panel>
          </DataState>
        </div>
      </div>
    </>
  )
}

function Term({
  label,
  value,
  update,
  suffix,
  scale,
}: {
  label: string
  value: number
  update: (v: string) => void
  suffix: string
  scale: number
}) {
  return (
    <label className="input-row">
      <span>{label}</span>
      <div className="input-with-unit">
        <input
          type="number"
          step={scale === 100 ? 0.5 : 1000000}
          value={isNaN(value) ? '' : (value * scale).toFixed(scale === 100 ? 1 : 0)}
          onChange={(e) => update(String(Number(e.target.value) / scale))}
        />
        <b>{suffix}</b>
      </div>
    </label>
  )
}

function Bridge({
  label,
  value,
  percentage = false,
  currency = 'USD',
}: {
  label: string
  value?: number
  percentage?: boolean
  currency?: string
}) {
  const unavailable = value === undefined || value === null || !Number.isFinite(value)
  return (
    <div className="bridge-row">
      <span className="bridge-label">{label}</span>
      <div className="bridge-track">
        <i
          className={unavailable || (value || 0) >= 0 ? 'positive' : 'negative'}
          style={{
            width: `${unavailable ? 8 : Math.min(100, Math.max(8, (Math.abs(value || 0) / (percentage ? 10 : 1e9)) * 100))}%`,
          }}
        />
      </div>
      <strong className="bridge-val">
        {unavailable ? 'UNAVAILABLE' : percentage ? `${(value as number).toFixed(1)}%` : money(value, false, currency)}
      </strong>
    </div>
  )
}
