"""S21: team assembly, tie dissolution, brokerage and impact, error sensitivity, temporal paths, communities, and the
extra OpenAlex data (funders, countries, careers, ties before 2016, world citers).

    python -m dpcn run s21            full run
    python -m dpcn run s21 --quick    fewer simulations, for a smoke test

Reads the submitted files, the s18/s19 code paths and, when present, the s20 tables (outputs/stats/enrich_*.csv).

  D1 team assembly         Guimera et al. (2005): share of team slots filled by incumbents (p) and of incumbent pairs that
                           repeat a past collaboration (q), per lab and year, on full author teams and on faculty; then a
                           paper-by-paper growth model of the faculty network (papers as hyperedges) with p, q and lab
                           preference h, against the real network and the s19 pair-by-pair model
  D2 tie dissolution       discrete-time hazard of a new pair writing together again, by years since the first joint paper;
                           life tables same lab vs cross-lab; dyadic-robust errors
  D3 brokerage and impact  faculty-year panel: network position in the previous three years (Burt's constraint, effective
                           size, betweenness, cross-lab ties) and next-year field-normalised citations and output, with
                           faculty and year fixed effects (within-person change) and faculty-clustered errors
  D4 error sensitivity     drop or misassign 5-20% of faculty-paper links, resample faculty, leave one lab out; re-estimate
                           the cross-lab share, the same-lab odds ratio, clustering and lab modularity
  D5 temporal paths        earliest-arrival (time-respecting) reachability between labs vs the static network and vs
                           shuffled contact years
  D6 communities           Louvain consensus and degree-corrected SBM description length of the lab, department and
                           Louvain partitions; agreement (NMI, ARI) with labs and departments
  D7 OpenAlex extras       international co-authorship per lab; shared funders, career age and pre-2016 ties in the tie
                           model; who cites the labs worldwide

Outputs: outputs/stats/dyn_*.csv, dyn_summary.json.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import special, stats

from .. import netmodels as M
from . import StepFailed
from .s18_netmodels import HAZ_MODELS, Data, _design, dyad_panel, json_safe
from .s19_extensions import M_wilson, cluster_cov, graph_stats, or_row, year_fe

log = logging.getLogger("dpcn.s21")
SEED = 42


# --------------------------------------------------------------------------- D1 team assembly

def teams_from_pairs(cfg) -> pd.DataFrame:
    """Full author teams (papers with at most the author cap) rebuilt from the submitted authorship network."""
    e = pd.read_csv(cfg.paths.submission / "authorship_network.csv", dtype=str, keep_default_na=False,
                    usecols=["paper_doi", "year", "author_a_id", "author_b_id"])
    t = pd.concat([e[["paper_doi", "year", "author_a_id"]].rename(columns={"author_a_id": "author"}),
                   e[["paper_doi", "year", "author_b_id"]].rename(columns={"author_b_id": "author"})])
    t = t.drop_duplicates()
    return t.groupby(["paper_doi", "year"])["author"].agg(lambda s: sorted(set(s))).reset_index()


def assembly_params(teams: list[tuple[int, str, list]], start: int) -> pd.DataFrame:
    """p = incumbent share of slots, q = share of incumbent pairs on a team that had written together before.
    Incumbent = appeared on a paper in an earlier year (the first year is burn-in). Computed per (lab, year)."""
    seen, prior = set(), set()
    acc = defaultdict(lambda: [0, 0, 0, 0, 0])   # slots, incumbents, inc pairs, repeated pairs, papers
    by_year = defaultdict(list)
    for y, lab, members in teams:
        by_year[y].append((lab, members))
    for y in sorted(by_year):
        new_seen, new_pairs = set(), set()
        for lab, members in by_year[y]:
            inc = [a for a in members if a in seen]
            for key in ((lab, y), ("ALL", y)):
                r = acc[key]
                r[0] += len(members)
                r[1] += len(inc)
                ip = list(combinations(sorted(inc), 2))
                r[2] += len(ip)
                r[3] += sum(pp in prior for pp in ip)
                r[4] += 1
            new_seen.update(members)
            new_pairs.update(combinations(sorted(members), 2))
        seen |= new_seen
        prior |= new_pairs
    rows = [{"lab": lab, "year": y, "papers": r[4], "slots": r[0], "incumbent_share_p": r[1] / r[0] if r[0] else np.nan,
             "incumbent_pairs": r[2], "repeat_share_q": r[3] / r[2] if r[2] else np.nan} for (lab, y), r in acc.items()]
    P = pd.DataFrame(rows).sort_values(["lab", "year"])
    return P[P["year"] > start - 1]


def team_growth(D: Data, q: float, h: float, n_sims: int, rng) -> list[nx.Graph]:
    """Grow the faculty network paper by paper (papers as hyperedges; Guimera et al. 2005 with lab preference h). Each
    real paper keeps its year, lead lab, number of faculty and number of first-time faculty; the newcomer slots go to
    faculty whose first real paper is in that year (so everyone enters when they really did), and each incumbent slot
    is, with probability q, a past collaborator of an incumbent already on the team, else any incumbent; with
    probability h a pick is restricted to the paper's lead lab."""
    small = D.main[D.main["n_authors"] <= D.max_authors]
    papers = []
    seen = set()
    rows = sorted(((int(g["year"].iat[0]), w, Counter(g["institution"]).most_common(1)[0][0], sorted(set(g["faculty_id"])))
                   for w, g in D.main.groupby("openalex_id")), key=lambda x: (x[0], x[1]))
    capped = set(small["openalex_id"])
    for y, w, lead, fs in rows:
        n_new = sum(f not in seen for f in fs)
        seen.update(fs)
        papers.append((y, lead, len(fs), n_new, w in capped))
    nodes = D.faculty
    lab = D.lab
    out = []
    for _ in range(n_sims):
        order = sorted(papers, key=lambda x: (x[0], rng.random()))
        appeared, nb = set(), defaultdict(set)
        due = defaultdict(list)
        for f in nodes:
            due[D.first[f]].append(f)
        G = nx.Graph()
        G.add_nodes_from(nodes)
        for y, lead, m, n_new, link in order:
            members = []
            for _ in range(n_new):
                cand = [a for a in due[y] if a not in appeared and a not in members]
                if rng.random() < h:
                    cand = [a for a in cand if lab[a] == lead] or cand
                if cand:
                    members.append(cand[rng.integers(len(cand))])
            for _ in range(m - len(members)):
                inc = [a for a in members if a in appeared]
                if inc and rng.random() < q:
                    cand = list(set().union(*(nb[a] for a in inc)) - set(members))
                else:
                    cand = [a for a in appeared if a not in members]
                if rng.random() < h:
                    cand = [a for a in cand if lab[a] == lead] or cand
                if cand:
                    members.append(cand[rng.integers(len(cand))])
            if link:
                for a, b in combinations(members, 2):
                    G.add_edge(a, b)
                    nb[a].add(b)
                    nb[b].add(a)
            appeared.update(members)
        out.append(G)
    return out


