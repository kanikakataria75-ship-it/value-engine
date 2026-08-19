library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
returns <- as.numeric(data$returns)
conf <- data$confidence
horizon <- data$horizon

if (length(returns) < 30) {
    cat(toJSON(list(status="UNAVAILABLE", message="Insufficient data for VaR/CVaR"), auto_unbox=TRUE))
    quit(status=0)
}

alpha <- 1 - conf
# Historical VaR
hist_var <- quantile(returns, alpha, na.rm=TRUE)
hist_cvar <- mean(returns[returns <= hist_var], na.rm=TRUE)

# Parametric VaR (Normal)
mu <- mean(returns, na.rm=TRUE)
sigma <- sd(returns, na.rm=TRUE)
param_var <- qnorm(alpha, mean=mu, sd=sigma)
param_cvar <- mu - sigma * dnorm(qnorm(alpha)) / alpha

cat(toJSON(list(
    status="VALID",
    historical_var = abs(hist_var) * sqrt(horizon),
    historical_cvar = abs(hist_cvar) * sqrt(horizon),
    parametric_var = abs(param_var) * sqrt(horizon),
    parametric_cvar = abs(param_cvar) * sqrt(horizon),
    confidence_level = conf,
    horizon = horizon,
    observations = length(returns),
    methodology = "Historical and Parametric (Normal Distribution) Estimation"
), auto_unbox=TRUE))
