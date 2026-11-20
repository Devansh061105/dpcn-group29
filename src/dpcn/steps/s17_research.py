"""S17: research analyses - does what the dashboard shows survive a proper baseline?

Each analysis compares an observed number with what chance (a randomised network) or a controlled model predicts:

  A1 citation audience     who cites our papers inside the corpus: the same authors (self), faculty who had already
                           written with them, the same lab, another of our labs
  A2 lab citation exchange observed lab-to-lab citations vs a permutation null that keeps every paper's citations
                           given and received, the cited year and both papers' fields (Monte Carlo, BH-corrected)
  A3 collaboration homophily  cross-lab co-authorship vs lab-label permutation and degree-preserving rewiring; a
                           logistic model of who writes with whom (same lab, same department, topic similarity)
  A4 citation by co-authorship distance  citations between faculty pairs by their distance in the co-authorship
                           network the year before, relative to a volume-only null (Singh et al. 2020 for Indian
                           physics, here for Indian biology labs)
  A5 led vs middle-author  papers our labs lead (first, last or corresponding author) vs papers where they are a
                           middle author, with citations normalised by field and year
  A6 tie persistence and triadic closure  do new collaborations last, and do they close triangles
  A7 lab impact with controls  log citations ~ lab + year + field + team size + review (OLS, HC1 errors)
  A8 the COVID-19 shock     share and citations of SARS-CoV-2 papers by lab and year

Outputs: outputs/stats/research_*.csv and research_summary.json. Randomness is seeded; inputs are the s05/s09 tables.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

from . import StepFailed

log = logging.getLogger("dpcn.s17")
SEED = 42
COVID = re.compile(r"sars-cov-2|covid|coronavirus|pandemic", re.I)


# --------------------------------------------------------------------------- small statistics helpers


def json_safe(o):
    """Replace NaN and infinity (invalid JSON) by None, recursively; numpy scalars become Python numbers."""
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, dict):
        return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    return o


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1)
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def ols_hc1(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS coefficients and heteroskedasticity-robust (HC1) standard errors."""
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    b = xtx_inv @ X.T @ y
    e = y - X @ b
    meat = (X * e[:, None] ** 2).T @ X
    v = xtx_inv @ meat @ xtx_inv * n / (n - k)
    return b, np.sqrt(np.diag(v))


