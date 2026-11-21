"""S18: dynamical processes on the faculty co-authorship network - how would something spread, and where would a walker go?

Network: undirected faculty co-authorship graph, all faculty with papers as nodes (isolates included), edge weight =
number of joint papers (papers with at most `max_authors_for_pairs` authors, 2016-2026). Epidemic processes use the
unweighted graph (one transmission chance per edge per step); random walks use the weights. Processes that need
connectivity (SIS sweep, random walks) run on the largest connected component (LCC). Nulls: degree-preserving
rewiring (double edge swaps, 10 x E swaps, several draws; connected swaps for random walks, with the observed edge
weights shuffled over the new edges) and Erdos-Renyi G(n, m) with the same n and m.

  D1 SIS threshold         discrete-time SIS (infection prob. beta per infected neighbour per step, recovery prob. mu)
                           swept over lambda = beta/mu; quasi-stationary prevalence (reactivation from one random node
                           when the infection dies out), survival from a single random seed, susceptibility chi; the
                           numeric threshold (chi peak) vs heterogeneous (<k>/<k^2>) and quenched (1/Lambda_max) mean-field
  D2 super-spreaders       SIR from every non-isolated faculty member at one transmissibility above threshold; spreading
                           influence vs degree, strength, k-shell, betweenness, eigenvector (Spearman; cf. Kitsak et al.
                           2010); five seeding strategies compared by final size and time to half the final size
  D3 lab walls             SIR seeded in each lab: probability and time to reach each other lab, observed vs rewired
  D4 random walks          stationary distribution vs strength; exact mean first-passage times lab -> lab; lab retention
                           P(still in lab after t steps); spectral gap / relaxation time; random walk with restart
                           "related faculty" suggestions excluding existing co-authors
  D5 edge interventions    add k cross-lab edges (random, hub-to-hub, most topic-similar never-co-authored pairs) and
                           measure cross-lab SIR reach, cross-lab MFPT and global efficiency

Outputs: outputs/stats/research_epi_*.csv, research_rw_*.csv and research_dynamics.json. Randomness is seeded.
"""
from __future__ import annotations

import json
import logging
import time
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sparse
from scipy import stats

from . import StepFailed
from .s17_research import SEED, Data, json_safe, topic_vectors

log = logging.getLogger("dpcn.s18")

MU = 0.2                 # recovery probability per step (SIS and SIR)
N_LAMBDA = 25            # lambda values in the SIS sweep
SIS_REPS = 100           # replicas per lambda per network (split over the null draws)
SIS_BURN, SIS_MEAS = 500, 500
N_NULL = 5               # rewired / ER draws for the SIS sweep
N_RW_NULL = 20           # rewired draws for random-walk nulls
N_CROSS_NULL = 10        # rewired draws for the cross-lab SIR null
LAMBDA_FACTOR = 1.5      # parts 2-3 run at this multiple of the observed numeric SIS threshold
SIR_REPS_NODE = 100      # SIR replicas per seed node
SIR_STRATEGY_RUNS = 1000
CROSS_RUNS = 1000        # SIR runs per seed lab (observed); the null splits them over draws
RESTART = 0.15
INTERVENTION_K = (5, 10, 20, 40)
INTERVENTION_DRAWS = 10
INTERVENTION_RUNS = 250  # SIR runs per seed lab per draw
CHUNK = 10000            # simulation rows per batch
CENT_PHRASE = {"degree": "degree", "strength": "strength (joint papers)", "kshell": "k-shell (core number)",
               "betweenness": "betweenness", "eigenvector": "eigenvector centrality"}
STRAT_PHRASE = {"random node": "a random faculty member", "highest degree": "the most-connected faculty member",
                "highest k-shell": "a member of the innermost k-core", "highest betweenness": "the top-betweenness broker",
                "one seed per lab": "one random faculty member in each lab (4 seeds)"}


def short(lab: str) -> str:
    return lab.replace("CSIR-", "")


# --------------------------------------------------------------------------- network and nulls

def build_graph(D: Data) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(D.faculty)
    w = D.coauth.groupby(["a", "b"])["work_id"].nunique()
    for (a, b), c in w.items():
        G.add_edge(a, b, weight=int(c))
    return G


def lcc(G: nx.Graph) -> nx.Graph:
    return G.subgraph(max(nx.connected_components(G), key=len)).copy()


def rewire(G: nx.Graph, seed: int, connected: bool = False) -> nx.Graph:
    """Degree-preserving rewiring (10 x E double edge swaps); the observed weights are shuffled over the new edges."""
    H = G.copy()
    m = H.number_of_edges()
    if connected:
        nx.connected_double_edge_swap(H, nswap=10 * m, seed=seed)
    else:
        nx.double_edge_swap(H, nswap=10 * m, max_tries=100 * m, seed=seed)
    w = np.array([d.get("weight", 1) for _, _, d in G.edges(data=True)])
    w = np.random.default_rng(seed).permutation(w)
    nx.set_edge_attributes(H, {e: int(x) for e, x in zip(H.edges(), w)}, "weight")
    return H


