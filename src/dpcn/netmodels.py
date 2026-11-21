"""Network models from the course applied to our co-authorship data (used by step s18).

Everything here is plain numpy / scipy / networkx so the step adds no dependency. Each function takes ordinary
Python or numpy inputs and returns plain data, which keeps it testable on toy graphs.

  heavy tails      discrete power-law fit with the Clauset-Shalizi-Newman (2009) recipe: x_min by minimum KS
                   distance, alpha by maximum likelihood, a bootstrap goodness-of-fit p-value, and Vuong likelihood-
                   ratio tests against log-normal, exponential and power law with exponential cutoff
  small world      path length and clustering against Erdos-Renyi and degree-preserving random graphs
  robustness       largest component and lab-to-lab connectivity as nodes are removed at random or by attack;
                   minimum edge cuts between labs; the Molloy-Reed random-failure threshold
  spreading        discrete-time SI and SIS on the network, with the epidemic threshold compared to theory
  link prediction  similarity scores and a logistic model, scored by AUC on links that form in a later year
  tie formation    discrete-time hazard model of new collaborations with dyadic-robust standard errors
"""
from __future__ import annotations

from itertools import combinations

import networkx as nx
import numpy as np
from scipy import optimize, special, stats

# --------------------------------------------------------------------------- heavy tails (Clauset et al. 2009)


def _pl_loglik_alpha(t: np.ndarray, xmin: int) -> float:
    """Discrete power-law MLE of alpha for the tail t (all values >= xmin)."""
    n, slx = len(t), np.log(t).sum()
    res = optimize.minimize_scalar(lambda a: n * np.log(special.zeta(a, xmin)) + a * slx,
                                   bounds=(1.0001, 8.0), method="bounded", options={"xatol": 1e-6})
    return float(res.x)


def _ks_power_law(t: np.ndarray, xmin: int, alpha: float) -> float:
    """KS distance between the empirical and fitted complementary CDFs of the tail."""
    u = np.unique(t)
    emp = 1 - np.searchsorted(np.sort(t), u, side="left") / len(t)       # P(X >= u)
    th = special.zeta(alpha, u) / special.zeta(alpha, xmin)
    return float(np.max(np.abs(emp - th)))


def fit_power_law(x, min_tail: int = 25, max_candidates: int = 60) -> dict:
    """Scan x_min, fit alpha at each, keep the x_min with the smallest KS distance (Clauset et al. 2009, sec. 3.3)."""
    x = np.asarray(x, float)
    x = np.round(x[x >= 1])
    cands = np.unique(x)
    cands = cands[np.array([(x >= c).sum() >= min_tail for c in cands], bool)]
    if len(cands) == 0:
        return {"xmin": np.nan, "alpha": np.nan, "ks": np.nan, "n_tail": 0, "n": len(x)}
    if len(cands) > max_candidates:   # keep the scan affordable: every value at the low end, then quantiles
        cands = np.unique(np.concatenate([cands[:20], np.quantile(cands, np.linspace(0, 1, max_candidates - 20)).round()]))
    best = None
    for c in cands:
        t = x[x >= c]
        a = _pl_loglik_alpha(t, int(c))
        d = _ks_power_law(t, int(c), a)
        if best is None or d < best[2]:
            best = (int(c), a, d)
    return {"xmin": best[0], "alpha": best[1], "ks": best[2], "n_tail": int((x >= best[0]).sum()), "n": len(x)}


def _sample_power_law(n: int, xmin: int, alpha: float, rng) -> np.ndarray:
    """Approximate discrete power-law draws (Clauset et al. 2009, eq. D.6)."""
    r = rng.random(n)
    return np.floor((xmin - 0.5) * (1 - r) ** (-1 / (alpha - 1)) + 0.5)


def power_law_gof(x, fit: dict, n_boot: int = 200, seed: int = 42, min_tail: int = 25) -> float:
    """Semi-parametric bootstrap p-value: share of synthetic data sets whose refitted KS is at least the observed one.
    p >= 0.1 means a power law is a plausible description of the tail."""
    x = np.round(np.asarray(x, float))
    x = x[x >= 1]
    if not np.isfinite(fit["alpha"]):
        return np.nan
    rng = np.random.default_rng(seed)
    body = x[x < fit["xmin"]]
    p_tail = fit["n_tail"] / len(x)
    worse = 0
    for _ in range(n_boot):
        k = rng.binomial(len(x), p_tail)
        syn = np.concatenate([_sample_power_law(k, fit["xmin"], fit["alpha"], rng),
                              rng.choice(body, len(x) - k) if len(body) else np.empty(0)])
        f = fit_power_law(syn, min_tail=min_tail)
        worse += f["ks"] >= fit["ks"]
    return worse / n_boot


