"""S27: methods from the instructor's papers that none of the 29 other reviewed groups did (inspiration.md, section 12).

  F1 P1, the full random walk   variance of yearly output changes by career-age bin (years since a faculty member's
                                first OpenAlex paper, from s20), with a faculty-block bootstrap and a permutation test;
                                exponential fit of first-year output; is cumulative output lognormal?
  F2 P8, group size and Gibrat  each PI's research group per year (distinct non-faculty lab co-authors); Gibrat's law
                                log(s[t+1]/s[t]) ~ log s[t]; department size against output per faculty member
  F3 P6, does co-authorship predict citation?  logistic model over ordered faculty pairs: i cites j (no shared author)
                                ~ earlier co-authorship + network distance + topic similarity + output + same lab, so
                                "cite because similar" is separated from "cite because co-author"
  F4 P3, citations around the first joint paper  event study of i->j citations before and after a pair's first joint
                                paper, against pairs at distance 2 that never co-author (difference in differences);
                                Weibull fit of the post-collaboration citation profile
  F5 P9, early diversity -> later success  entropy of each faculty member's 2016-20 partner sectors (university,
                                hospital, company, government, facility, foreign) against 2021-26 output and impact,
                                with a reshuffling null stratified by lab and early output
  F6 P10, stock and flow        does a lab's share of internationally collaborative faculty change because of who joins,
                                who leaves, or because the same people change? (entry / exit / within decomposition)

Outputs: outputs/stats/first_*.csv and first_summary.json. Randomness is seeded.
"""
from __future__ import annotations

import json
import logging
import math
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import StepFailed
from .s17_research import SEED, Data, json_safe, logit, ols_hc1, topic_vectors

log = logging.getLogger("dpcn.s27")


def write(df, cfg, name):
    df.to_csv(cfg.paths.stats / name, index=False, encoding="utf-8", lineterminator="\n")


def faculty_year(D: Data, cap: int = 100) -> pd.DataFrame:
    n_auth = D.works["n_authors"].to_dict()
    rows = [(f, D.year[w]) for w, fs in D.fac.items() if n_auth.get(w, 0) < cap for f in fs]
    M = pd.DataFrame(rows, columns=["f", "y"]).value_counts().unstack(fill_value=0)
    return M.reindex(columns=range(2016, 2026), fill_value=0)


# --------------------------------------------------------------------------- F1 P1 by career age

