"""
M&A Accretion/Dilution & LBO Valuation Engine Modules.
"""

from .data_loader import FinancialDataLoader
from .dcf_engine import run_dcf
from .ma_engine import run_ma_model
from .lbo_engine import run_lbo_model
from .excel_exporter import ExcelReportExporter

from .comps_engine import run_trading_comps, run_transaction_comps
from .model_health import evaluate_model_health, calculate_deal_quality

__all__ = [
    "FinancialDataLoader",
    "run_dcf",
    "calculate_wacc",
    "run_ma_model",
    "run_lbo_model",
    "ExcelReportExporter",
    "run_trading_comps",
    "run_transaction_comps",
    "evaluate_model_health",
    "calculate_deal_quality",
]