def logit(X: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Logistic regression by Newton-Raphson; coefficients and standard errors."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        w = p * (1 - p)
        H = (X * w[:, None]).T @ X
        step = np.linalg.solve(H + 1e-9 * np.eye(len(b)), X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    H = (X * (p * (1 - p))[:, None]).T @ X
    return b, np.sqrt(np.diag(np.linalg.pinv(H)))


# --------------------------------------------------------------------------- inputs

class Data:
    def __init__(self, cfg):
        it = cfg.paths.interim
        for f in ("works.parquet", "authorships.parquet", "faculty_papers.parquet", "cit_edges.parquet", "faculty_dept.parquet"):
            if not (it / f).exists():
                raise StepFailed(f"data/interim/{f} missing - run s05 to s09 first")
        self.labs = [l["short"] for l in cfg.labs]
        self.works = pd.read_parquet(it / "works.parquet").set_index("work_id")
        self.auth = pd.read_parquet(it / "authorships.parquet")
        self.links = pd.read_parquet(it / "faculty_papers.parquet")
        self.edges = pd.read_parquet(it / "cit_edges.parquet")
        dept = pd.read_parquet(it / "faculty_dept.parquet")
        self.dept = dict(zip(dept["faculty_id"], dept["department"]))
        self.max_authors = cfg.networks.max_authors_for_pairs
        ours = set(self.works.index)
        self.year = self.works["year"].astype(int).to_dict()
        self.field = self.works["field"].fillna("Unknown").to_dict()
        self.authors = self.auth.dropna(subset=["author_id"]).groupby("work_id")["author_id"].agg(set).to_dict()
        self.fac = self.links.groupby("work_id")["faculty_id"].agg(set).to_dict()
        self.lab_of_work = self.links.groupby("work_id")["institution"].agg(set).to_dict()
        self.fac_lab = self.links.drop_duplicates("faculty_id").set_index("faculty_id")["institution"].to_dict()
        self.internal = self.edges[(self.edges["scope"] == "internal") & self.edges["src"].isin(ours)
                                   & self.edges["tgt"].isin(ours)].copy()
        # faculty co-authorship events: (fi, fj, year, work) on papers within the author cap (as in s10)
        n_auth = self.works["n_authors"].to_dict()
        ev = []
        for w, fs in self.fac.items():
            if len(fs) > 1 and n_auth.get(w, 0) <= self.max_authors:
                for a, b in combinations(sorted(fs), 2):
                    ev.append((a, b, self.year[w], w))
        self.coauth = pd.DataFrame(ev, columns=["a", "b", "year", "work_id"])
        self.first_year = self.coauth.groupby(["a", "b"])["year"].min().to_dict()
        self.faculty = sorted(self.fac_lab)


def pair(a, b):
    return (a, b) if a < b else (b, a)


# --------------------------------------------------------------------------- A1 citation audience

def citation_audience(D: Data) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for s, t, y in D.internal[["src", "tgt", "year"]].itertuples(index=False):
        if s == t:
            continue
        shared = bool(D.authors.get(s, set()) & D.authors.get(t, set()))
        fs, ft = D.fac.get(s, set()), D.fac.get(t, set())
        prior = (not shared) and any(D.first_year.get(pair(a, b), 9999) <= y for a in fs for b in ft if a != b)
        ls, lt = D.lab_of_work.get(s, set()), D.lab_of_work.get(t, set())
        same = bool(ls & lt)
        cls = "self (shared author)" if shared else "co-author network" if prior else "same lab, independent" if same \
            else "other lab, independent"
        rows.append({"src": s, "tgt": t, "year": y, "class": cls, "same_lab": same,
                     "src_labs": ";".join(sorted(ls)), "tgt_labs": ";".join(sorted(lt))})
    e = pd.DataFrame(rows)
    out = []
    for scope in [*D.labs, "ALL"]:
        g = e if scope == "ALL" else e[e["src_labs"].str.split(";").map(lambda x: scope in x)]
        for cls, n in g["class"].value_counts().items():
            out.append({"citing_scope": scope, "class": cls, "citations": int(n), "share": n / len(g)})
    return e, pd.DataFrame(out)


def pagerank_independent(D: Data, e: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """PageRank on the internal citation network with and without self-citations (a shared author on both papers).
    A paper that ranks high only because its own authors cite it falls once those edges are removed."""
    out = []
    for basis, sub in (("all citations", e), ("independent citations", e[e["class"] != "self (shared author)"])):
        G = nx.DiGraph()
        G.add_nodes_from(D.works.index)
        G.add_edges_from(zip(sub["src"], sub["tgt"]))
        pr = nx.pagerank(G, alpha=0.85)
        rank = pd.Series(pr).rank(ascending=False, method="min")
        for w, v in sorted(pr.items(), key=lambda kv: -kv[1])[:n]:
            out.append({"basis": basis, "rank": int(rank[w]), "work_id": w, "title": D.works.at[w, "title"],
                        "year": int(D.works.at[w, "year"]), "labs": ";".join(sorted(D.lab_of_work.get(w, ()))),
                        "pagerank": v, "in_degree": G.in_degree(w), "citations": int(D.works.at[w, "cited_by_count"])})
        if basis == "all citations":
            all_rank = rank
        else:
            ind_rank = rank
    t = pd.DataFrame(out)
    t["rank_all"] = t["work_id"].map(all_rank).astype(int)
    t["rank_independent"] = t["work_id"].map(ind_rank).astype(int)
    return t


# --------------------------------------------------------------------------- A2 lab exchange vs a permutation null

def lab_exchange_null(D: Data, e: pd.DataFrame, n_perm: int = 1000) -> pd.DataFrame:
    """Lab-to-lab citation matrix vs targets permuted within strata (cited year; and cited year + both fields).

    A multi-lab paper splits its weight equally over its labs. Permuting the target column within a stratum keeps every
    citing paper's references count and every cited paper's citations count (within the stratum), so the null asks:
    with the same papers citing and being cited as much, in the same fields and years, how many citations would cross
    labs by chance?"""
    labs = D.labs
    idx = {l: i for i, l in enumerate(labs)}

    def vec(work):
        v = np.zeros(len(labs))
        ls = D.lab_of_work.get(work, set())
        for l in ls:
            v[idx[l]] = 1 / len(ls)
        return v
    res = []
    for basis, sub in (("all citations", e), ("independent citations (no shared author)", e[e["class"] != "self (shared author)"])):
        S = np.array([vec(s) for s in sub["src"]])
        T = np.array([vec(t) for t in sub["tgt"]])
        obs = S.T @ T
        rng = np.random.default_rng(SEED)
        for null, keys in (("same cited year", [sub["tgt"].map(D.year)]),
                           ("same cited year and fields", [sub["tgt"].map(D.year), sub["src"].map(D.field), sub["tgt"].map(D.field)])):
            strata = pd.Series(list(zip(*keys))).astype(str).to_numpy() if len(keys) > 1 else keys[0].astype(str).to_numpy()
            groups = [np.flatnonzero(strata == k) for k in np.unique(strata)]
            sims = np.empty((n_perm, len(labs), len(labs)))
            for i in range(n_perm):
                perm = np.arange(len(sub))
                for g in groups:
                    if len(g) > 1:
                        perm[g] = g[rng.permutation(len(g))]
                sims[i] = S.T @ T[perm]
            mean, sd = sims.mean(0), sims.std(0)
            p = np.minimum(1, 2 * np.minimum((sims >= obs).mean(0), (sims <= obs).mean(0)) + 1 / n_perm)
            q = bh(p.ravel()).reshape(p.shape)
            for a in labs:
                for b in labs:
                    i, j = idx[a], idx[b]
                    res.append({"basis": basis, "null": null, "citing_lab": a, "cited_lab": b, "observed": obs[i, j],
                                "expected": mean[i, j], "obs_exp": obs[i, j] / mean[i, j] if mean[i, j] else np.nan,
                                "z": (obs[i, j] - mean[i, j]) / sd[i, j] if sd[i, j] else np.nan, "p": p[i, j], "q_bh": q[i, j]})
            diag = np.trace(obs) / obs.sum()
            res.append({"basis": basis, "null": null, "citing_lab": "ALL", "cited_lab": "within-lab share",
                        "observed": diag, "expected": float(np.mean([np.trace(x) / x.sum() for x in sims])),
                        "obs_exp": np.nan, "z": np.nan, "p": np.nan, "q_bh": np.nan})
    return pd.DataFrame(res)


# --------------------------------------------------------------------------- A3 collaboration homophily

def topic_vectors(D: Data) -> dict[str, np.ndarray]:
    sub = D.works["subfield"].fillna("Unknown")
    cats = sorted(sub.unique())
    ci = {c: i for i, c in enumerate(cats)}
    vec = defaultdict(lambda: np.zeros(len(cats)))
    for w, f in zip(D.links["work_id"], D.links["faculty_id"]):
        vec[f][ci[sub.get(w, "Unknown")]] += 1
    return {f: v / np.linalg.norm(v) if np.linalg.norm(v) else v for f, v in vec.items()}


def homophily(D: Data, n_perm: int = 2000, n_rewire: int = 200) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    G = nx.Graph()
    G.add_nodes_from(D.faculty)
    for (a, b) in D.first_year:
        G.add_edge(a, b)
    lab = {f: D.fac_lab[f] for f in G}
    dept = {f: f"{D.fac_lab[f]}|{D.dept.get(f, '')}" for f in G}
    m = G.number_of_edges()
    edges = list(G.edges())

    def cross_share(lbl):
        return sum(lbl[a] != lbl[b] for a, b in edges) / m
    obs = cross_share(lab)
    rng = np.random.default_rng(SEED)
    nodes = list(G)
    labels = np.array([lab[n] for n in nodes])
    sims = []
    for _ in range(n_perm):
        p = dict(zip(nodes, rng.permutation(labels)))
        sims.append(cross_share(p))
    sims = np.array(sims)
    # degree-preserving rewiring
    rew_cross, rew_clust, rew_rc = [], [], []
    obs_clust = nx.average_clustering(G)
    deg = dict(G.degree())
    k_rich = int(np.percentile([d for d in deg.values() if d > 0], 90))

    def rich(H):
        rich_nodes = [n for n, d in H.degree() if d > k_rich]
        k = len(rich_nodes)
        return H.subgraph(rich_nodes).number_of_edges() / (k * (k - 1) / 2) if k > 1 else np.nan
    obs_rc = rich(G)
    for i in range(n_rewire):
        H = G.copy()
        nx.double_edge_swap(H, nswap=10 * m, max_tries=100 * m, seed=SEED + i)
        rew_cross.append(sum(lab[a] != lab[b] for a, b in H.edges()) / m)
        rew_clust.append(nx.average_clustering(H))
        rew_rc.append(rich(H))
    nx.set_node_attributes(G, lab, "lab")
    nx.set_node_attributes(G, dept, "dept")
    summary = {
        "faculty_nodes": G.number_of_nodes(), "faculty_links": m,
        "cross_lab_share_observed": obs, "cross_lab_share_label_permutation": float(sims.mean()),
        "cross_lab_ratio_vs_permutation": obs / sims.mean(), "cross_lab_z_permutation": (obs - sims.mean()) / sims.std(),
        "cross_lab_share_rewired": float(np.mean(rew_cross)),
        "lab_assortativity": nx.attribute_assortativity_coefficient(G, "lab"),
        "dept_assortativity": nx.attribute_assortativity_coefficient(G, "dept"),
        "clustering_observed": obs_clust, "clustering_rewired": float(np.mean(rew_clust)),
        "clustering_ratio": obs_clust / np.mean(rew_clust),
        "rich_club_degree_threshold": k_rich, "rich_club_observed": obs_rc, "rich_club_rewired": float(np.nanmean(rew_rc)),
        "rich_club_normalised": obs_rc / np.nanmean(rew_rc),
    }
    # who writes with whom: logistic model over all faculty pairs (with at least one paper each)
    tv = topic_vectors(D)
    npap = D.links.groupby("faculty_id")["work_id"].nunique().to_dict()
    rows = []
    for a, b in combinations(nodes, 2):
        rows.append((G.has_edge(a, b), lab[a] == lab[b], dept[a] == dept[b] and D.dept.get(a, "") not in ("", "Unknown"),
                     float(tv[a] @ tv[b]) if a in tv and b in tv else 0.0, np.log(npap.get(a, 1) * npap.get(b, 1))))
    P = np.array(rows, float)
    y = P[:, 0]
    specs = {"same lab only": [1], "same lab + topic similarity + size": [1, 3, 4],
             "same lab + same department + topic similarity + size": [1, 2, 3, 4]}
    names = {1: "same_lab", 2: "same_department", 3: "topic_similarity", 4: "log_papers_product"}
    coef = []
    for spec, cols in specs.items():
        X = np.column_stack([np.ones(len(P)), P[:, cols]])
        b, se = logit(X, y)
        for k, c in enumerate(cols, 1):
            coef.append({"model": spec, "term": names[c], "coef": b[k], "se": se[k], "odds_ratio": np.exp(b[k]),
                         "or_low": np.exp(b[k] - 1.96 * se[k]), "or_high": np.exp(b[k] + 1.96 * se[k]),
                         "pairs": len(P), "links": int(y.sum())})
    perm = pd.DataFrame({"statistic": ["cross-lab link share"], "observed": [obs], "null_mean": [sims.mean()],
                         "null_p2_5": [np.percentile(sims, 2.5)], "null_p97_5": [np.percentile(sims, 97.5)]})
    return pd.DataFrame(coef), perm, summary


# --------------------------------------------------------------------------- A4 citations by co-authorship distance

def distance_lift(D: Data, e: pd.DataFrame) -> pd.DataFrame:
    fac = D.faculty
    fi = {f: i for i, f in enumerate(fac)}
    n = len(fac)
    years = sorted(D.internal["year"].dropna().astype(int).unique())
    bins = ["1", "2", "3", "4+", "not connected"]

    def dclass(d):
        return "not connected" if d is None else "1" if d == 1 else "2" if d == 2 else "3" if d == 3 else "4+"
    out = []
    for basis, sub in (("all citations", e), ("independent citations", e[e["class"] != "self (shared author)"])):
        obs, exp = Counter(), Counter()
        for y in years:
            G = nx.Graph()
            G.add_nodes_from(fac)
            G.add_edges_from(k for k, v in D.first_year.items() if v < y)
            dist = dict(nx.all_pairs_shortest_path_length(G))
            ey = sub[sub["year"] == y]
            O, I = np.zeros(n), np.zeros(n)
            pairs = []
            for s, t in zip(ey["src"], ey["tgt"]):
                for a in D.fac.get(s, ()):
                    for b in D.fac.get(t, ()):
                        if a != b:
                            pairs.append((a, b))
                            O[fi[a]] += 1
                            I[fi[b]] += 1
            tot = len(pairs)
            if not tot:
                continue
            for a, b in pairs:
                obs[dclass(dist[a].get(b))] += 1
            E = np.outer(O, I) / tot
            np.fill_diagonal(E, 0)
            nz = np.argwhere(E > 0)
            for i, j in nz:
                exp[dclass(dist[fac[i]].get(fac[j]))] += E[i, j]
        for b in bins:
            out.append({"basis": basis, "distance": b, "observed": obs[b], "expected": exp[b],
                        "lift": obs[b] / exp[b] if exp[b] else np.nan})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- A5 led vs middle-author papers

def led_vs_middle(D: Data) -> pd.DataFrame:
    a = D.auth.sort_values(["work_id", "position_idx"])
    last = a.groupby("work_id")["position_idx"].transform("max")
    a["key"] = (a["position_idx"] == 0) | (a["position_idx"] == last) | a["is_corresponding"].fillna(False)
    a["lab_key"] = a["key"] & a["our_lab"].notna()
    led = a.groupby("work_id")["lab_key"].any()
    w = D.works.copy()
    w["led"] = w.index.map(led).fillna(False).astype(bool)
    w["norm_cites"] = w["cited_by_count"] / w.groupby(["field", "year"])["cited_by_count"].transform("mean").replace(0, np.nan)
    rows = []
    for scope in [*D.labs, "ALL"]:
        ids = set(D.links.loc[D.links["institution"] == scope, "work_id"]) if scope != "ALL" else set(w.index)
        g = w[w.index.isin(ids)]
        tot_c = g["cited_by_count"].sum()
        for led_v, h in g.groupby("led"):
            rows.append({"scope": scope, "role": "lab-led" if led_v else "middle author only", "papers": len(h),
                         "share_of_papers": len(h) / len(g), "citations": int(h["cited_by_count"].sum()),
                         "share_of_citations": h["cited_by_count"].sum() / tot_c if tot_c else np.nan,
                         "mean_norm_citations": h["norm_cites"].mean(), "median_authors": h["n_authors"].median(),
                         "share_10plus_authors": (h["n_authors"] >= 10).mean()})
        if g["led"].nunique() == 2:
            u = stats.mannwhitneyu(g.loc[g["led"], "norm_cites"].dropna(), g.loc[~g["led"], "norm_cites"].dropna())
            rows[-1]["mannwhitney_p_led_vs_middle"] = u.pvalue
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- A6 persistence and triadic closure

def persistence(D: Data) -> tuple[pd.DataFrame, pd.DataFrame]:
    years_of = D.coauth.groupby(["a", "b"])["year"].agg(lambda s: sorted(set(s))).to_dict()
    rows = []
    for (a, b), ys in years_of.items():
        t0 = ys[0]
        if t0 > 2022:
            continue
        again = any(t0 < y <= t0 + 3 for y in ys)
        rows.append({"cross_lab": D.fac_lab[a] != D.fac_lab[b], "first_year": t0, "repeat_3y": again})
    p = pd.DataFrame(rows)
    out = []
    for cross, g in p.groupby("cross_lab"):
        k, n = int(g["repeat_3y"].sum()), len(g)
        lo, hi = wilson(k, n)
        out.append({"pair_type": "cross-lab" if cross else "same lab", "new_pairs_2016_2022": n, "repeat_within_3y": k,
                    "share": k / n, "ci_low": lo, "ci_high": hi})
    if p["cross_lab"].nunique() == 2:
        a_, b_ = p[p.cross_lab], p[~p.cross_lab]
        tab = [[a_.repeat_3y.sum(), len(a_) - a_.repeat_3y.sum()], [b_.repeat_3y.sum(), len(b_) - b_.repeat_3y.sum()]]
        out[-1]["fisher_p_cross_vs_same"] = stats.fisher_exact(tab)[1]
    # triadic closure: probability that an unlinked pair links in year t, with vs without a common faculty co-author
    tri = []
    for t in range(2017, 2027):
        G = nx.Graph()
        G.add_nodes_from(D.faculty)
        G.add_edges_from(k for k, v in D.first_year.items() if v < t)
        new = {k for k, v in D.first_year.items() if v == t}
        closed = open_ = n_closed = n_open = 0
        for a, b in combinations(D.faculty, 2):
            if G.has_edge(a, b):
                continue
            common = any(True for _ in nx.common_neighbors(G, a, b))
            hit = pair(a, b) in new
            if common:
                n_closed += 1; closed += hit
            else:
                n_open += 1; open_ += hit
        tri.append({"year": t, "pairs_with_common_coauthor": n_closed, "linked_with_common": closed,
                    "pairs_without": n_open, "linked_without": open_,
                    "p_with": closed / n_closed if n_closed else np.nan, "p_without": open_ / n_open if n_open else np.nan})
    tri = pd.DataFrame(tri)
    tri["lift"] = tri["p_with"] / tri["p_without"]
    return pd.DataFrame(out), tri


# --------------------------------------------------------------------------- A7 lab impact with controls

def lab_impact(D: Data) -> pd.DataFrame:
    w = D.works.copy()
    lab_sets = w.index.map(lambda x: D.lab_of_work.get(x, set()))
    w = w[[len(s) == 1 for s in lab_sets]].copy()
    w["lab"] = [next(iter(D.lab_of_work[x])) for x in w.index]
    w["y"] = np.log1p(w["cited_by_count"])
    ref = "CSIR-CDRI"
    cols, X = [], [np.ones(len(w))]
    for l in D.labs:
        if l != ref:
            X.append((w["lab"] == l).astype(float).to_numpy()); cols.append(f"lab: {l}")
    base_models = {"lab only": False, "lab + year + field + team size + review": True}
    out = []
    for name, full in base_models.items():
        Xs, cs = list(X), list(cols)
        if full:
            for yv in sorted(w["year"].unique())[1:]:
                Xs.append((w["year"] == yv).astype(float).to_numpy()); cs.append(f"year {yv}")
            fields = w["field"].fillna("Unknown")
            for f in fields.value_counts().index[1:]:
                Xs.append((fields == f).astype(float).to_numpy()); cs.append(f"field: {f}")
            Xs.append(np.log(w["n_authors"].clip(lower=1)).to_numpy()); cs.append("log authors")
            Xs.append((w["work_type"] == "review").astype(float).to_numpy()); cs.append("review")
        b, se = ols_hc1(np.column_stack(Xs), w["y"].to_numpy())
        for k, c in enumerate(cs, 1):
            if c.startswith("lab:") or c in ("log authors", "review"):
                out.append({"model": name, "term": c, "coef": b[k], "se": se[k],
                            "pct_effect": np.expm1(b[k]) * 100, "pct_low": np.expm1(b[k] - 1.96 * se[k]) * 100,
                            "pct_high": np.expm1(b[k] + 1.96 * se[k]) * 100, "papers": len(w), "reference": ref})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- A8 COVID-19

def covid(D: Data) -> pd.DataFrame:
    w = D.works.copy()
    w["covid"] = [bool(COVID.search(f"{t} {tp}")) for t, tp in zip(w["title"].fillna(""), w["topic"].fillna(""))]
    rows = []
    for scope in [*D.labs, "ALL"]:
        ids = set(D.links.loc[D.links["institution"] == scope, "work_id"]) if scope != "ALL" else set(w.index)
        g = w[w.index.isin(ids)]
        for y, h in g.groupby("year"):
            rows.append({"scope": scope, "year": int(y), "papers": len(h), "covid_papers": int(h["covid"].sum()),
                         "covid_share": h["covid"].mean(), "citations": int(h["cited_by_count"].sum()),
                         "covid_citation_share": h.loc[h["covid"], "cited_by_count"].sum() / max(1, h["cited_by_count"].sum())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    D = Data(cfg)
    st = cfg.paths.stats
    log.info("internal citations: %d; faculty co-authorship events: %d", len(D.internal), len(D.coauth))
    e, aud = citation_audience(D)
    aud.to_csv(st / "research_citation_audience.csv", index=False, lineterminator="\n")
    pagerank_independent(D, e).to_csv(st / "research_pagerank_independent.csv", index=False, lineterminator="\n")
    ex = lab_exchange_null(D, e)
    ex.to_csv(st / "research_lab_exchange_null.csv", index=False, lineterminator="\n")
    coef, perm, hsum = homophily(D)
    coef.to_csv(st / "research_coauthor_model.csv", index=False, lineterminator="\n")
    perm.to_csv(st / "research_coauthor_null.csv", index=False, lineterminator="\n")
    dl = distance_lift(D, e)
    dl.to_csv(st / "research_distance_lift.csv", index=False, lineterminator="\n")
    lm = led_vs_middle(D)
    lm.to_csv(st / "research_led_vs_middle.csv", index=False, lineterminator="\n")
    pers, tri = persistence(D)
    pers.to_csv(st / "research_tie_persistence.csv", index=False, lineterminator="\n")
    tri.to_csv(st / "research_triadic_closure.csv", index=False, lineterminator="\n")
    imp = lab_impact(D)
    imp.to_csv(st / "research_lab_impact.csv", index=False, lineterminator="\n")
    cv = covid(D)
    cv.to_csv(st / "research_covid.csv", index=False, lineterminator="\n")

    a_all = aud[aud["citing_scope"] == "ALL"].set_index("class")["share"].to_dict()
    ind = ex[(ex["basis"].str.startswith("independent")) & (ex["cited_lab"] == "within-lab share")]
    diag = ex[(ex["basis"].str.startswith("independent")) & (ex["citing_lab"] == ex["cited_lab"])]
    summary = {
        "internal_citations": len(e), "citation_audience_shares": a_all,
        "within_lab_share_independent": {r.null: {"observed": r.observed, "expected": r.expected} for r in ind.itertuples()},
        "within_lab_obs_exp_independent_fields_null": {r.citing_lab: r.obs_exp for r in diag[diag["null"].str.contains("fields")].itertuples()},
        "homophily": hsum,
        "distance_lift": {f"{r.basis}|{r.distance}": r.lift for r in dl.itertuples()},
        "tie_persistence": pers.to_dict("records"),
        "triadic_closure_mean_lift": float(tri["lift"].replace([np.inf], np.nan).mean()),
        "led_vs_middle_all": lm[lm["scope"] == "ALL"].to_dict("records"),
        "lab_impact": imp.to_dict("records"),
        "covid_peak": cv.loc[cv.groupby("scope")["covid_share"].idxmax()].to_dict("records"),
    }
    (st / "research_summary.json").write_text(json.dumps(json_safe(summary), indent=2, default=float, allow_nan=False), encoding="utf-8")
    print("\nCitation audience (all internal citations):", {k: f"{v:.1%}" for k, v in a_all.items()})
    print("Within-lab share of independent citations:", {r.null: f"{r.observed:.1%} vs {r.expected:.1%} expected" for r in ind.itertuples()})
    print(f"Cross-lab co-authorship: {hsum['cross_lab_share_observed']:.1%} observed vs "
          f"{hsum['cross_lab_share_label_permutation']:.1%} under lab-label permutation (z = {hsum['cross_lab_z_permutation']:.1f})")
    print(f"Clustering {hsum['clustering_observed']:.2f} vs {hsum['clustering_rewired']:.2f} rewired; rich club x{hsum['rich_club_normalised']:.2f}")
    print("Same-lab odds ratio:", coef[["model", "term", "odds_ratio", "or_low", "or_high"]].query("term == 'same_lab'").to_string(index=False))
    print(dl.to_string(index=False))
    print(lm[lm.scope == "ALL"].to_string(index=False))
    print(pers.to_string(index=False))
    print("Triadic closure lift by year:", tri.set_index("year")["lift"].round(1).to_dict())
    print(imp.to_string(index=False))
