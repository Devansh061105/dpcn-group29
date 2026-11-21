# Stochastic actor-oriented model (RSiena) of the faculty co-authorship network, called by step s22.
#   Rscript siena_faculty.R <input dir> <output dir> <seed> <quick 0/1>
# Inputs (written by s22): wave1.csv .. waveK.csv (0/1 adjacency, no header), nodes.csv (lab, dept, seniority,
# output_w1 .. output_wK), topic.csv (topic similarity matrix, no header).
# Outputs: siena_estimates.csv (one row per model and effect), siena_fit.json (convergence and counts per model).

suppressPackageStartupMessages({ library(RSiena); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]; out <- args[2]; seed <- as.integer(args[3]); quick <- args[4] == "1"

waves <- sort(list.files(inp, pattern = "^wave[0-9]+\\.csv$", full.names = TRUE))
K <- length(waves)
nodes <- read.csv(file.path(inp, "nodes.csv"))
n <- nrow(nodes)
arr <- array(0L, dim = c(n, n, K))
for (k in seq_len(K)) arr[, , k] <- as.matrix(read.csv(waves[k], header = FALSE))
topic <- as.matrix(read.csv(file.path(inp, "topic.csv"), header = FALSE))

collab <- sienaDependent(arr, type = "oneMode", allowOnly = FALSE)
lab <- coCovar(as.numeric(nodes$lab))
dept <- coCovar(as.numeric(nodes$dept))
senior <- coCovar(as.numeric(nodes$seniority))
outp <- varCovar(as.matrix(nodes[, paste0("output_w", seq_len(K - 1))]))
topicSim <- coDyadCovar(topic)
dat <- sienaDataCreate(collab, lab, dept, senior, outp, topicSim)

base <- getEffects(dat)
specs <- list(
  "1 lab and structure" = function(e) {
    e <- includeEffects(e, transTriads, degPlus)
    includeEffects(e, sameX, interaction1 = "lab")
  },
  "2 + department, topic" = function(e) {
    e <- includeEffects(e, transTriads, degPlus)
    e <- includeEffects(e, sameX, interaction1 = "lab")
    e <- includeEffects(e, sameX, interaction1 = "dept")
    includeEffects(e, X, interaction1 = "topicSim")
  },
  "3 + seniority, output" = function(e) {
    e <- includeEffects(e, transTriads, degPlus)
    e <- includeEffects(e, sameX, interaction1 = "lab")
    e <- includeEffects(e, sameX, interaction1 = "dept")
    e <- includeEffects(e, X, interaction1 = "topicSim")
    e <- includeEffects(e, egoPlusAltX, interaction1 = "senior")
    includeEffects(e, egoPlusAltX, interaction1 = "outp")
  }
)

rows <- list(); fit <- list()
for (nm in names(specs)) {
  eff <- specs[[nm]](base)
  alg <- sienaAlgorithmCreate(projname = NULL, seed = seed, modelType = c(collab = 2L), firstg = 0.05, diagonalize = 0.3,
                              n3 = if (quick) 500 else 3000, nsub = if (quick) 2 else 4)
  ans <- siena07(alg, data = dat, effects = eff, batch = TRUE, verbose = FALSE, silent = TRUE, useCluster = FALSE)
  tries <- 1
  while (ans$tconv.max > 0.25 && tries < (if (quick) 2 else 4)) {
    ans <- siena07(alg, data = dat, effects = eff, prevAns = ans, batch = TRUE, verbose = FALSE, silent = TRUE)
    tries <- tries + 1
  }
  # with conditional estimation the basic rate parameters are not in theta: report them from ans$rate / ans$vrate
  inc <- eff[eff$include & !eff$basicRate, ]
  theta <- ans$theta; se <- sqrt(diag(ans$covtheta))
  stopifnot(length(theta) == nrow(inc))
  if (!is.null(ans$rate)) {
    for (i in seq_along(ans$rate)) {
      rows[[length(rows) + 1]] <- data.frame(model = nm, effect = paste("rate, period", i), short = "Rate", interaction = "",
                                             type = "rate", estimate = ans$rate[i], se = ans$vrate[i], t_conv = NA)
    }
  }
  for (i in seq_along(theta)) {
    rows[[length(rows) + 1]] <- data.frame(model = nm, effect = inc$effectName[i], short = inc$shortName[i],
                                           interaction = inc$interaction1[i], type = inc$type[i],
                                           estimate = theta[i], se = se[i], t_conv = ans$tconv[i])
  }
  fit[[nm]] <- list(tconv_max = as.numeric(ans$tconv.max), runs = tries, nodes = n, waves = K,
                    ties = as.list(apply(arr, 3, function(m) sum(m) / 2)))
}
est <- do.call(rbind, rows)
est$z <- est$estimate / est$se
est$p <- 2 * pnorm(-abs(est$z))
write.csv(est, file.path(out, "siena_estimates.csv"), row.names = FALSE)
writeLines(toJSON(fit, auto_unbox = TRUE, pretty = TRUE, digits = 6), file.path(out, "siena_fit.json"))
cat("done\n")
