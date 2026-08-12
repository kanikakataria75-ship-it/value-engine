import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.comps_engine import run_transaction_comps

target = {
    "ticker": "TESTCO",
    "company_name": "Test Company",
    "ebitda": 20.0,
    "total_debt": 30.0,
    "cash_and_equivalents": 10.0,
    "shares_outstanding": 10.0,
}

transactions = [
    {
        "ticker": "DEAL1",
        "company_name": "Deal One",
        "market_cap": 200.0,
        "total_debt": 20.0,
        "cash_and_equivalents": 0.0,
        "revenue": 100.0,
        "ebitda": 20.0,
        "net_income": 10.0,
    },
    {
        "ticker": "DEAL2",
        "company_name": "Deal Two",
        "market_cap": 220.0,
        "total_debt": 30.0,
        "cash_and_equivalents": 10.0,
        "revenue": 100.0,
        "ebitda": 20.0,
        "net_income": 11.0,
    },
    {
        "ticker": "DEAL3",
        "company_name": "Deal Three",
        "market_cap": 180.0,
        "total_debt": 40.0,
        "cash_and_equivalents": 0.0,
        "revenue": 100.0,
        "ebitda": 20.0,
        "net_income": 9.0,
    },
]

result = run_transaction_comps(target, transactions)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("IMPLIED SHARE PRICE:", result["implied_share_price_median"])

    print("\nTRANSACTION MULTIPLES:")
    print(result["transaction_multiples_df"].to_string(index=False))

    print("\nDISTRIBUTION:")
    print(result["distribution_df"].to_string())
else:
    print("MESSAGE:", result["message"])