def p1_career(D: Data, cfg, rng) -> tuple[pd.DataFrame, dict]:
    car = cfg.paths.stats / "enrich_faculty_career.csv"
    if not car.exists():
        raise StepFailed("outputs/stats/enrich_faculty_career.csv missing - run s20 first")
    first = pd.read_csv(car).set_index("faculty_id")["first_year_any"]
    M = faculty_year(D)
    M = M[M.sum(axis=1) >= 3]
    rows = []
    for f, r in M.iterrows():
        q = r.to_numpy(float)
        fy = first.get(f)
        if fy != fy or fy is None:
            continue
        for t in range(len(q) - 1):
            rows.append((f, 2016 + t - fy, q[t + 1] - q[t]))
    X = pd.DataFrame(rows, columns=["f", "age", "delta"])
    X = X[X["age"] >= 0]
    bins = [0, 10, 20, 30, 80]
    labels = ["0–9", "10–19", "20–29", "30+"]
    X["bin"] = pd.cut(X["age"], bins, right=False, labels=labels)

    def alpha(d):                     # Laplace scale: mean absolute deviation from the median
        return float(np.mean(np.abs(d - np.median(d)))) if len(d) else np.nan
    out = []
    fac = X["f"].unique()
    boots = {b: [] for b in labels}
    for _ in range(1000):
        pick = rng.choice(fac, len(fac))
        B = X.set_index("f").loc[pick].reset_index()
        for b in labels:
            boots[b].append(alpha(B.loc[B["bin"] == b, "delta"].to_numpy()))
    for b in labels:
        d = X.loc[X["bin"] == b, "delta"].to_numpy()
        out.append({"career_age": b, "faculty_years": len(d), "faculty": int(X.loc[X["bin"] == b, "f"].nunique()),
                    "laplace_alpha": alpha(d), "alpha_lo": np.nanpercentile(boots[b], 2.5), "alpha_hi": np.nanpercentile(boots[b], 97.5),
                    "mean_output": float(M.loc[X.loc[X["bin"] == b, "f"].unique()].to_numpy().mean()) if len(d) else np.nan})
    T = pd.DataFrame(out)
    T["relative_alpha"] = T["laplace_alpha"] / T["mean_output"]      # swings relative to the typical output at that age
    # permutation test: does variance fall with career age? Spearman of |delta - median| with age, shuffling ages across faculty
    dev = np.abs(X["delta"] - X["delta"].median())
    obs = stats.spearmanr(X["age"], dev)[0]
    fa = X.groupby("f")["age"].min()
    null = []
    for _ in range(1000):
        sh = dict(zip(fa.index, rng.permutation(fa.to_numpy())))
        age2 = X["f"].map(sh) + (X["age"] - X["f"].map(fa))
        null.append(stats.spearmanr(age2, dev)[0])
    # first-year output: exponential fit; cumulative output: lognormal vs power law (likelihood ratio, Vuong)
    q0 = M.iloc[:, 0].to_numpy(float)
    q0 = q0[q0 > 0]
    cum = M.sum(axis=1).to_numpy(float)
    ln = stats.lognorm.fit(cum, floc=0)
    ll_ln = stats.lognorm.logpdf(cum, *ln)
    a_pl = 1 + len(cum) / np.sum(np.log(cum / (cum.min() - 0.5)))
    ll_pl = np.log((a_pl - 1) / (cum.min() - 0.5)) - a_pl * np.log(cum / (cum.min() - 0.5))
    dl = ll_ln - ll_pl
    R, sd = dl.sum(), dl.std(ddof=1)
    S = {"faculty": int(X["f"].nunique()), "rho_age_variability": obs, "p_perm": float(np.mean(np.abs(null) >= abs(obs))),
         "first_year_exp_rate": 1 / q0.mean(), "cumulative_lognormal_mu": math.log(ln[2]), "cumulative_lognormal_sigma": ln[0],
         "lognormal_vs_powerlaw_R": float(R), "lognormal_vs_powerlaw_p": float(2 * stats.norm.sf(abs(R) / (sd * math.sqrt(len(dl)))))}
    return T, S


# --------------------------------------------------------------------------- F2 P8 group size, Gibrat