def _ll_power_law(t, xmin, alpha):
    return -alpha * np.log(t) - np.log(special.zeta(alpha, xmin))


def _ll_exponential(t, xmin):
    m = np.mean(t - xmin)
    lam = np.log1p(1 / m) if m > 0 else 50.0
    return np.log1p(-np.exp(-lam)) - lam * (t - xmin), {"lambda": lam}


def _ll_lognormal(t, xmin):
    lt = np.log(t)

    def ll(p, t=t):
        mu, s = p[0], np.exp(p[1])
        hi = stats.norm.cdf((np.log(t + 0.5) - mu) / s)
        lo = stats.norm.cdf((np.log(t - 0.5) - mu) / s)
        z = stats.norm.sf((np.log(xmin - 0.5) - mu) / s)
        return np.log(np.clip(hi - lo, 1e-300, None)) - np.log(max(z, 1e-300))
    res = optimize.minimize(lambda p: -ll(p).sum(), x0=[lt.mean(), np.log(lt.std() + 0.1)], method="Nelder-Mead",
                            options={"maxiter": 4000, "xatol": 1e-7, "fatol": 1e-9})
    return ll(res.x), {"mu": float(res.x[0]), "sigma": float(np.exp(res.x[1]))}


def _ll_truncated_power_law(t, xmin, alpha0):
    support = np.arange(xmin, max(int(t.max()) * 20, 10_000) + 1, dtype=float)
    lsup = np.log(support)

    def ll(p, t=t):
        a, lam = p[0], np.exp(p[1])
        lz = special.logsumexp(-a * lsup - lam * support)
        return -a * np.log(t) - lam * t - lz
    best = None
    for lam0 in (1e-4, 1e-3, 1e-2, 1e-1):
        res = optimize.minimize(lambda p: -ll(p).sum(), x0=[max(alpha0 - 0.3, 0.5), np.log(lam0)], method="Nelder-Mead",
                                options={"maxiter": 4000})
        if best is None or res.fun < best.fun:
            best = res
    return ll(best.x), {"alpha": float(best.x[0]), "lambda": float(np.exp(best.x[1]))}


def vuong(l1: np.ndarray, l2: np.ndarray, nested: bool = False) -> tuple[float, float]:
    """Log-likelihood ratio R (positive favours model 1) and its p-value (Vuong 1989; nested: chi-square, 1 df)."""
    d = l1 - l2
    R = float(d.sum())
    if nested:
        return R, float(stats.chi2.sf(2 * abs(R), 1))
    s = d.std()
    if s == 0:
        return R, 1.0
    return R, float(special.erfc(abs(R) / (np.sqrt(2 * len(d)) * s)))


def compare_tails(x, fit: dict) -> list[dict]:
    """Power law against three alternatives on the same tail (x >= x_min), as in Clauset et al. 2009 table 6.2."""
    x = np.round(np.asarray(x, float))
    t = x[x >= fit["xmin"]]
    lpl = _ll_power_law(t, fit["xmin"], fit["alpha"])
    out = []
    for name, (lalt, params), nested in (
            ("log-normal", _ll_lognormal(t, fit["xmin"]), False),
            ("exponential", _ll_exponential(t, fit["xmin"]), False),
            ("power law with cutoff", _ll_truncated_power_law(t, fit["xmin"], fit["alpha"]), True)):
        R, p = vuong(lpl, lalt, nested=nested)
        verdict = "inconclusive" if p >= 0.1 else ("power law favoured" if R > 0 else f"{name} favoured")
        out.append({"alternative": name, "llr": R, "p": p, "verdict": verdict,
                    "alt_params": ";".join(f"{k}={v:.4g}" for k, v in params.items())})
    return out


# --------------------------------------------------------------------------- small world


def largest_component(G: nx.Graph) -> nx.Graph:
    return G.subgraph(max(nx.connected_components(G), key=len)).copy() if G.number_of_nodes() else G.copy()


def mean_path_length(H: nx.Graph, max_sources: int = 600, seed: int = 42) -> float:
    """Average shortest path length of a connected graph; BFS from a random sample of sources when it is large."""
    nodes = list(H)
    if len(nodes) <= max_sources:
        return nx.average_shortest_path_length(H)
    rng = np.random.default_rng(seed)
    tot = cnt = 0
    for s in rng.choice(len(nodes), max_sources, replace=False):
        d = nx.single_source_shortest_path_length(H, nodes[s])
        tot += sum(d.values())
        cnt += len(d) - 1
    return tot / cnt


