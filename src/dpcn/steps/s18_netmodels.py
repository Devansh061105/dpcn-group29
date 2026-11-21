"""S18: course network models on our co-authorship data.

    python -m dpcn run s18            full run (a few minutes)
    python -m dpcn run s18 --quick    fewer bootstrap / null / permutation draws, for a smoke test

Like s16, it reads only the submitted files (group29_data.csv, authorship_network.csv), so its numbers sit on the same
snapshot as the submission and it runs without data/interim. The faculty network is rebuilt exactly as in s10: roster
faculty are nodes, and two are linked from the year of their first joint paper with at most
networks.max_authors_for_pairs authors.

  M1 heavy tails        CSN power-law fit + bootstrap p + likelihood-ratio tests (faculty degree, all-author degree,
                        paper citations)
  M2 small world        L and C vs Erdos-Renyi and degree-preserving nulls (faculty network and all-author network)
  M3 robustness         random failure vs targeted attack (degree, betweenness, cross-lab brokers); lab edge cuts;
                        Molloy-Reed threshold
  M4 spreading          SI on the weighted faculty network (time to reach every lab) vs a degree-preserving null and
                        with the main brokers removed; SIS prevalence and the epidemic threshold vs theory
  M5 link prediction    similarity scores and a logistic model, trained on earlier years and scored on links that
                        form in each test year (AUC, average precision), all pairs and cross-lab pairs separately
  M6 tie formation      discrete-time hazard model: P(first joint paper in year t | pair not yet linked), with lab,
                        department, topic, shared co-authors, degree, output and seniority; dyadic-robust errors and a
                        node-label permutation test for the lab and department terms (a dyadic substitute for a
                        stochastic actor-oriented model, which needs R/RSiena)

Outputs: outputs/stats/netmodel_*.csv, netmodel_summary.json, outputs/figures/netmodel_*.png. Randomness is seeded.
"""
from __future__ import annotations

import json
import logging
import re
import time
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

from .. import netmodels as M
from . import StepFailed

log = logging.getLogger("dpcn.s18")
SEED = 42


def seniority_rank(designation) -> float:
    """CSIR grade as an ordinal 1-6 (Scientist ... Chief / G, then fellows, directors and emeriti). NaN if unknown."""
    if not isinstance(designation, str) or not designation.strip():
        return np.nan
    d = re.sub(r"[-_]", " ", designation.lower())
    if re.search(r"bhatnagar|bose|distinguished|outstanding|director|emeritus|ramanujan fellow|ramalingaswami", d):
        return 6.0
    if re.search(r"chief scientist|scientist g\b|\bg\b grade", d):
        return 5.0
    if re.search(r"senior principal|scientist f\b", d):
        return 4.0
    if re.search(r"principal scientist|scientist e\b|scientist e[12i]", d):
        return 3.0
    if re.search(r"senior scientist|scientist d\b", d):
        return 2.0
    if re.search(r"scientist|fellow|investigator|\bpi\b", d):
        return 1.0
    return np.nan


# --------------------------------------------------------------------------- inputs