def p8_groups(D: Data, cfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    a = D.auth
    n_auth = D.works["n_authors"].to_dict()
    nonfac = a[a["our_lab"].notna() & a["faculty_id"].isna() & a["author_id"].notna()]
    members = nonfac.groupby("work_id")["author_id"].agg(set).to_dict()
    size = defaultdict(set)
    for w, fs in D.fac.items():
        if n_auth.get(w, 0) > 50:
            continue
        for f in fs:
            size[(f, D.year[w])] |= members.get(w, set())
    S = pd.Series({k: len(v) for k, v in size.items()})
    S.index = pd.MultiIndex.from_tuples(S.index, names=["f", "y"])
    G = S.unstack(fill_value=0).reindex(columns=range(2016, 2026), fill_value=0)
    rows = []
    for f, r in G.iterrows():
        s = r.to_numpy(float)
        for t in range(len(s) - 1):
            if s[t] >= 1 and s[t + 1] >= 1:
                rows.append((f, s[t], s[t + 1]))
    T = pd.DataFrame(rows, columns=["f", "s0", "s1"])
    x, y = np.log(T["s0"]), np.log(T["s1"] / T["s0"])
    X = np.column_stack([np.ones(len(x)), x])
    b, se = ols_hc1(X, y.to_numpy())
    # department size vs output per faculty member (P8)
    dept = pd.Series(D.dept)
    papers = pd.Series(Counter(f for fs in D.fac.values() for f in fs))
    dd = pd.DataFrame({"dept": dept, "lab": pd.Series(D.fac_lab), "papers": papers}).dropna(subset=["dept", "lab"])
    dd = dd[dd["dept"].astype(str).str.len() > 0]
    agg = dd.groupby(["lab", "dept"]).agg(faculty=("papers", "size"), papers=("papers", "sum")).reset_index()
    agg["papers_per_faculty"] = agg["papers"] / agg["faculty"]
    ok = agg[agg["faculty"] >= 2]
    sl = stats.linregress(np.log(ok["faculty"]), np.log(ok["papers_per_faculty"].clip(lower=0.1)))
    dist = G.to_numpy().ravel()
    dist = dist[dist > 0]
    summ = {"gibrat_slope": b[1], "gibrat_se": se[1], "gibrat_ci": [b[1] - 1.96 * se[1], b[1] + 1.96 * se[1]], "transitions": len(T),
            "median_group": float(np.median(dist)), "max_group": int(dist.max()),
            "dept_size_slope": sl.slope, "dept_size_p": sl.pvalue, "departments": len(ok)}
    hist = pd.Series(dist).value_counts().sort_index().rename_axis("group_size").reset_index(name="faculty_years")
    return hist, agg, summ


# --------------------------------------------------------------------------- F3 P6 co-authorship -> citation

def p6_citation(D: Data, rng) -> tuple[pd.DataFrame, dict]:
    fac = D.faculty
    ix = {f: i for i, f in enumerate(fac)}
    n = len(fac)
    cites = np.zeros((n, n), bool)
    for s, t in zip(D.internal["src"], D.internal["tgt"]):
        fs, ft = D.fac.get(s, set()), D.fac.get(t, set())
        if D.authors.get(s, set()) & D.authors.get(t, set()):
            continue                    # shared author: self-citation, not a citation between people
        for a in fs:
            for b in ft:
                if a != b:
                    cites[ix[a], ix[b]] = True
    G = nx.Graph()
    G.add_nodes_from(fac)
    G.add_edges_from({(a, b) for a, b, *_ in D.coauth.itertuples(index=False)})
    dist = dict(nx.all_pairs_shortest_path_length(G, cutoff=4))
    tv = topic_vectors(D)
    papers = Counter(f for fs in D.fac.values() for f in fs)
    rows = []
    for a in fac:
        va = tv.get(a)
        for b in fac:
            if a == b:
                continue
            d = dist.get(a, {}).get(b)
            vb = tv.get(b)
            cos = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb))) if va is not None and vb is not None and np.linalg.norm(va) and np.linalg.norm(vb) else 0.0
            rows.append((cites[ix[a], ix[b]], d == 1, d == 2, d is not None and d >= 3, cos, math.log1p(papers[a]), math.log1p(papers[b]),
                         D.fac_lab.get(a) == D.fac_lab.get(b)))
    P = pd.DataFrame(rows, columns=["cites", "coauthor", "dist2", "dist3plus", "topic", "log_out_i", "log_in_j", "same_lab"]).astype(float)
    models = [("co-authorship alone", ["coauthor"]), ("+ topic similarity", ["coauthor", "topic"]),
              ("+ distance, output, same lab", ["coauthor", "dist2", "dist3plus", "topic", "log_out_i", "log_in_j", "same_lab"])]
    out = []
    for name, cols in models:
        X = np.column_stack([np.ones(len(P))] + [P[c] for c in cols])
        b, se = logit(X, P["cites"].to_numpy())
        for i, c in enumerate(cols, 1):
            out.append({"model": name, "term": c, "odds_ratio": math.exp(b[i]), "or_lo": math.exp(b[i] - 1.96 * se[i]),
                        "or_hi": math.exp(b[i] + 1.96 * se[i]), "p": float(2 * stats.norm.sf(abs(b[i] / se[i]))), "pairs": len(P)})
    T = pd.DataFrame(out)
    full = T[T["model"].str.startswith("+ distance")].set_index("term")
    alone = T[T["model"] == "co-authorship alone"].set_index("term")
    S = {"pairs": len(P), "citing_pairs": int(P["cites"].sum()), "or_coauthor_alone": alone.loc["coauthor", "odds_ratio"],
         "or_coauthor_full": full.loc["coauthor", "odds_ratio"], "or_topic_full": full.loc["topic", "odds_ratio"],
         "share_of_effect_left": math.log(full.loc["coauthor", "odds_ratio"]) / math.log(alone.loc["coauthor", "odds_ratio"])}
    return T, S


# --------------------------------------------------------------------------- F4 P3 event study + Weibull

