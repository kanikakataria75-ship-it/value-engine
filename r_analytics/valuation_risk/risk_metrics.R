library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
vals <- as.numeric(data$valuations)
threshold <- data$threshold

cat(toJSON(list(
    mean_valuation = mean(vals, na.rm=TRUE),
    median_valuation = median(vals, na.rm=TRUE),
    standard_deviation = sd(vals, na.rm=TRUE),
    p05 = quantile(vals, 0.05, na.rm=TRUE),
    p10 = quantile(vals, 0.10, na.rm=TRUE),
    p25 = quantile(vals, 0.25, na.rm=TRUE),
    p50 = quantile(vals, 0.50, na.rm=TRUE),
    p75 = quantile(vals, 0.75, na.rm=TRUE),
    p90 = quantile(vals, 0.90, na.rm=TRUE),
    p95 = quantile(vals, 0.95, na.rm=TRUE),
    min = min(vals, na.rm=TRUE),
    max = max(vals, na.rm=TRUE),
    prob_lt_threshold = mean(vals < threshold, na.rm=TRUE),
    prob_gt_threshold = mean(vals > threshold, na.rm=TRUE)
), auto_unbox=TRUE))
