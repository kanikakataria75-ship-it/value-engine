export type DataMode = 'local' | 'live'

export type Status = 'VALID' | 'REVIEW_REQUIRED' | 'INVALID' | 'UNAVAILABLE' | 'DEMO' | 'LIVE' | 'LOCAL' | 'CACHED' | 'RATE_LIMITED' | 'LOADING' | 'ERROR'

export interface Envelope<T = Record<string, unknown>> {
  status: Status
  data: T
  warnings: string[]
  errors: string[]
  provenance: Record<string, unknown>
}

export interface PricePoint {
  date: string
  open?: number
  high?: number
  low?: number
  close: number
  volume?: number
}

export interface Company {
  ticker: string
  company_name: string
  current_price: number
  market_cap: number
  revenue: number
  ebitda: number
  ebit: number
  net_income: number
  eps?: number
  operating_cash_flow: number
  capex: number
  d_and_a?: number
  total_debt: number
  cash_and_equivalents: number
  book_equity?: number
  total_assets?: number
  total_liabilities?: number
  shares_outstanding: number
  exchange: string
  sector: string
  industry?: string
  currency: string
  beta?: number
  period?: string
  retrieved_at?: string
  historical_prices?: PricePoint[]
  data_quality_issues?: { rule: string; severity: string; message: string; field?: string }[]
}

export interface SearchResult {
  ticker: string
  company_name: string
  exchange: string
  country: string
  sector: string
  industry?: string
  currency: string
  current_price?: number
  market_cap?: number
}

export interface Dcf {
  implied_share_price: number
  upside_downside_pct: number
  enterprise_value: number
  equity_value: number
  terminal_value: number
  pv_terminal_value: number
  pv_ufcf_sum: number
  net_debt: number
  wacc: number
  terminal_growth_rate: number
  roic?: number
  value_creation_spread?: number
  projections_df: Record<string, number>[]
}

export interface Mna {
  offer_price: number
  total_purchase_price: number
  cash_debt_portion: number
  stock_portion: number
  pre_tax_synergies: number
  revenue_synergy_profit: number
  after_tax_integration: number
  eps_change_pct: number
  post_deal_eps: number
  acquirer_standalone_eps: number
  break_even_pre_tax_synergy: number
  is_accretive: boolean
}

export interface Lbo {
  entry_ev: number
  total_debt_initial: number
  sponsor_initial_equity: number
  exit_ev: number
  exit_debt: number
  exit_equity: number
  irr: number
  moic: number
  attr_ebitda_growth: number
  attr_multiple_expansion: number
  attr_debt_paydown: number
  attr_cash_generation: number
  schedule_df: Record<string, number>[]
}

export interface CopilotResponse {
  answer: string
  provider: string
  model: string
  is_fallback?: boolean
  citations?: string[]
  context_used?: {
    ticker?: string
    page?: string
    data_mode?: string
  }
}