def p3_event(D: Data, rng) -> tuple[pd.DataFrame, dict]:
    # directed citations per (citer, cited, year), independent of shared authors
    cy = Counter()
    for s, t in zip(D.internal["src"], D.internal["tgt"]):
        if D.authors.get(s, set()) & D.authors.get(t, set()):
            continue
        for a in D.fac.get(s, set()):
            for b in D.fac.get(t, set()):
                if a != b:
                    cy[(a, b, D.year[s])] += 1
    first = D.first_year                               # (a, b) sorted -> first joint year
    treated = [(a, b, y) for (a, b), y in first.items() if 2018 <= y <= 2022]
    # controls: pairs at distance 2 at the end of year y-1 that never co-author, same first-exposure year
    G = nx.Graph()
    ctrl = []
    by_year = defaultdict(list)
    for (a, b), y in first.items():
        by_year[y].append((a, b))
    for y in range(2016, 2023):
        G.add_edges_from(by_year.get(y - 1, []))
        if y < 2018:
            continue
        cand = set()
        for v in G:
            nb = list(G[v])
            for i in range(len(nb)):
                for j in range(i + 1, len(nb)):
                    p = tuple(sorted((nb[i], nb[j])))
                    if not G.has_edge(*p) and p not in first:
                        cand.add(p)
        cand = sorted(cand)
        k = min(len(cand), 3 * sum(1 for t in treated if t[2] == y))
        for i in rng.choice(len(cand), k, replace=False) if k else []:
            ctrl.append((*cand[i], y))
    rows = []
    for grp, pairs in (("first joint paper", treated), ("distance-2 control", ctrl)):
        for a, b, y in pairs:
            for tau in range(-3, 7):
                yr = y + tau
                if 2016 <= yr <= 2025:
                    rows.append((grp, tau, cy.get((a, b, yr), 0) + cy.get((b, a, yr), 0)))
    E = pd.DataFrame(rows, columns=["group", "tau", "cites"])
    T = E.groupby(["group", "tau"])["cites"].agg(["mean", "count", "std"]).reset_index()
    T["lo"] = T["mean"] - 1.96 * T["std"] / np.sqrt(T["count"])
    T["hi"] = T["mean"] + 1.96 * T["std"] / np.sqrt(T["count"])
    pre = lambda g: E[(E["group"] == g) & (E["tau"] < 0)]["cites"].mean()
    post = lambda g: E[(E["group"] == g) & (E["tau"] >= 1)]["cites"].mean()
    did = (post("first joint paper") - pre("first joint paper")) - (post("distance-2 control") - pre("distance-2 control"))
    # pair-level change (mean after minus mean before), resampled over pairs
    pair_stats = {}
    for g, pairs in (("first joint paper", treated), ("distance-2 control", ctrl)):
        st = []
        for a, b, y in pairs:
            pr = [cy.get((a, b, y + t), 0) + cy.get((b, a, y + t), 0) for t in (-3, -2, -1) if 2016 <= y + t <= 2025]
            po = [cy.get((a, b, y + t), 0) + cy.get((b, a, y + t), 0) for t in range(1, 7) if 2016 <= y + t <= 2025]
            if pr and po:
                st.append(np.mean(po) - np.mean(pr))
        pair_stats[g] = np.array(st)
    tA, cA = pair_stats["first joint paper"], pair_stats["distance-2 control"]
    boot = [rng.choice(tA, len(tA)).mean() - rng.choice(cA, len(cA)).mean() for _ in range(2000)]
    # Weibull shape of the post-collaboration profile (treated minus control), tau = 1..6
    prof = T.pivot(index="tau", columns="group", values="mean")
    excess = (prof["first joint paper"] - prof["distance-2 control"]).loc[1:6].clip(lower=1e-6)
    tt = excess.index.to_numpy(float)

    def weib(t, A, k, lam):
        return A * (k / lam) * (t / lam) ** (k - 1) * np.exp(-(t / lam) ** k)
    try:
        par, _ = optimize.curve_fit(weib, tt, excess.to_numpy(), p0=[excess.sum(), 1.5, 3], bounds=([0, 0.2, 0.3], [100, 10, 30]), maxfev=20000)
        peak = par[2] * ((par[1] - 1) / par[1]) ** (1 / par[1]) if par[1] > 1 else 0.0
    except Exception:                                   # noqa: BLE001
        par, peak = [np.nan] * 3, np.nan
    S = {"treated_pairs": len(treated), "control_pairs": len(ctrl), "did": float(np.mean(tA) - np.mean(cA)),
         "did_ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
         "pre_treated": pre("first joint paper"), "pre_control": pre("distance-2 control"),
         "weibull_shape": par[1], "weibull_scale": par[2], "weibull_peak_years": peak}
    return T, S


