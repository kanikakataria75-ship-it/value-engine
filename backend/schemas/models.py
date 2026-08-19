from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


Status = Literal["VALID", "REVIEW_REQUIRED", "INVALID", "UNAVAILABLE", "DEMO", "LIVE", "CACHED", "RATE_LIMITED", "LOCAL", "LOADING", "ERROR"]


class ApiEnvelope(BaseModel):
    status: Status
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CompanyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    mode: str = Field(default="local")


class DcfRequest(CompanyRequest):
    revenue_growth_rate: float = 0.07
    ebitda_margin: float = 0.25
    wacc: float = 0.085
    terminal_growth_rate: float = 0.025
    projection_years: int = Field(default=5, ge=1, le=10)
    tax_rate: float = Field(default=0.21, ge=0, le=1)
    mid_year_convention: bool = False


class MnaRequest(BaseModel):
    target_ticker: str = "AAPL"
    acquirer_ticker: str = "MSFT"
    offer_premium_pct: float = 0.25
    pct_cash: float = Field(default=0.5, ge=0, le=1)
    pct_stock: float = Field(default=0.5, ge=0, le=1)
    debt_interest_rate: float = Field(default=0.08, ge=0, le=1)
    revenue_synergies: float = Field(default=0, ge=0)
    incremental_margin: float = Field(default=0.20, ge=0, le=1)
    cost_synergies: float = Field(default=0, ge=0)
    integration_costs: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=0.21, ge=0, le=1)
    mode: str = Field(default="local")


class LboRequest(CompanyRequest):
    entry_multiple: float = Field(default=10.0, gt=0)
    senior_debt_pct: float = Field(default=0.4, ge=0, le=1)
    sub_debt_pct: float = Field(default=0.2, ge=0, le=1)
    senior_rate: float = Field(default=0.08, ge=0, le=1)
    sub_rate: float = Field(default=0.10, ge=0, le=1)
    exit_multiple: float = Field(default=11.0, gt=0)
    revenue_growth: float = Field(default=0.07, ge=-0.5, le=1)
    ebitda_margin: float = Field(default=0.25, gt=0, le=1)
    projection_years: int = Field(default=5, ge=1, le=10)
    tax_rate: float = Field(default=0.21, ge=0, le=1)


class AnalyticsRequest(DcfRequest):
    iterations: int = Field(default=300, ge=50, le=2000)


class ExportRequest(BaseModel):
    target_ticker: str = "AAPL"
    acquirer_ticker: str = "MSFT"
    mode: str = Field(default="local")

class CopilotRequest(BaseModel):
    message: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=12)
    context_scope: str = Field(default="current_company")
    page_context: str = Field(default="dashboard")
