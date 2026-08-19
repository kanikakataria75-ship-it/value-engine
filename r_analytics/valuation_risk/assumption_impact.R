library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
data <- fromJSON(args[1])
df <- as.data.frame(data$samples)
df$valuation <- data$valuations

# Normalize variables
df_scaled <- as.data.frame(scale(df))
model <- lm(valuation ~ rev + margin + wacc + term, data=df_scaled)
coeffs <- abs(coef(model)[-1])
contrib <- coeffs / sum(coeffs, na.rm=TRUE)
sorted_contrib <- sort(contrib, decreasing = TRUE)

out <- lapply(names(sorted_contrib), function(x) list(
    variable=x, 
    impact_contribution=sorted_contrib[[x]]
))

cat(toJSON(list(
    impacts = out,
    methodology = "Standardized Ordinary Least Squares Regression (OLS)"
), auto_unbox=TRUE))