class Data:
    def __init__(self, cfg, max_authors: int | None = None):
        sub = cfg.paths.submission
        f = sub / "group29_data.csv"
        if not f.exists():
            raise StepFailed("outputs/submission/group29_data.csv missing - run s08 first")
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        d["year"] = d["year"].astype(int)
        d["n_authors"] = pd.to_numeric(d["n_authors"], errors="coerce").fillna(0).astype(int)
        d["citations"] = pd.to_numeric(d["citations"], errors="coerce").fillna(0).astype(int)
        self.main = d
        self.labs = [l["short"] for l in cfg.labs]
        self.max_authors = max_authors or cfg.networks.max_authors_for_pairs
        fac = d.groupby("faculty_id")
        self.lab = fac["institution"].agg(lambda s: s.mode().iat[0]).to_dict()
        self.dept = fac["department"].agg(lambda s: s[s != ""].mode().iat[0] if (s != "").any() else "").to_dict()
        self.seniority = fac["designation"].agg(lambda s: seniority_rank(s[s != ""].iat[0]) if (s != "").any() else np.nan).to_dict()
        self.first = fac["year"].min().to_dict()
        self.last = fac["year"].max().to_dict()
        self.faculty = sorted(self.lab)
        # cumulative output and topic profile per faculty and year
        self.papers_by_year = d.drop_duplicates(["faculty_id", "openalex_id"]).groupby(["faculty_id", "year"]).size()
        subf = d["subfield"].replace("", "Unknown")
        self.subfields = sorted(subf.unique())
        self.topic_counts = d.assign(subfield=subf).drop_duplicates(["faculty_id", "openalex_id"]) \
            .groupby(["faculty_id", "year", "subfield"]).size()
        # co-authorship events within the author cap
        small = d[d["n_authors"] <= self.max_authors]
        ev = []
        for w, g in small.groupby("openalex_id"):
            fs = sorted(set(g["faculty_id"]))
            if len(fs) > 1:
                y = int(g["year"].iat[0])
                ev.extend((a, b, y) for a, b in combinations(fs, 2))
        self.events = pd.DataFrame(ev, columns=["a", "b", "year"])
        self.first_link = self.events.groupby(["a", "b"])["year"].min().to_dict()
        self.weight = self.events.groupby(["a", "b"]).size().to_dict()
        self.citations = d.drop_duplicates("openalex_id")["citations"].to_numpy()
        self.author_file = sub / "authorship_network.csv"

    def faculty_graph(self, upto: int | None = None, weighted: bool = False) -> nx.Graph:
        """Faculty network with links that formed by year `upto` (all years when None). Every faculty is a node."""
        G = nx.Graph()
        G.add_nodes_from(self.faculty)
        if upto is None:
            for (a, b), w in self.weight.items():
                G.add_edge(a, b, weight=w)
        else:
            sub = self.events[self.events["year"] <= upto]
            for (a, b), w in sub.groupby(["a", "b"]).size().items():
                G.add_edge(a, b, weight=int(w))
        if not weighted:
            for _, _, e in G.edges(data=True):
                e.pop("weight", None)
        return G

    def all_author_graph(self) -> nx.Graph:
        e = pd.read_csv(self.author_file, usecols=["author_a_id", "author_b_id"], dtype=str)
        G = nx.Graph()
        G.add_edges_from(zip(e["author_a_id"], e["author_b_id"]))
        G.remove_edges_from(nx.selfloop_edges(G))
        return G

    def topic_matrix(self, upto: int, nodes: list[str]) -> np.ndarray:
        """Row-normalised subfield profile of each faculty member from papers up to and including year `upto`."""
        ci = {s: i for i, s in enumerate(self.subfields)}
        ix = {f: i for i, f in enumerate(nodes)}
        T = np.zeros((len(nodes), len(self.subfields)))
        tc = self.topic_counts
        sel = tc[tc.index.get_level_values("year") <= upto]
        for (f, _, s), n in sel.items():
            if f in ix:
                T[ix[f], ci[s]] += n
        norm = np.linalg.norm(T, axis=1, keepdims=True)
        return np.divide(T, norm, out=np.zeros_like(T), where=norm > 0)

    def output_upto(self, upto: int) -> dict[str, int]:
        p = self.papers_by_year
        return p[p.index.get_level_values("year") <= upto].groupby(level=0).sum().to_dict()


# --------------------------------------------------------------------------- M1 heavy tails

def ccdf_rows(name: str, x, fit: dict, max_points: int = 120) -> list[dict]:
    """Empirical P(X >= x) on a log-spaced grid of observed values, with the fitted power law above x_min (scaled to
    the tail's share so it sits on the data)."""
    from scipy import special
    x = np.sort(np.round(np.asarray(x, float)))
    x = x[x >= 1]
    u = np.unique(x)
    if len(u) > max_points:
        u = np.unique(np.concatenate([u[:30], u[np.unique(np.geomspace(30, len(u) - 1, max_points - 30).astype(int))]]))
    cc = 1 - np.searchsorted(x, u, side="left") / len(x)
    share = fit["n_tail"] / len(x)
    out = []
    for v, c in zip(u, cc):
        f = float(special.zeta(fit["alpha"], v) / special.zeta(fit["alpha"], fit["xmin"]) * share) if v >= fit["xmin"] else None
        out.append({"distribution": name, "x": int(v), "ccdf": float(c), "fit": f})
    return out


