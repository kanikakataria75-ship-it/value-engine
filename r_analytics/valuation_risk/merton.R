library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])

E <- data$equity_value
D <- data$debt
sigma_E <- data$equity_volatility
r <- data$risk_free_rate
T <- data$debt_maturity

if(E <= 0 || D <= 0 || sigma_E <= 0 || T <= 0) {
    cat(toJSON(list(status="UNAVAILABLE", message="Invalid Merton inputs"), auto_unbox=TRUE))
    quit(status=0)
}

# Simplified Merton approach (iterative approximation)
V <- E + D
sigma_V <- (E / V) * sigma_E
for (i in 1:100) {
    d1 <- (log(V/D) + (r + 0.5 * sigma_V^2) * T) / (sigma_V * sqrt(T))
    d2 <- d1 - sigma_V * sqrt(T)
    V_new <- E + D * exp(-r * T) * pnorm(-d2) / pnorm(d1)
    sigma_V_new <- (E / V_new) * sigma_E / pnorm(d1)
    if (abs(V_new - V) < 1e-4 && abs(sigma_V_new - sigma_V) < 1e-4) break
    V <- V_new
    sigma_V <- sigma_V_new
}

d2 <- (log(V/D) + (r - 0.5 * sigma_V^2) * T) / (sigma_V * sqrt(T))
DD <- d2
PD <- pnorm(-DD)

cat(toJSON(list(
    status="VALID",
    estimated_asset_value = V,
    asset_volatility = sigma_V,
    distance_to_default = DD,
    probability_of_default = PD,
    methodology = "Merton Structural Credit-Risk Model",
    assumptions = "Equity as a call option on firm assets (Black-Scholes-Merton)"
), auto_unbox=TRUE))
