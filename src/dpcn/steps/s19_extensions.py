"""S19: robustness checks and network-dynamics extensions for the paper.

    python -m dpcn run s19            full run
    python -m dpcn run s19 --quick    fewer simulations / shuffles, for a smoke test

Reads the submitted files (group29_data.csv, citation_network.csv) and the s17/s18 outputs. Technique tags use paper
titles and OpenAlex topics; the secondary topics come from data/interim/works_raw when it exists and the tags are saved
to outputs/stats/ext_technique_papers.csv, which later runs reuse, so the analysis reruns from committed files.

  E1 specification curve   the same-lab effect on new collaborations under every combination of author cap (20/50/100),
                           risk-set rule (with or without look-ahead), years (with or without 2020-22), hubs (kept or
                           dropped) and controls (lab + year, or the full model)
  E2 technique diffusion   do faculty take up a method (CRISPR, sequencing, docking, machine learning, ...) after their
                           co-authors do? Discrete-time adoption hazard with exposure counts (simple vs complex
                           contagion), same-lab vs cross-lab exposure, adoptions not through a joint paper, and the
                           shuffle test of Anagnostopoulos et al. (2008) that separates influence from homophily
  E3 simplicial closure    do three faculty who have each worked in pairs go on to write a paper together? Closure
                           probability by the number and strength of pairwise ties (Benson et al. 2018, PNAS)
  E4 generative model      grow the network year by year from the fitted tie-formation model and check which
                           ingredient (lab, shared co-authors, degree, topic) is needed to reproduce the real network
  E5 COVID-19 shock        did collaborations formed on SARS-CoV-2 work last beyond the pandemic, especially across labs?
  E6 citation before collaboration  does citing a colleague's work predict starting to write with them?
  E7 test registry         every p-value in s17, s18 and s19, with Benjamini-Hochberg q across the whole set

Outputs: outputs/stats/ext_*.csv, ext_summary.json. Randomness is seeded.
"""
from __future__ import annotations

import gzip
import json
import logging
import re
from collections import defaultdict
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

from .. import netmodels as M
from . import StepFailed
from .s18_netmodels import Data, _design, dyad_panel, json_safe

log = logging.getLogger("dpcn.s19")
SEED = 42
COVID = re.compile(r"sars-cov-2|covid|coronavirus|pandemic", re.I)
TECHNIQUES = {
    "CRISPR / genome editing": r"crispr|cas9|cas12|genome[- ]edit",
    "Genome / exome sequencing": r"whole[- ]genome sequenc|whole[- ]exome|exome sequenc|next[- ]generation sequenc|genome sequencing",
    "Molecular docking / simulation": r"molecular docking|docking stud|molecular dynamics simulation|in silico",
    "Machine learning": r"machine learning|deep learning|neural network|artificial intelligence",
    "Metagenomics / microbiome": r"metagenom|microbiome|16s rrna",
    "Nanoparticles / nanocarriers": r"nanoparticle|nanocarrier|nanoformulation|nanoemulsion",
    "Proteomics / mass spectrometry": r"proteom|mass spectrometr",
    "Zebrafish models": r"zebrafish",
}


def bh(p) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1)
    return out


def cluster_cov(X, y, b, bread, groups) -> np.ndarray:
    """One-way cluster-robust covariance for a logit (clusters = faculty)."""
    p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    s = X * (y - p)[:, None]
    _, g = np.unique(np.asarray(groups).astype(str), return_inverse=True)
    S = np.zeros((g.max() + 1, X.shape[1]))
    np.add.at(S, g, s)
    G = len(S)
    return bread @ (S.T @ S) @ bread * G / max(G - 1, 1)


def or_row(name, term, b, se, **extra) -> dict:
    z = b / se if se > 0 else np.nan
    return {"model": name, "term": term, "coef": b, "se": se, "odds_ratio": np.exp(b), "or_low": np.exp(b - 1.96 * se),
            "or_high": np.exp(b + 1.96 * se), "p": float(2 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan, **extra}


def year_fe(years) -> np.ndarray:
    years = np.asarray(years)
    u = np.unique(years)
    return np.column_stack([(years == y).astype(float) for y in u[1:]]) if len(u) > 1 else np.empty((len(years), 0))


# --------------------------------------------------------------------------- E1 specification curve

def spec_curve(cfg, start: int, end: int) -> pd.DataFrame:
    rows = []
    full = ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product",
            "seniority_sum", "seniority_gap", "seniority_missing"]
    for cap in (20, 50, 100):
        D = Data(cfg, max_authors=cap)
        deg = dict(D.faculty_graph().degree())
        hubs = set(sorted(deg, key=lambda f: -deg[f])[:max(1, int(0.05 * len(deg)))])
        for mode in ("span", "recent"):
            P = dyad_panel(D, range(start, end + 1), active_mode=mode)
            for years in ("all years", "without 2020-2022"):
                for hub in ("hubs kept", "top 5% hubs dropped"):
                    Q = P
                    if years != "all years":
                        Q = Q[~Q["year"].between(2020, 2022)]
                    if hub != "hubs kept":
                        Q = Q[~(Q["a"].isin(hubs) | Q["b"].isin(hubs))]
                    for ctrl, cols in (("lab + year", ["same_lab"]), ("full model", full)):
                        X = _design(Q, cols)
                        y = Q["y"].to_numpy(float)
                        b, bread = M.logit_fit(X, y)
                        V = M.dyadic_robust_cov(X, y, b, bread, Q["a"].to_numpy(), Q["b"].to_numpy())
                        se = np.sqrt(np.clip(np.diag(V), 0, None))
                        r = {"author_cap": cap, "risk_set": "no look-ahead" if mode == "recent" else "active span",
                             "years": years, "hubs": hub, "controls": ctrl, "observations": len(Q), "new_links": int(y.sum())}
                        for k, c in enumerate(cols, 1):
                            if c in ("same_lab", "same_department", "log_cn"):
                                r[f"{c}_or"] = np.exp(b[k])
                                r[f"{c}_low"] = np.exp(b[k] - 1.96 * se[k])
                                r[f"{c}_high"] = np.exp(b[k] + 1.96 * se[k])
                        rows.append(r)
        log.info("E1 cap %d done", cap)
    S = pd.DataFrame(rows)
    S["spec_rank"] = S["same_lab_or"].rank(method="first").astype(int)
    return S


