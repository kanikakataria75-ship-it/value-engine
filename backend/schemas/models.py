"""Request schemas.

Every model endpoint accepts a Scenario: the analyst's assumptions for each model. Any field left
as None falls back to the company-specific baseline, so the frontend can send only what the user
changed and every downstream feature (Excel, health checks, Copilot, risk) sees the same inputs.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DataMode = Literal["local", "live"]
TICKER_PATTERN = r"^[A-Za-z0-9.\-&^]{1,20}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DcfAssumptions(StrictModel):
    revenue_growth: float | None = Field(None, gt=-0.5, lt=1.0)
    ebitda_margin: float | None = Field(None, gt=-1.0, lt=1.0)
    wacc: float | None = Field(None, gt=0.0, le=0.5)
    terminal_growth: float | None = Field(None, gt=-0.1, lt=0.2)
    tax_rate: float | None = Field(None, ge=0.0, lt=1.0)
    capex_pct: float | None = Field(None, ge=0.0, lt=1.0)
    da_pct: float | None = Field(None, ge=0.0, lt=1.0)
    nwc_pct: float | None = Field(None, gt=-1.0, lt=1.0)
    ronic: float | None = Field(None, gt=0.0, lt=2.0)
    projection_years: int | None = Field(None, ge=1, le=15)
    mid_year_convention: bool | None = None
    terminal_method: Literal["perpetuity", "exit_multiple"] | None = None
    exit_multiple: float | None = Field(None, gt=0.0, le=100.0)


class ExcessReturnAssumptions(StrictModel):
    roe: float | None = Field(None, gt=-0.5, lt=1.0)
    terminal_roe: float | None = Field(None, gt=-0.5, lt=1.0)
    cost_of_equity: float | None = Field(None, gt=0.0, le=0.5)
    book_growth: float | None = Field(None, gt=-0.5, lt=0.5)
    terminal_growth: float | None = Field(None, gt=-0.1, lt=0.2)
    projection_years: int | None = Field(None, ge=1, le=15)


class LboAssumptions(StrictModel):
    entry_multiple: float | None = Field(None, gt=0.0, le=100.0)
    exit_multiple: float | None = Field(None, gt=0.0, le=100.0)
    senior_debt_turns: float | None = Field(None, ge=0.0, le=15.0)
    sub_debt_turns: float | None = Field(None, ge=0.0, le=15.0)
    senior_rate: float | None = Field(None, ge=0.0, lt=0.5)
    sub_rate: float | None = Field(None, ge=0.0, lt=0.5)
    revenue_growth: float | None = Field(None, gt=-0.5, lt=1.0)
    target_ebitda_margin: float | None = Field(None, gt=0.0, lt=1.0)
    fees_pct: float | None = Field(None, ge=0.0, lt=0.2)
    projection_years: int | None = Field(None, ge=1, le=10)
    tax_rate: float | None = Field(None, ge=0.0, lt=1.0)


class MnaAssumptions(StrictModel):
    acquirer_ticker: str = Field(..., pattern=TICKER_PATTERN)
    offer_premium_pct: float | None = Field(None, gt=-0.5, lt=3.0)
    pct_stock: float = Field(0.5, ge=0.0, le=1.0)
    pct_cash: float = Field(0.0, ge=0.0, le=1.0)
    pct_debt: float = Field(0.5, ge=0.0, le=1.0)
    debt_interest_rate: float | None = Field(None, ge=0.0, lt=0.5)
    cash_yield: float | None = Field(None, ge=0.0, lt=0.5)
    revenue_synergies: float = Field(0.0, ge=0.0)
    incremental_margin: float = Field(0.20, ge=0.0, le=1.0)
    cost_synergies: float = Field(0.0, ge=0.0)
    integration_costs: float = Field(0.0, ge=0.0)
    tax_rate: float | None = Field(None, ge=0.0, lt=1.0)

    @field_validator("acquirer_ticker")
    @classmethod
    def upper(cls, value: str) -> str:
        return value.strip().upper()


class ScenarioRequest(StrictModel):
    ticker: str = Field(..., pattern=TICKER_PATTERN)
    mode: DataMode = "local"
    dcf: DcfAssumptions = Field(default_factory=DcfAssumptions)
    excess_return: ExcessReturnAssumptions = Field(default_factory=ExcessReturnAssumptions)
    lbo: LboAssumptions = Field(default_factory=LboAssumptions)
    mna: MnaAssumptions | None = None

    @field_validator("ticker")
    @classmethod
    def upper(cls, value: str) -> str:
        return value.strip().upper()


class MonteCarloRequest(ScenarioRequest):
    iterations: int = Field(5000, ge=500, le=20000)
    seed: int = Field(2024, ge=0, le=2**31 - 1)


class ChatMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=6000)


class CopilotRequest(StrictModel):
    message: str = Field(..., min_length=1, max_length=2000)
    ticker: str = Field(..., pattern=TICKER_PATTERN)
    page: str = Field("dashboard", max_length=40)
    mode: DataMode = "local"
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    scenario: ScenarioRequest | None = None