def heavy_tails(D: Data, G_fac: nx.Graph, G_all: nx.Graph, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, cc = [], []
    for name, x in (("faculty co-authorship degree", [d for _, d in G_fac.degree()]),
                    ("all-author co-authorship degree", [d for _, d in G_all.degree()]),
                    ("paper citations", D.citations)):
        x = np.asarray(x, float)
        t0 = time.time()
        fit = M.fit_power_law(x)
        p = M.power_law_gof(x, fit, n_boot=n_boot, seed=SEED)
        comps = M.compare_tails(x, fit)
        pos = x[x > 0]
        base = {"distribution": name, "n": len(x), "n_positive": len(pos), "mean": x.mean(), "max": x.max(),
                "xmin": fit["xmin"], "alpha": fit["alpha"], "n_tail": fit["n_tail"], "tail_share": fit["n_tail"] / len(pos),
                "ks": fit["ks"], "gof_p": p, "n_boot": n_boot, "power_law_plausible": bool(p >= 0.1)}
        for c in comps:
            rows.append({**base, **c})
        cc += ccdf_rows(name, x, fit)
        log.info("M1 %s: xmin=%s alpha=%.2f p=%.2f (%.0fs)", name, fit["xmin"], fit["alpha"], p, time.time() - t0)
    return pd.DataFrame(rows), pd.DataFrame(cc)


# --------------------------------------------------------------------------- M3 robustness

def robustness(D: Data, G: nx.Graph, n_random: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lab = D.lab
    n0 = G.number_of_nodes()
    curves = []
    for strat in ("degree", "betweenness", "brokers"):
        for i, lcc, pairs in M.attack(G, lab, strat):
            curves.append({"strategy": strat, "removed": i, "removed_share": i / n0, "lcc_share": lcc, "lab_pairs_joined": pairs})
    rnd = np.array([[r[1:] for r in M.attack(G, lab, "random", seed=SEED + k)] for k in range(n_random)])
    for i in range(n0 + 1):
        curves.append({"strategy": "random", "removed": i, "removed_share": i / n0, "lcc_share": rnd[:, i, 0].mean(),
                       "lab_pairs_joined": rnd[:, i, 1].mean(), "lcc_share_p05": np.percentile(rnd[:, i, 0], 5),
                       "lcc_share_p95": np.percentile(rnd[:, i, 0], 95)})
    c = pd.DataFrame(curves)
    lcc0 = c.loc[c["removed"] == 0, "lcc_share"].iat[0]
    summ = []
    for strat, g in c.groupby("strategy"):
        half = g[g["lcc_share"] < lcc0 / 2]
        split = g[g["lab_pairs_joined"] < 6]
        none = g[g["lab_pairs_joined"] == 0]
        summ.append({"strategy": strat, "lcc_share_start": lcc0,
                     "removed_to_halve_lcc": int(half["removed"].min()) if len(half) else None,
                     "share_to_halve_lcc": half["removed_share"].min() if len(half) else None,
                     "removed_until_a_lab_pair_splits": int(split["removed"].min()) if len(split) else None,
                     "removed_until_no_lab_pair_joined": int(none["removed"].min()) if len(none) else None,
                     "lcc_after_5pct": g.loc[g["removed_share"] >= 0.05, "lcc_share"].iat[0],
                     "lcc_after_10pct": g.loc[g["removed_share"] >= 0.10, "lcc_share"].iat[0]})
    cuts = pd.DataFrame(M.lab_edge_cuts(G, lab))
    return c, pd.DataFrame(summ), cuts


# --------------------------------------------------------------------------- M4 spreading

def spreading(D: Data, G_fac_w: nx.Graph, n_null: int, beta_si: float = 0.05) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    H = M.largest_component(G_fac_w)
    nodes = sorted(H)
    lab_idx = np.array([D.labs.index(D.lab[v]) for v in nodes])
    W = nx.to_numpy_array(H, nodelist=nodes, weight="weight")
    rng = np.random.default_rng(SEED)
    seeds = list(range(len(nodes)))

    def run(Wm, label, k=0):
        return [{"network": label, "replicate": k, **r} for r in M.si_runs(Wm, lab_idx, beta_si, seeds, seed=SEED + k)]

    si = run(W, "observed")
    weights = np.array([d["weight"] for _, _, d in H.edges(data=True)])
    for k in range(n_null):
        R = nx.Graph(H.edges())
        nx.double_edge_swap(R, nswap=5 * R.number_of_edges(), max_tries=200 * R.number_of_edges(), seed=int(rng.integers(1 << 31)))
        for (u, v), w in zip(R.edges(), rng.permutation(weights)):
            R[u][v]["weight"] = w
        si += run(nx.to_numpy_array(R, nodelist=nodes, weight="weight"), "degree-preserving null", k)
    # remove the five faculty with the most cross-lab co-authors (their rows/columns zeroed, they are not seeds)
    brokers = sorted(nodes, key=lambda u: (-sum(D.lab[w] != D.lab[u] for w in H[u]), -H.degree(u), u))[:5]
    keep = np.array([v not in brokers for v in nodes])
    Wb = W * keep[:, None] * keep[None, :]
    si += [{"network": "five brokers removed", "replicate": 0, **r}
           for r in M.si_runs(Wb, lab_idx, beta_si, [i for i in seeds if keep[i]], seed=SEED)]
    si = pd.DataFrame(si)

    def agg(g):
        return pd.Series({"runs": len(g), "share_reaching_all_labs": g["t_all_labs"].notna().mean(),
                          "median_t_other_lab": g["t_other_lab"].median(), "median_t_all_labs": g["t_all_labs"].median(),
                          "median_t50": g["t50"].median(), "median_t90": g["t90"].median()})
    si_sum = si.groupby("network").apply(agg, include_groups=False).reset_index()
    si_sum["beta"] = beta_si
    # SIS on the unweighted component
    A = (W > 0).astype(float)
    th = M.sis_theory(A)
    mu = 0.2
    rows = []
    nets = [("observed", A)]
    R = nx.Graph(H.edges())
    nx.double_edge_swap(R, nswap=5 * R.number_of_edges(), max_tries=200 * R.number_of_edges(), seed=SEED)
    nets.append(("degree-preserving null", nx.to_numpy_array(R, nodelist=nodes, weight=None)))
    for lam in np.round(np.linspace(0.2, 4.0, 20) * th["threshold_qmf"], 5):
        for label, Am in nets:
            m, s = M.sis_prevalence(Am, beta=min(lam * mu, 0.99), mu=mu, seed=SEED)
            rows.append({"network": label, "lambda": lam, "lambda_over_qmf": lam / th["threshold_qmf"], "beta": lam * mu,
                         "mu": mu, "prevalence": m, "prevalence_sd": s})
    sis = pd.DataFrame(rows)
    obs = sis[sis["network"] == "observed"]
    above = obs[obs["prevalence"] >= 0.01]
    th.update({"mu": mu, "threshold_empirical": float(above["lambda"].min()) if len(above) else None,
               "brokers_removed": [{"faculty_id": b, "lab": D.lab[b]} for b in brokers], "lcc_nodes": len(nodes)})
    return si, si_sum, sis, th


# --------------------------------------------------------------------------- M5 link prediction / M6 tie formation

def active_faculty(D: Data, t: int, mode: str = "span") -> list[str]:
    """Faculty at risk of a new link in year t.
    span    first paper before t and a paper in t or later (uses each person's last paper year: mild look-ahead)
    recent  first paper before t and a paper in t-3 .. t-1 (only past information)"""
    if mode == "span":
        return [f for f in D.faculty if D.first[f] <= t - 1 and D.last[f] >= t]
    if mode == "recent":
        py = D.papers_by_year
        recent = set(py[(py.index.get_level_values("year") >= t - 3) & (py.index.get_level_values("year") <= t - 1)]
                     .index.get_level_values(0))
        return [f for f in D.faculty if D.first[f] <= t - 1 and f in recent]
    raise ValueError(mode)


def dyad_panel(D: Data, years: range, active_mode: str = "span") -> pd.DataFrame:
    """One row per (year t, unlinked faculty pair active in t-1 and t): features from the network up to t-1 and
    whether the pair's first joint paper (within the author cap) is in year t."""
    rows = []
    for t in years:
        G = D.faculty_graph(upto=t - 1)
        active = active_faculty(D, t, active_mode)
        pairs = [(a, b) for a, b in combinations(sorted(active), 2) if not G.has_edge(a, b)]
        if not pairs:
            continue
        feats = M.pair_features(G, pairs)
        T = D.topic_matrix(t - 1, active)
        ix = {f: i for i, f in enumerate(active)}
        out = D.output_upto(t - 1)
        a = np.array([ix[p] for p, _ in pairs])
        b = np.array([ix[q] for _, q in pairs])
        dist = dict(nx.all_pairs_shortest_path_length(G.subgraph(active)))
        df = pd.DataFrame({"year": t, "a": [p for p, _ in pairs], "b": [q for _, q in pairs], **feats})
        df["topic_similarity"] = (T[a] * T[b]).sum(1)
        df["same_lab"] = [D.lab[p] == D.lab[q] for p, q in pairs]
        df["same_department"] = [D.lab[p] == D.lab[q] and D.dept[p] == D.dept[q] and D.dept[p] not in ("", "Unknown")
                                 for p, q in pairs]
        df["log_output_product"] = [np.log1p(out.get(p, 0)) + np.log1p(out.get(q, 0)) for p, q in pairs]
        df["distance"] = [dist.get(p, {}).get(q, np.inf) for p, q in pairs]
        df["y"] = [D.first_link.get((p, q)) == t for p, q in pairs]
        rows.append(df)
    P = pd.concat(rows, ignore_index=True)
    s = P["a"].map(D.seniority), P["b"].map(D.seniority)
    med = np.nanmedian(list(D.seniority.values()))
    P["seniority_missing"] = (s[0].isna() | s[1].isna()).astype(float)
    sa, sb = s[0].fillna(med), s[1].fillna(med)
    P["seniority_sum"] = sa + sb
    P["seniority_gap"] = (sa - sb).abs()
    P["log_cn"] = np.log1p(P["common_neighbours"])
    P["log_pa"] = np.log1p(P["preferential_attachment"])
    P["inv_distance"] = np.where(np.isfinite(P["distance"]), 1 / P["distance"].replace(0, np.inf), 0)
    return P


LP_SCORES = ["common_neighbours", "jaccard", "adamic_adar", "resource_allocation", "preferential_attachment", "katz",
             "inv_distance", "topic_similarity", "same_lab"]
LP_MODEL = ["log_cn", "adamic_adar", "katz", "log_pa", "inv_distance", "same_lab", "same_department", "topic_similarity",
            "log_output_product"]


def link_prediction(P: pd.DataFrame, test_years: range) -> pd.DataFrame:
    rows = []
    for t in test_years:
        train, test = P[P["year"] < t], P[P["year"] == t]
        if test["y"].sum() == 0 or train["y"].sum() == 0:
            continue
        Xtr = train[LP_MODEL].to_numpy(float)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        b, _ = M.logit_fit(np.column_stack([np.ones(len(train)), (Xtr - mu) / sd]), train["y"].to_numpy(float), ridge=1.0)
        Xte = np.column_stack([np.ones(len(test)), (test[LP_MODEL].to_numpy(float) - mu) / sd])
        scores = {s: test[s].to_numpy(float) for s in LP_SCORES}
        scores["logistic model (all features)"] = Xte @ b
        for subset, mask in (("all pairs", np.ones(len(test), bool)), ("cross-lab pairs", ~test["same_lab"].to_numpy()),
                             ("same-lab pairs", test["same_lab"].to_numpy())):
            y = test["y"].to_numpy()[mask]
            for name, s in scores.items():
                if name == "same_lab" and subset != "all pairs":
                    continue
                rows.append({"test_year": t, "subset": subset, "method": name, "candidates": int(mask.sum()),
                             "new_links": int(y.sum()), "auc": M.auc(s[mask], y), "average_precision": M.average_precision(s[mask], y),
                             "base_rate": y.mean() if len(y) else np.nan})
    return pd.DataFrame(rows)


HAZ_MODELS = {
    "1 lab": ["same_lab"],
    "2 + department, topic": ["same_lab", "same_department", "topic_similarity"],
    "3 + network structure, output": ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product"],
    "4 + seniority": ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product",
                      "seniority_sum", "seniority_gap", "seniority_missing"],
    "5 + lab x shared co-authors": ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product",
                                    "seniority_sum", "seniority_gap", "seniority_missing", "same_lab_x_log_cn"],
}