# --------------------------------------------------------------------------- technique tags

def paper_topics(cfg, ids: set[str]) -> dict[str, list[str]]:
    raw = cfg.paths.interim / "works_raw"
    out = {}
    if not raw.exists():
        return out
    for f in sorted(raw.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as h:
            for line in h:
                w = json.loads(line)
                if w["id"] in ids and w["id"] not in out:
                    out[w["id"]] = [t.get("display_name", "") for t in (w.get("topics") or [])]
    return out


def technique_tags(cfg, D: Data) -> pd.DataFrame:
    path = cfg.paths.stats / "ext_technique_papers.csv"
    pap = D.main.drop_duplicates("openalex_id")[["openalex_id", "title", "primary_topic"]]
    topics = paper_topics(cfg, set(pap["openalex_id"]))
    if not topics and path.exists():
        log.info("works_raw not found: reusing %s", cfg.rel(path))
        return pd.read_csv(path, dtype=str)
    rows = []
    for w, title, pt in pap.itertuples(index=False):
        text = " | ".join([title, pt, *topics.get(w, [])])
        for tech, pat in TECHNIQUES.items():
            if re.search(pat, text, re.I):
                rows.append({"openalex_id": w, "technique": tech, "source": "title+topics" if w in topics else "title+primary topic"})
    T = pd.DataFrame(rows)
    T.to_csv(path, index=False, lineterminator="\n")
    return T


# --------------------------------------------------------------------------- E2 technique diffusion

class Diffusion:
    """Faculty-year adoption panel for each technique, with exposure from the co-authorship network of earlier years."""

    def __init__(self, D: Data, tags: pd.DataFrame, start: int, end: int):
        self.D = D
        self.nodes = D.faculty
        self.ix = {f: i for i, f in enumerate(self.nodes)}
        self.lab = np.array([D.lab[f] for f in self.nodes])
        self.same_lab = self.lab[:, None] == self.lab[None, :]
        self.years = list(range(start, end + 1))
        self.A = {t: nx.to_numpy_array(D.faculty_graph(upto=t - 1), nodelist=self.nodes, weight=None) for t in self.years}
        self.active = {t: np.array([D.first[f] <= t - 1 and D.last[f] >= t for f in self.nodes]) for t in self.years}
        fp = D.main[["openalex_id", "faculty_id", "year"]].drop_duplicates()
        self.adopt, self.adopt_papers = {}, {}
        for tech, g in tags.groupby("technique"):
            sub = fp[fp["openalex_id"].isin(g["openalex_id"])]
            first = sub.groupby("faculty_id")["year"].min()
            self.adopt[tech] = np.array([first.get(f, 9999) for f in self.nodes], float)
            # faculty on each faculty member's adopting papers (first year) - to tell adoption through a joint paper
            fy = sub.merge(first.rename("fy"), left_on="faculty_id", right_index=True)
            fy = fy[fy["year"] == fy["fy"]]
            on_paper = sub.groupby("openalex_id")["faculty_id"].agg(set).to_dict()
            co = defaultdict(set)
            for w, f in zip(fy["openalex_id"], fy["faculty_id"]):
                co[f] |= on_paper.get(w, set()) - {f}
            self.adopt_papers[tech] = co

    def panel(self, tech: str, adopt: np.ndarray, independent: bool = False) -> pd.DataFrame:
        rows = []
        co = self.adopt_papers[tech]
        for t in self.years:
            prior = adopt <= t - 1
            risk = self.active[t] & ~prior & (adopt >= t)
            if not risk.any():
                continue
            A = self.A[t]
            k = A @ prior
            k_same = (A * self.same_lab) @ prior
            deg = A.sum(1)
            y = adopt == t
            idx = np.flatnonzero(risk)
            for i in idx:
                via = bool(y[i]) and any(adopt[self.ix[c]] <= t - 1 for c in co.get(self.nodes[i], ()) if c in self.ix)
                if independent and via:
                    continue
                rows.append((tech, self.nodes[i], self.lab[i], t, k[i], k_same[i], k[i] - k_same[i], deg[i], bool(y[i]), via))
        return pd.DataFrame(rows, columns=["technique", "faculty_id", "lab", "year", "k", "k_same", "k_cross", "degree", "y", "via_joint_paper"])


def _diff_design(P: pd.DataFrame, spec: str) -> tuple[np.ndarray, list[str]]:
    deg = np.log1p(P["degree"].to_numpy(float))
    k = P["k"].to_numpy(float)
    if spec == "dose":
        cols = ["exposed: 1 adopting co-author", "exposed: 2 adopting co-authors", "exposed: 3+ adopting co-authors"]
        X = np.column_stack([k == 1, k == 2, k >= 3]).astype(float)
    elif spec == "any":
        cols = ["any adopting co-author"]
        X = (k >= 1).astype(float)[:, None]
    elif spec == "split":
        cols = ["same-lab adopting co-authors (log)", "cross-lab adopting co-authors (log)"]
        X = np.column_stack([np.log1p(P["k_same"]), np.log1p(P["k_cross"])])
    else:
        raise ValueError(spec)
    fe = [year_fe(P["year"]), year_fe(P["technique"]), year_fe(P["lab"])]
    return np.column_stack([np.ones(len(P)), X, deg, *fe]), cols + ["degree (log)"]


def diffusion(cfg, D: Data, tags: pd.DataFrame, start: int, end: int, n_shuffle: int):
    Df = Diffusion(D, tags, start, end)
    techs = sorted(Df.adopt)
    P = pd.concat([Df.panel(t, Df.adopt[t]) for t in techs], ignore_index=True)
    Pi = pd.concat([Df.panel(t, Df.adopt[t], independent=True) for t in techs], ignore_index=True)
    coef = []
    for name, data, spec in (("dose-response", P, "dose"), ("same vs cross lab", P, "split"),
                             ("dose-response, adoptions not through a joint paper", Pi, "dose"), ("any exposure", P, "any")):
        X, cols = _diff_design(data, spec)
        y = data["y"].to_numpy(float)
        b, bread = M.logit_fit(X, y)
        V = cluster_cov(X, y, b, bread, data["faculty_id"])
        se = np.sqrt(np.clip(np.diag(V), 0, None))
        for k, c in enumerate(cols, 1):
            coef.append(or_row(name, c, b[k], se[k], observations=len(data), adoptions=int(y.sum())))
    # raw dose-response: adoption rate by number of adopting co-authors (and by degree band, to show it is not degree)
    P["k_band"] = np.where(P["k"] >= 3, "3+", P["k"].astype(int).astype(str))
    P["deg_band"] = pd.cut(P["degree"], [-1, 4, 10, 1000], labels=["degree 0-4", "degree 5-10", "degree 11+"]).astype(str)
    dose = P.groupby(["deg_band", "k_band"]).agg(faculty_years=("y", "size"), adoptions=("y", "sum")).reset_index()
    dose["rate"] = dose["adoptions"] / dose["faculty_years"]
    dose_all = P.groupby("k_band").agg(faculty_years=("y", "size"), adoptions=("y", "sum")).reset_index().assign(deg_band="all")
    dose_all["rate"] = dose_all["adoptions"] / dose_all["faculty_years"]
    # simple contagion: each adopting co-author independently passes the method on with the probability implied by
    # the one-exposure rate; complex contagion would put the 2+ rates above this prediction
    r0 = dose_all.set_index("k_band").at["0", "rate"]
    r1 = dose_all.set_index("k_band").at["1", "rate"]
    e = (r1 - r0) / (1 - r0)
    pred = r0 + (1 - r0) * (1 - (1 - e) ** P["k"].to_numpy(float))
    dose_all["simple_contagion_pred"] = dose_all["k_band"].map(pd.Series(pred).groupby(P["k_band"].to_numpy()).mean())
    dose = pd.concat([dose_all, dose], ignore_index=True)
    lo_hi = [M_wilson(a, n) for a, n in zip(dose["adoptions"], dose["faculty_years"])]
    dose["rate_low"], dose["rate_high"] = [x[0] for x in lo_hi], [x[1] for x in lo_hi]
    # shuffle test: adoption years permuted among each technique's adopters (within the window)
    X, _ = _diff_design(P, "any")
    b_obs, _ = M.logit_fit(X, P["y"].to_numpy(float))
    rng = np.random.default_rng(SEED)
    sims = []
    for s in range(n_shuffle):
        parts = []
        for t in techs:
            a = Df.adopt[t].copy()
            inwin = np.flatnonzero(a <= end)
            a[inwin] = rng.permutation(a[inwin])
            parts.append(Df.panel(t, a))
        Q = pd.concat(parts, ignore_index=True)
        Xq, _ = _diff_design(Q, "any")
        bq, _ = M.logit_fit(Xq, Q["y"].to_numpy(float), iters=30)
        sims.append(bq[1])
    sims = np.array(sims)
    shuffle = {"coef_observed": float(b_obs[1]), "or_observed": float(np.exp(b_obs[1])), "shuffle_mean_coef": float(sims.mean()),
               "shuffle_or_mean": float(np.exp(sims.mean())), "shuffle_sd": float(sims.std()), "shuffles": n_shuffle,
               "p_one_sided": float((1 + (sims >= b_obs[1]).sum()) / (n_shuffle + 1)),
               "shuffle_coefs": [float(x) for x in sims]}
    per_tech = (P.groupby("technique").agg(faculty_years=("y", "size"), adoptions=("y", "sum"),
                                           via_joint_paper=("via_joint_paper", "sum")).reset_index())
    per_tech["adopters_total"] = per_tech["technique"].map({t: int((Df.adopt[t] < 9999).sum()) for t in techs})
    per_tech["papers"] = per_tech["technique"].map(tags.groupby("technique")["openalex_id"].nunique())
    return pd.DataFrame(coef), dose, shuffle, per_tech


def M_wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


# --------------------------------------------------------------------------- E3 simplicial closure

def simplicial_closure(D: Data, split: int, end: int) -> tuple[pd.DataFrame, dict]:
    small = D.main[D.main["n_authors"] <= D.max_authors]
    hyper = [(int(g["year"].iat[0]), frozenset(g["faculty_id"])) for _, g in small.groupby("openalex_id")]
    hyper = [(y, s) for y, s in hyper if len(s) >= 2]
    train = [s for y, s in hyper if y <= split]
    test = [s for y, s in hyper if split < y <= end]
    nodes = sorted({f for f in D.faculty if D.first[f] <= split and D.last[f] > split})
    nset = set(nodes)
    W = defaultdict(int)
    closed_train = set()
    for s in train:
        for a, b in combinations(sorted(s), 2):
            W[(a, b)] += 1
        if len(s) >= 3:
            closed_train.update(combinations(sorted(s), 3))
    closed_test = set()
    for s in test:
        s = sorted(set(s) & nset)
        if len(s) >= 3:
            closed_test.update(combinations(s, 3))
    adj = defaultdict(set)
    for (a, b) in W:
        if a in nset and b in nset:
            adj[a].add(b)
            adj[b].add(a)

    def w(a, b):
        return W.get((a, b) if a < b else (b, a), 0)

    def classify(tr):
        a, b, c = tr
        ws = [w(a, b), w(a, c), w(b, c)]
        e = sum(x > 0 for x in ws)
        labs = {D.lab[a], D.lab[b], D.lab[c]}
        cls = f"{e} pairwise ties"
        if e == 3:
            cls += ", all repeated" if min(ws) >= 2 else ", some single"
        return cls, e, "one lab" if len(labs) == 1 else "mixed labs"
    # triples with at least one train tie (edge x third node), plus every test-closed triple
    seen = {}
    for (a, b) in W:
        if a not in nset or b not in nset:
            continue
        for c in nodes:
            if c != a and c != b:
                tr = tuple(sorted((a, b, c)))
                if tr not in seen and tr not in closed_train:
                    seen[tr] = classify(tr)
    for tr in closed_test:
        if tr not in seen and tr not in closed_train:
            seen[tr] = classify(tr)
    n = len(nodes)
    total = n * (n - 1) * (n - 2) // 6 - len([t for t in closed_train if set(t) <= nset])
    rows = defaultdict(lambda: [0, 0])
    for tr, (cls, e, mix) in seen.items():
        rows[(cls, e, mix)][0] += 1
        rows[(cls, e, mix)][1] += tr in closed_test
        rows[(cls, e, "all")][0] += 1
        rows[(cls, e, "all")][1] += tr in closed_test
    zero_seen = sum(v[0] for (c, e, m), v in rows.items() if e == 0 and m == "all")
    zero_closed = sum(v[1] for (c, e, m), v in rows.items() if e == 0 and m == "all")
    zero_total = total - sum(v[0] for (c, e, m), v in rows.items() if e > 0 and m == "all")
    rows[("0 pairwise ties", 0, "all")] = [zero_total, zero_closed]
    out = []
    for (cls, e, mix), (k, c) in rows.items():
        if e == 0 and mix != "all":
            continue
        lo, hi = M_wilson(c, k)
        out.append({"configuration": cls, "pairwise_ties": e, "labs": mix, "triples": k, "closed": c, "closure_rate": c / k if k else np.nan,
                    "rate_low": lo, "rate_high": hi})
    T = pd.DataFrame(out).sort_values(["labs", "pairwise_ties", "configuration"]).reset_index(drop=True)
    g = T[T["labs"] == "all"].set_index("configuration")

    def get(c, f):
        return g.loc[c, f] if c in g.index else 0
    two_k, two_c = get("2 pairwise ties", "triples"), get("2 pairwise ties", "closed")
    thr_k = get("3 pairwise ties, all repeated", "triples") + get("3 pairwise ties, some single", "triples")
    thr_c = get("3 pairwise ties, all repeated", "closed") + get("3 pairwise ties, some single", "closed")
    odds, p = stats.fisher_exact([[thr_c, thr_k - thr_c], [two_c, two_k - two_c]]) if thr_k and two_k else (np.nan, np.nan)
    rep_k, rep_c = get("3 pairwise ties, all repeated", "triples"), get("3 pairwise ties, all repeated", "closed")
    odds_r, p_r = stats.fisher_exact([[rep_c, rep_k - rep_c], [two_c, two_k - two_c]]) if rep_k and two_k else (np.nan, np.nan)
    m = T[T["pairwise_ties"] == 2].set_index("labs")
    mix_k, mix_c = (m.at["mixed labs", "triples"], m.at["mixed labs", "closed"]) if "mixed labs" in m.index else (0, 0)
    one_k, one_c = (m.at["one lab", "triples"], m.at["one lab", "closed"]) if "one lab" in m.index else (0, 0)
    odds_m, p_m = stats.fisher_exact([[mix_c, mix_k - mix_c], [one_c, one_k - one_c]]) if mix_k and one_k else (np.nan, np.nan)
    summ = {"repeated_triangle_vs_wedge_odds_ratio": odds_r, "repeated_triangle_vs_wedge_p": p_r,
            "wedge_mixed_vs_one_lab_odds_ratio": odds_m, "wedge_mixed_vs_one_lab_p": p_m,
            "train_years": f"{D.main['year'].min()}-{split}", "test_years": f"{split + 1}-{end}", "faculty": n,
            "train_papers": len(train), "test_papers": len(test), "triples_closed_in_test": len(closed_test),
            "open_triangle_vs_wedge_odds_ratio": odds, "open_triangle_vs_wedge_p": p, "zero_tie_triples_seen": zero_seen}
    return T, summ


# --------------------------------------------------------------------------- E4 generative model

GEN_VARIANTS = {
    "full model": ["same_lab", "topic_similarity", "log_cn", "log_pa"],
    "without lab": ["topic_similarity", "log_cn", "log_pa"],
    "without shared co-authors": ["same_lab", "topic_similarity", "log_pa"],
    "without degree": ["same_lab", "topic_similarity", "log_cn"],
    "without topic": ["same_lab", "log_cn", "log_pa"],
    "random (no terms)": [],
}


def graph_stats(G: nx.Graph, lab: dict, ref_deg: np.ndarray | None = None) -> dict:
    m = G.number_of_edges()
    H = M.largest_component(G)
    deg = np.array([d for _, d in G.degree()])
    parts = defaultdict(set)
    for v in G:
        parts[lab[v]].add(v)
    out = {"links": m, "cross_lab_share": sum(lab[a] != lab[b] for a, b in G.edges()) / m if m else np.nan,
           "clustering": nx.average_clustering(G), "transitivity": nx.transitivity(G),
           "lcc_share": H.number_of_nodes() / G.number_of_nodes(), "path_length": nx.average_shortest_path_length(H) if H.number_of_nodes() > 1 else np.nan,
           "lab_modularity": nx.community.modularity(G, list(parts.values())) if m else np.nan,
           "max_degree": int(deg.max()), "degree_sd": float(deg.std())}
    if ref_deg is not None:
        out["degree_ks"] = float(stats.ks_2samp(deg, ref_deg).statistic)
    return out


def generative(cfg, D: Data, P: pd.DataFrame, start: int, end: int, n_sims: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Grow the network from the links of the first year: each later year adds as many links between active, unlinked
    pairs as really formed, drawn with probability proportional to exp(x'b), where x is recomputed on the simulated
    network every year and b comes from a logit with year effects fitted to the real pair-years."""
    nodes = D.faculty
    ix = {f: i for i, f in enumerate(nodes)}
    lab = D.lab
    lab_arr = np.array([lab[f] for f in nodes])
    G0 = D.faculty_graph(upto=start - 1)
    obs = G0.copy()
    for a, b in P.loc[P["y"], ["a", "b"]].itertuples(index=False):
        obs.add_edge(a, b)
    ref_deg = np.array([d for _, d in obs.degree()])
    obs_stats = graph_stats(obs, lab, ref_deg)
    m_t = P.groupby("year")["y"].sum().to_dict()
    topics = {t: D.topic_matrix(t - 1, nodes) for t in range(start, end + 1)}
    active = {t: np.array(sorted(ix[f] for f in set(P.loc[P["year"] == t, "a"]) | set(P.loc[P["year"] == t, "b"]))) for t in range(start, end + 1)}
    params = []
    rows = []
    rng = np.random.default_rng(SEED)
    for name, cols in GEN_VARIANTS.items():
        if cols:
            X = _design(P, cols)
            b, bread = M.logit_fit(X, P["y"].to_numpy(float))
            beta = dict(zip(cols, b[1:1 + len(cols)]))
        else:
            beta = {}
        params.append({"variant": name, **{f"b_{k}": v for k, v in beta.items()}})
        for s in range(n_sims):
            A = nx.to_numpy_array(G0, nodelist=nodes, weight=None)
            for t in range(start, end + 1):
                act = active[t]
                if len(act) < 2 or not m_t.get(t):
                    continue
                Aa = A[np.ix_(act, act)]
                iu = np.triu_indices(len(act), 1)
                free = Aa[iu] == 0
                ia, ib = iu[0][free], iu[1][free]
                score = np.zeros(len(ia))
                if "same_lab" in beta:
                    score += beta["same_lab"] * (lab_arr[act][ia] == lab_arr[act][ib])
                if "topic_similarity" in beta:
                    T = topics[t][act]
                    score += beta["topic_similarity"] * (T[ia] * T[ib]).sum(1)
                if "log_cn" in beta or "log_pa" in beta:
                    deg = A.sum(1)[act]
                    if "log_cn" in beta:
                        CN = (A[act] @ A[:, act])
                        score += beta["log_cn"] * np.log1p(CN[ia, ib])
                    if "log_pa" in beta:
                        score += beta["log_pa"] * np.log1p(deg[ia] * deg[ib])
                w = np.exp(score - score.max())
                k = min(int(m_t[t]), len(w))
                pick = rng.choice(len(w), size=k, replace=False, p=w / w.sum())
                A[act[ia[pick]], act[ib[pick]]] = 1
                A[act[ib[pick]], act[ia[pick]]] = 1
            G = nx.from_numpy_array(A)
            G = nx.relabel_nodes(G, dict(enumerate(nodes)))
            rows.append({"variant": name, "sim": s, **graph_stats(G, lab, ref_deg)})
        log.info("E4 %s done", name)
    R = pd.DataFrame(rows)
    stats_cols = [c for c in R.columns if c not in ("variant", "sim")]
    summ = []
    for name, g in R.groupby("variant", sort=False):
        for c in stats_cols:
            v = g[c].to_numpy(float)
            o = obs_stats.get(c, np.nan)
            summ.append({"variant": name, "statistic": c, "observed": o, "sim_mean": np.nanmean(v), "sim_low": np.nanpercentile(v, 2.5),
                         "sim_high": np.nanpercentile(v, 97.5), "observed_inside_95": bool(np.nanpercentile(v, 2.5) <= o <= np.nanpercentile(v, 97.5)) if np.isfinite(o) else None,
                         "ratio_to_observed": np.nanmean(v) / o if o else np.nan})
    S = pd.DataFrame(summ)
    return S, pd.DataFrame(params)


# --------------------------------------------------------------------------- E5 COVID-19 shock

def covid_shock(cfg, D: Data, topics: dict[str, list[str]], end: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    small = D.main[D.main["n_authors"] <= D.max_authors]
    pap = small.drop_duplicates("openalex_id").set_index("openalex_id")
    is_cov = {w: bool(COVID.search(" | ".join([r.title, r.primary_topic, *topics.get(w, [])]))) for w, r in pap.iterrows()}
    fac = small.groupby("openalex_id")["faculty_id"].agg(lambda s: sorted(set(s)))
    pair_papers = defaultdict(list)
    for w, fs in fac.items():
        for a, b in combinations(fs, 2):
            pair_papers[(a, b)].append((int(pap.at[w, "year"]), is_cov[w]))
    rows = []
    for (a, b), pp in pair_papers.items():
        y0 = min(y for y, _ in pp)
        if not 2020 <= y0 <= 2022:
            continue
        formed_covid = any(c for y, c in pp if y == y0)
        later = [(y, c) for y, c in pp if y > y0]
        rows.append({"a": a, "b": b, "year": y0, "formed_on_covid": formed_covid, "same_lab": D.lab[a] == D.lab[b],
                     "later_any": bool(later), "later_non_covid": any(not c for y, c in later),
                     "later_within_3y": any(y <= y0 + 3 for y, _ in later)})
    T = pd.DataFrame(rows)
    out = []
    for lab_t, g0 in (("all pairs", T), ("same lab", T[T["same_lab"]]), ("cross-lab", T[~T["same_lab"]])):
        for cov, g in g0.groupby("formed_on_covid"):
            for outcome in ("later_any", "later_non_covid", "later_within_3y"):
                k, n = int(g[outcome].sum()), len(g)
                lo, hi = M_wilson(k, n)
                out.append({"pairs": lab_t, "formed_on": "COVID-19 paper" if cov else "other paper", "outcome": outcome,
                            "new_pairs": n, "continued": k, "share": k / n if n else np.nan, "low": lo, "high": hi})
        g1, g2 = g0[g0["formed_on_covid"]], g0[~g0["formed_on_covid"]]
        if len(g1) and len(g2):
            for outcome in ("later_any", "later_non_covid"):
                odds, p = stats.fisher_exact([[g1[outcome].sum(), len(g1) - g1[outcome].sum()], [g2[outcome].sum(), len(g2) - g2[outcome].sum()]])
                out.append({"pairs": lab_t, "formed_on": "COVID vs other (Fisher)", "outcome": outcome, "new_pairs": len(g0),
                            "continued": np.nan, "share": odds, "low": np.nan, "high": np.nan, "p": p})
    O = pd.DataFrame(out)
    # yearly new links by lab type and topic
    yr = []
    for (a, b), pp in pair_papers.items():
        y0 = min(y for y, _ in pp)
        yr.append({"year": y0, "cross_lab": D.lab[a] != D.lab[b], "covid": any(c for y, c in pp if y == y0)})
    Y = pd.DataFrame(yr).groupby(["year", "cross_lab", "covid"]).size().rename("new_links").reset_index()
    # logit: continuing (any later joint paper) ~ covid * cross-lab + year
    X = np.column_stack([np.ones(len(T)), T["formed_on_covid"], ~T["same_lab"], T["formed_on_covid"] & ~T["same_lab"], year_fe(T["year"])]).astype(float)
    y = T["later_any"].to_numpy(float)
    b, bread = M.logit_fit(X, y, ridge=0.01)
    V = M.dyadic_robust_cov(X, y, b, bread, T["a"].to_numpy(), T["b"].to_numpy())
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    L = pd.DataFrame([or_row("continuation ~ COVID x cross-lab + year", t, b[k], se[k], n_pairs=len(T))
                      for k, t in enumerate(["formed on COVID paper", "cross-lab pair", "COVID x cross-lab"], 1)])
    return pd.concat([O, L.assign(kind="logit")], ignore_index=True), Y, T


# --------------------------------------------------------------------------- E6 citation before collaboration

def citation_before_collab(cfg, D: Data, P: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cn = pd.read_csv(cfg.paths.submission / "citation_network.csv", dtype=str, keep_default_na=False,
                     usecols=["source_openalex_id", "target_openalex_id", "year", "edge_scope"])
    cn = cn[cn["edge_scope"] == "internal"]
    fac = D.main.groupby("openalex_id")["faculty_id"].agg(set).to_dict()
    ev = defaultdict(list)    # (a, b) undirected -> years of independent citations between them
    for s, t, y in zip(cn["source_openalex_id"], cn["target_openalex_id"], cn["year"]):
        fs, ft = fac.get(s, set()), fac.get(t, set())
        if not fs or not ft or fs & ft:
            continue           # shared faculty author = self-citation of a group
        for a in fs:
            for b in ft:
                ev[(a, b) if a < b else (b, a)].append(int(y))
    yrs = {k: np.sort(v) for k, v in ev.items()}

    def prior(a, b, t):
        v = yrs.get((a, b))
        return 0 if v is None else int(np.searchsorted(v, t - 1, side="right"))
    Q = P.copy()
    Q["prior_citations"] = [prior(a, b, t) for a, b, t in zip(Q["a"], Q["b"], Q["year"])]
    Q["log_prior_citations"] = np.log1p(Q["prior_citations"])
    Q["any_prior_citation"] = (Q["prior_citations"] > 0).astype(float)
    base = ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product",
            "seniority_sum", "seniority_gap", "seniority_missing"]
    rows = []
    for name, cols in (("prior citation only", ["any_prior_citation"]), ("model 4 + any prior citation", base + ["any_prior_citation"]),
                       ("model 4 + log prior citations", base + ["log_prior_citations"])):
        X = _design(Q, cols)
        y = Q["y"].to_numpy(float)
        b, bread = M.logit_fit(X, y)
        V = M.dyadic_robust_cov(X, y, b, bread, Q["a"].to_numpy(), Q["b"].to_numpy())
        se = np.sqrt(np.clip(np.diag(V), 0, None))
        for k, c in enumerate(cols, 1):
            if c in ("any_prior_citation", "log_prior_citations", "same_lab", "topic_similarity", "log_cn"):
                rows.append(or_row(name, c, b[k], se[k], observations=len(Q)))
    formed = Q[Q["y"]]
    summ = {"independent_citation_pairs": len(yrs), "new_links": len(formed),
            "share_new_links_with_prior_citation": float((formed["prior_citations"] > 0).mean()),
            "share_unlinked_pairs_with_prior_citation": float((Q.loc[~Q["y"], "prior_citations"] > 0).mean()),
            "cross_lab_new_links_with_prior_citation": float((formed.loc[~formed["same_lab"], "prior_citations"] > 0).mean()) if (~formed["same_lab"]).any() else None}
    return pd.DataFrame(rows), summ


# --------------------------------------------------------------------------- E7 test registry

def test_registry(st, ext_tests: list[dict]) -> pd.DataFrame:
    rows = []

    def add(source, test, p, effect=None):
        if p is None or not np.isfinite(p):
            return
        rows.append({"source": source, "test": test, "effect": effect, "p": float(p)})

    def read(name):
        f = st / name
        return pd.read_csv(f) if f.exists() else pd.DataFrame()
    r = read("research_lab_exchange_null.csv")
    for x in r.dropna(subset=["p"]).itertuples():
        add("s17 A2 lab exchange", f"{x.basis} | {x.null} | {x.citing_lab} -> {x.cited_lab}", x.p, x.obs_exp)
    r = read("research_coauthor_model.csv")
    for x in r.itertuples():
        add("s17 A3 co-author model", f"{x.model} | {x.term}", 2 * stats.norm.sf(abs(x.coef / x.se)) if x.se > 0 else None, x.odds_ratio)
    r = read("research_led_vs_middle.csv")
    for x in r.drop_duplicates("scope").itertuples():
        add("s17 A5 led vs middle", f"Mann-Whitney | {x.scope}", x.mannwhitney_p_led_vs_middle)
    r = read("research_tie_persistence.csv")
    for x in r.dropna(subset=["fisher_p_cross_vs_same"]).itertuples():
        add("s17 A6 tie persistence", "Fisher cross vs same lab", x.fisher_p_cross_vs_same)
    r = read("research_lab_impact.csv")
    for x in r.itertuples():
        if x.se and x.se > 0:
            add("s17 A7 lab impact", f"{x.model} | {x.term}", 2 * stats.norm.sf(abs(x.coef / x.se)), x.pct_effect)
    r = read("netmodel_degree_fits.csv")
    for x in r.drop_duplicates("distribution").itertuples():
        add("s18 M1 power-law fit", f"bootstrap goodness of fit | {x.distribution}", x.gof_p)
    for x in r.itertuples():
        add("s18 M1 likelihood ratio", f"{x.distribution} vs {x.alternative}", x.p, x.llr)
    r = read("netmodel_tie_formation.csv")
    for x in r[r["model"].str.startswith(("4", "5"))].itertuples():
        add("s18 M6 tie formation", f"{x.model} | {x.term}", x.p, x.odds_ratio)
    r = read("netmodel_tie_permutation.csv")
    for x in r.itertuples():
        add("s18 M6 permutation", f"{x.model} | {x.term}", x.p_one_sided)
    for t in ext_tests:
        add(t["source"], t["test"], t.get("p"), t.get("effect"))
    # later steps (s21, s22), when their outputs exist: rerun s19 after them for a registry of everything
    for name, src in (("dyn_tie_repeat.csv", "s21 D2 tie survival"), ("dyn_tie_extras.csv", "s21 D7 OpenAlex extras")):
        r = read(name)
        for x in r.itertuples():
            add(src, f"{x.model} | {x.term}", x.p, x.odds_ratio)
    r = read("dyn_brokerage_impact.csv")
    for x in r.itertuples():
        add("s21 D3 brokerage and impact", f"{x.model} | {x.outcome} | {x.term}", x.p, x.coef)
    r = read("siena_estimates.csv")
    if len(r):
        for x in r[r["type"] == "eval"].itertuples():
            add("s22 RSiena", f"{x.model} | {x.effect}", x.p, x.estimate)
    R = pd.DataFrame(rows)
    R["q_bh_all"] = bh(R["p"])
    R["significant_p05"] = R["p"] < 0.05
    R["significant_q05"] = R["q_bh_all"] < 0.05
    return R


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    quick = "--quick" in argv
    n_shuffle, n_sims = (20, 5) if quick else (200, 40)
    st = cfg.paths.stats
    if not (st / "netmodel_summary.json").exists():
        raise StepFailed("run s18 before s19 (it reuses the s18 outputs for the test registry)")
    start, end = cfg.window.start + 1, cfg.window.cagr_end
    D = Data(cfg)
    P = dyad_panel(D, range(start, end + 1))
    ext_tests = []
    summary = {"quick": quick}

    spec = spec_curve(cfg, start, end)
    spec.to_csv(st / "ext_spec_curve.csv", index=False, lineterminator="\n")
    summary["spec_curve"] = {"specifications": len(spec), "same_lab_or_min": spec["same_lab_or"].min(), "same_lab_or_median": spec["same_lab_or"].median(),
                             "same_lab_or_max": spec["same_lab_or"].max(), "same_lab_low_min": spec["same_lab_low"].min(),
                             "all_above_1": bool((spec["same_lab_low"] > 1).all()),
                             "same_department_or_range": [spec["same_department_or"].min(), spec["same_department_or"].max()],
                             "same_department_significant_specs": int((spec["same_department_low"] > 1).sum()),
                             "log_cn_or_range": [spec["log_cn_or"].min(), spec["log_cn_or"].max()]}
    log.info("E1 specification curve: %d specs, same-lab OR %.1f-%.1f", len(spec), spec["same_lab_or"].min(), spec["same_lab_or"].max())

    tags = technique_tags(cfg, D)
    dcoef, dose, shuffle, per_tech = diffusion(cfg, D, tags, start, end, n_shuffle)
    dcoef.to_csv(st / "ext_diffusion_models.csv", index=False, lineterminator="\n")
    dose.to_csv(st / "ext_diffusion_dose.csv", index=False, lineterminator="\n")
    per_tech.to_csv(st / "ext_diffusion_techniques.csv", index=False, lineterminator="\n")
    summary["diffusion_shuffle"] = shuffle
    for x in dcoef.itertuples():
        ext_tests.append({"source": "s19 E2 technique diffusion", "test": f"{x.model} | {x.term}", "p": x.p, "effect": x.odds_ratio})
    ext_tests.append({"source": "s19 E2 shuffle test", "test": "influence vs shuffled adoption times", "p": shuffle["p_one_sided"], "effect": shuffle["or_observed"]})
    log.info("E2 diffusion done")

    closure, csum = simplicial_closure(D, split=2020, end=end)
    closure.to_csv(st / "ext_simplicial_closure.csv", index=False, lineterminator="\n")
    summary["simplicial_closure"] = csum
    ext_tests.append({"source": "s19 E3 simplicial closure", "test": "open triangle vs open wedge (Fisher)", "p": csum["open_triangle_vs_wedge_p"],
                      "effect": csum["open_triangle_vs_wedge_odds_ratio"]})
    ext_tests.append({"source": "s19 E3 simplicial closure", "test": "repeated open triangle vs open wedge (Fisher)", "p": csum["repeated_triangle_vs_wedge_p"],
                      "effect": csum["repeated_triangle_vs_wedge_odds_ratio"]})
    ext_tests.append({"source": "s19 E3 simplicial closure", "test": "open wedge: mixed labs vs one lab (Fisher)", "p": csum["wedge_mixed_vs_one_lab_p"],
                      "effect": csum["wedge_mixed_vs_one_lab_odds_ratio"]})
    log.info("E3 simplicial closure done")

    gen, gparams = generative(cfg, D, P, start, end, n_sims)
    gen.to_csv(st / "ext_generative.csv", index=False, lineterminator="\n")
    gparams.to_csv(st / "ext_generative_params.csv", index=False, lineterminator="\n")
    summary["generative_inside_95"] = gen.groupby("variant", sort=False)["observed_inside_95"].sum().to_dict()

    topics = paper_topics(cfg, set(D.main["openalex_id"]))
    cov, cov_year, _ = covid_shock(cfg, D, topics, end)
    cov.to_csv(st / "ext_covid_ties.csv", index=False, lineterminator="\n")
    cov_year.to_csv(st / "ext_covid_new_links.csv", index=False, lineterminator="\n")
    for r in cov.dropna(subset=["p"]).to_dict("records"):
        if r.get("kind") == "logit":
            ext_tests.append({"source": "s19 E5 COVID ties", "test": f"{r['model']} | {r['term']}", "p": r["p"], "effect": r["odds_ratio"]})
        else:
            ext_tests.append({"source": "s19 E5 COVID ties", "test": f"{r['pairs']} | {r['outcome']} | Fisher COVID vs other", "p": r["p"], "effect": r["share"]})
    log.info("E5 COVID done")

    cit, cit_sum = citation_before_collab(cfg, D, P)
    cit.to_csv(st / "ext_citation_before_collab.csv", index=False, lineterminator="\n")
    summary["citation_before_collab"] = cit_sum
    for x in cit.itertuples():
        if "citation" in x.term:
            ext_tests.append({"source": "s19 E6 citation before collaboration", "test": f"{x.model} | {x.term}", "p": x.p, "effect": x.odds_ratio})

    reg = test_registry(st, ext_tests)
    reg.to_csv(st / "ext_test_registry.csv", index=False, lineterminator="\n")
    summary["test_registry"] = {"tests": len(reg), "p_below_05": int(reg["significant_p05"].sum()), "q_below_05": int(reg["significant_q05"].sum()),
                                "lost_after_correction": int((reg["significant_p05"] & ~reg["significant_q05"]).sum())}
    (st / "ext_summary.json").write_text(json.dumps(json_safe(summary), indent=1), encoding="utf-8")
    log.info("wrote ext_*.csv and ext_summary.json")
