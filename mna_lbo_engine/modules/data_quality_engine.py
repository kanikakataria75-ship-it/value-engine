"""
Data Quality Engine Module.
Validates financial accounting identities, tags data provenance, and flags anomalies.
Categories: HARD ERROR, WARNING, INFORMATION.
"""

from typing import Dict, Any, List

def run_data_quality_checks(financials: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Run accounting identity checks and return a list of issues.
    Issue format: {"severity": "HARD ERROR" | "WARNING" | "INFORMATION", "metric": str, "message": str}
    """
    issues = []

    # Require critical fields
    critical_fields = ["revenue", "ebitda", "ebit", "net_income", "total_debt", "cash_and_equivalents"]
    for field in critical_fields:
        val = financials.get(field)
        if val is None:
            issues.append({
                "severity": "HARD ERROR" if field in ["revenue", "ebitda"] else "WARNING",
                "metric": "Missing Data",
                "message": f"Critical field '{field}' is genuinely missing (None)."
            })
        elif field == "revenue" and val <= 0:
            issues.append({
                "severity": "HARD ERROR",
                "metric": "Invalid Revenue",
                "message": f"Revenue ({val}) must be strictly positive."
            })
        elif field in ["total_debt", "cash_and_equivalents"] and val < 0:
            issues.append({
                "severity": "HARD ERROR",
                "metric": "Negative Balances",
                "message": f"Field '{field}' cannot be negative ({val})."
            })

    # Identity 1: Market Cap vs Price * Shares
    shares = financials.get("shares_outstanding", 0)
    price = financials.get("current_price", 0.0)
    reported_mcap = financials.get("market_cap", 0.0)
    calc_mcap = shares * price

    if calc_mcap > 0:
        mcap_diff = abs(reported_mcap - calc_mcap) / calc_mcap
        if mcap_diff > 0.10:
            issues.append({
                "severity": "WARNING",
                "metric": "Market Cap Mismatch",
                "message": f"Reported Market Cap ({reported_mcap/1e9:,.1f}B) deviates >10% from Price x Shares ({calc_mcap/1e9:,.1f}B)."
            })

    # Identity 2: EBITDA vs EBIT
    ebitda = financials.get("ebitda", 0.0)
    ebit = financials.get("ebit", 0.0)
    if ebit > ebitda and ebitda > 0:
        issues.append({
            "severity": "HARD ERROR",
            "metric": "Accounting Violation",
            "message": f"EBIT ({ebit/1e6:,.1f}M) > EBITDA ({ebitda/1e6:,.1f}M). Invalid accounting identity."
        })

    # Identity 3: Net Debt
    t_debt = financials.get("total_debt", 0.0)
    t_cash = financials.get("cash_and_equivalents", 0.0)
    if t_debt < 0 or t_cash < 0:
        issues.append({
            "severity": "HARD ERROR",
            "metric": "Negative Balances",
            "message": "Debt or Cash balances cannot be negative."
        })

    return issues

def attach_provenance(financials: Dict[str, Any], source: str, period: str, date: str) -> Dict[str, Any]:
    """
    Attach provenance metadata to the financials dictionary.
    source: 'LIVE', 'CACHED', 'DEMO', 'USER'
    """
    financials["provenance"] = {
        "source": source,
        "period": period,
        "retrieved_date": date
    }
    financials["_provenance"] = source
    return financials