def _design(P: pd.DataFrame, cols: list[str]) -> np.ndarray:
    years = sorted(P["year"].unique())
    fe = np.column_stack([(P["year"] == y).to_numpy(float) for y in years[1:]]) if len(years) > 1 else np.empty((len(P), 0))
    return np.column_stack([np.ones(len(P)), P[cols].to_numpy(float), fe])


def tie_formation(P: pd.DataFrame, D: Data, n_perm: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    P = P.copy()
    P["same_lab_x_log_cn"] = P["same_lab"] * P["log_cn"]
    y = P["y"].to_numpy(float)
    coef, fit = [], []
    ll0 = len(y) * (y.mean() * np.log(y.mean()) + (1 - y.mean()) * np.log(1 - y.mean()))
    for name, cols in HAZ_MODELS.items():
        X = _design(P, cols)
        b, bread = M.logit_fit(X, y)
        V = M.dyadic_robust_cov(X, y, b, bread, P["a"].to_numpy(), P["b"].to_numpy())
        se_n, se_d = np.sqrt(np.diag(bread)), np.sqrt(np.clip(np.diag(V), 0, None))
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        ll = float((y * np.log(p + 1e-300) + (1 - y) * np.log(1 - p + 1e-300)).sum())
        fit.append({"model": name, "observations": len(y), "new_links": int(y.sum()), "pairs": P[["a", "b"]].drop_duplicates().shape[0],
                    "years": f"{P['year'].min()}-{P['year'].max()}", "log_likelihood": ll, "mcfadden_r2": 1 - ll / ll0,
                    "in_sample_auc": M.auc(X @ b, y.astype(bool)), "parameters": X.shape[1]})
        for k, c in enumerate(cols, 1):
            z = b[k] / se_d[k] if se_d[k] > 0 else np.nan
            coef.append({"model": name, "term": c, "coef": b[k], "se_naive": se_n[k], "se_dyadic": se_d[k],
                         "odds_ratio": np.exp(b[k]), "or_low": np.exp(b[k] - 1.96 * se_d[k]), "or_high": np.exp(b[k] + 1.96 * se_d[k]),
                         "z": z, "p": float(2 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan})
    # node-label permutation (QAP-style) for the lab and department terms in model 4
    cols = HAZ_MODELS["4 + seniority"]
    X = _design(P, cols)
    b_obs, _ = M.logit_fit(X, y)
    fac = D.faculty
    labels = [(D.lab[f], D.dept[f]) for f in fac]
    rng = np.random.default_rng(SEED)
    a_idx = P["a"].map({f: i for i, f in enumerate(fac)}).to_numpy()
    b_idx = P["b"].map({f: i for i, f in enumerate(fac)}).to_numpy()
    sims = []
    for _ in range(n_perm):
        perm = rng.permutation(len(fac))
        lab_p = np.array([labels[i][0] for i in perm])
        dep_p = np.array([labels[i][1] for i in perm])
        Xp = X.copy()
        Xp[:, 1] = lab_p[a_idx] == lab_p[b_idx]
        Xp[:, 2] = (lab_p[a_idx] == lab_p[b_idx]) & (dep_p[a_idx] == dep_p[b_idx]) & ~np.isin(dep_p[a_idx], ["", "Unknown"])
        bp, _ = M.logit_fit(Xp, y, iters=30)
        sims.append(bp[1:3])
    sims = np.array(sims)
    perm_rows = []
    for k, term in enumerate(["same_lab", "same_department"]):
        perm_rows.append({"model": "4 + seniority", "term": term, "coef_observed": b_obs[k + 1],
                          "perm_mean": sims[:, k].mean(), "perm_sd": sims[:, k].std(), "perm_p95": np.percentile(sims[:, k], 95),
                          "p_one_sided": (1 + (sims[:, k] >= b_obs[k + 1]).sum()) / (n_perm + 1), "permutations": n_perm})
    return pd.DataFrame(coef), pd.DataFrame(fit), pd.DataFrame(perm_rows)


def holdout_auc(P: pd.DataFrame, split_year: int) -> dict:
    P = P.copy()
    P["same_lab_x_log_cn"] = P["same_lab"] * P["log_cn"]
    cols = HAZ_MODELS["4 + seniority"]
    tr, te = P[P["year"] <= split_year], P[P["year"] > split_year]
    Xtr = np.column_stack([np.ones(len(tr)), tr[cols].to_numpy(float)])   # no year effects: they cannot be extrapolated
    b, _ = M.logit_fit(Xtr, tr["y"].to_numpy(float))
    Xte = np.column_stack([np.ones(len(te)), te[cols].to_numpy(float)])
    return {"train_years": f"{P['year'].min()}-{split_year}", "test_years": f"{split_year + 1}-{P['year'].max()}",
            "test_pairs": len(te), "test_new_links": int(te["y"].sum()), "auc": M.auc(Xte @ b, te["y"].to_numpy()),
            "auc_same_lab_only": M.auc(te["same_lab"].to_numpy(float), te["y"].to_numpy())}


# --------------------------------------------------------------------------- figures

def figures(cfg, D, G_fac, G_all, tails, rob, sis, lp) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import special
    fig_dir = cfg.paths.figures
    made = []
    # degree / citation CCDFs with the power-law fit
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, (name, x) in zip(axes, (("faculty co-authorship degree", [d for _, d in G_fac.degree()]),
                                    ("all-author co-authorship degree", [d for _, d in G_all.degree()]),
                                    ("paper citations", D.citations))):
        x = np.sort(np.asarray(x, float))
        x = x[x >= 1]
        u = np.unique(x)
        ccdf = 1 - np.searchsorted(x, u, side="left") / len(x)
        ax.loglog(u, ccdf, "o", ms=3, color="#4c6ef5", label="data")
        r = tails[tails["distribution"] == name].iloc[0]
        xs = u[u >= r["xmin"]]
        ax.loglog(xs, special.zeta(r["alpha"], xs) / special.zeta(r["alpha"], r["xmin"]) * r["tail_share"], "-", color="#e8590c",
                  label=f"power law a={r['alpha']:.2f}, xmin={int(r['xmin'])}\nbootstrap p={r['gof_p']:.2f}")
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("x")
        ax.set_ylabel("P(X >= x)")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "netmodel_tails.png", dpi=150)
    plt.close(fig)
    made.append("netmodel_tails.png")
    # robustness
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for strat, g in rob.groupby("strategy"):
        axes[0].plot(g["removed_share"], g["lcc_share"], label=strat)
        axes[1].plot(g["removed_share"], g["lab_pairs_joined"], label=strat)
    axes[0].set_xlabel("share of faculty removed")
    axes[0].set_ylabel("largest component / all faculty")
    axes[1].set_xlabel("share of faculty removed")
    axes[1].set_ylabel("lab pairs still connected (of 6)")
    axes[0].legend(fontsize=8)
    for ax in axes:
        ax.set_xlim(0, 0.5)
    fig.tight_layout()
    fig.savefig(fig_dir / "netmodel_robustness.png", dpi=150)
    plt.close(fig)
    made.append("netmodel_robustness.png")
    # SIS
    fig, ax = plt.subplots(figsize=(6, 4))
    for net, g in sis.groupby("network"):
        ax.errorbar(g["lambda_over_qmf"], g["prevalence"], yerr=g["prevalence_sd"], marker="o", ms=3, label=net)
    ax.axvline(1, ls="--", color="grey", lw=1)
    ax.set_xlabel("lambda / (1 / largest eigenvalue)")
    ax.set_ylabel("stationary prevalence")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "netmodel_sis.png", dpi=150)
    plt.close(fig)
    made.append("netmodel_sis.png")
    # link prediction
    fig, ax = plt.subplots(figsize=(7, 4))
    a = lp[lp["subset"] == "all pairs"]
    for m in ["logistic model (all features)", "adamic_adar", "common_neighbours", "preferential_attachment", "same_lab", "topic_similarity"]:
        g = a[a["method"] == m]
        ax.plot(g["test_year"], g["auc"], marker="o", ms=3, label=m)
    ax.axhline(0.5, ls="--", color="grey", lw=1)
    ax.set_xlabel("test year")
    ax.set_ylabel("AUC")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(fig_dir / "netmodel_linkpred.png", dpi=150)
    plt.close(fig)
    made.append("netmodel_linkpred.png")
    return made


