library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
returns <- as.numeric(data$returns)

if (length(returns) < 50) {
    cat(toJSON(list(status="UNAVAILABLE", message="Insufficient data for EVT"), auto_unbox=TRUE))
    quit(status=0)
}

losses <- -returns
threshold <- quantile(losses, 0.90, na.rm=TRUE)
exceedances <- losses[losses > threshold]

cat(toJSON(list(
    status="VALID",
    threshold = threshold,
    exceedances_count = length(exceedances),
    extreme_quantiles = list(p99 = quantile(losses, 0.99, na.rm=TRUE)),
    sample_size = length(returns),
    methodology = "Empirical Peak Over Threshold (Proxy for GPD)",
    diagnostics = "Basic tail approximation"
), auto_unbox=TRUE))
