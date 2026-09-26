"""Response schemas: the typed API contract.

FastAPI validates every engine result against these models and the frontend's TypeScript types
are generated from the same models (scripts/generate_ts_types.py), so a renamed or missing field
fails the build instead of silently rendering "UNAVAILABLE" in the UI.
"""
from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
Num = float | None

Status = Literal[
    "VALID", "REVIEW_REQUIRED", "INVALID", "UNAVAILABLE", "LOCAL", "LIVE", "CACHED",
    "LOCAL_FALLBACK", "RATE_LIMITED", "ERROR",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Flag(Model):
    severity: Literal["INVALID", "REVIEW", "INFO"]
    module: str
    code: str
    message: str


class Provenance(Model):
    source_type: str | None = None
    source_name: str | None = None
    origin: str | None = None
    retrieved_at: str | None = None
    period_end: str | None = None
    period_type: str | None = None
    currency: str | None = None
    derived_fields: list[str] = Field(default_factory=list)
    repairs: list[str] = Field(default_factory=list)
    notice: str | None = None


class Envelope(Model, Generic[T]):
    status: Status
    data: T | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


# ----------------------------------------------------------------------------- meta / search
class FxInfo(Model):
    pair: str
    rate: float
    date: str
    source: str | None = None


class Meta(Model):
    company_count: int
    companies_by_currency: dict[str, int]
    price_rows: int
    price_start: str | None = None
    price_end: str | None = None
    history_rows: int
    history_companies: int
    retrieved_from: str | None = None
    retrieved_to: str | None = None
    fx: list[FxInfo]
    live_provider_configured: bool
    llm_providers: list[str]
    auth_required: bool
    version: str


class SearchResult(Model):
    ticker: str
    company_name: str
    exchange: str
    country: str
    sector: str
    industry: str
    currency: str
    current_price: Num = None
    market_cap: Num = None
    market_cap_usd: Num = None


class SearchData(Model):
    results: list[SearchResult]
    count: int


# ----------------------------------------------------------------------------- company
class PricePoint(Model):
    date: str
    open: Num = None
    high: Num = None
    low: Num = None
    close: float
    volume: Num = None


class QualityIssue(Model):
    severity: Literal["ERROR", "WARNING", "INFO"]
    rule: str
    field: str | None = None
    message: str


class QualitySummary(Model):
    fields_present: int
    fields_total: int
    completeness: float
    missing_fields: list[str]
    counts: dict[str, int]
    score: float
    status: str
    price_records: int


class Company(Model):
    ticker: str
    company_name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str
    country: str
    period: str | None = None
    retrieved_at: str | None = None
    current_price: Num = None
    market_cap: Num = None
    shares_outstanding: Num = None
    revenue: Num = None
    ebitda: Num = None
    ebit: Num = None
    net_income: Num = None
    eps: Num = None
    operating_cash_flow: Num = None
    capex: Num = None
    d_and_a: Num = None
    total_debt: Num = None
    cash_and_equivalents: Num = None
    book_equity: Num = None
    total_assets: Num = None
    total_liabilities: Num = None
    beta: Num = None
    balance_sheet_financial: bool
    historical_prices: list[PricePoint]
    provenance: Provenance
    quality: QualitySummary
    issues: list[QualityIssue]


class HistoryRow(Model):
    period_end: str
    revenue: Num = None
    ebitda: Num = None
    ebit: Num = None
    net_income: Num = None
    operating_cash_flow: Num = None
    capex: Num = None
    d_and_a: Num = None
    currency: str | None = None
    source: str | None = None


class GrowthPoint(Model):
    period_end: str
    growth: float


class MarginPoint(Model):
    period_end: str
    margin: float


class HistoryMetrics(Model):
    years: int
    periods: list[str] = Field(default_factory=list)
    revenue_cagr: Num = None
    growth_series: list[GrowthPoint] = Field(default_factory=list)
    margin_series: list[MarginPoint] = Field(default_factory=list)
    growth_volatility: Num = None
    margin_volatility: Num = None
    margin_average: Num = None
    capex_pct_average: Num = None
    da_pct_average: Num = None


class HistoryResult(Model):
    rows: list[HistoryRow]
    metrics: HistoryMetrics


# ----------------------------------------------------------------------------- baseline
class MarketParams(Model):
    currency: str
    country: str
    risk_free_rate: float
    equity_risk_premium: float
    credit_spread: float
    tax_rate: float
    terminal_growth: float
    growth_anchor: float
    source_note: str


class Classification(Model):
    balance_sheet_financial: bool
    intrinsic_model: Literal["dcf", "excess_return"]


class Actuals(Model):
    ebitda_margin: Num = None
    ebit_margin: Num = None
    net_margin: Num = None
    capex_pct: Num = None
    da_pct: Num = None
    enterprise_value: Num = None
    ev_ebitda: Num = None
    ev_revenue: Num = None
    pe: Num = None
    pb: Num = None
    roe: Num = None
    roic: Num = None
    invested_capital: Num = None
    net_debt: Num = None
    net_debt_to_ebitda: Num = None


class WaccBuild(Model):
    wacc: float
    cost_of_equity: float
    pre_tax_cost_of_debt: float
    after_tax_cost_of_debt: float
    beta: float
    beta_source: str
    provider_beta: Num = None
    regression_beta: Num = None
    risk_free_rate: float
    equity_risk_premium: float
    credit_spread: float
    leverage_premium: float
    tax_rate: float
    weight_equity: float
    weight_debt: float
    net_debt_to_ebitda: Num = None


class DcfInputsModel(Model):
    revenue_growth: float
    ebitda_margin: float
    wacc: float
    terminal_growth: float
    tax_rate: float
    capex_pct: float
    da_pct: float
    nwc_pct: float
    ronic: Num = None
    projection_years: int
    mid_year_convention: bool
    terminal_method: Literal["perpetuity", "exit_multiple"]
    exit_multiple: Num = None
    margin_ramp: bool = True


class LboInputsModel(Model):
    entry_multiple: float
    exit_multiple: float
    senior_debt_turns: float
    sub_debt_turns: float
    senior_rate: float
    sub_rate: float
    revenue_growth: float
    target_ebitda_margin: float
    fees_pct: float
    projection_years: int
    tax_rate: float
    capex_pct: Num = None
    da_pct: Num = None
    nwc_pct: float


class ExcessReturnInputsModel(Model):
    roe: float
    terminal_roe: float
    cost_of_equity: float
    book_growth: float
    terminal_growth: float
    projection_years: int


class Baseline(Model):
    ticker: str
    currency: str
    market: MarketParams
    classification: Classification
    actuals: Actuals
    history: HistoryMetrics
    wacc_build: WaccBuild
    dcf: DcfInputsModel
    lbo: LboInputsModel | None = None
    excess_return: ExcessReturnInputsModel | None = None
    notes: list[str]


# ----------------------------------------------------------------------------- intrinsic valuation
class DcfProjectionRow(Model):
    year: int
    revenue: float
    revenue_growth: float
    ebitda: float
    ebitda_margin: float
    d_and_a: float
    ebit: float
    taxes: float
    nopat: float
    capex: float
    delta_nwc: float
    ufcf: float
    discount_factor: float
    pv_ufcf: float


class DcfResult(Model):
    method: Literal["dcf"]
    ticker: str
    company_name: str | None = None
    currency: str
    inputs: DcfInputsModel
    current_margin: float
    projections: list[DcfProjectionRow]
    pv_ufcf_sum: float
    terminal_method: str
    terminal_value: float
    classic_terminal_value: Num = None
    terminal_fcf: Num = None
    pv_terminal_value: float
    terminal_share_of_ev: Num = None
    enterprise_value: float
    total_debt: float
    cash: float
    net_debt: float
    equity_value: float
    shares_outstanding: float
    implied_share_price: float
    current_price: Num = None
    upside: Num = None
    implied_ev_ebitda: Num = None
    roic: Num = None
    ronic: Num = None
    value_creation_spread: Num = None
    flags: list[Flag]


class ResidualIncomeRow(Model):
    year: int
    opening_book: float
    roe: float
    net_income: float
    equity_charge: float
    residual_income: float
    closing_book: float
    implied_payout: float
    pv_residual_income: float


class ExcessReturnResult(Model):
    method: Literal["excess_return"]
    ticker: str
    currency: str
    inputs: ExcessReturnInputsModel
    book_equity: float
    book_value_per_share: float
    schedule: list[ResidualIncomeRow]
    pv_residual_income_sum: float
    terminal_value: float
    pv_terminal_value: float
    equity_value: float
    shares_outstanding: float
    implied_share_price: float
    current_price: Num = None
    upside: Num = None
    justified_pb: float
    market_pb: Num = None
    market_implied_roe: Num = None
    flags: list[Flag]


IntrinsicResult = Annotated[Union[DcfResult, ExcessReturnResult], Field(discriminator="method")]

Grid = list[list[Num]]


class DcfSensitivity(Model):
    method: Literal["dcf"]
    currency: str
    current_price: Num = None
    wacc_values: list[float]
    terminal_growth_values: list[float]
    wacc_terminal: Grid
    revenue_growth_values: list[float]
    ebitda_margin_values: list[float]
    growth_margin: Grid


class ExcessReturnSensitivity(Model):
    method: Literal["excess_return"]
    cost_of_equity_values: list[float]
    terminal_growth_values: list[float]
    terminal_roe_values: list[float]
    ke_growth: Grid
    ke_roe: Grid


SensitivityResult = Annotated[Union[DcfSensitivity, ExcessReturnSensitivity], Field(discriminator="method")]


# ----------------------------------------------------------------------------- M&A
class FxQuoteModel(Model):
    from_currency: str
    to_currency: str
    rate: float
    date: str | None = None
    source: str


class MnaInputsModel(Model):
    offer_premium_pct: float
    pct_stock: float
    pct_cash: float
    pct_debt: float
    debt_interest_rate: float
    cash_yield: float
    revenue_synergies: float
    incremental_margin: float
    cost_synergies: float
    integration_costs: float
    tax_rate: float


class MnaResult(Model):
    currency: str
    target_currency: str
    fx: FxQuoteModel | None = None
    acquirer_ticker: str
    target_ticker: str
    inputs: MnaInputsModel
    offer_price: float
    offer_price_target_currency: float
    total_purchase_price: float
    offer_enterprise_value: float
    implied_ev_ebitda: Num = None
    implied_pe: Num = None
    acquirer_pe: Num = None
    stock_consideration: float
    cash_consideration: float
    new_debt: float
    new_shares_issued: float
    new_debt_interest_pre_tax: float
    foregone_interest_pre_tax: float
    after_tax_financing_cost: float
    pre_tax_synergies: float
    after_tax_synergies: float
    after_tax_integration: float
    acquirer_net_income: float
    target_net_income: float
    pro_forma_net_income: float
    pro_forma_net_income_run_rate: float
    pro_forma_shares: float
    acquirer_standalone_eps: float
    post_deal_eps: float
    post_deal_eps_run_rate: float
    eps_change: float
    eps_change_pct: Num = None
    eps_change_run_rate: float
    eps_change_pct_run_rate: Num = None
    is_accretive: bool
    break_even_pre_tax_synergy: Num = None
    ownership_acquirer: float
    ownership_target: float
    pro_forma_debt: float
    pro_forma_net_debt_to_ebitda: Num = None
    acquirer_cash: float
    flags: list[Flag]


# ----------------------------------------------------------------------------- LBO
class LboScheduleRow(Model):
    year: int
    revenue: float
    ebitda: float
    ebitda_margin: float
    d_and_a: float
    ebit: float
    interest: float
    taxes: float
    capex: float
    delta_nwc: float
    levered_fcf: float
    mandatory_amortization: float
    senior_sweep: float
    sub_sweep: float
    revolver_draw: float
    revolver_repayment: float
    beginning_senior: float
    ending_senior: float
    beginning_sub: float
    ending_sub: float
    revolver_balance: float
    cash_balance: float
    total_debt: float
    net_debt: float
    leverage: Num = None
    interest_coverage: Num = None


class LboAttribution(Model):
    ebitda_growth: float
    multiple_expansion: float
    deleveraging: float
    fees_and_leakage: float
    equity_floor: float


class LboResultInputs(LboInputsModel):
    senior_amortization: float
    revolver_rate: float


class LboResult(Model):
    currency: str
    inputs: LboResultInputs
    entry_ebitda: float
    entry_margin: float
    entry_ev: float
    fees: float
    total_uses: float
    senior_debt: float
    sub_debt: float
    total_debt_initial: float
    sponsor_initial_equity: float
    equity_contribution_pct: float
    entry_leverage: float
    schedule: list[LboScheduleRow]
    exit_ebitda: float
    exit_ev: float
    exit_net_debt: float
    exit_equity: float
    moic: float
    irr: float
    value_creation: float
    attribution: LboAttribution
    min_interest_coverage: Num = None
    peak_revolver: float
    flags: list[Flag]


class StressScenario(Model):
    name: str
    description: str
    status: str | None = None
    irr: Num = None
    moic: Num = None
    min_interest_coverage: Num = None
    peak_revolver: Num = None
    message: str | None = None


class StressResult(Model):
    currency: str
    scenarios: list[StressScenario]


# ----------------------------------------------------------------------------- comps
class PeerRow(Model):
    ticker: str
    company_name: str | None = None
    country: str
    industry: str | None = None
    currency: str | None = None
    market_cap_usd: Num = None
    same_industry: bool | None = None
    similarity: Num = None
    ev_revenue: Num = None
    ev_ebitda: Num = None
    pe: Num = None
    pb: Num = None


class MultipleStats(Model):
    n: int
    min: float
    p25: float
    median: float
    mean: float
    p75: float
    max: float
    label: str
    excluded_outliers: int


class ImpliedRange(Model):
    label: str
    low: Num = None
    mid: Num = None
    high: Num = None


class CompsResult(Model):
    currency: str
    primary_multiple: str
    primary_label: str
    implied_share_price_median: Num = None
    implied_range: ImpliedRange
    implied_by_multiple: dict[str, ImpliedRange]
    upside: Num = None
    target_multiples: dict[str, Num]
    peers: list[PeerRow]
    peer_count: int
    same_industry_count: int
    distribution: dict[str, MultipleStats]
    methodology: str


# ----------------------------------------------------------------------------- risk
class McMetrics(Model):
    mean: float
    median: float
    std: float
    p05: float
    p10: float
    p25: float
    p75: float
    p90: float
    p95: float
    prob_below_market: Num = None
    prob_above_market: Num = None
    prob_negative: float


class HistogramBin(Model):
    start: float
    end: float
    mid: float
    count: int


class AttributionRow(Model):
    variable: str
    label: str
    standardized_coefficient: float
    variance_share: float


class TornadoRow(Model):
    variable: str
    label: str
    low_input: float
    high_input: float
    price_at_low: float
    price_at_high: float
    swing: float


class McSample(Model):
    revenue_growth: float
    ebitda_margin: float
    price: float


class MonteCarloResult(Model):
    currency: str
    iterations: int
    valid_scenarios: int
    seed: int
    adjusted_terminal_growth_draws: int
    base_price: float
    current_price: Num = None
    metrics: McMetrics
    histogram: list[HistogramBin]
    input_volatility: dict[str, float]
    correlation: list[list[float]]
    attribution: list[AttributionRow]
    attribution_r_squared: float
    tornado: list[TornadoRow]
    sample: list[McSample]
    methodology: str


class VarRow(Model):
    method: Literal["historical", "normal", "cornish_fisher"]
    confidence: float
    var_1d: float
    es_1d: float
    var_10d: float
    es_10d: float


class ReturnBin(Model):
    value: float
    count: int
    normal: float


class VarResult(Model):
    observations: int
    mean_daily_return: float
    daily_volatility: float
    annualized_volatility: float
    skewness: float
    excess_kurtosis: float
    jarque_bera_p_value: float
    normality_rejected: bool
    worst_day: float
    best_day: float
    table: list[VarRow]
    histogram: list[ReturnBin]
    max_drawdown: Num = None
    peak_date: str | None = None
    trough_date: str | None = None
    methodology: str


class EvtLevel(Model):
    confidence: float
    var_1d: float
    es_1d: Num = None
    empirical_var_1d: Num = None


class QQPoint(Model):
    empirical: float
    model: float


class EvtResult(Model):
    threshold: float
    threshold_quantile: float
    exceedances: int
    observations: int
    shape_xi: float
    scale_beta: float
    tail_interpretation: str
    levels: list[EvtLevel]
    ks_p_value: float
    qq: list[QQPoint]
    low_sample_warning: bool
    methodology: str


class RegimeState(Model):
    label: str
    mean_daily: float
    annualized_return: float
    annualized_volatility: float
    persistence: float
    expected_duration_days: Num = None
    share_of_days: float


class RegimePoint(Model):
    date: str
    value: float
    p_high_vol: float


class RegimeResult(Model):
    observations: int
    current_regime: str
    current_probabilities: dict[str, float]
    states: list[RegimeState]
    transition_matrix: list[list[float]]
    volatility_ratio: float
    log_likelihood: float
    bic_hmm: float
    bic_single_regime: float
    regimes_supported: bool
    sequence: list[RegimePoint]
    methodology: str


class Coefficient(Model):
    factor: str
    label: str
    coefficient: float
    std_error: float
    t_stat: float
    p_value: float


class CumulativePoint(Model):
    date: str
    stock: float
    market: float


class FactorUniverse(Model):
    constituents: int
    portfolio_sizes: dict[str, int]
    rf_daily: float


class FactorResult(Model):
    market: str
    observations: int
    start_date: str
    end_date: str
    coefficients: list[Coefficient]
    alpha_annualized: float
    r_squared: float
    adjusted_r_squared: float
    residual_volatility_annualized: float
    capm_beta: float
    capm_beta_std_error: float
    capm_r_squared: float
    provider_beta: Num = None
    universe: FactorUniverse
    cumulative: list[CumulativePoint]
    methodology: str
    limitations: str


class MertonInputs(Model):
    equity_value: float
    default_point: float
    equity_volatility: float
    risk_free_rate: float
    horizon_years: float
    volatility_window_days: int


class MertonSensitivity(Model):
    equity_volatility: float
    distance_to_default: float
    probability_of_default: float


class MertonResult(Model):
    inputs: MertonInputs
    asset_value: float
    asset_volatility: float
    distance_to_default: Num = None
    probability_of_default: float
    market_leverage: float
    implied_credit_spread: Num = None
    sensitivity: list[MertonSensitivity]
    note: str | None = None
    methodology: str


class CopulaFit(Model):
    family: str
    name: str
    params: dict[str, float]
    log_likelihood: float
    aic: float
    lower_tail: float
    upper_tail: float


class JointCrash(Model):
    quantile: float
    model_probability: float
    empirical_probability: float
    independence_probability: float
    multiple_of_independence: float


class EmpiricalTail(Model):
    quantile: float
    lower: float
    upper: float


class CorrelationPoint(Model):
    date: str
    correlation: float


class PseudoObservation(Model):
    u: float
    v: float


class CopulaResult(Model):
    pair: dict[str, str]
    observations: int
    start_date: str
    end_date: str
    kendall_tau: float
    spearman_rho: float
    pearson_correlation: float
    selected_copula: str
    selected_family: str
    selected_params: dict[str, float]
    lower_tail_dependence: float
    upper_tail_dependence: float
    fits: list[CopulaFit]
    joint_crash: JointCrash
    empirical_tail_dependence: list[EmpiricalTail]
    rolling_correlation: list[CorrelationPoint]
    pseudo_observations: list[PseudoObservation]
    methodology: str


class ConfidenceComponent(Model):
    key: str
    label: str
    score: Num = None
    detail: str
    weight: float


class ConfidenceResult(Model):
    score: Num = None
    label: str | None = None
    components: list[ConfidenceComponent]
    methodology: str


# ----------------------------------------------------------------------------- health / quality
class ScorecardComponent(Model):
    label: str
    points: int
    max: int
    detail: str


class Scorecard(Model):
    score: Num = None
    components: list[ScorecardComponent]
    note: str


class HealthResult(Model):
    status: str
    flags: list[Flag]
    counts: dict[str, int]
    scorecard: Scorecard
    acquirer_ticker: str | None = None


class DataQualityResult(Model):
    issues: list[QualityIssue]
    summary: QualitySummary


# ----------------------------------------------------------------------------- expectations
class ImpliedDrivers(Model):
    revenue_growth: Num = None
    ebitda_margin: Num = None
    terminal_growth: Num = None
    expected_return: Num = None


class FrontierPoint(Model):
    revenue_growth: float
    required_margin: float


class OperatingPoint(Model):
    period_end: str
    revenue_growth: float
    ebitda_margin: float


class CloudPoint(Model):
    revenue_growth: float
    ebitda_margin: float
    beats_price: bool
    value: float


class ValueSurface(Model):
    growth: list[float]
    margin: list[float]
    values: Grid


class ExpectationsScenario(Model):
    revenue_growth: float
    ebitda_margin: float
    wacc: float
    terminal_growth: float
    projection_years: int
    terminal_method: str


class HistoricalReference(Model):
    revenue_cagr: Num = None
    margin_average: Num = None
    years: int


class DcfExpectations(Model):
    method: Literal["dcf"]
    currency: str
    market_price: float
    scenario_value: float
    scenario_upside: float
    scenario: ExpectationsScenario
    current_margin: float
    implied: ImpliedDrivers
    historical: HistoricalReference
    expectations_gap: Num = None
    stance: str | None = None
    frontier: list[FrontierPoint]
    history_points: list[OperatingPoint]
    odds_fundamentals_beat_price: float
    cloud: list[CloudPoint]
    surface: ValueSurface
    input_volatility: dict[str, float]
    narrative: list[str]
    methodology: str


class FinancialExpectations(Model):
    method: Literal["excess_return"]
    currency: str
    market_price: float
    scenario_value: float
    scenario_upside: float
    market_pb: float
    current_roe: float
    cost_of_equity: float
    implied_steady_state_roe: float
    implied_terminal_roe: Num = None
    expectations_gap: float
    stance: str
    narrative: list[str]
    methodology: str


ExpectationsResult = Annotated[Union[DcfExpectations, FinancialExpectations], Field(discriminator="method")]


class RadarRow(Model):
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str
    country: str
    model: str
    market_cap: Num = None
    market_cap_usd: Num = None
    price: Num = None
    status: str
    implied_growth: Num = None
    historical_cagr: Num = None
    baseline_growth: Num = None
    expectations_gap: Num = None
    implied_return: Num = None
    wacc: Num = None
    ebitda_margin: Num = None
    scenario_upside: Num = None
    implied_roe: Num = None
    current_roe: Num = None


class RadarSummary(Model):
    companies: int
    dcf_companies: int
    financial_companies: int
    not_reachable: int
    most_optimistic: list[RadarRow]
    most_pessimistic: list[RadarRow]
    sector_median_implied_growth: dict[str, float]
    median_implied_growth: Num = None
    median_historical_cagr: Num = None


class RadarResult(Model):
    rows: list[RadarRow]
    summary: RadarSummary
    computed_at: str
    methodology: str


# ----------------------------------------------------------------------------- AI
class CopilotResult(Model):
    answer: str
    provider: str
    model: str | None = None
    mode: Literal["llm", "offline"]
    is_fallback: bool
    errors: list[str]
    context_ticker: str


class MemoResult(Model):
    markdown: str
    provider: str
    mode: Literal["llm", "offline"]
    generated_at: str