def _config_null(H: nx.Graph, seed: int) -> nx.Graph:
    M = nx.configuration_model([d for _, d in H.degree()], seed=seed)
    G = nx.Graph(M)
    G.remove_edges_from(nx.selfloop_edges(G))
    return G


def small_world(G: nx.Graph, n_null: int = 20, seed: int = 42, swap: bool = True, max_sources: int = 600) -> dict:
    """Clustering and path length of the largest component against random graphs of the same size.

    ER: G(n, m) with the component's n and m (its own largest component is measured). Degree-preserving: double-edge
    swaps when `swap`, else a simplified configuration model (faster for large graphs). sigma = (C/C_r) / (L/L_r)
    (Humphries & Gurney 2008); sigma well above 1 with L close to L_r is the small-world signature."""
    H = largest_component(G)
    n, m = H.number_of_nodes(), H.number_of_edges()
    k = 2 * m / n
    out = {"n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(), "lcc_nodes": n, "lcc_edges": m,
           "mean_degree": k, "clustering": nx.average_clustering(H), "transitivity": nx.transitivity(H),
           "path_length": mean_path_length(H, max_sources, seed), "diameter_lb": nx.approximation.diameter(H) if n < 5000 else np.nan,
           "er_path_length_theory": np.log(n) / np.log(k) if k > 1 else np.nan, "er_clustering_theory": k / n}
    rng = np.random.default_rng(seed)
    er_c, er_l, dp_c, dp_l = [], [], [], []
    for i in range(n_null):
        R = largest_component(nx.gnm_random_graph(n, m, seed=int(rng.integers(1 << 31))))
        er_c.append(nx.average_clustering(R))
        er_l.append(mean_path_length(R, max_sources, seed + i))
        if swap:
            D = H.copy()
            nx.double_edge_swap(D, nswap=5 * m, max_tries=100 * m, seed=int(rng.integers(1 << 31)))
        else:
            D = _config_null(H, int(rng.integers(1 << 31)))
        D = largest_component(D)
        dp_c.append(nx.average_clustering(D))
        dp_l.append(mean_path_length(D, max_sources, seed + i))
    out.update({"er_clustering": float(np.mean(er_c)), "er_path_length": float(np.mean(er_l)),
                "degree_preserving_clustering": float(np.mean(dp_c)), "degree_preserving_path_length": float(np.mean(dp_l)),
                "degree_null": "double-edge swap" if swap else "configuration model", "n_null": n_null})
    out["sigma_er"] = (out["clustering"] / out["er_clustering"]) / (out["path_length"] / out["er_path_length"])
    out["sigma_degree_preserving"] = ((out["clustering"] / out["degree_preserving_clustering"])
                                      / (out["path_length"] / out["degree_preserving_path_length"]))
    return out


# --------------------------------------------------------------------------- robustness


def molloy_reed(G: nx.Graph) -> dict:
    """kappa = <k^2>/<k>; a giant component exists while kappa > 2; random-failure threshold f_c = 1 - 1/(kappa - 1)
    (Cohen et al. 2000). Assumes a configuration-model graph, so it is a reference, not a prediction."""
    k = np.array([d for _, d in G.degree()], float)
    kappa = (k ** 2).mean() / k.mean()
    return {"mean_k": k.mean(), "mean_k2": (k ** 2).mean(), "kappa": kappa,
            "fc_random_theory": 1 - 1 / (kappa - 1) if kappa > 1 else 0.0}


def _state(G: nx.Graph, lab: dict, n0: int, labs: list[str]) -> tuple[float, int]:
    """(largest component / original n, number of lab pairs still joined by some path)."""
    if G.number_of_nodes() == 0:
        return 0.0, 0
    comps = list(nx.connected_components(G))
    lcc = max(len(c) for c in comps) / n0
    joined = set()
    for c in comps:
        ls = sorted({lab[v] for v in c})
        joined.update(combinations(ls, 2))
    return lcc, len(joined)