def er(G: nx.Graph, seed: int) -> nx.Graph:
    H = nx.gnm_random_graph(G.number_of_nodes(), G.number_of_edges(), seed=seed)
    return nx.relabel_nodes(H, dict(enumerate(G.nodes())))


def adj(G: nx.Graph, nodes, weight=None) -> np.ndarray:
    return nx.to_numpy_array(G, nodelist=list(nodes), weight=weight, dtype=np.float32 if weight is None else float)


def sim_adj(G: nx.Graph, nodes) -> sparse.csr_matrix:
    """Unweighted sparse adjacency for the simulators (sparse products avoid BLAS thread contention)."""
    return sparse.csr_matrix(adj(G, nodes))


def pressure(A: sparse.csr_matrix, X: np.ndarray) -> np.ndarray:
    """Number of infected neighbours of every node, for every replica row of X."""
    return (A @ X.T.astype(np.float32)).T


def mf_thresholds(G: nx.Graph) -> tuple[float, float]:
    k = np.array([d for _, d in G.degree()], float)
    lam_max = np.linalg.eigvalsh(adj(G, G.nodes()).astype(float))[-1]
    return k.mean() / (k ** 2).mean(), 1 / lam_max


# --------------------------------------------------------------------------- vectorised simulators
# Each row of a state matrix is one independent replica; one uniform number per node per step decides both
# recovery (infected nodes) and infection (susceptible nodes), since the two sets are disjoint.

def sis_rows(A: sparse.csr_matrix, beta: np.ndarray, rng, burn: int, meas: int) -> dict:
    """SIS from one random infected node per row; when a row dies out it is reactivated at one random node
    (quasi-stationary estimate). Returns per-row time means of rho and rho^2 and whether the row ever died out."""
    rows, N = len(beta), A.shape[0]
    logq = np.log1p(-beta).astype(np.float32)[:, None]
    X = np.zeros((rows, N), bool)
    X[np.arange(rows), rng.integers(0, N, rows)] = True
    alive = np.ones(rows, bool)
    s1, s2 = np.zeros(rows), np.zeros(rows)
    for t in range(burn + meas):
        k = pressure(A, X)
        u = rng.random((rows, N), dtype=np.float32)
        X = np.where(X, u >= MU, u < -np.expm1(k * logq))
        n = X.sum(1)
        dead = np.flatnonzero(n == 0)
        if len(dead):
            alive[dead] = False
            X[dead, rng.integers(0, N, len(dead))] = True
            n[dead] = 1
        if t >= burn:
            rho = n / N
            s1 += rho
            s2 += rho ** 2
    return {"m1": s1 / meas, "m2": s2 / meas, "alive": alive}


def sis_survival(A: sparse.csr_matrix, seeds: np.ndarray, beta: float, rng, steps: int = 300) -> np.ndarray:
    """Absorbing SIS from one seed node per row; True where the infection is still alive after `steps`."""
    out = np.zeros(len(seeds), bool)
    logq = np.float32(np.log1p(-beta))
    for c in range(0, len(seeds), CHUNK):
        s = seeds[c:c + CHUNK]
        X = np.zeros((len(s), A.shape[0]), bool)
        X[np.arange(len(s)), s] = True
        act = np.arange(len(s))
        for _ in range(steps):
            k = pressure(A, X)
            u = rng.random(X.shape, dtype=np.float32)
            X = np.where(X, u >= MU, u < -np.expm1(k * logq))
            keep = X.any(1)
            if not keep.all():
                X, act = X[keep], act[keep]
            if not len(act):
                break
        out[c + act] = True
    return out


def sir_rows(A: sparse.csr_matrix, seeds: np.ndarray, beta: float, rng, groups: np.ndarray | None = None,
             max_steps: int = 2000) -> dict:
    """Discrete-time SIR; `seeds` is a (rows, N) boolean matrix of initially infected nodes. Returns final size,
    time to reach half the final size and (if `groups` - a node -> group one-hot matrix - is given) the first step
    at which each group has a newly infected node (inf if never)."""
    out = {"size": [], "t_half": [], "t_first": [], "ever": []}
    logq = np.float32(np.log1p(-beta))
    for c in range(0, len(seeds), CHUNK):
        I = seeds[c:c + CHUNK].copy()
        ever = I.copy()
        counts = [ever.sum(1)]
        tf = np.full((len(I), 0 if groups is None else groups.shape[1]), np.inf)
        t = 0
        while I.any() and t < max_steps:
            t += 1
            k = pressure(A, I)
            u = rng.random(I.shape, dtype=np.float32)
            new = ~ever & (u < -np.expm1(k * logq))
            I = (I & (u >= MU)) | new
            ever |= new
            counts.append(ever.sum(1))
            if groups is not None:
                hit = (new.astype(np.float32) @ groups) > 0
                tf[hit & np.isinf(tf)] = t
        C = np.array(counts)
        size = C[-1]
        out["size"].append(size)
        out["t_half"].append(np.argmax(C >= 0.5 * size, axis=0))
        out["t_first"].append(tf)
        out["ever"].append(ever)
    return {k: np.concatenate(v) for k, v in out.items()}


