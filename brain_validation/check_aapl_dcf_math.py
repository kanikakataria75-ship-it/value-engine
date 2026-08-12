import json
from pathlib import Path

p = Path("brain_validation/golden_data/aapl_real.json")
d = json.loads(p.read_text())

f = d["financials"]

growth = 0.08
margin = f["ebitda"] / f["revenue"]
tax = 0.24

rev = f["revenue"]

print("BASE REVENUE:", rev)
print("EBITDA MARGIN:", margin)
print("CAPEX % REVENUE:", f["capex"] / f["revenue"])
print("D&A % REVENUE:", f["da"] / f["revenue"])

for year in range(1, 6):
    prev = rev
    rev = prev * (1 + growth)

    ebitda = rev * margin
    da = rev * (f["da"] / f["revenue"])
    ebit = ebitda - da
    taxes = max(0, ebit * tax)
    nopat = ebit - taxes
    capex = rev * (f["capex"] / f["revenue"])
    delta_nwc = (rev - prev) * 0.02
    ufcf = nopat + da - capex - delta_nwc

    print(f"\nYEAR {year}")
    print("Revenue:", rev)
    print("EBITDA:", ebitda)
    print("D&A:", da)
    print("EBIT:", ebit)
    print("Taxes:", taxes)
    print("NOPAT:", nopat)
    print("CapEx:", capex)
    print("Delta NWC:", delta_nwc)
    print("UFCF:", ufcf)
