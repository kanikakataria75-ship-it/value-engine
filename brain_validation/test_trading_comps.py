import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.comps_engine import run_trading_comps

target = {
    "ticker": "TESTCO",
    "company_name": "Test Company",
    "ebitda": 20.0,
    "total_debt": 30.0,
    "cash_and_equivalents": 10.0,
    "shares_outstanding": 10.0,
}

peers = [
    {
        "ticker": "PEER1",
        "company_name": "Peer One",
        "market_cap": 100.0,
        "total_debt": 20.0,
        "cash_and_equivalents": 10.0,
        "revenue": 50.0,
        "ebitda": 10.0,
        "net_income": 5.0,
    },
    {
        "ticker": "PEER2",
        "company_name": "Peer Two",
        "market_cap": 200.0,
        "total_debt": 40.0,
        "cash_and_equivalents": 20.0,
        "revenue": 100.0,
        "ebitda": 20.0,
        "net_income": 10.0,
    },
    {
        "ticker": "PEER3",
        "company_name": "Peer Three",
        "market_cap": 300.0,
        "total_debt": 60.0,
        "cash_and_equivalents": 30.0,
        "revenue": 150.0,
        "ebitda": 30.0,
        "net_income": 15.0,
    },
]

result = run_trading_comps(target, peers)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("IMPLIED SHARE PRICE:", result["implied_share_price_median"])
    print("\nPEER MULTIPLES:")
    print(result["peer_multiples_df"].to_string(index=False))
    print("\nDISTRIBUTION:")
    print(result["distribution_df"].to_string())
else:
    print("MESSAGE:", result.get("message"))