# --------------------------------------------------------------------------- F5 P9 diversity -> success

def p9_diversity(D: Data, cfg, rng) -> tuple[pd.DataFrame, dict]:
    inst = pd.read_parquet(cfg.paths.interim / "institutions.parquet").set_index("inst_id")
    ours = set(inst.index[inst["our_lab"].notna()])
    ty, cc = inst["type"].to_dict(), inst["country_code"].to_dict()
    per = D.auth.explode("inst_ids").dropna(subset=["inst_ids"]).groupby("work_id")["inst_ids"].agg(set).to_dict()
    n_auth = D.works["n_authors"].to_dict()
    sect = defaultdict(Counter)
    for w, fs in D.fac.items():
        if D.year[w] > 2020 or n_auth.get(w, 0) > 50:
            continue
        kinds = set()
        for i in per.get(w, set()) - ours:
            kinds.add("foreign" if cc.get(i) not in (None, "IN") else (ty.get(i) or "other"))
        for f in fs:
            for k in kinds:
                sect[f][k] += 1
    def H(c):
        v = np.array(list(c.values()), float)
        return float(-(v / v.sum() * np.log2(v / v.sum())).sum()) if v.sum() else 0.0
    mean_fy = D.works.groupby(["field", "year"])["cited_by_count"].transform("mean")
    ncs = (D.works["cited_by_count"] / mean_fy.replace(0, np.nan)).to_dict()
    rows = []
    for f in D.faculty:
        early = [w for w, fs in D.fac.items() if f in fs and D.year[w] <= 2020]
        late = [w for w, fs in D.fac.items() if f in fs and D.year[w] >= 2021]
        if len(early) < 3:
            continue
        rows.append({"faculty_id": f, "lab": D.fac_lab.get(f), "entropy": H(sect[f]), "early_papers": len(early), "late_papers": len(late),
                     "late_ncs": np.nanmean([ncs.get(w, np.nan) for w in late]) if late else np.nan})
    P = pd.DataFrame(rows)
    P["tercile"] = P.groupby("lab")["early_papers"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    out = []
    for y in ("late_papers", "late_ncs"):
        Q = P.dropna(subset=[y])
        yy = np.log1p(Q[y]) if y == "late_papers" else Q[y]
        obs = stats.spearmanr(Q["entropy"], yy)[0]
        null = []
        for _ in range(2000):
            sh = Q.groupby(["lab", "tercile"])["entropy"].transform(lambda s: rng.permutation(s.to_numpy()))
            null.append(stats.spearmanr(sh, yy)[0])
        out.append({"outcome": y, "faculty": len(Q), "spearman": obs, "null_mean": float(np.mean(null)),
                    "null_lo": float(np.percentile(null, 2.5)), "null_hi": float(np.percentile(null, 97.5)),
                    "p": float(np.mean(np.abs(np.array(null) - np.mean(null)) >= abs(obs - np.mean(null))))})
    T = pd.DataFrame(out)
    return T, {"faculty": len(P), "median_entropy_bits": float(P["entropy"].median())}


# --------------------------------------------------------------------------- F6 P10 stock and flow

def p10_flows(D: Data, cfg) -> tuple[pd.DataFrame, dict]:
    cw = cfg.paths.stats / "enrich_work_countries.csv"
    if not cw.exists():
        raise StepFailed("outputs/stats/enrich_work_countries.csv missing - run s20 first")
    w = pd.read_csv(cw)
    intl = dict(zip(w["openalex_id"].str.rsplit("/", n=1).str[-1], w["international"].astype(str).str.lower() == "true"))
    fy = defaultdict(lambda: [0, 0])
    for wid, fs in D.fac.items():
        for f in fs:
            fy[(f, D.year[wid])][0] += 1
            fy[(f, D.year[wid])][1] += int(intl.get(wid, False))
    act = pd.DataFrame([(f, y, n, k) for (f, y), (n, k) in fy.items()], columns=["f", "y", "n", "k"])
    act = act[act["y"] <= 2025]
    span = act.groupby("f")["y"].agg(["min", "max"])
    rows = []
    for lab in sorted(set(D.fac_lab.values())):
        fl = [f for f in span.index if D.fac_lab.get(f) == lab]
        for y in range(2018, 2026):
            def state(yr):         # active in a 3-year window ending at yr; attribute = >= 1/3 of those papers international
                a = act[(act["f"].isin(fl)) & act["y"].between(yr - 2, yr)].groupby("f")[["n", "k"]].sum()
                return (a["k"] / a["n"] >= 1 / 3)
            s0, s1 = state(y - 1), state(y)
            stay = s0.index.intersection(s1.index)
            ent, ex = s1.index.difference(s0.index), s0.index.difference(s1.index)
            n0, n1 = len(s0), len(s1)
            if not n0 or not n1:
                continue
            share0, share1 = s0.mean(), s1.mean()
            # contributions to the change in share: entrants, leavers, and the same people changing
            within = (s1[stay].astype(int) - s0[stay].astype(int)).sum() / n1
            entry = (s1[ent].sum() - len(ent) * share0) / n1
            exit_ = -(s0[ex].sum() - len(ex) * share0) / n1
            rows.append({"lab": lab, "year": y, "faculty_active": n1, "share_international": share1, "change": share1 - share0,
                         "entry": entry, "exit": exit_, "within": within, "residual": (share1 - share0) - entry - exit_ - within,
                         "entrants": len(ent), "leavers": len(ex)})
    T = pd.DataFrame(rows)
    tot = T[["change", "entry", "exit", "within"]].abs().sum()
    S = {"share_from_within": float(tot["within"] / (tot["entry"] + tot["exit"] + tot["within"])),
         "share_from_entry": float(tot["entry"] / (tot["entry"] + tot["exit"] + tot["within"])),
         "share_from_exit": float(tot["exit"] / (tot["entry"] + tot["exit"] + tot["within"]))}
    return T, S


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    rng = np.random.default_rng(SEED)
    D = Data(cfg)
    T1, S1 = p1_career(D, cfg, rng); write(T1, cfg, "first_p1_career.csv")
    H2, A2, S2 = p8_groups(D, cfg); write(H2, cfg, "first_p8_group_sizes.csv"); write(A2, cfg, "first_p8_departments.csv")
    T3, S3 = p6_citation(D, rng); write(T3, cfg, "first_p6_citation_model.csv")
    T4, S4 = p3_event(D, rng); write(T4, cfg, "first_p3_event.csv")
    T5, S5 = p9_diversity(D, cfg, rng); write(T5, cfg, "first_p9_diversity.csv")
    T6, S6 = p10_flows(D, cfg); write(T6, cfg, "first_p10_flows.csv")
    young, old = T1.iloc[0], T1.iloc[-1]
    f = [
        f"P1 by career age: in absolute terms yearly output swings {'grow' if old.laplace_alpha > young.laplace_alpha else 'shrink'} with seniority "
        f"(Laplace scale {young.laplace_alpha:.2f} papers in the first decade of a career, {old.laplace_alpha:.2f} after 30 years; Spearman with career age "
        f"{S1['rho_age_variability']:.2f}, permutation p = {S1['p_perm']:.3f}). "
        + (f"Relative to their higher output they shrink ({young.relative_alpha:.2f} vs {old.relative_alpha:.2f} of the mean), as Zhang et al. found. "
           if old.relative_alpha < young.relative_alpha else
           f"This is not only because senior faculty publish more: relative to output the swings also grow ({young.relative_alpha:.2f} vs {old.relative_alpha:.2f} "
           f"of the mean), the opposite of Zhang et al.'s computer scientists, whose variability falls over a career. ")
        + f"Cumulative output is "
        f"{'lognormal rather than power-law' if S1['lognormal_vs_powerlaw_R'] > 0 else 'closer to a power law than lognormal'} "
        f"(likelihood ratio {S1['lognormal_vs_powerlaw_R']:.0f}, p = {S1['lognormal_vs_powerlaw_p']:.3f}).",
        f"P8 research groups: a PI's group (distinct students, postdocs and staff on their papers that year) has median size {S2['median_group']:.0f}; "
        f"its growth follows Gibrat's law {'only partly: large groups grow more slowly' if S2['gibrat_ci'][1] < 0 else 'closely: growth does not depend on size'} "
        f"(slope {S2['gibrat_slope']:.2f}, 95% CI {S2['gibrat_ci'][0]:.2f} to {S2['gibrat_ci'][1]:.2f}; 0 = Gibrat). Across {S2['departments']} departments, "
        f"papers per faculty member {('show no clear relation to' if S2['dept_size_p'] >= 0.05 else 'fall with' if S2['dept_size_slope'] < 0 else 'rise with')} department size (log–log slope {S2['dept_size_slope']:.2f}, p = {S2['dept_size_p']:.2f}).",
        f"P6 co-authorship and citation: having written together multiplies the odds that one faculty member cites the other (independent citations only) by "
        f"{S3['or_coauthor_alone']:.0f} alone and still {S3['or_coauthor_full']:.1f} after topic similarity, network distance, output and lab are held equal, "
        f"so citation follows the social tie, not just shared interests ({S3['citing_pairs']:,} citing pairs of {S3['pairs']:,}).",
        f"P3 around the first joint paper: pairs who start writing together cite each other {S4['did']:+.2f} times more per year afterwards than "
        f"distance-2 pairs who never do (difference in differences, 95% CI {S4['did_ci'][0]:+.2f} to {S4['did_ci'][1]:+.2f}; {S4['treated_pairs']} new pairs); "
        + (f"the extra citations peak about {S4['weibull_peak_years']:.1f} years after the first paper (Weibull shape {S4['weibull_shape']:.1f})." if S4['weibull_shape'] > 1 else
         f"the extra citations are largest right after the first paper and fade slowly (Weibull shape {S4['weibull_shape']:.1f} < 1, scale {S4['weibull_scale']:.1f} years)."),
    ]
    for r in T5.itertuples():
        f.append(f"P9 early diversity: faculty whose 2016–20 partners spanned more sectors (universities, hospitals, industry, government, abroad) "
                 f"{'had' if r.p < 0.05 else 'did not clearly have'} {'more' if r.spearman > r.null_mean else 'less'} "
                 f"{'2021–26 output' if r.outcome == 'late_papers' else 'field-normalised impact in 2021–26'} (Spearman {r.spearman:.2f} vs {r.null_mean:.2f} "
                 f"in a reshuffle within lab and early-output tercile, p = {r.p:.3f}).")
    f.append(f"P10 stock and flow: changes in each lab's share of internationally collaborative faculty come {S6['share_from_within']:.0%} from the same people "
             f"changing, {S6['share_from_entry']:.0%} from who joins and {S6['share_from_exit']:.0%} from who leaves.")
    S = {"p1": S1, "p8": S2, "p6": S3, "p3": S4, "p9": S5, "p10": S6, "findings": f,
         "methods": {"p1": "Faculty-year paper counts (< 100 authors, 2016–2025), career age from the first OpenAlex paper (s20); Laplace scale per career-age bin with a 1,000-draw faculty bootstrap; permutation of career ages across faculty; lognormal vs power-law likelihood ratio (Vuong).",
                     "p8": "Group = distinct non-roster lab co-authors on a PI's papers (≤ 50 authors) in a year; Gibrat regression of log growth on log size with HC1 errors; log–log regression of papers per faculty on department size (departments with ≥ 2 faculty).",
                     "p6": "Logistic regression over all ordered faculty pairs: cites (any independent citation, no shared author) on co-authorship, distance 2 and 3+, topic cosine, log output, same lab.",
                     "p3": "Event study of yearly citations between a pair from 3 years before to 6 after its first joint paper (2018–2022), against 3 random distance-2 pairs per new pair that never co-author; pair-bootstrap difference in differences; Weibull curve fitted to the excess.",
                     "p9": "Shannon entropy of partner sectors on 2016–20 papers (faculty with ≥ 3); Spearman with 2021–26 log papers and mean normalised citations; 2,000 reshuffles within lab × early-output tercile.",
                     "p10": "Faculty active in a 3-year window; attribute = at least a third of their papers in that window with a foreign co-author (s20 countries); change in the share split into entrants, leavers and within-person change."}}
    (cfg.paths.stats / "first_summary.json").write_text(json.dumps(json_safe(S), ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    for s in f:
        print(" -", s)