def attack(G: nx.Graph, lab: dict, strategy: str, seed: int = 0) -> list[tuple[int, float, int]]:
    """Remove nodes one at a time; returns (removed, lcc share, lab pairs joined) after each removal.

    random       uniform order
    degree       highest current degree first (recomputed after every removal)
    betweenness  highest current betweenness first (recomputed)
    brokers      most cross-lab co-authors first (recomputed), ties broken by degree"""
    H = G.copy()
    n0 = H.number_of_nodes()
    labs = sorted(set(lab.values()))
    rng = np.random.default_rng(seed)
    order = list(rng.permutation(list(H))) if strategy == "random" else None
    out = [(0, *_state(H, lab, n0, labs))]
    for i in range(1, n0 + 1):
        if strategy == "random":
            v = order[i - 1]
        elif strategy == "degree":
            v = max(H.degree(), key=lambda kv: (kv[1], str(kv[0])))[0]
        elif strategy == "betweenness":
            b = nx.betweenness_centrality(H) if H.number_of_edges() else {v: 0 for v in H}
            v = max(b, key=lambda u: (b[u], H.degree(u), str(u)))
        elif strategy == "brokers":
            v = max(H, key=lambda u: (sum(lab[w] != lab[u] for w in H[u]), H.degree(u), str(u)))
        else:
            raise ValueError(strategy)
        H.remove_node(v)
        out.append((i, *_state(H, lab, n0, labs)))
    return out


def lab_edge_cuts(G: nx.Graph, lab: dict) -> list[dict]:
    """Minimum number of co-author links whose removal separates two labs (or one lab from the other three).
    Computed as a max flow between super-nodes attached to every member of each side."""
    labs = sorted(set(lab.values()))
    out = []
    sides = [((a,), (b,)) for a, b in combinations(labs, 2)] + [((a,), tuple(l for l in labs if l != a)) for a in labs]
    for A, B in sides:
        F = nx.Graph()
        F.add_edges_from(G.edges(), capacity=1)
        for v in G:
            if lab[v] in A:
                F.add_edge("__S", v, capacity=10 ** 9)
            elif lab[v] in B:
                F.add_edge("__T", v, capacity=10 ** 9)
        cut = nx.maximum_flow_value(F, "__S", "__T") if "__S" in F and "__T" in F else 0
        direct = sum(1 for u, v in G.edges() if {lab[u], lab[v]} & set(A) and {lab[u], lab[v]} & set(B) and lab[u] != lab[v])
        out.append({"side_a": "+".join(A), "side_b": "+".join(B), "min_edge_cut": int(cut), "direct_links": direct})
    return out


# --------------------------------------------------------------------------- spreading


def si_runs(W: np.ndarray, lab_idx: np.ndarray, beta: float, seeds: list[int], max_t: int = 400, seed: int = 42) -> list[dict]:
    """Discrete-time SI: a susceptible node with infected neighbours j is infected with probability
    1 - (1 - beta)^(sum_j w_ij) per step (each joint paper is a contact). One run per seed node. Records when half
    and 90% of the reachable nodes are infected and when every lab has an infected member."""
    rng = np.random.default_rng(seed)
    n = len(W)
    n_labs = len(np.unique(lab_idx))
    # nodes reachable from each seed (its component) bound the coverage
    comp = _components(W)
    out = []
    log1m = np.log1p(-min(beta, 1 - 1e-12))
    for s in seeds:
        I = np.zeros(n, bool)
        I[s] = True
        reach = (comp == comp[s]).sum()
        t50 = t90 = t_all = t_other = None
        home = lab_idx[s]
        for t in range(1, max_t + 1):
            pressure = W @ I
            p = 1 - np.exp(log1m * pressure)
            I = I | (rng.random(n) < p)
            k = I.sum()
            labs_hit = np.unique(lab_idx[I])
            if t_other is None and (labs_hit != home).any():
                t_other = t
            if t_all is None and len(labs_hit) == n_labs:
                t_all = t
            if t50 is None and k >= 0.5 * reach:
                t50 = t
            if t90 is None and k >= 0.9 * reach:
                t90 = t
            if k == reach:
                break
        out.append({"seed": int(s), "reachable": int(reach), "t50": t50, "t90": t90, "t_other_lab": t_other, "t_all_labs": t_all})
    return out


def _components(W: np.ndarray) -> np.ndarray:
    G = nx.from_numpy_array((W > 0).astype(int))
    comp = np.empty(len(W), int)
    for i, c in enumerate(nx.connected_components(G)):
        comp[list(c)] = i
    return comp


def sis_prevalence(A: np.ndarray, beta: float, mu: float, steps: int = 600, burn: int = 300, init: float = 0.1,
                   reps: int = 10, seed: int = 42) -> tuple[float, float]:
    """Mean stationary prevalence (and its spread over runs) of discrete-time SIS on an unweighted adjacency matrix:
    infection 1 - (1 - beta)^(infected neighbours), recovery mu per step. Absorbing state (0) counts as 0."""
    rng = np.random.default_rng(seed)
    n = len(A)
    log1m = np.log1p(-beta)
    vals = []
    for _ in range(reps):
        I = rng.random(n) < init
        acc = []
        for t in range(steps):
            p = 1 - np.exp(log1m * (A @ I))
            new = (~I) & (rng.random(n) < p)
            rec = I & (rng.random(n) < mu)
            I = (I | new) & ~rec
            if t >= burn:
                acc.append(I.mean())
            if not I.any():
                acc.extend([0.0] * max(0, steps - max(t + 1, burn)))
                break
        vals.append(np.mean(acc) if acc else 0.0)
    return float(np.mean(vals)), float(np.std(vals))