# --------------------------------------------------------------------------- D1 SIS threshold

def sis_threshold(L: nx.Graph) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED)
    hmf, qmf = mf_thresholds(L)
    lams = np.logspace(np.log10(0.01), np.log10(0.4), N_LAMBDA)
    nets = {"observed": [L], "rewired": [rewire(L, SEED + i) for i in range(N_NULL)],
            "ER": [er(L, SEED + i) for i in range(N_NULL)]}
    curve, thr, theo = [], [], {}
    for name, gs in nets.items():
        reps = SIS_REPS // len(gs)
        res = {"m1": [], "m2": [], "alive": []}
        for H in gs:
            A = sim_adj(H, H.nodes())
            r = sis_rows(A, np.repeat(lams * MU, reps), rng, SIS_BURN, SIS_MEAS)
            for k in res:
                res[k].append(r[k].reshape(len(lams), reps))
        res = {k: np.concatenate(v, axis=1) for k, v in res.items()}
        N = L.number_of_nodes()
        for i, lam in enumerate(lams):
            m1, m2 = res["m1"][i], res["m2"][i]
            curve.append({"network": name, "lam": lam, "beta": lam * MU, "mu": MU, "prevalence_mean": m1.mean(),
                          "prevalence_lo": np.percentile(m1, 2.5), "prevalence_hi": np.percentile(m1, 97.5),
                          "survival": res["alive"][i].mean(), "chi": N * (m2.mean() - m1.mean() ** 2) / m1.mean()})
        c = pd.DataFrame([r for r in curve if r["network"] == name])
        thr.append({"network": name, "method": "numeric (chi peak)", "lambda_c": c.loc[c["chi"].idxmax(), "lam"]})
        th = np.array([mf_thresholds(H) for H in gs])
        thr.append({"network": name, "method": "heterogeneous mean-field <k>/<k2>", "lambda_c": th[:, 0].mean()})
        thr.append({"network": name, "method": "quenched mean-field 1/Lambda_max", "lambda_c": th[:, 1].mean()})
        log.info("SIS sweep done: %s", name)
    return pd.DataFrame(curve), pd.DataFrame(thr), {"hmf": hmf, "qmf": qmf}


# --------------------------------------------------------------------------- D2 super-spreaders and strategies

def spreaders(D: Data, G: nx.Graph, names: dict, beta: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED + 100)
    nodes = list(G.nodes())
    idx = {f: i for i, f in enumerate(nodes)}
    A = sim_adj(G, nodes)
    act = [f for f in nodes if G.degree(f) > 0]
    seed_idx = np.repeat([idx[f] for f in act], SIR_REPS_NODE)
    S = np.zeros((len(seed_idx), len(nodes)), bool)
    S[np.arange(len(seed_idx)), seed_idx] = True
    r = sir_rows(A, S, beta, rng)
    size = r["size"].reshape(len(act), SIR_REPS_NODE)
    surv = sis_survival(A, seed_idx, beta, rng).reshape(len(act), SIR_REPS_NODE).mean(1)
    H = G.subgraph(act)
    core = nx.core_number(H)
    btw = nx.betweenness_centrality(H)
    # principal eigenvector of the (disconnected) adjacency matrix: nodes outside the LCC get ~0
    vals, vecs = np.linalg.eigh(adj(H, act).astype(float))
    eig = dict(zip(act, np.abs(vecs[:, -1])))
    t = pd.DataFrame({"faculty_id": act, "name": [names.get(f) for f in act], "lab": [D.fac_lab[f] for f in act],
                      "degree": [G.degree(f) for f in act], "strength": [G.degree(f, weight="weight") for f in act],
                      "kshell": [core[f] for f in act], "betweenness": [btw[f] for f in act],
                      "eigenvector": [abs(eig[f]) for f in act], "sir_size_mean": size.mean(1),
                      "sir_size_sd": size.std(1, ddof=1), "sis_survival": surv})
    t["rank_influence"] = t["sir_size_mean"].rank(ascending=False, method="min").astype(int)
    t = t.sort_values("rank_influence")
    corr = {}
    for c in ("degree", "strength", "kshell", "betweenness", "eigenvector"):
        rho, p = stats.spearmanr(t[c], t["sir_size_mean"])
        rho_s, p_s = stats.spearmanr(t[c], t["sis_survival"])
        corr[c] = {"rho_sir": rho, "p_sir": p, "rho_sis_survival": rho_s, "p_sis_survival": p_s}

    # seeding strategies (single seed except "one per lab", which uses one random seed in each lab)
    deg = dict(G.degree())
    top = {"highest degree": [f for f in act if deg[f] == max(deg[g] for g in act)],
           "highest k-shell": [f for f in act if core[f] == max(core.values())],
           "highest betweenness": [max(act, key=btw.get)]}
    by_lab = {l: [idx[f] for f in act if D.fac_lab[f] == l] for l in D.labs}
    n = SIR_STRATEGY_RUNS
    rows = []
    for strat in ("random node", "highest degree", "highest k-shell", "highest betweenness", "one seed per lab"):
        S = np.zeros((n, len(nodes)), bool)
        if strat == "random node":
            S[np.arange(n), rng.choice([idx[f] for f in act], n)] = True
        elif strat == "one seed per lab":
            for l, ids in by_lab.items():
                S[np.arange(n), rng.choice(ids, n)] = True
        else:
            S[np.arange(n), rng.choice([idx[f] for f in top[strat]], n)] = True
        r = sir_rows(A, S, beta, rng)
        major = r["size"] >= 0.1 * len(act)
        rows.append({"strategy": strat, "seeds": int(S[0].sum()), "runs": n, "size_mean": r["size"].mean(),
                     "size_lo": np.percentile(r["size"], 2.5), "size_hi": np.percentile(r["size"], 97.5),
                     "size_median": np.median(r["size"]),
                     # time to half the final size, among major outbreaks (>= 10% of non-isolated faculty)
                     "t_half_median": np.median(r["t_half"][major]) if major.any() else np.nan,
                     "t_half_median_all": np.median(r["t_half"]), "p_major_outbreak": major.mean()})
    return t, pd.DataFrame(rows), corr


