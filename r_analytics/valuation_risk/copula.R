library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
retA <- as.numeric(data$acquirer_returns)
retT <- as.numeric(data$target_returns)

if (length(retA) < 30 || length(retT) < 30) {
    cat(toJSON(list(status="UNAVAILABLE", message="Insufficient data for Copula"), auto_unbox=TRUE))
    quit(status=0)
}

# Empirical tail dependence approximation
q10_A <- quantile(retA, 0.10, na.rm=TRUE)
q10_T <- quantile(retT, 0.10, na.rm=TRUE)
lower_tail <- mean(retA <= q10_A & retT <= q10_T) / 0.10

q90_A <- quantile(retA, 0.90, na.rm=TRUE)
q90_T <- quantile(retT, 0.90, na.rm=TRUE)
upper_tail <- mean(retA >= q90_A & retT >= q90_T) / 0.10

cat(toJSON(list(
    status="VALID",
    dependence_parameters = list(spearman = cor(retA, retT, method="spearman")),
    selected_copula = "Empirical",
    lower_tail_dependence = lower_tail,
    upper_tail_dependence = upper_tail,
    sample_size = length(retA),
    methodology = "Empirical Tail Dependence Copula Proxy"
), auto_unbox=TRUE))