def sis_theory(A: np.ndarray) -> dict:
    k = A.sum(1)
    lam_max = float(np.max(np.linalg.eigvalsh(A)))
    return {"lambda_max": lam_max, "threshold_qmf": 1 / lam_max, "threshold_hmf": k.mean() / (k ** 2).mean()}


# --------------------------------------------------------------------------- link prediction


def auc(scores: np.ndarray, y: np.ndarray) -> float:
    """Area under the ROC curve by the rank-sum (Mann-Whitney) formula; ties count one half."""
    y = np.asarray(y, bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = stats.rankdata(scores)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(scores: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y, bool)
    if y.sum() == 0:
        return np.nan
    order = np.argsort(-scores, kind="stable")
    hits = y[order]
    prec = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float(prec[hits].mean())


def pair_features(G: nx.Graph, pairs: list[tuple], katz_beta: float = 0.05) -> dict[str, np.ndarray]:
    """Classic link-prediction scores for each candidate pair on graph G (Liben-Nowell & Kleinberg 2007)."""
    nodes = list(G)
    ix = {v: i for i, v in enumerate(nodes)}
    A = nx.to_numpy_array(G, nodelist=nodes, weight=None)
    deg = A.sum(1)
    CN = A @ A
    inv_log = np.where(deg > 1, 1 / np.log(np.maximum(deg, 2)), 0)
    AA = (A * inv_log) @ A
    RA = (A * np.where(deg > 0, 1 / np.maximum(deg, 1), 0)) @ A
    # Katz truncated at paths of length 4 (keeps it well defined whatever the spectral radius)
    K, P = np.zeros_like(A), np.eye(len(A))
    for l in range(1, 5):
        P = P @ A
        K += katz_beta ** l * P
    a = np.array([ix[u] for u, _ in pairs], int)
    b = np.array([ix[v] for _, v in pairs], int)
    cn = CN[a, b]
    union = deg[a] + deg[b] - cn
    return {"common_neighbours": cn, "jaccard": np.where(union > 0, cn / np.maximum(union, 1), 0),
            "adamic_adar": AA[a, b], "resource_allocation": RA[a, b], "preferential_attachment": deg[a] * deg[b],
            "katz": K[a, b]}


# --------------------------------------------------------------------------- logistic model with dyadic-robust errors


def logit_fit(X: np.ndarray, y: np.ndarray, ridge: float = 0.0, iters: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """Newton-Raphson logistic regression; returns coefficients and the inverse Hessian (naive covariance)."""
    b = np.zeros(X.shape[1])
    R = ridge * np.eye(X.shape[1])
    R[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        H = (X * (p * (1 - p))[:, None]).T @ X + R
        g = X.T @ (y - p) - R @ b
        step = np.linalg.solve(H + 1e-9 * np.eye(len(b)), g)
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    H = (X * (p * (1 - p))[:, None]).T @ X + R
    return b, np.linalg.pinv(H)


def dyadic_robust_cov(X: np.ndarray, y: np.ndarray, b: np.ndarray, bread: np.ndarray, node_a, node_b) -> np.ndarray:
    """Dyadic cluster-robust covariance (Fafchamps & Gubert 2007; Aronow, Samii & Assenova 2015): score correlation
    is allowed between any two observations that share a node. meat = sum_v S_v S_v' - sum_d S_d S_d', where S_v sums
    the scores of observations involving node v and S_d those of dyad d (same pair, other years), which the node sum
    counts twice."""
    p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    s = X * (y - p)[:, None]
    names, codes = np.unique(np.concatenate([np.asarray(node_a), np.asarray(node_b)]).astype(str), return_inverse=True)
    ca, cb = codes[:len(s)], codes[len(s):]
    S = np.zeros((len(names), X.shape[1]))
    np.add.at(S, ca, s)
    np.add.at(S, cb, s)
    _, dcode = np.unique(ca.astype(np.int64) * len(names) + cb, return_inverse=True)
    Dsum = np.zeros((dcode.max() + 1, X.shape[1]))
    np.add.at(Dsum, dcode, s)
    meat = S.T @ S - Dsum.T @ Dsum
    return bread @ meat @ bread