# --------------------------------------------------------------------------- D3 cross-lab SIR

def lab_onehot(nodes, lab_of, labs) -> np.ndarray:
    return np.array([[lab_of[f] == l for l in labs] for f in nodes], np.float32)


def crosslab_runs(G: nx.Graph, lab_of: dict, labs: list, beta: float, runs: int, rng) -> dict:
    """SIR seeded at a random (non-isolated) node of each lab; reach and first-infection times per target lab.
    Infection of the seed itself does not count as reaching its own lab."""
    nodes = list(G.nodes())
    A = sim_adj(G, nodes)
    Gm = lab_onehot(nodes, lab_of, labs)
    out = {}
    for si, l in enumerate(labs):
        ids = [i for i, f in enumerate(nodes) if lab_of[f] == l and G.degree(f) > 0]
        S = np.zeros((runs, len(nodes)), bool)
        S[np.arange(runs), rng.choice(ids, runs)] = True
        out[l] = sir_rows(A, S, beta, rng, groups=Gm)["t_first"]
    return out


def crosslab(D: Data, G: nx.Graph, beta: float) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 200)
    res = {"observed": [crosslab_runs(G, D.fac_lab, D.labs, beta, CROSS_RUNS, rng)],
           "rewired": [crosslab_runs(rewire(G, SEED + 300 + i), D.fac_lab, D.labs, beta, CROSS_RUNS // N_CROSS_NULL, rng)
                       for i in range(N_CROSS_NULL)]}
    rows = []
    for net, draws in res.items():
        for sl in D.labs:
            tf = np.concatenate([d[sl] for d in draws])
            for ti, tl in enumerate(D.labs):
                x = tf[:, ti]
                hit = x[np.isfinite(x)]
                rows.append({"network": net, "seed_lab": sl, "target_lab": tl, "p_reach": np.isfinite(x).mean(),
                             "t_first_median": np.median(hit) if len(hit) else np.nan,
                             "t_first_lo": np.percentile(hit, 2.5) if len(hit) else np.nan,
                             "t_first_hi": np.percentile(hit, 97.5) if len(hit) else np.nan, "runs": len(x)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- D4 random walks

def transition(W: np.ndarray) -> np.ndarray:
    s = W.sum(1)
    return np.divide(W, s[:, None], out=np.zeros_like(W), where=s[:, None] > 0)


def mfpt_matrix(W: np.ndarray, lab: np.ndarray, labs: list) -> np.ndarray:
    """Exact mean first-passage time from a stationary-weighted node of lab A to any node of lab B (A != B)."""
    P = transition(W)
    pi = W.sum(1) / W.sum()
    M = np.full((len(labs), len(labs)), np.nan)
    for bi, b in enumerate(labs):
        out = lab != b
        h = np.zeros(len(lab))
        h[out] = np.linalg.solve(np.eye(out.sum()) - P[np.ix_(out, out)], np.ones(out.sum()))
        for ai, a in enumerate(labs):
            if a != b:
                ia = lab == a
                M[ai, bi] = (pi[ia] * h[ia]).sum() / pi[ia].sum()
    return M


def retention(W: np.ndarray, lab: np.ndarray, labs: list, steps: int = 20) -> np.ndarray:
    P = transition(W)
    pi = W.sum(1) / W.sum()
    R = np.zeros((len(labs), steps))
    for ai, a in enumerate(labs):
        ia = lab == a
        v = np.where(ia, pi, 0)
        v /= v.sum()
        for t in range(steps):
            v = v @ P
            R[ai, t] = v[ia].sum()
    return R


def spectral_gap(W: np.ndarray) -> tuple[float, float]:
    s = W.sum(1)
    Sm = W / np.sqrt(np.outer(s, s))
    ev = np.sort(np.abs(np.linalg.eigvalsh(Sm)))[::-1]
    lam2 = ev[1]
    return 1 - lam2, 1 / (1 - lam2)


def random_walks(D: Data, G: nx.Graph, L: nx.Graph, names: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    nodes = list(L.nodes())
    lab = np.array([D.fac_lab[f] for f in nodes])
    W = adj(L, nodes, weight="weight")
    s = W.sum(1)
    P = transition(W)
    ev, vec = np.linalg.eig(P.T)
    pi_num = np.abs(np.real(vec[:, np.argmin(np.abs(ev - 1))]))
    pi_num /= pi_num.sum()
    pi_r = stats.pearsonr(pi_num, s)[0]
    M_obs, R_obs = mfpt_matrix(W, lab, D.labs), retention(W, lab, D.labs)
    gap_obs, relax_obs = spectral_gap(W)
    Ms, Rs, gaps = [], [], []
    for i in range(N_RW_NULL):
        H = rewire(L, SEED + 400 + i, connected=True)
        Wh = adj(H, nodes, weight="weight")
        Ms.append(mfpt_matrix(Wh, lab, D.labs))
        Rs.append(retention(Wh, lab, D.labs))
        gaps.append(spectral_gap(Wh))
    Ms, Rs, gaps = np.array(Ms), np.array(Rs), np.array(gaps)
    mf = []
    for ai, a in enumerate(D.labs):
        for bi, b in enumerate(D.labs):
            if a != b:
                mf.append({"from_lab": a, "to_lab": b, "mfpt_obs": M_obs[ai, bi], "mfpt_null_mean": Ms[:, ai, bi].mean(),
                           "mfpt_null_sd": Ms[:, ai, bi].std(ddof=1), "ratio": M_obs[ai, bi] / Ms[:, ai, bi].mean()})
    ret = [{"lab": a, "step": t + 1, "p_stay_obs": R_obs[ai, t], "p_stay_null": Rs[:, ai, t].mean()}
           for ai, a in enumerate(D.labs) for t in range(R_obs.shape[1])]

    # random walk with restart on the full graph (walks from small components stay in them)
    fn = list(G.nodes())
    Wf = adj(G, fn, weight="weight")
    Pf = transition(Wf)
    Rr = RESTART * np.linalg.inv(np.eye(len(fn)) - (1 - RESTART) * Pf)
    rel = []
    for i, f in enumerate(fn):
        sc = Rr[i].copy()
        sc[i] = 0
        sc[Wf[i] > 0] = 0
        order = [j for j in np.argsort(-sc) if sc[j] > 1e-12][:5]
        for r, j in enumerate(order, 1):
            rel.append({"faculty_id": f, "related_id": fn[j], "related_name": names.get(fn[j]),
                        "related_lab": D.fac_lab[fn[j]], "score": sc[j], "rank": r})
    summ = {"stationary_vs_strength_pearson": pi_r, "spectral_gap_obs": gap_obs, "relaxation_time_obs": relax_obs,
            "spectral_gap_null_mean": gaps[:, 0].mean(), "spectral_gap_null_sd": gaps[:, 0].std(ddof=1),
            "relaxation_time_null_mean": gaps[:, 1].mean()}
    return pd.DataFrame(mf), pd.DataFrame(ret), pd.DataFrame(rel), summ


# --------------------------------------------------------------------------- D5 edge interventions

def candidate_edges(D: Data, G: nx.Graph, rng) -> dict:
    """Ordered lists of cross-lab non-edges for the deterministic strategies (hub-to-hub, topic-similar)."""
    nodes = list(G.nodes())
    deg = dict(G.degree())
    ever = set()
    for fs in D.fac.values():
        ever.update(combinations(sorted(fs), 2))
    cross = [(a, b) for a, b in combinations(sorted(nodes), 2) if D.fac_lab[a] != D.fac_lab[b]]
    hub = [e for e in cross if not G.has_edge(*e)]
    tie = rng.random(len(hub))
    hub = [hub[i] for i in np.lexsort((tie, [-deg[a] * deg[b] for a, b in hub]))]
    tv = topic_vectors(D)
    sim = [e for e in cross if e not in ever and not G.has_edge(*e) and e[0] in tv and e[1] in tv]
    cos = np.array([tv[a] @ tv[b] for a, b in sim])
    tie = rng.random(len(sim))
    sim_sorted = [sim[i] for i in np.lexsort((tie, -cos))]
    return {"pairs": [e for e in cross if not G.has_edge(*e)], "hub": hub, "topic": sim_sorted,
            "topic_cos": np.sort(cos)[::-1]}


def intervention_metrics(D: Data, H: nx.Graph, beta: float, rng) -> tuple[float, float, float]:
    r = crosslab_runs(H, D.fac_lab, D.labs, beta, INTERVENTION_RUNS, rng)
    reach = np.mean([np.isfinite(r[sl][:, ti]).mean() for sl in D.labs for ti, tl in enumerate(D.labs) if tl != sl])
    Lh = lcc(H)
    nodes = list(Lh.nodes())
    M = mfpt_matrix(adj(Lh, nodes, weight="weight"), np.array([D.fac_lab[f] for f in nodes]), D.labs)
    return reach, np.nanmean(M), nx.global_efficiency(H)


def interventions(D: Data, G: nx.Graph, beta: float) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED + 500)
    cand = candidate_edges(D, G, rng)
    rows = []

    def record(strategy, k, res):
        res = np.array(res)
        rows.append({"strategy": strategy, "k": k, "reach_mean": res[:, 0].mean(),
                     "reach_lo": np.percentile(res[:, 0], 2.5), "reach_hi": np.percentile(res[:, 0], 97.5),
                     "mfpt_mean": res[:, 1].mean(), "efficiency": res[:, 2].mean(), "draws": len(res)})
    record("none (observed)", 0, [intervention_metrics(D, G, beta, rng) for _ in range(INTERVENTION_DRAWS)])
    for k in INTERVENTION_K:
        res = []
        for _ in range(INTERVENTION_DRAWS):
            H = G.copy()
            H.add_edges_from([cand["pairs"][i] for i in rng.choice(len(cand["pairs"]), k, replace=False)], weight=1)
            res.append(intervention_metrics(D, H, beta, rng))
        record("random cross-lab", k, res)
        for name, key in (("hub-to-hub", "hub"), ("topic-similar", "topic")):
            H = G.copy()
            H.add_edges_from(cand[key][:k], weight=1)
            record(name, k, [intervention_metrics(D, H, beta, rng) for _ in range(INTERVENTION_DRAWS)])
        log.info("interventions done: k=%d", k)
    return pd.DataFrame(rows), {"topic_cos_top40_min": cand["topic_cos"][:max(INTERVENTION_K)].min()}


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    t0 = time.time()
    D = Data(cfg)
    st = cfg.paths.stats
    names = pd.read_parquet(cfg.paths.interim / "roster.parquet").set_index("faculty_id")["name"].to_dict()
    G = build_graph(D)
    L = lcc(G)
    if L.number_of_nodes() < 10:
        raise StepFailed("faculty co-authorship network has no usable connected component")
    kL = np.array([d for _, d in L.degree()], float)
    k = np.array([d for _, d in G.degree()], float)
    log.info("faculty network: n=%d m=%d LCC=%d", G.number_of_nodes(), G.number_of_edges(), L.number_of_nodes())

    def save(df, f):
        df.to_csv(st / f, index=False, lineterminator="\n")

    curve, thr, mf = sis_threshold(L)
    save(curve, "research_epi_sis_curve.csv")
    save(thr, "research_epi_threshold.csv")
    tval = thr.set_index(["network", "method"])["lambda_c"]
    lam_c = tval[("observed", "numeric (chi peak)")]
    lam = LAMBDA_FACTOR * lam_c
    beta = lam * MU
    T = beta / (1 - (1 - beta) * (1 - MU))       # per-edge SIR transmissibility
    T_c = k.mean() / ((k ** 2).mean() - k.mean())  # configuration-model SIR threshold on the full graph
    log.info("parts 2-3: lambda=%.4f beta=%.4f T=%.3f (T_c=%.3f)  [%.0fs]", lam, beta, T, T_c, time.time() - t0)

    sp, strat, corr = spreaders(D, G, names, beta)
    save(sp, "research_epi_spreaders.csv")
    save(strat, "research_epi_strategies.csv")
    log.info("spreaders done [%.0fs]", time.time() - t0)
    cl = crosslab(D, G, beta)
    save(cl, "research_epi_crosslab.csv")
    log.info("cross-lab done [%.0fs]", time.time() - t0)
    mfpt, ret, rel, rw = random_walks(D, G, L, names)
    save(mfpt, "research_rw_mfpt.csv")
    save(ret, "research_rw_retention.csv")
    save(rel, "research_rw_related.csv")
    log.info("random walks done [%.0fs]", time.time() - t0)
    iv, ivx = interventions(D, G, beta)
    save(iv, "research_epi_intervention.csv")
    log.info("interventions done [%.0fs]", time.time() - t0)

    # ------------------------------------------------------------------ summary
    x = cl[cl["seed_lab"] != cl["target_lab"]]
    reach = x.groupby("network")["p_reach"].mean().to_dict()
    piv = x.pivot_table(index=["seed_lab", "target_lab"], columns="network", values="p_reach")
    piv["diff"] = piv["observed"] - piv["rewired"]
    wall = piv["diff"].idxmin()
    tmed = x.groupby("network")["t_first_median"].median().to_dict()
    best_strat = strat.loc[strat["size_mean"].idxmax()]
    rnd = strat.set_index("strategy").loc["random node"]
    best_c = max(corr, key=lambda c: corr[c]["rho_sir"])
    r5 = ret[ret["step"] == 5].set_index("lab")
    retention5 = {r.Index: {"observed": r.p_stay_obs, "null": r.p_stay_null} for r in r5.itertuples()}
    base = iv[iv["k"] == 0].iloc[0]
    best_iv = {}
    for kk, g in iv[iv["k"] > 0].groupby("k"):
        b = g.loc[g["reach_mean"].idxmax()]
        bm = g.loc[g["mfpt_mean"].idxmin()]
        best_iv[int(kk)] = {"by_reach": b["strategy"], "reach_mean": b["reach_mean"], "reach_gain": b["reach_mean"] - base["reach_mean"],
                            "by_mfpt": bm["strategy"], "mfpt_mean": bm["mfpt_mean"],
                            "by_efficiency": g.loc[g["efficiency"].idxmax(), "strategy"]}
    kmax = max(INTERVENTION_K)
    big = iv[iv["k"] == kmax].set_index("strategy")
    top_sp = sp.head(5)
    num = {n: tval[(n, "numeric (chi peak)")] for n in ("observed", "rewired", "ER")}

    def pct(v):
        return f"{100 * v:.0f}%"
    sl, tl = wall
    findings = [
        f"An SIS infection (recovery {MU} per step) becomes endemic on the faculty network once beta/mu exceeds about "
        f"{num['observed']:.3f} (susceptibility peak; mean-field predictions: quenched 1/Lambda_max = {mf['qmf']:.3f}, "
        f"heterogeneous <k>/<k2> = {mf['hmf']:.3f}), "
        + ("lower than" if num["observed"] < min(num["rewired"], num["ER"]) else "compared with")
        + f" {num['rewired']:.3f} on degree-preserving rewired networks and {num['ER']:.3f} on Erdos-Renyi networks.",
        f"At beta/mu = {lam:.3f} ({LAMBDA_FACTOR}x the threshold), a single infected faculty member's outbreak size "
        f"correlates best with {CENT_PHRASE[best_c]} (Spearman rho = {corr[best_c]['rho_sir']:.2f}); k-shell gives "
        f"{corr['kshell']['rho_sir']:.2f} and degree {corr['degree']['rho_sir']:.2f}.",
        f"Seeding {STRAT_PHRASE[best_strat['strategy']]} reaches {best_strat['size_mean']:.0f} faculty on average "
        f"versus {rnd['size_mean']:.0f} from a random faculty member, with a major outbreak (>= 10% of faculty) in "
        f"{pct(best_strat['p_major_outbreak'])} vs {pct(rnd['p_major_outbreak'])} of runs.",
        f"An outbreak started in one lab reaches a given other lab in {pct(reach['observed'])} of runs on the observed "
        f"network vs {pct(reach['rewired'])} on degree-preserving rewired networks; the largest gap is "
        f"{short(sl)} -> {short(tl)}: {pct(piv.loc[wall, 'observed'])} vs {pct(piv.loc[wall, 'rewired'])}.",
        f"A random walker on the co-authorship network takes on average {mfpt['mfpt_obs'].mean():.0f} steps to first reach "
        f"another lab vs {mfpt['mfpt_null_mean'].mean():.0f} on rewired networks (mean ratio "
        f"{mfpt['ratio'].mean():.1f}x, range {mfpt['ratio'].min():.1f}-{mfpt['ratio'].max():.1f}x).",
        "After 5 steps a walker started in a lab is still inside it with probability "
        + ", ".join(f"{short(l)} {v['observed']:.2f}" for l, v in retention5.items())
        + " vs " + ", ".join(f"{v['null']:.2f}" for v in retention5.values()) + " on rewired networks.",
        f"The walk's spectral gap is {rw['spectral_gap_obs']:.3f} (relaxation time {rw['relaxation_time_obs']:.0f} steps) "
        f"vs {rw['spectral_gap_null_mean']:.3f} ({rw['relaxation_time_null_mean']:.0f} steps) after rewiring"
        + (": walks mix more slowly on the real network, as expected if labs act as communities."
           if rw["relaxation_time_obs"] > rw["relaxation_time_null_mean"] else "."),
        f"Adding {kmax} cross-lab collaborations raises cross-lab outbreak reach from {pct(base['reach_mean'])} to "
        + ", ".join(f"{pct(big.loc[s, 'reach_mean'])} ({s})" for s in ("random cross-lab", "hub-to-hub", "topic-similar"))
        + f", and lowers the mean cross-lab first-passage time from {base['mfpt_mean']:.0f} to "
        + ", ".join(f"{big.loc[s, 'mfpt_mean']:.0f}" for s in ("random cross-lab", "hub-to-hub", "topic-similar")) + " steps.",
    ]
    summary = {
        "n": G.number_of_nodes(), "m": G.number_of_edges(), "isolates": int((k == 0).sum()),
        "lcc_n": L.number_of_nodes(), "lcc_m": L.number_of_edges(),
        "k_mean": k.mean(), "k2_mean": (k ** 2).mean(), "lcc_k_mean": kL.mean(), "lcc_k2_mean": (kL ** 2).mean(),
        "thresholds": {f"{n}|{m}": v for (n, m), v in tval.items()},
        "threshold_numeric": num, "threshold_hmf_observed": mf["hmf"], "threshold_qmf_observed": mf["qmf"],
        "sis_mu": MU, "chosen_lambda": lam, "chosen_beta": beta, "chosen_mu": MU, "sir_transmissibility": T,
        "sir_transmissibility_threshold": T_c,
        "influence_spearman": corr, "best_centrality": best_c,
        "top_spreaders": top_sp[["faculty_id", "name", "lab", "degree", "kshell", "sir_size_mean"]].to_dict("records"),
        "strategies": strat.to_dict("records"), "best_strategy": best_strat["strategy"],
        "crosslab_reach": reach, "crosslab_t_first_median": tmed,
        "crosslab_largest_gap": {"seed_lab": sl, "target_lab": tl, "observed": piv.loc[wall, "observed"],
                                 "rewired": piv.loc[wall, "rewired"]},
        "mfpt_ratio": {"mean": mfpt["ratio"].mean(), "min": mfpt["ratio"].min(), "max": mfpt["ratio"].max(),
                       "mfpt_obs_mean": mfpt["mfpt_obs"].mean(), "mfpt_null_mean": mfpt["mfpt_null_mean"].mean()},
        "retention_t5": retention5, "random_walk": rw,
        "intervention_baseline": {"reach": base["reach_mean"], "mfpt": base["mfpt_mean"], "efficiency": base["efficiency"]},
        "best_intervention": best_iv, **ivx,
        "findings": findings,
        "methods": {
            "network": "faculty co-authorship graph, weight = joint papers with <= "
                       f"{D.max_authors} authors; SIS sweep and random walks on the largest connected component",
            "nulls": "degree-preserving double-edge-swap rewiring (10 x E swaps; connected swaps with shuffled weights "
                     "for random walks) and Erdos-Renyi G(n, m)",
            "sis": f"discrete-time SIS, mu = {MU}, {N_LAMBDA} lambda values, {SIS_REPS} replicas per lambda from one "
                   f"random seed, {SIS_BURN} burn-in + {SIS_MEAS} measured steps, reactivation at one random node "
                   "when extinct (quasi-stationary); survival = never went extinct",
            "threshold": "numeric = lambda at the peak of chi = N(<rho^2>-<rho>^2)/<rho>; HMF = <k>/<k^2>; "
                         "QMF = 1/largest adjacency eigenvalue",
            "sir": f"discrete-time SIR at beta = {beta:.4f}, mu = {MU} (beta/mu = {LAMBDA_FACTOR} x observed numeric SIS "
                   f"threshold); {SIR_REPS_NODE} runs per seed node, {SIR_STRATEGY_RUNS} per strategy",
            "crosslab": f"SIR from a random node of each lab, {CROSS_RUNS} runs per lab observed and over "
                        f"{N_CROSS_NULL} rewired networks; reach = any new infection in the target lab",
            "random_walk": "weighted walk P = S^-1 W on the LCC; MFPT solved exactly; retention from the stationary "
                           f"distribution restricted to the lab; {N_RW_NULL} connected rewired nulls; "
                           f"RWR restart {RESTART} on the full graph",
            "interventions": f"add k cross-lab edges (weight 1): random pairs ({INTERVENTION_DRAWS} draws), largest "
                             "degree product, or highest subfield cosine among never-co-authored pairs; "
                             f"{INTERVENTION_RUNS} SIR runs per seed lab per draw",
        },
        "runtime_seconds": time.time() - t0,
    }
    (st / "research_dynamics.json").write_text(json.dumps(json_safe(summary), indent=2, default=float, allow_nan=False),
                                               encoding="utf-8")
    print(f"\nFaculty network: n={G.number_of_nodes()} m={G.number_of_edges()} LCC={L.number_of_nodes()} "
          f"<k>={k.mean():.2f} <k2>={(k ** 2).mean():.1f}")
    print(thr.to_string(index=False))
    print(strat.round(2).to_string(index=False))
    print(pd.DataFrame(corr).T.round(3).to_string())
    print(iv.round(3).to_string(index=False))
    for f in findings:
        print("-", f)
    print(f"runtime {time.time() - t0:.0f}s")
