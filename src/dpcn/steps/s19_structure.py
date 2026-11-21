"""S19: structure of the faculty network - null models, communities, students, growth, prediction, citation main path.

Faculty network G as in s17: every faculty member with papers is a node, a link joins two faculty who co-authored a
paper with at most `networks.max_authors_for_pairs` authors, weight = number of joint papers.

  B1 null-model table      clustering, transitivity, Louvain Q, degree and lab assortativity, LCC path length and
                           size, components vs Erdos-Renyi G(n,m), degree-preserving rewiring and a bipartite
                           configuration null (faculty-paper incidence shuffled keeping both degree sequences, then
                           projected); filled vs hollow triangles (do the three members share one paper?)
  B2 communities vs org chart  Louvain over 50 seeds (stability = mean pairwise NMI); NMI / ARI / AMI of the best
                           partition vs lab and department with a label-permutation null; k-core decomposition
  B3 students are the glue non-faculty authors of our labs who link faculty pairs that never wrote together;
                           LCC, isolates and cross-lab share with and without these mediated links; top glue people
  B4 growth laws           cumulative network per year: densification exponent (E ~ N^alpha), effective diameter,
                           LCC fraction; preferential attachment kernel A(k) ~ k^gamma (cumulative-kernel method)
  B5 early position -> later output  2016-20 degree, betweenness, Burt constraint, clustering vs 2021-26 output and
                           field-year normalised citations (OLS, HC1, lab fixed effects, standardised predictors)
  B6 fragility of cross-lab links  minimum node / edge cuts between labs, links resting on one paper, links lost
                           when the top cross-lab papers are removed
  B7 link prediction       train 2016-20, test new links 2021-26 (CN, Jaccard, Adamic-Adar, PA, topic cosine,
                           logistic combination); "twins who never co-author" and a back-test of topic similarity
  B8 topic contagion       does a faculty member start publishing in a subfield more often when a prior co-author
                           already publishes there? placebos: future co-authors and random same-lab faculty
  B9 citation main path    SPC weights on the internal citation DAG, global main path; per-lab subfield entropy
                           and year-to-year turnover of the top subfields

Outputs: outputs/stats/research_*.csv (see run) and research_structure.json. Randomness is seeded.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import gammaln

from . import StepFailed
from .s17_research import SEED, Data, json_safe, logit, ols_hc1, pair, topic_vectors, wilson

log = logging.getLogger("dpcn.s19")
N_NULL = 100          # draws per null model
N_LOUVAIN = 50        # Louvain seeds for stability
N_PERM = 1000         # label permutations
N_BOOT = 500          # bootstrap replicates
EARLY = (2016, 2020)
LATE = (2021, 2026)
SHORT_TENURE = 6     # active in our corpus for <= 6 calendar years: proxy for students / postdocs


def _csv(df: pd.DataFrame, st, name: str) -> None:
    df.to_csv(st / name, index=False, lineterminator="\n")


# --------------------------------------------------------------------------- shared helpers

def faculty_graph(D: Data, until: int | None = None, since: int | None = None) -> nx.Graph:
    """Faculty co-authorship graph (all faculty as nodes); weight = number of joint papers in the year range."""
    ev = D.coauth
    if until is not None:
        ev = ev[ev["year"] <= until]
    if since is not None:
        ev = ev[ev["year"] >= since]
    G = nx.Graph()
    G.add_nodes_from(D.faculty)
    for (a, b), n in ev.groupby(["a", "b"])["work_id"].nunique().items():
        G.add_edge(a, b, weight=int(n))
    return G


def lcc(G: nx.Graph) -> set:
    return max(nx.connected_components(G), key=len) if G.number_of_nodes() else set()


def contingency(a, b) -> np.ndarray:
    ai, bi = pd.factorize(pd.Series(list(a)))[0], pd.factorize(pd.Series(list(b)))[0]
    M = np.zeros((ai.max() + 1, bi.max() + 1))
    np.add.at(M, (ai, bi), 1)
    return M


def _h(c: np.ndarray) -> float:
    p = c[c > 0] / c.sum()
    return float(-(p * np.log(p)).sum())


def _mi(M: np.ndarray) -> float:
    n = M.sum()
    a, b = M.sum(1), M.sum(0)
    nz = M > 0
    return float((M[nz] / n * np.log(n * M[nz] / np.outer(a, b)[nz])).sum())


def nmi(a, b) -> float:
    M = contingency(a, b)
    ha, hb = _h(M.sum(1)), _h(M.sum(0))
    if ha == 0 and hb == 0:
        return 1.0
    return _mi(M) / ((ha + hb) / 2) if ha + hb else 0.0


def ari(a, b) -> float:
    M = contingency(a, b)
    c2 = lambda x: x * (x - 1) / 2
    n = M.sum()
    s_ij, s_a, s_b = c2(M).sum(), c2(M.sum(1)).sum(), c2(M.sum(0)).sum()
    exp = s_a * s_b / c2(n)
    mx = (s_a + s_b) / 2
    return float((s_ij - exp) / (mx - exp)) if mx != exp else 1.0


def ami(a, b) -> float:
    """Adjusted mutual information (arithmetic normalisation, as sklearn's default)."""
    M = contingency(a, b)
    N = int(M.sum())
    A, B = M.sum(1).astype(int), M.sum(0).astype(int)
    emi = 0.0
    lgN = gammaln(N + 1)
    for ai in A:
        for bj in B:
            lo, hi = max(1, ai + bj - N), min(ai, bj)
            for nij in range(lo, hi + 1):
                term = nij / N * np.log(N * nij / (ai * bj))
                lw = (gammaln(ai + 1) + gammaln(bj + 1) + gammaln(N - ai + 1) + gammaln(N - bj + 1) - lgN
                      - gammaln(nij + 1) - gammaln(ai - nij + 1) - gammaln(bj - nij + 1) - gammaln(N - ai - bj + nij + 1))
                emi += term * np.exp(lw)
    ha, hb = _h(A.astype(float)), _h(B.astype(float))
    den = (ha + hb) / 2 - emi
    return float((_mi(M) - emi) / den) if den else 1.0


def auc(score: np.ndarray, y: np.ndarray) -> float:
    r = stats.rankdata(score)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else np.nan


def ols_ci(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Slope of y on x with a 95% t-interval (classical errors)."""
    r = stats.linregress(x, y)
    t = stats.t.ppf(0.975, len(x) - 2)
    return r.slope, r.slope - t * r.stderr, r.slope + t * r.stderr


# --------------------------------------------------------------------------- B1 null-model table

def graph_metrics(G: nx.Graph, lab: dict) -> dict:
    H = nx.Graph(G.edges())
    H.add_nodes_from(G.nodes())
    nx.set_node_attributes(H, lab, "lab")
    comms = nx.community.louvain_communities(H, seed=SEED)
    L = H.subgraph(lcc(H))
    comps = [c for c in nx.connected_components(H) if len(c) > 1]
    return {"average clustering": nx.average_clustering(H), "transitivity": nx.transitivity(H),
            "Louvain modularity Q": nx.community.modularity(H, comms),
            "degree assortativity": nx.degree_assortativity_coefficient(H),
            "lab assortativity": nx.attribute_assortativity_coefficient(H, "lab"),
            "LCC mean shortest path": nx.average_shortest_path_length(L) if len(L) > 1 else np.nan,
            "LCC size": L.number_of_nodes(), "components (size >= 2)": len(comps),
            "isolates": sum(1 for _ in nx.isolates(H))}


def incidence(D: Data) -> pd.DataFrame:
    n_auth = D.works["n_authors"].to_dict()
    rows = sorted((w, f) for w, fs in D.fac.items() if n_auth.get(w, 0) <= D.max_authors for f in fs)
    return pd.DataFrame(rows, columns=["work_id", "faculty_id"])


def project(works: np.ndarray, facs: np.ndarray, nodes) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(nodes)
    order = np.argsort(works, kind="stable")
    w, f = works[order], facs[order]
    cuts = np.flatnonzero(np.diff(w)) + 1
    for grp in np.split(f, cuts):
        u = np.unique(grp)
        if len(u) > 1:
            G.add_edges_from(combinations(u.tolist(), 2))
    return G


def bipartite_shuffle(works: np.ndarray, facs: np.ndarray, rng) -> tuple[np.ndarray, int]:
    """Shuffle the faculty stubs over paper stubs; repair duplicate (paper, faculty) incidences by random swaps."""
    f = facs[rng.permutation(len(facs))]
    for _ in range(50):
        dup = pd.DataFrame({"w": works, "f": f}).duplicated().to_numpy()
        idx = np.flatnonzero(dup)
        if not len(idx):
            break
        j = rng.integers(0, len(f), len(idx))
        f[idx], f[j] = f[j], f[idx].copy()
    lost = int(pd.DataFrame({"w": works, "f": f}).duplicated().sum())
    return f, lost


def null_table(D: Data, G: nx.Graph) -> tuple[pd.DataFrame, dict]:
    lab = {f: D.fac_lab[f] for f in G}
    obs = graph_metrics(G, lab)
    nodes = list(G)
    n, m = G.number_of_nodes(), G.number_of_edges()
    inc = incidence(D)
    works = pd.factorize(inc["work_id"])[0]
    facs = inc["faculty_id"].to_numpy()
    rng = np.random.default_rng(SEED)
    sims = defaultdict(list)
    lost = []
    for i in range(N_NULL):
        er = nx.relabel_nodes(nx.gnm_random_graph(n, m, seed=SEED + i), dict(enumerate(nodes)))
        sims["Erdos-Renyi G(n,m)"].append(graph_metrics(er, lab))
        rw = nx.Graph(G.edges())
        rw.add_nodes_from(nodes)
        nx.double_edge_swap(rw, nswap=10 * m, max_tries=100 * m, seed=SEED + i)
        sims["degree-preserving rewiring"].append(graph_metrics(rw, lab))
        f, k = bipartite_shuffle(works, facs, rng)
        lost.append(k)
        sims["bipartite configuration (papers x faculty)"].append(graph_metrics(project(works, f, nodes), lab))
    rows = []
    for model, lst in sims.items():
        df = pd.DataFrame(lst)
        for metric, o in obs.items():
            s = df[metric].dropna().to_numpy(float)
            mu, sd = (s.mean(), s.std(ddof=1)) if len(s) else (np.nan, np.nan)
            p = min(1.0, 2 * min((s >= o).mean(), (s <= o).mean()) + 1 / len(s)) if len(s) else np.nan
            rows.append({"metric": metric, "observed": o, "model": model, "null_mean": mu, "null_sd": sd,
                         "z": (o - mu) / sd if sd else np.nan, "p_two_sided": p})
    # filled vs hollow triangles
    n_auth = D.works["n_authors"].to_dict()
    triples = set()
    for w, fs in D.fac.items():
        if len(fs) >= 3 and n_auth.get(w, 0) <= D.max_authors:
            triples.update(combinations(sorted(fs), 3))
    tri = filled = 0
    adj = {u: set(G[u]) for u in G}
    for u in G:
        for v in adj[u]:
            if v <= u:
                continue
            for w in adj[u] & adj[v]:
                if w <= v:
                    continue
                tri += 1
                filled += tuple(sorted((u, v, w))) in triples
    extra = {"faculty_nodes": n, "faculty_links": m, "incidences": len(inc), "bipartite_lost_incidences_mean": float(np.mean(lost)),
             "triangles": tri, "filled_triangles": filled, "filled_triangle_share": filled / tri if tri else np.nan}
    return pd.DataFrame(rows), extra


# --------------------------------------------------------------------------- B2 communities vs the org chart

def communities(D: Data, G: nx.Graph, cfg) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    nodes = [v for v in G if G.degree(v) > 0]
    H = G.subgraph(nodes)
    parts = []
    for s in range(N_LOUVAIN):
        cs = nx.community.louvain_communities(H, weight="weight", seed=SEED + s)
        parts.append((nx.community.modularity(H, cs, weight="weight"), {v: i for i, c in enumerate(cs) for v in c}))
    labels = [[p[v] for v in nodes] for _, p in parts]
    pw = [nmi(labels[i], labels[j]) for i, j in combinations(range(len(labels)), 2)]
    best_q, best = max(parts, key=lambda t: t[0])
    comm = [best[v] for v in nodes]
    lab = [D.fac_lab[v] for v in nodes]
    known = [v for v in nodes if D.dept.get(v) not in (None, "", "Unknown")]
    rng = np.random.default_rng(SEED)
    rows = []
    for name, vs, lbl in (("best Louvain partition vs lab", nodes, lab),
                          ("best Louvain partition vs department (lab|department, known only)", known,
                           [f"{D.fac_lab[v]}|{D.dept[v]}" for v in known])):
        c = [best[v] for v in vs]
        o = nmi(c, lbl)
        arr = np.array(lbl)
        null = np.array([nmi(c, rng.permutation(arr)) for _ in range(N_PERM)])
        rows.append({"comparison": name, "n_nodes": len(vs), "n_communities": len(set(c)), "n_groups": len(set(lbl)),
                     "nmi": o, "ari": ari(c, lbl), "ami": ami(c, lbl), "null_nmi_mean": null.mean(),
                     "null_nmi_sd": null.std(ddof=1), "z": (o - null.mean()) / null.std(ddof=1)})
    rows.append({"comparison": "Louvain stability (mean pairwise NMI over seeds)", "n_nodes": len(nodes),
                 "n_communities": float(np.mean([len(set(l)) for l in labels])), "n_groups": N_LOUVAIN,
                 "nmi": float(np.mean(pw)), "ari": float(np.mean([ari(labels[i], labels[j]) for i, j in
                                                                  combinations(range(min(20, len(labels))), 2)])),
                 "ami": np.nan, "null_nmi_mean": np.nan, "null_nmi_sd": np.nan, "z": np.nan})
    val = pd.DataFrame(rows)
    # how many communities mix labs (the best partition)
    cdf = pd.DataFrame({"c": comm, "lab": lab})
    purity = cdf.groupby("c")["lab"].agg(lambda s: s.value_counts().iloc[0] / len(s))
    sizes = cdf.groupby("c").size()
    # k-core
    core = nx.core_number(G)
    kmax = max(core.values())
    kc = []
    for k in range(1, kmax + 1):
        inside = [v for v, c in core.items() if c >= k]
        row = {"k": k, "n_nodes": len(inside), "shell_nodes": sum(1 for c in core.values() if c == k),
               "is_main_core": k == kmax}
        cnt = Counter(D.fac_lab[v] for v in inside)
        for l in D.labs:
            row[l] = cnt.get(l, 0)
        kc.append(row)
    roster = pd.read_parquet(cfg.paths.interim / "roster.parquet").set_index("faculty_id")["name"]
    kf = pd.DataFrame({"faculty_id": list(core), "core_number": list(core.values())})
    kf["name"] = kf["faculty_id"].map(roster)
    kf["lab"] = kf["faculty_id"].map(D.fac_lab)
    kf["degree"] = kf["faculty_id"].map(dict(G.degree()))
    kf = kf.sort_values(["core_number", "degree"], ascending=False)[["faculty_id", "name", "lab", "core_number", "degree"]]
    main = kf[kf["core_number"] == kmax]
    extra = {"louvain_stability_mean_pairwise_nmi": float(np.mean(pw)), "louvain_stability_min_nmi": float(np.min(pw)),
             "best_modularity_weighted": best_q, "n_communities_best": len(set(comm)),
             "communities_size5plus": int((sizes >= 5).sum()),
             "communities_size5plus_mixed_labs": int(((sizes >= 5) & (purity < 0.9)).sum()),
             "kcore_max": kmax, "main_core_size": len(main),
             "main_core_by_lab": main["lab"].value_counts().to_dict()}
    return val, pd.DataFrame(kc), kf, extra


# --------------------------------------------------------------------------- B3 students are the glue

def students_glue(D: Data, G: nx.Graph) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    a = D.auth
    n_auth = D.works["n_authors"].to_dict()
    fac_ids = set(a.loc[a["faculty_id"].notna(), "author_id"].dropna())
    nf = a[a["our_lab"].notna() & a["faculty_id"].isna() & a["author_id"].notna() & ~a["author_id"].isin(fac_ids)
           & (a["work_id"].map(n_auth).fillna(999) <= D.max_authors)]
    direct = {pair(u, v) for u, v in G.edges()}
    med = Counter()
    people = []
    for aid, g in nf.groupby("author_id"):
        ws = set(g["work_id"])
        F = set().union(*(D.fac.get(w, set()) for w in ws))
        if len(F) < 2:
            continue
        ps = {pair(u, v) for u, v in combinations(sorted(F), 2)} - direct
        if not ps:
            continue
        med.update(ps)
        cross = sum(D.fac_lab[u] != D.fac_lab[v] for u, v in ps)
        y0, y1 = int(min(D.year[w] for w in ws)), int(max(D.year[w] for w in ws))
        name = re.sub(r"[^\w .,'-]", "", g["author_name"].mode().iloc[0]).strip()
        people.append({"name": name, "lab": g["our_lab"].mode().iloc[0], "n_pairs": len(ps),
                       "n_cross_lab_pairs": cross, "n_faculty": len(F), "n_papers": len(ws),
                       "first_year": y0, "last_year": y1, "active_years": y1 - y0 + 1,
                       "short_tenure": y1 - y0 + 1 <= SHORT_TENURE, "_pairs": ps})
    glue = pd.DataFrame(people).sort_values(["n_pairs", "n_papers"], ascending=False)
    med_short = Counter(p for ps, st in zip(glue["_pairs"], glue["short_tenure"]) if st for p in ps)

    def graph_with(pairs):
        H = nx.Graph()
        H.add_nodes_from(G)
        H.add_edges_from(direct)
        H.add_edges_from(pairs)
        return H
    Gs = graph_with(med)
    Gs2 = graph_with([p for p, c in med.items() if c >= 2])
    graphs = {"faculty_only": G, "with_students": Gs, "with_students_2plus_mediators": Gs2,
              "with_short_tenure_only": graph_with(med_short)}
    rows = []

    def add(scope, metric, fn):
        rows.append({"scope": scope, "metric": metric, **{k: fn(H) for k, H in graphs.items()}})
    n = G.number_of_nodes()
    add("ALL", "links", lambda H: H.number_of_edges())
    add("ALL", "density", nx.density)
    add("ALL", "mean degree", lambda H: 2 * H.number_of_edges() / n)
    add("ALL", "isolates", lambda H: sum(1 for _ in nx.isolates(H)))
    add("ALL", "components (size >= 2)", lambda H: sum(1 for c in nx.connected_components(H) if len(c) > 1))
    add("ALL", "LCC size", lambda H: len(lcc(H)))
    add("ALL", "LCC fraction", lambda H: len(lcc(H)) / n)
    add("ALL", "cross-lab share of links", lambda H: np.mean([D.fac_lab[u] != D.fac_lab[v] for u, v in H.edges()]))
    add("ALL", "average clustering", nx.average_clustering)
    for l in D.labs:
        vs = [v for v in G if D.fac_lab[v] == l]
        add(l, "within-lab links", lambda H, vs=vs: H.subgraph(vs).number_of_edges())
        add(l, "within-lab density", lambda H, vs=vs: nx.density(H.subgraph(vs)))
        add(l, "faculty with no within-lab link", lambda H, vs=vs: sum(1 for _ in nx.isolates(H.subgraph(vs))))
        add(l, "cross-lab links", lambda H, l=l: sum((D.fac_lab[u] == l) != (D.fac_lab[v] == l) for u, v in H.edges()))
    for l1, l2 in combinations(D.labs, 2):
        add(f"{l1} - {l2}", "cross-lab links",
            lambda H, l1=l1, l2=l2: sum({D.fac_lab[u], D.fac_lab[v]} == {l1, l2} for u, v in H.edges()))
    t = pd.DataFrame(rows)
    iso_before = set(nx.isolates(G))
    extra = {"nonfaculty_lab_authors": int(nf["author_id"].nunique()),
             "nonfaculty_authors_bridging": len(glue), "mediated_pairs": len(med),
             "mediated_pairs_cross_lab": sum(D.fac_lab[u] != D.fac_lab[v] for u, v in med),
             "mediated_pairs_2plus_mediators": sum(c >= 2 for c in med.values()),
             "isolates_faculty_only": len(iso_before),
             "isolates_connected_by_students": len(iso_before - set(nx.isolates(Gs))),
             "bridging_authors_short_tenure": int(glue["short_tenure"].sum()),
             "mediated_pairs_short_tenure": len(med_short),
             "lcc_short_tenure_only": len(lcc(graphs["with_short_tenure_only"])),
             "top5_glue_share_of_mediated_pairs": glue.head(5)["n_pairs"].sum() / len(med) if len(med) else np.nan}
    cols = ["name", "lab", "n_pairs", "n_cross_lab_pairs", "n_faculty", "n_papers", "first_year", "last_year",
            "active_years", "short_tenure"]
    return t, glue.head(15)[cols], extra


# --------------------------------------------------------------------------- B4 growth laws

def growth(D: Data, years: range) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = []
    for y in years:
        G = faculty_graph(D, until=y)
        act = [v for v in G if G.degree(v) > 0]
        H = G.subgraph(act)
        L = H.subgraph(lcc(H)) if act else H
        d = []
        for s, dd in nx.all_pairs_shortest_path_length(L):
            d.extend(v for t, v in dd.items() if t > s)
        rows.append({"year": y, "N": len(act), "E": H.number_of_edges(), "mean_degree": 2 * H.number_of_edges() / max(1, len(act)),
                     "lcc_size": L.number_of_nodes(), "lcc_fraction": L.number_of_nodes() / max(1, len(act)),
                     "effective_diameter": float(np.percentile(d, 90)) if d else np.nan,
                     "diameter": max(d) if d else np.nan})
    g = pd.DataFrame(rows)
    alpha, lo, hi = ols_ci(np.log(g["N"]), np.log(g["E"]))
    g["alpha_fit"] = alpha
    # preferential attachment: node-years (degree at end of t-1, new links gained in t)
    first_pub = D.links.assign(year=D.links["work_id"].map(D.year)).groupby("faculty_id")["year"].min().to_dict()
    nodes = D.faculty
    fi = {f: i for i, f in enumerate(nodes)}
    ny = []
    for t in list(years)[1:]:
        G = faculty_graph(D, until=t - 1)
        gain = Counter()
        for (a, b), y0 in D.first_year.items():
            if y0 == t:
                gain[a] += 1
                gain[b] += 1
        for f in nodes:
            if first_pub.get(f, 9999) <= t - 1:
                ny.append((fi[f], G.degree(f), gain.get(f, 0)))
    ny = np.array(ny)
    kk = ny[:, 1]
    K = int(np.percentile(kk[kk >= 1], 95))
    pa = []
    for k in range(0, K + 1):
        m = kk == k
        pa.append({"k": k, "n_nodes": int(m.sum()), "new_links": int(ny[m, 2].sum()),
                   "rate": ny[m, 2].sum() / m.sum() if m.sum() else np.nan})
    pa = pd.DataFrame(pa)

    def gamma(w):
        n = np.bincount(kk, weights=w, minlength=K + 1)[:K + 1]
        g_ = np.bincount(kk, weights=w * ny[:, 2], minlength=K + 1)[:K + 1]
        A = np.divide(g_, n, out=np.zeros_like(g_), where=n > 0)
        ks = np.arange(1, K + 1)
        kap = np.cumsum(A[1:])
        ok = kap > 0
        return np.polyfit(np.log(ks[ok]), np.log(kap[ok]), 1)[0] - 1
    gam = gamma(np.ones(len(ny)))
    rng = np.random.default_rng(SEED)
    nf = len(nodes)
    boot = []
    for _ in range(N_BOOT):
        cnt = np.bincount(rng.integers(0, nf, nf), minlength=nf)
        boot.append(gamma(cnt[ny[:, 0]].astype(float)))
    pa["cumulative_kernel"] = pa["rate"].where(pa["k"] >= 1, 0).fillna(0).cumsum()
    ok = (pa["k"] >= 1) & (pa["rate"] > 0)
    direct = np.polyfit(np.log(pa.loc[ok, "k"]), np.log(pa.loc[ok, "rate"]), 1, w=np.sqrt(pa.loc[ok, "n_nodes"]))[0]
    extra = {"densification_alpha": alpha, "densification_alpha_ci": [lo, hi],
             "pa_gamma": gam, "pa_gamma_ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
             "pa_gamma_direct_fit": direct, "pa_k_max_used": K, "pa_node_years": len(ny),
             "pa_rate_k0": float(pa.loc[pa.k == 0, "rate"].iloc[0])}
    return g, pa, extra


# --------------------------------------------------------------------------- B5 early position -> later output

def ncs_series(D: Data) -> pd.Series:
    w = D.works
    k = [w["subfield"].fillna("Unknown"), w["year"]]
    return w["cited_by_count"] / w.groupby(k)["cited_by_count"].transform("mean").replace(0, np.nan)


def position_model(D: Data) -> tuple[pd.DataFrame, dict]:
    L = D.links.drop_duplicates(["work_id", "faculty_id"]).copy()
    L["year"] = L["work_id"].map(D.year)
    L["cites"] = L["work_id"].map(D.works["cited_by_count"])
    L["ncs"] = L["work_id"].map(ncs_series(D))
    e = L[L["year"].between(*EARLY)]
    late = L[L["year"].between(*LATE)]
    pe = e.groupby("faculty_id")["work_id"].nunique()
    fac = sorted(pe[pe >= 2].index)
    G = faculty_graph(D, until=EARLY[1])
    btw = nx.betweenness_centrality(G)
    con = nx.constraint(G, nodes=[f for f in fac if G.degree(f) > 0])
    clu = nx.clustering(G)
    df = pd.DataFrame({"faculty_id": fac})
    df["degree"] = df["faculty_id"].map(dict(G.degree()))
    df["betweenness"] = df["faculty_id"].map(btw)
    df["constraint"] = df["faculty_id"].map(con).fillna(1.0)   # isolates: fully constrained
    df["clustering"] = df["faculty_id"].map(clu)
    df["papers_2016_20"] = df["faculty_id"].map(pe)
    df["log_citations_2016_20"] = np.log1p(df["faculty_id"].map(e.groupby("faculty_id")["cites"].sum()))
    df["lab"] = df["faculty_id"].map(D.fac_lab)
    df["y_log_papers"] = np.log1p(df["faculty_id"].map(late.groupby("faculty_id")["work_id"].nunique()).fillna(0))
    df["y_mean_ncs"] = df["faculty_id"].map(late.groupby("faculty_id")["ncs"].mean())
    preds = ["degree", "betweenness", "constraint", "clustering", "papers_2016_20", "log_citations_2016_20"]
    out = []
    for outcome in ("y_log_papers", "y_mean_ncs"):
        d = df.dropna(subset=[outcome])
        Z = (d[preds] - d[preds].mean()) / d[preds].std(ddof=0)
        fe = [(d["lab"] == l).astype(float).to_numpy() for l in D.labs[1:]]
        X = np.column_stack([np.ones(len(d)), Z.to_numpy(), *fe])
        y = d[outcome].to_numpy(float)
        b, se = ols_hc1(X, y)
        r2 = 1 - ((y - X @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        for k, t in enumerate(preds, 1):
            out.append({"outcome": outcome.removeprefix("y_") + "_2021_26", "term": f"{t} (per SD)", "coef": b[k],
                        "se": se[k], "ci_lo": b[k] - 1.96 * se[k], "ci_hi": b[k] + 1.96 * se[k],
                        "p": 2 * stats.norm.sf(abs(b[k] / se[k])), "n": len(d), "r2": r2})
    res = pd.DataFrame(out)
    extra = {"position_model_n": len(df), "spearman_degree_papers_early": stats.spearmanr(df["degree"], df["papers_2016_20"])[0]}
    return res, extra


# --------------------------------------------------------------------------- B6 fragility of cross-lab links

def node_cut(G: nx.Graph, A: set, B: set) -> tuple[int, list]:
    H = nx.DiGraph()
    for v in G:
        H.add_edge((v, 0), (v, 1), capacity=1)
    for u, v in G.edges():
        H.add_edge((u, 1), (v, 0))
        H.add_edge((v, 1), (u, 0))
    for a in A:
        H.add_edge("S", (a, 0))
    for b in B:
        H.add_edge((b, 1), "T")
    val, (S, _) = nx.minimum_cut(H, "S", "T")
    return int(val), sorted(v for v in G if (v, 0) in S and (v, 1) not in S)


def edge_cut(G: nx.Graph, A: set, B: set) -> int:
    H = nx.DiGraph()
    for u, v in G.edges():
        H.add_edge(u, v, capacity=1)
        H.add_edge(v, u, capacity=1)
    for a in A:
        H.add_edge("S", a)
    for b in B:
        H.add_edge(b, "T")
    return int(nx.minimum_cut_value(H, "S", "T"))


def fragility(D: Data, G: nx.Graph, cfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    roster = pd.read_parquet(cfg.paths.interim / "roster.parquet").set_index("faculty_id")["name"]
    ev = D.coauth.copy()
    ev["cross"] = ev["a"].map(D.fac_lab) != ev["b"].map(D.fac_lab)
    cx = ev[ev["cross"]]
    works_of = cx.groupby(["a", "b"])["work_id"].agg(set).to_dict()
    per_paper = cx.groupby("work_id").size().sort_values(ascending=False)
    only_here = Counter(next(iter(ws)) for ws in works_of.values() if len(ws) == 1)
    ranked = per_paper.index.tolist()
    labpair = {p: tuple(sorted((D.fac_lab[p[0]], D.fac_lab[p[1]]))) for p in works_of}
    L = G.subgraph(lcc(G))
    rows = []
    scopes = [("ALL", None)] + [(f"{a} - {b}", (a, b)) for a, b in combinations(D.labs, 2)]
    for name, lp in scopes:
        ps = [p for p in works_of if lp is None or labpair[p] == lp]
        row = {"lab_pair": name, "cross_links": len(ps), "single_paper_links": sum(len(works_of[p]) == 1 for p in ps)}
        row["single_paper_share"] = row["single_paper_links"] / len(ps) if ps else np.nan
        for k in (1, 5, 10):
            drop = set(ranked[:k])
            row[f"links_left_without_top{k}_papers"] = sum(bool(works_of[p] - drop) for p in ps)
        if lp is not None:
            A = {v for v in L if D.fac_lab[v] == lp[0]}
            B = {v for v in L if D.fac_lab[v] == lp[1]}
            val, cut = node_cut(L, A, B)
            row["min_node_cut"] = val
            row["min_node_cut_faculty"] = "; ".join(f"{roster.get(v, v)} ({D.fac_lab[v]})" for v in cut)
            row["min_edge_cut"] = edge_cut(L, A, B)
        rows.append(row)
    fr = pd.DataFrame(rows)
    top = []
    for w in ranked[:20]:
        top.append({"work_id": w, "title": D.works.at[w, "title"], "year": D.year[w], "n_authors": int(D.works.at[w, "n_authors"]),
                    "n_faculty": len(D.fac[w]), "labs": "; ".join(sorted(D.lab_of_work.get(w, ()))),
                    "cross_lab_pairs": int(per_paper[w]), "pairs_only_on_this_paper": only_here.get(w, 0),
                    "cited_by_count": int(D.works.at[w, "cited_by_count"])})
    allr = fr.iloc[0]
    extra = {"cross_lab_links": int(allr["cross_links"]), "cross_lab_single_paper_share": allr["single_paper_share"],
             "cross_lab_left_after_top1": int(allr["links_left_without_top1_papers"]),
             "cross_lab_left_after_top5": int(allr["links_left_without_top5_papers"]),
             "cross_lab_left_after_top10": int(allr["links_left_without_top10_papers"]),
             "min_node_cut": fr.dropna(subset=["min_node_cut"]).set_index("lab_pair")["min_node_cut"].to_dict()}
    return fr, pd.DataFrame(top), extra


# --------------------------------------------------------------------------- B7 link prediction and twins

def subfield_counts(D: Data, y0: int, y1: int) -> tuple[np.ndarray, list, list]:
    L = D.links.drop_duplicates(["work_id", "faculty_id"])
    L = L[L["work_id"].map(D.year).between(y0, y1)]
    sub = D.works["subfield"].fillna("Unknown")
    cats = sorted(sub.unique())
    ci = {c: i for i, c in enumerate(cats)}
    fi = {f: i for i, f in enumerate(D.faculty)}
    M = np.zeros((len(D.faculty), len(cats)))
    for w, f in zip(L["work_id"], L["faculty_id"]):
        M[fi[f], ci[sub[w]]] += 1
    return M, cats, D.faculty


def cosine_matrix(M: np.ndarray) -> np.ndarray:
    nrm = np.linalg.norm(M, axis=1)
    U = np.divide(M, nrm[:, None], out=np.zeros_like(M), where=nrm[:, None] > 0)
    return U @ U.T


def pair_features(D: Data, G: nx.Graph, cos: np.ndarray) -> dict[str, np.ndarray]:
    A = nx.to_numpy_array(G, nodelist=D.faculty, weight=None)
    deg = A.sum(1)
    cn = A @ A
    with np.errstate(divide="ignore"):
        inv = np.divide(1, np.log(deg), out=np.zeros_like(deg), where=deg > 1)
    aa = (A * inv) @ A
    jac = np.divide(cn, deg[:, None] + deg[None, :] - cn, out=np.zeros_like(cn), where=(deg[:, None] + deg[None, :] - cn) > 0)
    lab = np.array([D.fac_lab[f] for f in D.faculty])
    return {"A": A, "common neighbours": cn, "Jaccard": jac, "Adamic-Adar": aa,
            "preferential attachment": np.outer(deg, deg), "topic cosine (subfields)": cos,
            "same lab": (lab[:, None] == lab[None, :]).astype(float)}


def active(D: Data, y0: int, y1: int) -> set:
    L = D.links
    return set(L.loc[L["work_id"].map(D.year).between(y0, y1), "faculty_id"])


def candidates(D: Data, F: dict, act: set, y_new: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    idx = np.array(sorted(D.faculty.index(f) for f in act))
    I, J = np.triu_indices(len(idx), 1)
    I, J = idx[I], idx[J]
    keep = F["A"][I, J] == 0
    I, J = I[keep], J[keep]
    y = np.array([y_new[0] <= D.first_year.get(pair(D.faculty[i], D.faculty[j]), 0) <= y_new[1] for i, j in zip(I, J)], int)
    return I, J, y


def link_prediction(D: Data, cfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED)
    # logistic weights fitted on 2016-18 -> 2019-20
    Mtr, _, _ = subfield_counts(D, 2016, 2018)
    Ftr = pair_features(D, faculty_graph(D, until=2018), cosine_matrix(Mtr))
    I, J, y = candidates(D, Ftr, active(D, 2016, 2018) & active(D, 2019, 2020), (2019, 2020))

    def X_of(F, I, J):
        return np.column_stack([np.ones(len(I)), F["same lab"][I, J], F["topic cosine (subfields)"][I, J],
                                np.log1p(F["Adamic-Adar"][I, J])])
    b, _ = logit(X_of(Ftr, I, J), y)
    # test: 2016-20 network -> new links 2021-26
    M, cats, _ = subfield_counts(D, *EARLY)
    cos_e = cosine_matrix(M)
    F = pair_features(D, faculty_graph(D, until=EARLY[1]), cos_e)
    I, J, y = candidates(D, F, active(D, *EARLY) & active(D, *LATE), LATE)
    scores = {k: F[k][I, J] for k in ("common neighbours", "Jaccard", "Adamic-Adar", "preferential attachment",
                                      "topic cosine (subfields)", "same lab")}
    scores["logistic (same lab + topic + log AA), fit 2016-18 -> 2019-20"] = X_of(F, I, J) @ b
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    tie = rng.random(len(y))
    rows = []
    for name, s in scores.items():
        bs = []
        for _ in range(N_BOOT):
            ii = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
            bs.append(auc(s[ii], y[ii]))
        top = np.lexsort((tie, -s))[:50]
        rows.append({"method": name, "auc": auc(s, y), "auc_lo": np.percentile(bs, 2.5), "auc_hi": np.percentile(bs, 97.5),
                     "precision_at_50": y[top].mean(), "candidate_pairs": len(y), "new_links": int(y.sum()),
                     "base_rate": y.mean()})
    lp = pd.DataFrame(rows)
    # back-test: cross-lab pairs in the top decile of 2016-20 topic similarity
    cross = F["same lab"][I, J] == 0
    c = cos_e[I, J][cross]
    yc = y[cross]
    thr = np.percentile(c, 90)
    hi_ = c >= thr
    k1, n1, k0, n0 = int(yc[hi_].sum()), int(hi_.sum()), int(yc[~hi_].sum()), int((~hi_).sum())
    bt = {"cross_lab_pairs": len(yc), "top_decile_threshold": thr, "top_decile_linked": k1, "top_decile_pairs": n1,
          "top_decile_rate": k1 / n1, "top_decile_ci": list(wilson(k1, n1)), "other_linked": k0, "other_pairs": n0,
          "other_rate": k0 / n0, "other_ci": list(wilson(k0, n0)),
          "ratio": (k1 / n1) / (k0 / n0) if k0 else np.nan,
          "fisher_p": stats.fisher_exact([[k1, n1 - k1], [k0, n0 - k0]])[1]}
    # twins: all-year topic cosine, cross-lab, never on any paper together, >=5 papers each
    Mall, cats, _ = subfield_counts(D, 1900, 3000)
    cos_all = cosine_matrix(Mall)
    ever = {pair(u, v) for fs in D.fac.values() for u, v in combinations(sorted(fs), 2)}
    npap = Mall.sum(1)
    roster = pd.read_parquet(cfg.paths.interim / "roster.parquet").set_index("faculty_id")["name"]
    lab = np.array([D.fac_lab[f] for f in D.faculty])
    I2, J2 = np.triu_indices(len(D.faculty), 1)
    ok = (lab[I2] != lab[J2]) & (npap[I2] >= 5) & (npap[J2] >= 5)
    I2, J2 = I2[ok], J2[ok]
    order = np.argsort(-cos_all[I2, J2], kind="stable")
    tw = []
    for k in order:
        i, j = I2[k], J2[k]
        a_, b_ = D.faculty[i], D.faculty[j]
        if pair(a_, b_) in ever:
            continue
        sh = np.minimum(Mall[i] / Mall[i].sum(), Mall[j] / Mall[j].sum())
        top3 = [cats[t] for t in np.argsort(-sh)[:3] if sh[t] > 0]
        tw.append({"a_id": a_, "a_name": roster.get(a_, a_), "a_lab": D.fac_lab[a_], "b_id": b_, "b_name": roster.get(b_, b_),
                   "b_lab": D.fac_lab[b_], "cosine": cos_all[i, j], "a_papers": int(npap[i]), "b_papers": int(npap[j]),
                   "shared_subfields": "; ".join(top3)})
        if len(tw) == 25:
            break
    extra = {"link_prediction": lp.set_index("method")[["auc", "auc_lo", "auc_hi", "precision_at_50"]].to_dict("index"),
             "logit_coefficients_2016_18": dict(zip(["const", "same_lab", "topic_cosine", "log1p_AA"], b.tolist())),
             "twin_backtest": bt}
    return lp, pd.DataFrame(tw), extra


# --------------------------------------------------------------------------- B8 topic contagion

def contagion(D: Data) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED)
    L = D.links.drop_duplicates(["work_id", "faculty_id"])
    sub = D.works["subfield"].fillna("Unknown")
    cats = sorted(sub.unique())
    ci = {c: i for i, c in enumerate(cats)}
    fac = D.faculty
    fi = {f: i for i, f in enumerate(fac)}
    FP = np.full((len(fac), len(cats)), np.inf)
    pub_years = defaultdict(set)
    for w, f in zip(L["work_id"], L["faculty_id"]):
        y = D.year[w]
        FP[fi[f], ci[sub[w]]] = min(FP[fi[f], ci[sub[w]]], y)
        pub_years[f].add(y)
    unknown = ci.get("Unknown", -1)
    partners = defaultdict(dict)
    for (a, b), y in D.first_year.items():
        partners[a][b] = y
        partners[b][a] = y
    lab_members = defaultdict(list)
    for f in fac:
        lab_members[D.fac_lab[f]].append(fi[f])
    rows_f, rows_adopt, e_prior, e_fut, e_rand = [], [], [], [], []
    for t in range(2018, 2027):
        for f in fac:
            ys = pub_years[f]
            if not ys or min(ys) >= t or t not in ys:
                continue
            i = fi[f]
            risk = FP[i] >= t
            if unknown >= 0:
                risk[unknown] = False
            if not risk.any():
                continue
            P = [fi[g] for g, y0 in partners[f].items() if y0 < t]
            Fu = [fi[g] for g, y0 in partners[f].items() if y0 > t]
            ep = (FP[P] < t).any(0) if P else np.zeros(len(cats), bool)
            ef = (FP[Fu] < t).any(0) if Fu else np.zeros(len(cats), bool)
            er = np.zeros(len(cats))
            if P:
                excl = {i, *[fi[g] for g in partners[f]]}
                pool = np.array([j for j in lab_members[D.fac_lab[f]] if j not in excl])
                if len(pool):
                    for _ in range(20):
                        dr = rng.choice(pool, min(len(P), len(pool)), replace=False)
                        er += (FP[dr] < t).any(0)
                    er /= 20
            s = np.flatnonzero(risk)
            rows_f.append(np.full(len(s), i))
            rows_adopt.append(FP[i, s] == t)
            e_prior.append(ep[s])
            e_fut.append(ef[s])
            e_rand.append(er[s])
    fidx = np.concatenate(rows_f)
    adopt = np.concatenate(rows_adopt).astype(float)
    E = {"prior co-authors (linked before the year)": np.concatenate(e_prior).astype(float),
         "placebo: future co-authors (linked after the year)": np.concatenate(e_fut).astype(float),
         "placebo: random same-lab non-co-authors (size-matched)": np.concatenate(e_rand)}

    def rr(e, w):
        a1, n1 = (w * adopt * e).sum(), (w * e).sum()
        a0, n0 = (w * adopt * (1 - e)).sum(), (w * (1 - e)).sum()
        return (a1 / n1) / (a0 / n0) if n1 and n0 and a0 else np.nan
    nf = len(fac)
    boots = {k: [] for k in E}
    ratio_boot = []
    for _ in range(N_BOOT):
        cnt = np.bincount(rng.integers(0, nf, nf), minlength=nf).astype(float)
        w = cnt[fidx]
        vals = {k: rr(e, w) for k, e in E.items()}
        for k in E:
            boots[k].append(vals[k])
        ratio_boot.append(vals[list(E)[0]] / vals[list(E)[1]])
    out = []
    one = np.ones(len(adopt))
    for k, e in E.items():
        n1, n0 = e.sum(), (1 - e).sum()
        out.append({"exposure": k, "at_risk_rows": len(adopt), "adoptions": int(adopt.sum()), "exposed_rows": n1,
                    "adoption_rate_exposed": (adopt * e).sum() / n1, "adoption_rate_unexposed": (adopt * (1 - e)).sum() / n0,
                    "rr": rr(e, one), "rr_lo": np.nanpercentile(boots[k], 2.5), "rr_hi": np.nanpercentile(boots[k], 97.5),
                    "share_of_adoptions_exposed": (adopt * e).sum() / adopt.sum()})
    c = pd.DataFrame(out)
    extra = {"contagion": c.set_index("exposure")[["rr", "rr_lo", "rr_hi", "share_of_adoptions_exposed"]].to_dict("index"),
             "rr_ratio_prior_vs_future": c["rr"].iloc[0] / c["rr"].iloc[1],
             "rr_ratio_prior_vs_future_ci": [float(np.nanpercentile(ratio_boot, 2.5)), float(np.nanpercentile(ratio_boot, 97.5))],
             "adoption_events": int(adopt.sum()), "faculty_years_subfield_rows": len(adopt)}
    return c, extra


# --------------------------------------------------------------------------- B9 main path and specialisation

def main_path(D: Data) -> tuple[pd.DataFrame, dict]:
    w = D.works
    order_key = pd.Series(list(zip(w["year"], w["pub_date"].fillna(""), w.index)), index=w.index).rank(method="first")
    e = D.internal[["src", "tgt"]].drop_duplicates()
    e = e[e["src"] != e["tgt"]]
    ok = e["src"].map(order_key) > e["tgt"].map(order_key)
    dropped = int((~ok).sum())
    e = e[ok]
    G = nx.DiGraph()
    G.add_edges_from(zip(e["src"], e["tgt"]))        # citing -> cited
    topo = list(nx.topological_sort(G))
    n_from = {}                                        # paths from any source (uncited paper) to v
    for v in topo:
        preds = list(G.predecessors(v))
        n_from[v] = 1.0 if not preds else sum(n_from[u] for u in preds)
    n_to = {}                                          # paths from v to any sink (paper citing none inside)
    for v in reversed(topo):
        succ = list(G.successors(v))
        n_to[v] = 1.0 if not succ else sum(n_to[u] for u in succ)
    total = sum(n_from[v] for v in G if G.out_degree(v) == 0)
    spc = {(u, v): n_from[u] * n_to[v] for u, v in G.edges()}
    # global main path: maximum total SPC from a source to a sink
    best, nxt = {}, {}
    for v in reversed(topo):
        succ = list(G.successors(v))
        if not succ:
            best[v] = 0.0
            continue
        u = max(succ, key=lambda s: spc[(v, s)] + best[s])
        best[v] = spc[(v, u)] + best[u]
        nxt[v] = u
    start = max((v for v in G if G.in_degree(v) == 0), key=lambda v: best[v])
    path = [start]
    while path[-1] in nxt:
        path.append(nxt[path[-1]])
    path = path[::-1]                                  # oldest first
    rows = []
    for k, v in enumerate(path, 1):
        rows.append({"order": k, "work_id": v, "title": w.at[v, "title"], "year": int(w.at[v, "year"]),
                     "labs": "; ".join(sorted(D.lab_of_work.get(v, ()))), "subfield": w.at[v, "subfield"],
                     "spc_weight": n_from[v] * n_to[v] / total,
                     "edge_spc_to_next": spc[(path[k], v)] / total if k < len(path) else np.nan,
                     "cited_by_count": int(w.at[v, "cited_by_count"])})
    extra = {"citation_dag_nodes": G.number_of_nodes(), "citation_dag_edges": G.number_of_edges(),
             "citation_edges_dropped_order": dropped, "main_path_length": len(path),
             "main_path_years": [rows[0]["year"], rows[-1]["year"]],
             "main_path_labs": dict(Counter(l for r in rows for l in r["labs"].split("; ") if l))}
    return pd.DataFrame(rows), extra


def entropy(D: Data) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    sub = D.works["subfield"].fillna("Unknown")
    L = D.links.drop_duplicates(["work_id", "institution"])
    L = L.assign(year=L["work_id"].map(D.year), sub=L["work_id"].map(sub))
    n_min = int(min(50, L.groupby(["institution", "year"]).size().min()))
    rows = []
    for lab in D.labs:
        prev = None
        for y, g in L[L["institution"] == lab].groupby("year"):
            c = g["sub"].value_counts()
            p = c.to_numpy(float) / c.sum()
            H = float(-(p * np.log2(p)).sum())
            arr = g["sub"].to_numpy()
            rare = []
            for _ in range(200):
                cc = pd.Series(rng.choice(arr, n_min, replace=False)).value_counts().to_numpy(float) / n_min
                rare.append(-(cc * np.log2(cc)).sum())
            top = set(c.index[:10])
            rows.append({"lab": lab, "year": int(y), "papers": len(g), "subfields": len(c), "entropy_bits": H,
                         "effective_subfields": 2 ** H, f"entropy_rarefied_n{n_min}": float(np.mean(rare)),
                         "top_subfield": c.index[0], "top_subfield_share": p[0],
                         "top10_jaccard_vs_prev_year": len(top & prev) / len(top | prev) if prev else np.nan})
            prev = top
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    t0 = time.time()
    D = Data(cfg)
    st = cfg.paths.stats
    G = faculty_graph(D)
    if G.number_of_edges() == 0:
        raise StepFailed("faculty co-authorship network is empty")
    log.info("faculty network: %d nodes, %d links", G.number_of_nodes(), G.number_of_edges())
    S: dict = {}
    clock = {}

    def tick(name):
        clock[name] = round(time.time() - t0, 1)
        log.info("%s done at %.0fs", name, clock[name])

    nt, S["null"] = null_table(D, G)
    _csv(nt, st, "research_null_table.csv"); tick("null models")
    val, kc, kf, S["communities"] = communities(D, G, cfg)
    _csv(val, st, "research_community_validation.csv")
    _csv(kc, st, "research_kcore.csv")
    _csv(kf, st, "research_kcore_faculty.csv"); tick("communities")
    sg, glue, S["students"] = students_glue(D, G)
    _csv(sg, st, "research_students_glue.csv")
    _csv(glue, st, "research_glue_people.csv"); tick("students")
    gr, pa, S["growth"] = growth(D, range(int(cfg.window.start), int(cfg.window.end) + 1))
    _csv(gr, st, "research_growth.csv")
    _csv(pa, st, "research_pref_attach.csv"); tick("growth")
    pm, S["position"] = position_model(D)
    _csv(pm, st, "research_position_model.csv"); tick("position model")
    fr, cp, S["fragility"] = fragility(D, G, cfg)
    _csv(fr, st, "research_crosslab_fragility.csv")
    _csv(cp, st, "research_crosslab_papers.csv"); tick("fragility")
    lp, tw, S["link_prediction"] = link_prediction(D, cfg)
    _csv(lp, st, "research_link_prediction.csv")
    _csv(tw, st, "research_twins.csv"); tick("link prediction")
    ct, S["contagion"] = contagion(D)
    _csv(ct, st, "research_contagion.csv"); tick("contagion")
    mp, S["main_path"] = main_path(D)
    _csv(mp, st, "research_main_path.csv")
    en = entropy(D)
    _csv(en, st, "research_entropy.csv"); tick("main path and entropy")

    # ------------------------------------------------------------------ findings (all numbers from computed values)
    def nrow(metric, model):
        return nt[(nt.metric == metric) & (nt.model == model)].iloc[0]
    bip = "bipartite configuration (papers x faculty)"
    rew = "degree-preserving rewiring"
    c_b, c_r, c_e = (nrow("average clustering", m) for m in (bip, rew, "Erdos-Renyi G(n,m)"))
    q_b = nrow("Louvain modularity Q", bip)
    sv = sg.set_index(["scope", "metric"])
    lab_row = val.iloc[0]
    dep_row = val.iloc[1]
    gS, fS, lS, cS = S["growth"], S["fragility"], S["link_prediction"], S["contagion"]
    pmi = pm.set_index(["outcome", "term"])
    lp_i = lp.set_index("method")
    best_lp = lp_i["auc"].idxmax()
    prior_k, fut_k, rand_k = list(cS["contagion"])
    bt = lS["twin_backtest"]
    last_full = int(cfg.window.end) - (1 if cfg.window.partial_year else 0)
    rcol = [c for c in en.columns if c.startswith("entropy_rarefied")][0]
    ent = en[en["year"].isin([int(cfg.window.start), last_full])].pivot(index="lab", columns="year", values=rcol)
    turn = en.groupby("lab")["top10_jaccard_vs_prev_year"].mean()
    deg_ncs = pmi.loc[("mean_ncs_2021_26", "degree (per SD)")]
    pap_pap = pmi.loc[("log_papers_2021_26", "papers_2016_20 (per SD)")]
    deg_pap = pmi.loc[("log_papers_2021_26", "degree (per SD)")]
    findings = [
        f"Faculty clustering is {c_b.observed:.2f}, against {c_e.null_mean:.2f} in a random graph, {c_r.null_mean:.2f} after "
        f"degree-preserving rewiring and {c_b.null_mean:.2f} when papers are reshuffled among faculty keeping team sizes "
        f"(z = {c_b.z:.1f}); much of the clustering is what multi-faculty papers produce mechanically, so the paper-level "
        f"null is the fair baseline.",
        f"Only {S['null']['filled_triangle_share']:.0%} of the {S['null']['triangles']} faculty triangles are 'filled' (all three "
        f"on one paper); the rest close through separate papers, i.e. genuine triadic closure.",
        f"Louvain modularity is {q_b.observed:.2f} vs {q_b.null_mean:.2f} under the bipartite null, and the best partition "
        f"matches lab membership with NMI {lab_row.nmi:.2f} (ARI {lab_row.ari:.2f}; permutation z = {lab_row.z:.0f}) but "
        f"departments only with NMI {dep_row.nmi:.2f} (AMI {dep_row.ami:.2f}): communities follow the lab wall more than the "
        f"department chart.",
        f"Adding links through non-faculty lab authors (students, postdocs, staff) raises the faculty LCC from "
        f"{sv.loc[('ALL', 'LCC size'), 'faculty_only']:.0f} to {sv.loc[('ALL', 'LCC size'), 'with_students']:.0f} of "
        f"{S['null']['faculty_nodes']} faculty, connects {S['students']['isolates_connected_by_students']} of "
        f"{S['students']['isolates_faculty_only']} isolates, and moves the cross-lab share of links from "
        f"{sv.loc[('ALL', 'cross-lab share of links'), 'faculty_only']:.1%} to "
        f"{sv.loc[('ALL', 'cross-lab share of links'), 'with_students']:.1%}; counting only short-tenure authors (a "
        f"proxy for students and postdocs) the LCC is {sv.loc[('ALL', 'LCC size'), 'with_short_tenure_only']:.0f} and the "
        f"cross-lab share {sv.loc[('ALL', 'cross-lab share of links'), 'with_short_tenure_only']:.1%}.",
        f"The network densifies with E ~ N^{gS['densification_alpha']:.2f} (95% CI {gS['densification_alpha_ci'][0]:.2f}-"
        f"{gS['densification_alpha_ci'][1]:.2f}; inflated because the roster fixes the node pool, so N saturates) and new links attach with kernel A(k) ~ k^{gS['pa_gamma']:.2f} "
        f"(CI {gS['pa_gamma_ci'][0]:.2f}-{gS['pa_gamma_ci'][1]:.2f}), "
        + ("i.e. sub-linear preferential attachment." if gS["pa_gamma_ci"][1] < 1 else
           "consistent with linear preferential attachment." if gS["pa_gamma_ci"][0] <= 1 <= gS["pa_gamma_ci"][1] else
           "i.e. super-linear attachment."),
        f"Of {fS['cross_lab_links']} cross-lab faculty links, {fS['cross_lab_single_paper_share']:.0%} rest on a single joint "
        f"paper, and removing the 10 papers that create the most cross-lab pairs leaves only {fS['cross_lab_left_after_top10']} "
        f"({fS['cross_lab_left_after_top10'] / fS['cross_lab_links']:.0%}) of them.",
        f"Early collaboration (2016-20 degree) predicts 2021-26 output by {deg_pap.coef:+.2f} log-papers per SD "
        f"(p = {deg_pap.p:.2g}) beside early papers ({pap_pap.coef:+.2f}, p = {pap_pap.p:.2g}); its association with later "
        f"field-normalised citations is {deg_ncs.coef:+.2f} per SD (p = {deg_ncs.p:.2g}"
        + (", not significant at 5%)." if deg_ncs.p >= 0.05 else ").")
        + " Brokerage (betweenness, constraint) adds nothing once degree and output are controlled"
        + ("." if pmi.xs("betweenness (per SD)", level="term")["p"].min() >= 0.05
           and pmi.xs("constraint (per SD)", level="term")["p"].min() >= 0.05 else " in most specifications."),
        f"For future co-authorship, {best_lp} works best (AUC {lp_i.loc[best_lp, 'auc']:.2f}, precision@50 "
        f"{lp_i.loc[best_lp, 'precision_at_50']:.0%}); cross-lab pairs in the top decile of 2016-20 topic similarity "
        f"linked in 2021-26 at {bt['top_decile_rate']:.1%} vs {bt['other_rate']:.1%} for other cross-lab pairs "
        f"({bt['ratio']:.1f}x, {bt['top_decile_linked']} of {bt['top_decile_pairs']} pairs; Fisher p = {bt['fisher_p']:.2g}).",
        f"Faculty start publishing in a new subfield {cS['contagion'][prior_k]['rr']:.1f}x as often when a prior co-author "
        f"already works there (CI {cS['contagion'][prior_k]['rr_lo']:.1f}-{cS['contagion'][prior_k]['rr_hi']:.1f}), vs "
        f"{cS['contagion'][fut_k]['rr']:.1f}x for future co-authors and {cS['contagion'][rand_k]['rr']:.1f}x for random "
        f"same-lab colleagues (ratio prior/future {cS['rr_ratio_prior_vs_future']:.2f}, CI "
        f"{cS['rr_ratio_prior_vs_future_ci'][0]:.2f}-{cS['rr_ratio_prior_vs_future_ci'][1]:.2f}), "
        + ("so the co-author effect is not distinguishable from shared interest (homophily), not evidence of influence."
           if cS["rr_ratio_prior_vs_future_ci"][0] <= 1 else
           "so co-authors carry some influence beyond shared interest."),
        f"The internal citation main path runs {S['main_path']['main_path_length']} papers from "
        f"{S['main_path']['main_path_years'][0]} to {S['main_path']['main_path_years'][1]} and is dominated by "
        f"{max(S['main_path']['main_path_labs'], key=S['main_path']['main_path_labs'].get)}; subfield entropy changed "
        + ", ".join(f"{l} {r.iloc[0]:.2f}->{r.iloc[1]:.2f}" for l, r in ent.iterrows())
        + f" bits ({int(cfg.window.start)} vs {last_full}, rarefied), with mean top-10 subfield turnover Jaccard "
        + ", ".join(f"{l} {v:.2f}" for l, v in turn.items()) + ".",
    ]
    methods = {
        "network": f"Faculty co-authorship on papers with <= {D.max_authors} authors; all {G.number_of_nodes()} faculty with papers are nodes.",
        "null_models": f"{N_NULL} draws each: G(n,m); double-edge-swap rewiring (10 m swaps); faculty-paper incidence shuffled keeping paper and faculty degrees (duplicates repaired by swaps), then projected. Metrics unweighted; Louvain seed {SEED}.",
        "filled_triangles": "A triangle is filled when one paper (<= author cap) carries all three faculty.",
        "communities": f"Weighted Louvain on non-isolated faculty over {N_LOUVAIN} seeds; best-modularity partition compared with lab and lab|department labels by NMI/ARI/AMI; z from {N_PERM} label permutations.",
        "kcore": "Unweighted core numbers on the full faculty graph; main core = highest k.",
        "students": "Non-faculty authors affiliated with our labs (not matched to any roster author ID) on papers within the author cap; a faculty pair is mediated when both wrote (on any papers) with the same such author but never with each other. 'Short tenure' = active in our corpus for <= 6 calendar years (a censored proxy for students and postdocs).",
        "growth": "Cumulative network per year; alpha from OLS of log E on log N (t interval); effective diameter = 90th percentile of LCC shortest paths.",
        "preferential_attachment": f"Node-years (degree at end of t-1, new links in t); A(k) = links gained / node-years at k; gamma from log cumulative kernel ~ (gamma+1) log k over k = 1..95th percentile; CI from {N_BOOT} faculty-cluster bootstraps.",
        "position_model": "Faculty with >= 2 papers 2016-20; network measures on the 2016-20 graph (isolate constraint set to 1); OLS with HC1 errors and lab fixed effects; ncs = citations / mean of dataset papers with the same subfield and year.",
        "fragility": "Node cut via node-splitting max-flow between all faculty of two labs within the LCC (cut may include their own faculty); top papers ranked by cross-lab faculty pairs created.",
        "link_prediction": f"Candidates = unlinked pairs of faculty active 2016-20 and 2021-26; scores from the 2016-20 graph and subfield vectors; AUC CI from {N_BOOT} stratified bootstraps; precision@50 with random tie-breaking; logistic weights fitted on 2016-18 -> 2019-20.",
        "twins": "Cross-lab pairs, each with >= 5 papers, never on any paper together, ranked by all-years subfield cosine.",
        "contagion": f"Rows = (faculty active in year t with earlier papers, t in 2018-2026, subfield not yet used); adoption = first paper in that subfield in t; exposure = a qualifying alter published there before t; relative risk with {N_BOOT} faculty-cluster bootstraps; random placebo averages 20 size-matched draws.",
        "main_path": "Internal citations ordered by (year, publication date, id), backward edges dropped; SPC edge weight = paths into citing paper x paths out of cited paper; global main path maximises summed SPC.",
        "entropy": "Shannon entropy (bits) of each lab's subfield distribution per year, also rarefied to a common sample size; turnover = Jaccard of top-10 subfields vs previous year.",
    }
    S["runtime_seconds"] = clock
    S["findings"] = findings
    S["methods"] = methods
    (st / "research_structure.json").write_text(json.dumps(json_safe(S), indent=2, default=float, allow_nan=False), encoding="utf-8")
    print(nt[nt.model == bip].round(3).to_string(index=False))
    print(val.round(3).to_string(index=False))
    print(lp.round(3).to_string(index=False))
    print(ct.round(3).to_string(index=False))
    print("\nFindings:")
    for f in findings:
        print(" -", f)
