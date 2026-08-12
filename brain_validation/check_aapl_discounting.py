wacc = 0.09
terminal_growth = 0.03
projection_years = 5

ufcf = [
    102202353600.0,
    110378541888.0,
    119208825239.04001,
    128745531258.1632,
    139045173758.81628
]

pv_sum = 0

for year, cashflow in enumerate(ufcf, 1):
    df = 1 / ((1 + wacc) ** year)
    pv = cashflow * df
    pv_sum += pv

    print(f"YEAR {year}")
    print("Discount Factor:", df)
    print("PV UFCF:", pv)

terminal_value = ufcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
pv_terminal = terminal_value / ((1 + wacc) ** projection_years)

enterprise_value = pv_sum + pv_terminal

print("\nPV UFCF SUM:", pv_sum)
print("TERMINAL VALUE:", terminal_value)
print("PV TERMINAL VALUE:", pv_terminal)
print("ENTERPRISE VALUE:", enterprise_value)