# --------------------------------------------------------------------------- run

def json_safe(o):
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, dict):
        return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    return o


def run(cfg, oa, argv=()) -> None:
    quick = "--quick" in argv
    n_boot, n_null, n_random, n_perm, n_si_null = (40, 5, 20, 30, 2) if quick else (300, 50, 100, 200, 10)
    st = cfg.paths.stats
    D = Data(cfg)
    G_fac = D.faculty_graph()
    G_fac_w = D.faculty_graph(weighted=True)
    G_all = D.all_author_graph()
    log.info("faculty network %d nodes / %d links; all-author network %d nodes / %d links",
             G_fac.number_of_nodes(), G_fac.number_of_edges(), G_all.number_of_nodes(), G_all.number_of_edges())

    tails, ccdf = heavy_tails(D, G_fac, G_all, n_boot)
    tails.to_csv(st / "netmodel_degree_fits.csv", index=False, lineterminator="\n")
    ccdf.to_csv(st / "netmodel_ccdf.csv", index=False, lineterminator="\n")

    sw = [{"network": "faculty co-authorship", **M.small_world(G_fac, n_null=n_null, seed=SEED, swap=True)},
          {"network": "all-author co-authorship", **M.small_world(G_all, n_null=max(3, n_null // 10), seed=SEED, swap=False,
                                                                   max_sources=300)}]
    sw = pd.DataFrame(sw)
    sw.to_csv(st / "netmodel_small_world.csv", index=False, lineterminator="\n")
    log.info("M2 small world done")

    rob, rob_sum, cuts = robustness(D, G_fac, n_random)
    rob.to_csv(st / "netmodel_robustness.csv", index=False, lineterminator="\n")
    rob_sum.to_csv(st / "netmodel_robustness_summary.csv", index=False, lineterminator="\n")
    cuts.to_csv(st / "netmodel_lab_cuts.csv", index=False, lineterminator="\n")
    mr = M.molloy_reed(G_fac)
    log.info("M3 robustness done")

    si, si_sum, sis, sis_th = spreading(D, G_fac_w, n_si_null)
    si_sum.to_csv(st / "netmodel_si.csv", index=False, lineterminator="\n")
    sis.to_csv(st / "netmodel_sis.csv", index=False, lineterminator="\n")
    log.info("M4 spreading done")

    start = cfg.window.start
    last_full = cfg.window.cagr_end
    P = dyad_panel(D, range(start + 1, last_full + 1))
    log.info("dyad panel: %d pair-years, %d new links", len(P), int(P["y"].sum()))
    lp = link_prediction(P, range(start + 3, last_full + 1))
    lp.to_csv(st / "netmodel_linkpred.csv", index=False, lineterminator="\n")
    coef, fit, perm = tie_formation(P, D, n_perm)
    coef.to_csv(st / "netmodel_tie_formation.csv", index=False, lineterminator="\n")
    fit.to_csv(st / "netmodel_tie_formation_fit.csv", index=False, lineterminator="\n")
    perm.to_csv(st / "netmodel_tie_permutation.csv", index=False, lineterminator="\n")
    hold = holdout_auc(P, last_full - 3)
    log.info("M5/M6 done")

    made = figures(cfg, D, G_fac, G_all, tails, rob, sis, lp)

    lpa = lp[lp["subset"] == "all pairs"].groupby("method")[["auc", "average_precision"]].mean()
    lpx = lp[lp["subset"] == "cross-lab pairs"].groupby("method")["auc"].mean()
    m4 = coef[coef["model"] == "4 + seniority"].set_index("term")
    summary = {
        "inputs": {"faculty_nodes": G_fac.number_of_nodes(), "faculty_links": G_fac.number_of_edges(),
                   "all_author_nodes": G_all.number_of_nodes(), "all_author_links": G_all.number_of_edges(),
                   "max_authors_for_pairs": D.max_authors, "quick": quick},
        "heavy_tails": tails.drop_duplicates("distribution")[["distribution", "xmin", "alpha", "n_tail", "gof_p",
                                                              "power_law_plausible"]].to_dict("records"),
        "heavy_tails_tests": tails[["distribution", "alternative", "llr", "p", "verdict"]].to_dict("records"),
        "small_world": sw.to_dict("records"),
        "molloy_reed": mr,
        "robustness": rob_sum.to_dict("records"),
        "lab_cuts": cuts.to_dict("records"),
        "si": si_sum.to_dict("records"),
        "sis": sis_th,
        "link_prediction_mean_auc_all": lpa["auc"].to_dict(),
        "link_prediction_mean_ap_all": lpa["average_precision"].to_dict(),
        "link_prediction_mean_auc_cross_lab": lpx.to_dict(),
        "tie_formation_fit": fit.to_dict("records"),
        "tie_formation_model4_or": {t: {"or": r.odds_ratio, "low": r.or_low, "high": r.or_high, "p": r.p} for t, r in m4.iterrows()},
        "tie_formation_permutation": perm.to_dict("records"),
        "tie_formation_holdout": hold,
        "figures": made,
    }
    (st / "netmodel_summary.json").write_text(json.dumps(json_safe(summary), indent=1), encoding="utf-8")
    log.info("wrote netmodel_*.csv, netmodel_summary.json and %d figures", len(made))
