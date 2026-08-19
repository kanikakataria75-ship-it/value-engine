library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
# We expect data to have lists for returns, mkt, smb, hml, rmw, cma
ret <- data$returns; mkt <- data$mkt; smb <- data$smb; hml <- data$hml; rmw <- data$rmw; cma <- data$cma

if (length(ret) < 30) {
    cat(toJSON(list(status="UNAVAILABLE", message="Insufficient data for Fama-French"), auto_unbox=TRUE))
    quit(status=0)
}

df <- data.frame(ret, mkt, smb, hml, rmw, cma)
model <- lm(ret ~ mkt + smb + hml + rmw + cma, data=df)
s <- summary(model)
coefs <- s$coefficients

cat(toJSON(list(
    status="VALID",
    coefficients = as.list(coefs[, "Estimate"]),
    standard_errors = as.list(coefs[, "Std. Error"]),
    t_statistics = as.list(coefs[, "t value"]),
    p_values = as.list(coefs[, "Pr(>|t|)"]),
    r_squared = s$r.squared,
    adjusted_r_squared = s$adj.r.squared,
    observations = nrow(df),
    methodology = "Fama-French 5-Factor OLS Regression"
), auto_unbox=TRUE))
