library(jsonlite)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) quit(status = 1)
input_data <- fromJSON(args[1])

iter <- input_data$iterations
set.seed(42)

# Generate distributions
rev_samples <- rnorm(iter, mean=input_data$base_rev_growth, sd=max(0.01, input_data$base_rev_growth * 0.1))
margin_samples <- rnorm(iter, mean=input_data$base_ebitda_margin, sd=max(0.01, input_data$base_ebitda_margin * 0.1))
wacc_samples <- rnorm(iter, mean=input_data$base_wacc, sd=max(0.005, input_data$base_wacc * 0.05))
term_samples <- rnorm(iter, mean=input_data$base_term_growth, sd=max(0.002, input_data$base_term_growth * 0.1))

# Clip
rev_samples <- pmax(-0.2, pmin(0.5, rev_samples))
margin_samples <- pmax(0.01, pmin(0.8, margin_samples))
wacc_samples <- pmax(input_data$base_term_growth + 0.001, pmin(0.3, wacc_samples))

cat(toJSON(list(
    rev_samples = rev_samples,
    margin_samples = margin_samples,
    wacc_samples = wacc_samples,
    term_samples = term_samples,
    simulation_count = iter,
    methodology = "Normal distribution with sensible bounds"
), auto_unbox=TRUE))