def team_assembly(cfg, D: Data, n_sims: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    start = cfg.window.start + 1
    T = teams_from_pairs(cfg)
    doi_lab = D.main.groupby("doi")["institution"].agg(lambda s: Counter(s).most_common(1)[0][0]).to_dict()
    full = [(int(y), doi_lab.get(doi, "other"), m) for doi, y, m in T.itertuples(index=False) if doi in doi_lab]
    small = D.main[D.main["n_authors"] <= D.max_authors]
    fac = [(int(g["year"].iat[0]), Counter(g["institution"]).most_common(1)[0][0], sorted(set(g["faculty_id"])))
           for _, g in small.groupby("openalex_id")]
    Pf = assembly_params(full, start).assign(team="all authors")
    Pc = assembly_params(fac, start).assign(team="faculty only")
    params = pd.concat([Pf, Pc], ignore_index=True)
    allp = params[params["lab"] == "ALL"]

    def pooled(team, col, w):
        g = allp[allp["team"] == team]
        return float(np.average(g[col].fillna(0), weights=g[w].clip(lower=1)))
    p_hat = pooled("faculty only", "incumbent_share_p", "slots")
    q_hat = pooled("faculty only", "repeat_share_q", "incumbent_pairs")
    # lab preference: share of a team's faculty from its lead lab
    tot = same = 0
    for _, lead, members in fac:
        tot += len(members)
        same += sum(D.lab[a] == lead for a in members)
    h_hat = same / tot
    rng = np.random.default_rng(SEED)
    real = D.faculty_graph()
    ref_deg = np.array([d for _, d in real.degree()])
    real_stats = graph_stats(real, D.lab, ref_deg)
    rows = []
    for name, (q, h) in {"team model (q, h)": (q_hat, h_hat), "no repeat collaborators (q = 0)": (0.0, h_hat),
                         "no lab preference (h = 0)": (q_hat, 0.0), "neither (q = 0, h = 0)": (0.0, 0.0)}.items():
        for G in team_growth(D, q, h, n_sims, rng):
            rows.append({"variant": name, **graph_stats(G, D.lab, ref_deg)})
        log.info("D1 %s done", name)
    R = pd.DataFrame(rows)
    summ = []
    for v, g in R.groupby("variant", sort=False):
        for c in [c for c in R.columns if c != "variant"]:
            x = g[c].to_numpy(float)
            o = real_stats.get(c, np.nan)
            summ.append({"variant": v, "statistic": c, "observed": o, "sim_mean": np.nanmean(x), "sim_low": np.nanpercentile(x, 2.5),
                         "sim_high": np.nanpercentile(x, 97.5), "ratio_to_observed": np.nanmean(x) / o if o else np.nan})
    return params, pd.DataFrame(summ), {"p": p_hat, "q": q_hat, "h": h_hat}


# --------------------------------------------------------------------------- D2 tie dissolution

def tie_dissolution(D: Data, end: int, horizon: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = D.events
    years = ev.groupby(["a", "b"])["year"].agg(lambda s: sorted(set(s))).to_dict()
    n_on_first = ev.groupby(["a", "b", "year"]).size().to_dict()
    deg0 = {}
    rows, life = [], []
    T = {y: D.topic_matrix(y, D.faculty) for y in range(D.main["year"].min(), end + 1)}
    ix = {f: i for i, f in enumerate(D.faculty)}
    for (a, b), ys in years.items():
        y0 = ys[0]
        if y0 > end - 1:
            continue
        G = deg0.get(y0)
        if G is None:
            G = deg0[y0] = D.faculty_graph(upto=y0 - 1)
        cn = len(set(G[a]) & set(G[b])) if a in G and b in G else 0
        topic = float(T[y0][ix[a]] @ T[y0][ix[b]])
        later = [y for y in ys if y > y0]
        first_repeat = later[0] if later else None
        same = D.lab[a] == D.lab[b]
        for k in range(1, horizon + 1):
            t = y0 + k
            if t > end:
                break
            y = first_repeat == t
            rows.append({"a": a, "b": b, "formed": y0, "year": t, "since": k, "repeat": y, "same_lab": same, "log_cn_at_formation": np.log1p(cn),
                         "first_year_papers": n_on_first.get((a, b, y0), 1), "topic_similarity": topic})
            if y:
                break
        life.append({"same_lab": same, "formed": y0, "first_repeat_after": (first_repeat - y0) if first_repeat else None,
                     "observed_years": end - y0})
    R = pd.DataFrame(rows)
    R["log_first_year_papers"] = np.log1p(R["first_year_papers"])
    sen = R["a"].map(D.seniority), R["b"].map(D.seniority)
    med = np.nanmedian(list(D.seniority.values()))
    R["seniority_sum"] = sen[0].fillna(med) + sen[1].fillna(med)
    cols = ["same_lab", "log_cn_at_formation", "log_first_year_papers", "topic_similarity", "seniority_sum"]
    X = np.column_stack([np.ones(len(R)), R[cols].to_numpy(float), year_fe(R["since"]), year_fe(R["formed"])])
    y = R["repeat"].to_numpy(float)
    b, bread = M.logit_fit(X, y)
    V = M.dyadic_robust_cov(X, y, b, bread, R["a"].to_numpy(), R["b"].to_numpy())
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    coef = pd.DataFrame([or_row("repeat hazard (years since formation and cohort effects)", c, b[k], se[k],
                                pair_years=len(R), repeats=int(y.sum()), pairs=R[["a", "b"]].drop_duplicates().shape[0])
                         for k, c in enumerate(cols, 1)])
    L = pd.DataFrame(life)
    lt = []
    for same, g in L.groupby("same_lab"):
        surv = 1.0
        for k in range(1, horizon + 1):
            at_risk = g[(g["observed_years"] >= k) & ((g["first_repeat_after"].isna()) | (g["first_repeat_after"] >= k))]
            ev_k = (at_risk["first_repeat_after"] == k).sum()
            n = len(at_risk)
            surv *= (1 - ev_k / n) if n else 1
            lt.append({"pairs": "same lab" if same else "cross-lab", "years_since_formation": k, "at_risk": n, "repeats": int(ev_k),
                       "share_not_yet_repeated": surv})
    return coef, pd.DataFrame(lt)


# --------------------------------------------------------------------------- D3 brokerage and impact

def brokerage_panel(D: Data, start: int, end: int) -> pd.DataFrame:
    d = D.main.drop_duplicates(["faculty_id", "openalex_id"]).copy()
    pap = D.main.drop_duplicates("openalex_id")
    fy_mean = pap.groupby(["field", "year"])["citations"].mean()
    d["norm_cit"] = d["citations"] / d.set_index(["field", "year"]).index.map(fy_mean).to_numpy()
    out_y = d.groupby(["faculty_id", "year"]).agg(papers=("openalex_id", "size"), norm_cit=("norm_cit", "mean")).reset_index()
    rows = []
    ev = D.events
    for t in range(start, end + 1):
        sub = ev[(ev["year"] >= t - 3) & (ev["year"] <= t - 1)]
        G = nx.Graph()
        G.add_nodes_from(D.faculty)
        for (a, b), w in sub.groupby(["a", "b"]).size().items():
            G.add_edge(a, b, weight=int(w))
        con = nx.constraint(G)
        eff = nx.effective_size(G)
        btw = nx.betweenness_centrality(G)
        for f in D.faculty:
            if not (D.first[f] <= t - 1 and D.last[f] >= t):
                continue
            k = G.degree(f)
            rows.append({"faculty_id": f, "year": t, "lab": D.lab[f], "degree": k, "constraint": con.get(f, np.nan) if k else np.nan,
                         "effective_size": eff.get(f, 0) if k else 0, "betweenness": btw.get(f, 0),
                         "cross_lab_ties": sum(D.lab[g] != D.lab[f] for g in G[f])})
    P = pd.DataFrame(rows).merge(out_y, on=["faculty_id", "year"], how="left")
    P["papers"] = P["papers"].fillna(0)
    P["log_papers"] = np.log1p(P["papers"])
    P["log_norm_cit"] = np.log1p(P["norm_cit"])
    P["log_degree"] = np.log1p(P["degree"])
    P["any_cross_lab"] = (P["cross_lab_ties"] > 0).astype(float)
    P["brokerage"] = 1 - P["constraint"].fillna(1).clip(upper=1)     # 0 = closed, 1 = spanning holes
    P["betweenness_x100"] = 100 * P["betweenness"]
    return P


def fe_ols(P: pd.DataFrame, ycol: str, xcols: list[str], fe: str = "faculty_id") -> list[dict]:
    """Two-way fixed effects (faculty and year) by within-faculty demeaning of y, X and year dummies; clustered errors."""
    Q = P.dropna(subset=[ycol, *xcols]).copy()
    Y = pd.get_dummies(Q["year"], prefix="y", drop_first=True).astype(float)
    X = pd.concat([Q[xcols].astype(float), Y], axis=1)
    g = Q[fe]
    Xd = (X - X.groupby(g).transform("mean")).to_numpy()
    yd = (Q[ycol] - Q.groupby(fe)[ycol].transform("mean")).to_numpy()
    keep = np.abs(Xd).sum(1) > 0
    Xd, yd, gg = Xd[keep], yd[keep], g.to_numpy()[keep]
    xtx = np.linalg.pinv(Xd.T @ Xd)
    b = xtx @ Xd.T @ yd
    e = yd - Xd @ b
    _, gi = np.unique(gg, return_inverse=True)
    S = np.zeros((gi.max() + 1, Xd.shape[1]))
    np.add.at(S, gi, Xd * e[:, None])
    G = len(S)
    n_fe = Q[fe].nunique()
    V = xtx @ (S.T @ S) @ xtx * G / (G - 1) * (len(yd) - 1) / max(len(yd) - Xd.shape[1] - n_fe, 1)
    se = np.sqrt(np.diag(V))
    return [{"outcome": ycol, "term": c, "coef": b[k], "se": se[k], "low": b[k] - 1.96 * se[k], "high": b[k] + 1.96 * se[k],
             "p": float(2 * stats.norm.sf(abs(b[k] / se[k]))) if se[k] > 0 else np.nan, "observations": len(yd), "faculty": n_fe}
            for k, c in enumerate(xcols)]


def brokerage_impact(D: Data, start: int, end: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    P = brokerage_panel(D, start, end)
    rows = []
    for spec, xs in (("degree + cross-lab ties", ["log_degree", "any_cross_lab"]),
                     ("degree + brokerage (1 - constraint)", ["log_degree", "brokerage"]),
                     ("degree + betweenness", ["log_degree", "betweenness_x100"])):
        for ycol in ("log_norm_cit", "log_papers"):
            for r in fe_ols(P, ycol, xs):
                rows.append({"model": spec, "estimator": "faculty + year fixed effects", **r})
    return pd.DataFrame(rows), P


# --------------------------------------------------------------------------- D4 error sensitivity

def static_measures(main: pd.DataFrame, lab: dict, dept: dict, subfield_col: str = "subfield", max_authors: int = 50) -> dict:
    small = main[main["n_authors"] <= max_authors]
    G = nx.Graph()
    facs = sorted(set(main["faculty_id"]))
    G.add_nodes_from(facs)
    for _, g in small.groupby("openalex_id"):
        fs = sorted(set(g["faculty_id"]))
        G.add_edges_from(combinations(fs, 2))
    m = G.number_of_edges()
    # topic vectors and paper counts
    sub = main.drop_duplicates(["faculty_id", "openalex_id"])
    cats = {c: i for i, c in enumerate(sorted(sub[subfield_col].unique()))}
    V = np.zeros((len(facs), len(cats)))
    fi = {f: i for i, f in enumerate(facs)}
    for f, s in zip(sub["faculty_id"], sub[subfield_col]):
        V[fi[f], cats[s]] += 1
    npap = V.sum(1)
    Vn = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-12)
    iu = np.triu_indices(len(facs), 1)
    A = nx.to_numpy_array(G, nodelist=facs, weight=None)
    labs = np.array([lab[f] for f in facs])
    deps = np.array([f"{lab[f]}|{dept.get(f, '')}" for f in facs])
    y = A[iu]
    X = np.column_stack([np.ones(len(y)), labs[iu[0]] == labs[iu[1]], (Vn[iu[0]] * Vn[iu[1]]).sum(1),
                         np.log(np.maximum(npap[iu[0]] * npap[iu[1]], 1))]).astype(float)
    b, bread = M.logit_fit(X, y)
    parts = defaultdict(set)
    for f in facs:
        parts[lab[f]].add(f)
    return {"links": m, "cross_lab_share": float(np.mean([lab[a] != lab[c] for a, c in G.edges()])) if m else np.nan,
            "same_lab_or": float(np.exp(b[1])), "clustering": nx.average_clustering(G),
            "lab_modularity": nx.community.modularity(G, list(parts.values())) if m else np.nan}


def error_sensitivity(D: Data, n_reps: int, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    main = D.main.copy()
    main["subfield"] = main["subfield"].replace("", "Unknown")
    base = static_measures(main, D.lab, D.dept)
    rows = [{"scenario": "observed", "rate": 0.0, "rep": 0, **base}]
    fac_by_lab = defaultdict(list)
    for f in D.faculty:
        fac_by_lab[D.lab[f]].append(f)
    allf = np.array(D.faculty)
    for rate in (0.05, 0.10, 0.20):
        for rep in range(n_reps):
            keep = rng.random(len(main)) >= rate
            rows.append({"scenario": "drop links", "rate": rate, "rep": rep, **static_measures(main[keep], D.lab, D.dept)})
            mis = main.copy()
            sel = np.flatnonzero(rng.random(len(mis)) < rate)
            mis.iloc[sel, mis.columns.get_loc("faculty_id")] = [fac_by_lab[D.lab[f]][rng.integers(len(fac_by_lab[D.lab[f]]))]
                                                                for f in mis["faculty_id"].iloc[sel]]
            rows.append({"scenario": "misassign within lab", "rate": rate, "rep": rep, **static_measures(mis, D.lab, D.dept)})
            mis2 = main.copy()
            mis2.iloc[sel, mis2.columns.get_loc("faculty_id")] = allf[rng.integers(len(allf), size=len(sel))]
            rows.append({"scenario": "misassign to any lab", "rate": rate, "rep": rep, **static_measures(mis2, D.lab, D.dept)})
        log.info("D4 rate %.2f done", rate)
    # faculty bootstrap and leave-one-lab-out
    for rep in range(n_boot):
        pick = rng.choice(allf, len(allf), replace=True)
        cnt = Counter(pick)
        sub = main[main["faculty_id"].isin(cnt)]
        rows.append({"scenario": "faculty bootstrap", "rate": np.nan, "rep": rep, **static_measures(sub, D.lab, D.dept)})
    for lab in sorted(set(D.lab.values())):
        sub = main[main["institution"] != lab]
        sub = sub[sub["faculty_id"].map(D.lab) != lab]
        rows.append({"scenario": f"without {lab}", "rate": np.nan, "rep": 0, **static_measures(sub, D.lab, D.dept)})
    R = pd.DataFrame(rows)
    stats_cols = ["cross_lab_share", "same_lab_or", "clustering", "lab_modularity", "links"]
    S = R.groupby(["scenario", "rate"], dropna=False)[stats_cols].agg(["mean", lambda x: np.percentile(x, 2.5), lambda x: np.percentile(x, 97.5)])
    S.columns = [f"{a}_{'mean' if b == 'mean' else ('low' if b == '<lambda_0>' else 'high')}" for a, b in S.columns]
    return S.reset_index(), R


# --------------------------------------------------------------------------- D5 temporal paths

def earliest_arrival(contacts: dict[int, list[tuple[str, str]]], sources: list[str], start: int, end: int,
                     multi_hop: bool) -> dict[str, dict[str, int]]:
    """Earliest year each node is reached from each source along time-respecting paths. multi_hop: several hops may be
    chained inside one year (snapshot reachability); otherwise one hop per year."""
    out = {}
    for s in sources:
        reach = {s: start - 1}
        for y in range(start, end + 1):
            E = contacts.get(y, [])
            if not E:
                continue
            if multi_hop:
                for comp in nx.connected_components(nx.Graph(E)):
                    if any(v in reach for v in comp):
                        for v in comp:
                            reach.setdefault(v, y)
            else:
                new = {}
                for a, b in E:
                    if a in reach and b not in reach:
                        new[b] = y
                    elif b in reach and a not in reach:
                        new[a] = y
                reach.update(new)
        out[s] = reach
    return out


def temporal_paths(D: Data, start: int, end: int, n_null: int) -> tuple[pd.DataFrame, dict]:
    ev = D.events.drop_duplicates(["a", "b", "year"])
    contacts = defaultdict(list)
    for a, b, y in ev[["a", "b", "year"]].itertuples(index=False):
        contacts[int(y)].append((a, b))
    labs = sorted(set(D.lab.values()))
    srcs = [f for f in D.faculty if D.first[f] <= start + 1]

    def lab_reach(arr):
        rows = []
        for s, reach in arr.items():
            for L in labs:
                if L == D.lab[s]:
                    continue
                ys = [y for v, y in reach.items() if D.lab.get(v) == L and v != s]
                rows.append({"source": s, "source_lab": D.lab[s], "target_lab": L, "arrival": min(ys) if ys else None})
        return pd.DataFrame(rows)
    rows = []
    res = {}
    for mode in (True, False):
        A = lab_reach(earliest_arrival(contacts, srcs, start, end, mode))
        res[mode] = A
        rows.append({"network": "observed", "hops": "several per year" if mode else "one per year", "rep": 0,
                     "share_reaching_other_lab": A["arrival"].notna().mean(), "median_arrival_year": A["arrival"].median()})
    # null: contact years shuffled across contacts (keeps the aggregated network and the yearly contact counts)
    rng = np.random.default_rng(SEED)
    years = ev["year"].to_numpy()
    pairs = list(zip(ev["a"], ev["b"]))
    for rep in range(n_null):
        perm = rng.permutation(years)
        c2 = defaultdict(list)
        for (a, b), y in zip(pairs, perm):
            c2[int(y)].append((a, b))
        for mode in (True, False):
            A = lab_reach(earliest_arrival(c2, srcs, start, end, mode))
            rows.append({"network": "shuffled contact years", "hops": "several per year" if mode else "one per year", "rep": rep,
                         "share_reaching_other_lab": A["arrival"].notna().mean(), "median_arrival_year": A["arrival"].median()})
    # static reference: aggregated network over the whole window
    G = D.faculty_graph()
    comp = {v: i for i, c in enumerate(nx.connected_components(G)) for v in c}
    stat = np.mean([any(comp[s] == comp[v] for v in D.faculty if D.lab[v] == L) for s in srcs for L in labs if L != D.lab[s]])
    R = pd.DataFrame(rows)
    by_pair = res[False].groupby(["source_lab", "target_lab"]).agg(sources=("source", "size"),
                                                                    reached=("arrival", lambda x: x.notna().mean()),
                                                                    median_arrival=("arrival", "median")).reset_index()
    return R, {"static_share_reaching_other_lab": float(stat), "sources": len(srcs), "lab_pairs": by_pair.to_dict("records")}


# --------------------------------------------------------------------------- D6 communities

def dcsbm_dl(G: nx.Graph, part: dict) -> dict:
    """Degree-corrected SBM log-likelihood (Karrer & Newman 2011) and a description length that adds the cost of the
    block matrix and the node labels (Peixoto-style approximation), for a fixed partition."""
    blocks = sorted(set(part.values()))
    bi = {b: i for i, b in enumerate(blocks)}
    B = len(blocks)
    m = G.number_of_edges()
    E = np.zeros((B, B))
    for u, v in G.edges():
        i, j = bi[part[u]], bi[part[v]]
        E[i, j] += 1
        E[j, i] += 1
    K = E.sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        L = np.nansum(np.where(E > 0, E * np.log(E / np.outer(K, K)), 0)) / 2
    n = G.number_of_nodes()
    # description length (nats): edges among blocks (multiset coefficient) + node partition + degree sequence term
    S_e = special.gammaln(B * (B + 1) / 2 + m) - special.gammaln(m + 1) - special.gammaln(B * (B + 1) / 2)
    sizes = np.array(list(Counter(part.values()).values()))
    S_b = special.gammaln(n + 1) - special.gammaln(sizes + 1).sum() + np.log(n)
    return {"blocks": B, "log_likelihood": L, "description_length": -L + S_e + S_b}


def communities(D: Data, n_runs: int) -> tuple[pd.DataFrame, dict]:
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    G = M.largest_component(D.faculty_graph())
    nodes = sorted(G)
    labs = [D.lab[v] for v in nodes]
    deps = [f"{D.lab[v]}|{D.dept.get(v, '')}" for v in nodes]
    runs = []
    co = np.zeros((len(nodes), len(nodes)))
    ix = {v: i for i, v in enumerate(nodes)}
    for s in range(n_runs):
        comms = nx.community.louvain_communities(G, seed=SEED + s)
        lab_of = {v: k for k, c in enumerate(comms) for v in c}
        runs.append([lab_of[v] for v in nodes])
        for c in comms:
            idx = [ix[v] for v in c]
            co[np.ix_(idx, idx)] += 1
    co /= n_runs
    # consensus: Louvain on the graph of pairs placed together in at least half of the runs
    W = np.where(co >= 0.5, co, 0)            # Lancichinetti & Fortunato (2012): cluster the co-occurrence matrix
    np.fill_diagonal(W, 0)
    C = nx.from_numpy_array(W)
    cons = {v: k for k, c in enumerate(nx.community.louvain_communities(C, weight="weight", seed=SEED)) for v in c}
    consensus = [cons[i] for i in range(len(nodes))]
    rows = []
    for name, lab_list in (("labs", labs), ("lab departments", deps), ("Louvain consensus", consensus)):
        part = dict(zip(nodes, lab_list))
        dl = dcsbm_dl(G, part)
        rows.append({"partition": name, **dl, "nmi_with_labs": normalized_mutual_info_score(labs, lab_list),
                     "ari_with_labs": adjusted_rand_score(labs, lab_list), "nmi_with_departments": normalized_mutual_info_score(deps, lab_list),
                     "modularity": nx.community.modularity(G, [set(v for v, l in part.items() if l == k) for k in set(lab_list)])})
    nmis = [normalized_mutual_info_score(labs, r) for r in runs]
    purity = []
    cc = Counter(consensus)
    for k, size in cc.items():
        members = [nodes[i] for i in range(len(nodes)) if consensus[i] == k]
        top = Counter(D.lab[v] for v in members).most_common(1)[0][1]
        purity.append(top / size)
    summ = {"louvain_runs": n_runs, "nmi_runs_mean": float(np.mean(nmis)), "nmi_runs_sd": float(np.std(nmis)),
            "consensus_communities": len(cc), "consensus_mean_lab_purity_weighted": float(np.average(purity, weights=list(cc.values()))),
            "consensus_communities_spanning_labs": int(sum(p < 0.9 for p in purity))}
    return pd.DataFrame(rows), summ


# --------------------------------------------------------------------------- D7 OpenAlex extras

def openalex_extras(cfg, D: Data, P: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict]:
    st = cfg.paths.stats
    out, summ = {}, {}
    pap = D.main.drop_duplicates(["openalex_id", "institution"])
    # international vs domestic vs cross-lab
    f = st / "enrich_work_countries.csv"
    if f.exists():
        C = pd.read_csv(f, keep_default_na=False)
        C["international"] = C["international"].astype(str).str.lower() == "true"
        labs_of = D.main.groupby("openalex_id")["institution"].agg(set)
        x = pap.merge(C, on="openalex_id", how="left")
        x["multi_lab"] = x["openalex_id"].map(labs_of).map(len) > 1
        x["indian_partner"] = x["coauthor_institutes"].astype(str).str.len() > 0
        rows = []
        for lab, g in [*x.groupby("institution"), ("ALL", x.drop_duplicates("openalex_id"))]:
            rows.append({"lab": lab, "papers": len(g), "international_share": g["international"].mean(),
                         "other_indian_institution_share": g["indian_partner"].mean(), "another_of_our_labs_share": g["multi_lab"].mean(),
                         "mean_countries": g["n_countries"].replace("", np.nan).astype(float).mean()})
        out["international"] = pd.DataFrame(rows)
    # world citers
    f = st / "enrich_world_citers.csv"
    if f.exists():
        W = pd.read_csv(f, keep_default_na=False)
        Wc = W[W["kind"] == "country"].copy()
        tot = Wc.groupby("lab")["citing_works"].transform("sum")
        Wc["share_of_country_mentions"] = Wc["citing_works"] / tot
        out["world_citers"] = pd.concat([Wc.sort_values(["lab", "citing_works"], ascending=[True, False]).groupby("lab").head(12),
                                         W[W["kind"] == "field"].sort_values(["lab", "citing_works"], ascending=[True, False]).groupby("lab").head(8)])
        summ["india_share_of_citing_country_mentions"] = {lab: float(g.loc[g["key"] == "IN", "share_of_country_mentions"].sum())
                                                         for lab, g in Wc.groupby("lab")}
    # tie model with shared funders, career age and pre-2016 ties
    fu, ca, pt = st / "enrich_work_funders.csv", st / "enrich_faculty_career.csv", st / "enrich_prior_ties.csv"
    if fu.exists() and ca.exists() and pt.exists():
        F = pd.read_csv(fu, keep_default_na=False)
        fp = D.main[["openalex_id", "faculty_id", "year"]].drop_duplicates().merge(F, on="openalex_id")
        fund_by = defaultdict(lambda: defaultdict(set))       # faculty -> year -> funders
        for fid, y, fun in zip(fp["faculty_id"], fp["year"], fp["funder_id"]):
            fund_by[fid][int(y)].add(fun)

        def funders_upto(fid, t):
            s = set()
            for y, v in fund_by[fid].items():
                if y <= t:
                    s |= v
            return s
        cache = {}

        def fu_set(fid, t):
            k = (fid, t)
            if k not in cache:
                cache[k] = funders_upto(fid, t)
            return cache[k]
        Q = P.copy()
        Q["shared_funder"] = [float(bool(fu_set(a, t - 1) & fu_set(b, t - 1))) for a, b, t in zip(Q["a"], Q["b"], Q["year"])]
        car = pd.read_csv(ca).set_index("faculty_id")["first_year_any"]
        car = car.where(car >= 1960).to_dict()        # earlier first years come from merged namesake profiles
        ca_a = Q["year"] - Q["a"].map(car)
        ca_b = Q["year"] - Q["b"].map(car)
        med = np.nanmedian(pd.concat([ca_a, ca_b]))
        Q["career_age_sum_dec"] = (ca_a.fillna(med) + ca_b.fillna(med)) / 10
        Q["career_age_gap_dec"] = (ca_a.fillna(med) - ca_b.fillna(med)).abs() / 10
        PT = pd.read_csv(pt)
        prior = {(r.a, r.b) if r.a < r.b else (r.b, r.a) for r in PT.itertuples()}
        Q["tie_before_2016"] = [float((a, b) in prior) for a, b in zip(Q["a"], Q["b"])]
        base = ["same_lab", "same_department", "topic_similarity", "log_cn", "log_pa", "log_output_product"]
        rows = []
        for name, cols in (("model 3 + shared funder", base + ["shared_funder"]),
                           ("model 3 + career age (decades)", base + ["career_age_sum_dec", "career_age_gap_dec"]),
                           ("model 3 + tie before 2016", base + ["tie_before_2016"]),
                           ("all extras", base + ["shared_funder", "career_age_sum_dec", "career_age_gap_dec", "tie_before_2016"])):
            X = _design(Q, cols)
            y = Q["y"].to_numpy(float)
            b, bread = M.logit_fit(X, y)
            V = M.dyadic_robust_cov(X, y, b, bread, Q["a"].to_numpy(), Q["b"].to_numpy())
            se = np.sqrt(np.clip(np.diag(V), 0, None))
            for k, c in enumerate(cols, 1):
                rows.append(or_row(name, c, b[k], se[k], observations=len(Q)))
        out["tie_extras"] = pd.DataFrame(rows)
        summ["shared_funder_share_new_links"] = float(Q.loc[Q["y"], "shared_funder"].mean())
        summ["shared_funder_share_unlinked"] = float(Q.loc[~Q["y"], "shared_funder"].mean())
        summ["pairs_with_tie_before_2016_in_risk_set"] = int(Q["tie_before_2016"].sum())
        top = F.merge(pap[["openalex_id", "institution"]], on="openalex_id").groupby(["institution", "funder"]).size() \
            .rename("papers").reset_index().sort_values(["institution", "papers"], ascending=[True, False]).groupby("institution").head(8)
        out["funders"] = top
        summ["papers_with_funder"] = int(F["openalex_id"].nunique())
    return out, summ


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    quick = "--quick" in argv
    n_team, n_reps, n_boot, n_null, n_louvain = (3, 3, 10, 3, 10) if quick else (30, 20, 200, 50, 100)
    st = cfg.paths.stats
    start, end = cfg.window.start + 1, cfg.window.cagr_end
    D = Data(cfg)
    summary = {"quick": quick}

    params, team_sim, pqh = team_assembly(cfg, D, n_team)
    params.to_csv(st / "dyn_team_params.csv", index=False, lineterminator="\n")
    team_sim.to_csv(st / "dyn_team_model.csv", index=False, lineterminator="\n")
    summary["team_assembly"] = pqh

    coef, life = tie_dissolution(D, end)
    coef.to_csv(st / "dyn_tie_repeat.csv", index=False, lineterminator="\n")
    life.to_csv(st / "dyn_tie_life_table.csv", index=False, lineterminator="\n")
    log.info("D2 done")

    bi, panel = brokerage_impact(D, start, end)
    bi.to_csv(st / "dyn_brokerage_impact.csv", index=False, lineterminator="\n")
    summary["brokerage_panel"] = {"faculty_years": len(panel), "faculty": panel["faculty_id"].nunique(),
                                  "with_cross_lab_tie": float(panel["any_cross_lab"].mean())}
    log.info("D3 done")

    es, _ = error_sensitivity(D, n_reps, n_boot)
    es.to_csv(st / "dyn_error_sensitivity.csv", index=False, lineterminator="\n")

    tp, tps = temporal_paths(D, cfg.window.start, end, n_null)
    tp.to_csv(st / "dyn_temporal_paths.csv", index=False, lineterminator="\n")
    summary["temporal_paths"] = tps
    log.info("D5 done")

    cm, cms = communities(D, n_louvain)
    cm.to_csv(st / "dyn_communities.csv", index=False, lineterminator="\n")
    summary["communities"] = cms
    log.info("D6 done")

    P = dyad_panel(D, range(start, end + 1))
    extras, xs = openalex_extras(cfg, D, P)
    for k, v in extras.items():
        v.to_csv(st / f"dyn_{k}.csv", index=False, lineterminator="\n")
    summary["openalex_extras"] = xs
    if not extras:
        log.warning("no enrich_*.csv tables: run s20 for the OpenAlex extras")
    (st / "dyn_summary.json").write_text(json.dumps(json_safe(summary), indent=1), encoding="utf-8")
    log.info("wrote dyn_*.csv and dyn_summary.json")
