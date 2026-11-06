"""Phase II calculations (instructor's additional directions). Pure functions on DataFrames, no network.

Input is the submitted dataset (one row per paper x faculty member x lab), so everything here reproduces from the
deliverable files. Journal impact factors come from step s16 (JCR file if supplied, else an OpenAlex proxy).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from types import SimpleNamespace

import networkx as nx
import numpy as np
import pandas as pd

ACSIR = "Academy of Scientific and Innovative Research"
_COLLAB = re.compile(r"^(.*)\s\(([A-Z?]{1,3})\)$")


# --------------------------------------------------------------------------- small helpers

def norm_issn(x) -> str:
    return re.sub(r"[^0-9Xx]", "", str(x or "")).upper()


def norm_title(x) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(x or "").lower()).strip()


def h_index(cites) -> int:
    c = sorted((int(x) for x in cites), reverse=True)
    return sum(1 for i, x in enumerate(c, 1) if x >= i)


def parse_collab(s: str) -> list[tuple[str, str]]:
    """'Name (IN); Other Name (FR)' -> [('Name', 'IN'), ('Other Name', 'FR')]."""
    out = []
    for part in (s or "").split("; "):
        part = part.strip()
        if part:
            m = _COLLAB.match(part)
            out.append((m.group(1).strip(), m.group(2)) if m else (part, "?"))
    return out


def author_class(n, p2) -> str:
    """Bucket a paper by author count using the configured thresholds (default <10, 10-99, 100-999, 1000+)."""
    multi, hyper, mega = p2.multi_author_min, p2.hyper_author_min, p2.mega_author_min
    if pd.isna(n):
        return "unknown"
    n = int(n)
    return (f"<{multi}" if n < multi else f"{multi}-{hyper - 1}" if n < hyper
            else f"{hyper}-{mega - 1}" if n < mega else f"{mega}+")


def class_order(p2) -> list[str]:
    return [f"<{p2.multi_author_min}", f"{p2.multi_author_min}-{p2.hyper_author_min - 1}",
            f"{p2.hyper_author_min}-{p2.mega_author_min - 1}", f"{p2.mega_author_min}+"]


# --------------------------------------------------------------------------- preparation

# Conference and poster abstracts that a journal prints in a supplement. They count as publications (OpenAlex lists them
# as journal papers), but they inherit the journal's impact factor, so they are kept out of the IF-ranked lists.
_ABSTRACT_TITLE = re.compile(r"^(?:[A-Z]{1,2})?\d{3,5}[A-Z]?(?=[A-Z][a-z])|^[A-Z]{1,3}\d{2,4}\.\s")   # "P5108Title...", "241PTitle...", "AB062. Title"
_ABSTRACT_DOI = re.compile(r"\.(?:p|po|op|s)\d{2,5}$", re.I)                                       # ".../ehy566.p5108", ".../acmi.cc2021.po0042"


def is_meeting_abstract(title, doi) -> bool:
    return bool(_ABSTRACT_TITLE.search(str(title or "").strip()) or _ABSTRACT_DOI.search(str(doi or "").strip()))


def prepare(main: pd.DataFrame, impact: pd.DataFrame, labs: list[str], p2) -> pd.DataFrame:
    """Typed copy of the dataset with impact factor, author class and collaborating-institution sets added."""
    d = main.copy()
    for c in ("year", "citations", "n_authors"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["issn_n"] = d["issn"].map(norm_issn)
    imp = impact.drop_duplicates("issn_n")[["issn_n", "impact_factor", "if_source"]]
    d = d.merge(imp, on="issn_n", how="left")
    d["is_journal"] = d["type"] == "journal"
    d["is_abstract"] = [is_meeting_abstract(a, b) for a, b in zip(d["title"], d["doi"])]
    d["is_q1"] = d["quartile"] == "Q1"
    d["author_class"] = d["n_authors"].map(lambda n: author_class(n, p2))
    lab_set = set(labs)

    def sets(s):
        names = [(n, cc) for n, cc in parse_collab(s) if n != ACSIR]
        return names
    parsed = d["coauthor_institutes_all"].map(sets)
    d["collab_all"] = parsed.map(lambda xs: {n for n, _ in xs})
    d["collab_in"] = parsed.map(lambda xs: {n for n, cc in xs if cc == "IN"})
    d["collab_foreign"] = parsed.map(lambda xs: {n for n, cc in xs if cc != "IN"})
    return d


def scopes_of(d: pd.DataFrame, labs: list[str]) -> dict[str, pd.DataFrame]:
    """scope -> one row per paper. A paper shared by two labs appears under each and once under ALL."""
    out = {lab: d[d["institution"] == lab].drop_duplicates("openalex_id") for lab in labs}
    out["ALL"] = d.drop_duplicates("openalex_id")
    return out


def _share(a, b):
    return float(a) / float(b) if b else float("nan")


def collab_count(papers: pd.DataFrame, key: str, scope: str, labs) -> int:
    """Distinct collaborating institutions on these papers. For "All labs" our own four labs are not collaborators."""
    u: set = set().union(*papers[key]) if len(papers) else set()
    return len(u - set(labs)) if scope == "ALL" else len(u)


# --------------------------------------------------------------------------- 1. institutional overview

def overview_table(d, labs, p2, roster_faculty: dict[str, int]) -> pd.DataFrame:
    sc = scopes_of(d, labs)
    t = list(p2.if_thresholds)
    rows = []
    for scope, p in sc.items():
        fac = d if scope == "ALL" else d[d["institution"] == scope]
        j = p[p["is_journal"]]
        known_q = j[j["quartile"].isin(["Q1", "Q2", "Q3", "Q4"])]
        r = {"scope": scope, "roster_faculty": roster_faculty.get(scope), "faculty_with_papers": int(fac["faculty_id"].nunique()),
             "papers": len(p), "journal_papers": len(j), "citations": int(p["citations"].sum()),
             "q1_papers": int(j["is_q1"].sum()), "quartile_known": len(known_q),
             "q1_share": _share(j["is_q1"].sum(), len(known_q)),
             "if_known": int(j["impact_factor"].notna().sum()),
             "if_coverage": _share(j["impact_factor"].notna().sum(), len(j)),
             "if_proxy_share": _share((j["if_source"].fillna("").str.contains("proxy")).sum(), j["impact_factor"].notna().sum())}
        near = np.zeros(len(j), dtype=bool)
        for x in t:
            near |= ((j["impact_factor"] - x).abs() <= 0.10 * x).to_numpy()
        r["if_borderline_papers"] = int(near.sum())
        r["if_borderline_share"] = _share(near.sum(), len(j))
        for x in t:
            r[f"papers_if_gt{x}"] = int((j["impact_factor"] > x).sum())
            r[f"q1_if_gt{x}"] = int((j["is_q1"] & (j["impact_factor"] > x)).sum())
            r[f"q1_if_gt{x}_share_of_q1"] = _share(r[f"q1_if_gt{x}"], r["q1_papers"])
        for c in class_order(p2):
            sub = p[p["author_class"] == c]
            r[f"papers_{c}"] = len(sub)
            r[f"share_{c}"] = _share(len(sub), len(p))
            r[f"citations_{c}"] = int(sub["citations"].sum())
            r[f"citation_share_{c}"] = _share(sub["citations"].sum(), p["citations"].sum())
        multi = p[p["n_authors"] >= p2.multi_author_min]
        r["papers_multi"] = len(multi)
        r["share_multi"] = _share(len(multi), len(p))
        r["mean_authors"] = float(p["n_authors"].mean())
        r["median_authors"] = float(p["n_authors"].median())
        nh = p[p["n_authors"] < p2.hyper_author_min]        # consortium papers inflate this count enormously
        for key, name in (("collab_all", "all"), ("collab_in", "indian"), ("collab_foreign", "foreign")):
            r[f"collab_inst_{name}"] = collab_count(p, key, scope, labs)
            r[f"collab_inst_{name}_excl_hyper"] = collab_count(nh, key, scope, labs)
        rows.append(r)
    return pd.DataFrame(rows)


def yearly_table(d, labs, p2) -> pd.DataFrame:
    sc = scopes_of(d, labs)
    t = list(p2.if_thresholds)
    rows = []
    for scope, p in sc.items():
        for year, g in p.groupby("year"):
            j = g[g["is_journal"]]
            r = {"scope": scope, "year": int(year), "papers": len(g), "citations": int(g["citations"].sum()),
                 "papers_lt_multi": int((g["n_authors"] < p2.multi_author_min).sum()),
                 "papers_multi": int((g["n_authors"] >= p2.multi_author_min).sum()),
                 "papers_hyper": int((g["n_authors"] >= p2.hyper_author_min).sum()),
                 "q1_papers": int(j["is_q1"].sum())}
            for x in t:
                r[f"q1_if_gt{x}"] = int((j["is_q1"] & (j["impact_factor"] > x)).sum())
            nh = g[g["n_authors"] < p2.hyper_author_min]
            for key, name in (("collab_all", "all"), ("collab_in", "indian"), ("collab_foreign", "foreign")):
                r[f"collab_inst_{name}"] = collab_count(g, key, scope, labs)
                r[f"collab_inst_{name}_excl_hyper"] = collab_count(nh, key, scope, labs)
            ext = g["collab_all"].map(lambda s: bool(s - set(labs)))
            r["papers_with_external_collab"] = int(ext.sum())
            rows.append(r)
    return pd.DataFrame(rows).sort_values(["scope", "year"]).reset_index(drop=True)


def if_histogram(d, labs, top: int = 20) -> pd.DataFrame:
    """Journal papers by impact factor in bins of 1 (the last bin is `top` and above), per scope, with the Q1 count."""
    sc = scopes_of(d, labs)
    rows = []
    for scope, p in sc.items():
        j = p[p["is_journal"] & p["impact_factor"].notna()]
        b = np.minimum(np.floor(j["impact_factor"]).astype(int), top)
        for k in range(top + 1):
            m = (b == k).to_numpy()
            rows.append({"scope": scope, "bin_start": k, "open_ended": k == top, "papers": int(m.sum()),
                         "q1_papers": int(j["is_q1"].to_numpy()[m].sum())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- 2. faculty comparison

def faculty_table(d, labs, p2, fm: pd.DataFrame) -> pd.DataFrame:
    """One row per faculty member. `fm` is outputs/stats/faculty_metrics.csv (network measures, lifetime h)."""
    t = list(p2.if_thresholds)
    rows = []
    for fid, g0 in d.groupby("faculty_id"):
        g = g0.drop_duplicates("openalex_id")
        j = g[g["is_journal"]]
        hyper = g[g["n_authors"] >= p2.hyper_author_min]
        multi = g[g["n_authors"] >= p2.multi_author_min]
        cit = int(g["citations"].sum())
        top = int(g["citations"].max()) if len(g) else 0
        lab = g0["institution"].iloc[0]
        r = {"faculty_id": fid, "name": g0["author"].iloc[0], "lab": lab, "department": g0["department"].iloc[0],
             "status": g0["faculty_status"].iloc[0], "papers": len(g), "journal_papers": len(j),
             "q1_papers": int(j["is_q1"].sum()), "citations": cit,
             "papers_multi": len(multi), "papers_hyper": len(hyper),
             "citations_from_multi": int(multi["citations"].sum()), "citations_from_hyper": int(hyper["citations"].sum()),
             "cit_share_multi": _share(multi["citations"].sum(), cit), "cit_share_hyper": _share(hyper["citations"].sum(), cit),
             "citations_excl_hyper": cit - int(hyper["citations"].sum()),
             "top_paper_citations": top, "top_paper_share": _share(top, cit),
             "h_all": h_index(g["citations"]), "h_excl_hyper": h_index(g.loc[g["n_authors"] < p2.hyper_author_min, "citations"]),
             "collab_inst_all": len(set().union(*g["collab_all"])) if len(g) else 0,
             "collab_inst_indian": len(set().union(*g["collab_in"])) if len(g) else 0,
             "collab_inst_foreign": len(set().union(*g["collab_foreign"])) if len(g) else 0}
        for x in t:
            r[f"q1_if_gt{x}"] = int((j["is_q1"] & (j["impact_factor"] > x)).sum())
        r["mean_if"] = float(j["impact_factor"].mean()) if j["impact_factor"].notna().any() else float("nan")
        rows.append(r)
    f = pd.DataFrame(rows)
    keep = [c for c in ("faculty_id", "degree", "strength", "betweenness", "community", "n_partner_insts", "h_lifetime",
                        "designation") if c in fm.columns]
    f = f.merge(fm[keep], on="faculty_id", how="left")
    enough = f["citations"] >= p2.faculty_flag_min_citations
    f["flag_hyper"] = enough & (f["cit_share_hyper"] >= p2.faculty_flag_share_hyper)
    f["flag_multi"] = enough & (f["cit_share_multi"] >= p2.faculty_flag_share_multi)
    f["flag"] = [("; ".join(x for x in (
        f"{100 * h:.0f}% of citations from papers with {p2.hyper_author_min}+ authors" if fh else "",
        f"{100 * m:.0f}% from papers with {p2.multi_author_min}+ authors" if fm_ and not fh else "") if x))
        for fh, fm_, h, m in zip(f["flag_hyper"], f["flag_multi"], f["cit_share_hyper"], f["cit_share_multi"])]
    f["rank_productive"] = f["papers"].rank(ascending=False, method="min").astype(int)
    f["rank_connected"] = f["collab_inst_all"].rank(ascending=False, method="min").astype(int)
    return f.sort_values(["lab", "papers"], ascending=[True, False]).reset_index(drop=True)


# --------------------------------------------------------------------------- journals and top papers

def journals_table(d, labs, top: int = 20) -> pd.DataFrame:
    sc = scopes_of(d, labs)
    rows = []
    for scope, p in sc.items():
        j = p[p["is_journal"]]
        g = j.groupby("journal_name")
        agg = g.agg(papers=("openalex_id", "size"), citations=("citations", "sum"), impact_factor=("impact_factor", "first"),
                    if_source=("if_source", "first"), quartile=("quartile", lambda s: s.mode().iat[0] if len(s.mode()) else "NA"),
                    issn=("issn", "first")).reset_index()
        agg = agg.sort_values(["papers", "citations"], ascending=False).head(top)
        agg.insert(0, "rank", range(1, len(agg) + 1))
        agg.insert(0, "scope", scope)
        rows.append(agg)
    return pd.concat(rows, ignore_index=True)


def _paper_cols(p: pd.DataFrame, names: dict) -> pd.DataFrame:
    out = p[["openalex_id", "title", "journal_name", "impact_factor", "if_source", "quartile", "year", "citations",
             "n_authors", "doi"]].copy()
    out["faculty"] = out["openalex_id"].map(names)
    return out


def top_papers_by_if(d, labs, n: int = 30) -> pd.DataFrame:
    """Top n papers per scope ranked by the journal's impact factor, then by citations."""
    sc = scopes_of(d, labs)
    names = d.groupby("openalex_id")["author"].agg(lambda s: "; ".join(sorted(set(s))))
    rows = []
    for scope, p in sc.items():
        q = _paper_cols(p[p["is_journal"] & p["impact_factor"].notna() & ~p["is_abstract"]], names)
        q = q.sort_values(["impact_factor", "citations"], ascending=False).head(n)
        q.insert(0, "rank", range(1, len(q) + 1))
        q.insert(0, "scope", scope)
        rows.append(q)
    return pd.concat(rows, ignore_index=True).drop(columns=["openalex_id"])


def faculty_top_papers(d, n: int = 10) -> pd.DataFrame:
    """Each faculty member's top n papers ranked by journal impact factor (then citations)."""
    rows = []
    for fid, g0 in d.groupby("faculty_id"):
        g = g0.drop_duplicates("openalex_id")
        g = g[g["is_journal"] & g["impact_factor"].notna() & ~g["is_abstract"]].sort_values(["impact_factor", "citations"], ascending=False).head(n)
        if g.empty:
            continue
        q = g[["title", "journal_name", "impact_factor", "if_source", "quartile", "year", "citations", "n_authors", "doi"]].copy()
        q.insert(0, "rank", range(1, len(q) + 1))
        q.insert(0, "lab", g0["institution"].iloc[0])
        q.insert(0, "name", g0["author"].iloc[0])
        q.insert(0, "faculty_id", fid)
        rows.append(q)
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- hyperauthorship

def author_class_table(d, labs, p2) -> pd.DataFrame:
    """Papers and citations by author-count class, per scope: where do the citations come from?"""
    sc = scopes_of(d, labs)
    rows = []
    for scope, p in sc.items():
        tot = p["citations"].sum()
        for c in class_order(p2):
            g = p[p["author_class"] == c]
            rows.append({"scope": scope, "author_class": c, "papers": len(g), "citations": int(g["citations"].sum()),
                         "share_of_papers": _share(len(g), len(p)), "share_of_citations": _share(g["citations"].sum(), tot),
                         "mean_citations": float(g["citations"].mean()) if len(g) else float("nan")})
    return pd.DataFrame(rows)


def hyper_papers(d, labs, p2) -> pd.DataFrame:
    p = d.drop_duplicates("openalex_id")
    p = p[p["n_authors"] >= p2.hyper_author_min].copy()
    labs_of = d.groupby("openalex_id")["institution"].agg(lambda s: "; ".join(sorted(set(s))))
    fac_of = d.groupby("openalex_id")["author"].agg(lambda s: "; ".join(sorted(set(s))))
    p["labs"] = p["openalex_id"].map(labs_of)
    p["our_faculty"] = p["openalex_id"].map(fac_of)
    p["share_of_all_citations"] = p["citations"] / d.drop_duplicates("openalex_id")["citations"].sum()
    return (p.sort_values("citations", ascending=False)[["title", "journal_name", "year", "n_authors", "citations",
                                                         "share_of_all_citations", "labs", "our_faculty", "doi"]]
            .reset_index(drop=True))


# --------------------------------------------------------------------------- 3. networks over time

def temporal_faculty_network(pairs: pd.DataFrame, fac_lab: dict[str, str], labs: list[str]) -> pd.DataFrame:
    """Faculty co-authorship network year by year (students excluded), and cumulatively.

    `pairs` is the submitted authorship_network.csv. Nodes are 'F:<faculty_id>' ids; an edge is a pair of faculty who
    co-authored at least one dataset paper that year. Per lab, the graph is induced on that lab's faculty.
    """
    both = pairs[(pairs["a_is_faculty"] == "TRUE") & (pairs["b_is_faculty"] == "TRUE")]
    e = both[["author_a_id", "author_b_id", "year"]].copy()
    e["year"] = pd.to_numeric(e["year"], errors="coerce")
    e = e.dropna().drop_duplicates()
    e["a"] = e["author_a_id"].str.replace("^F:", "", regex=True)
    e["b"] = e["author_b_id"].str.replace("^F:", "", regex=True)
    lab_of = lambda f: fac_lab.get(f)
    e["la"], e["lb"] = e["a"].map(lab_of), e["b"].map(lab_of)
    rows = []
    for scope in [*labs, "ALL"]:
        sub = e if scope == "ALL" else e[(e["la"] == scope) & (e["lb"] == scope)]
        seen: set = set()
        for mode in ("year", "cumulative"):
            seen = set()
            for y in sorted(e["year"].unique()):
                cur = sub[sub["year"] == y] if mode == "year" else sub[sub["year"] <= y]
                edges = {tuple(sorted(x)) for x in zip(cur["a"], cur["b"])}
                G = nx.Graph(); G.add_edges_from(edges)
                n, m = G.number_of_nodes(), G.number_of_edges()
                comp = max((len(c) for c in nx.connected_components(G)), default=0)
                new = len(edges - seen) if mode == "year" else float("nan")
                rows.append({"scope": scope, "mode": mode, "year": int(y), "faculty_active": n, "links": m,
                             "mean_degree": 2 * m / n if n else 0.0, "density": 2 * m / (n * (n - 1)) if n > 1 else 0.0,
                             "largest_component_share": comp / n if n else 0.0, "new_links": new,
                             "cross_lab_links": int(sum(1 for a, b in edges if lab_of(a) != lab_of(b)))})
                if mode == "year":
                    seen |= edges
    return pd.DataFrame(rows)


def temporal_citations(cit: pd.DataFrame, labs: list[str]) -> pd.DataFrame:
    """Citation activity by citing year: citations among our papers (within lab / to another lab), and Indian in/out flow."""
    c = cit.copy()
    c["year"] = pd.to_numeric(c["year"], errors="coerce")
    lab_set = set(labs)
    c["src"] = c["source_inst"].map(lambda s: lab_set & set(str(s).split("; ")))
    c["tgt"] = c["target_inst"].map(lambda s: lab_set & set(str(s).split("; ")))
    rows = []
    for scope in [*labs, "ALL"]:
        for y, g in c.groupby("year"):
            inte = g[g["edge_scope"] == "internal"]
            has = lambda col, frame: np.array([scope in s for s in frame[col]], dtype=bool)
            if scope == "ALL":
                s_int = inte
                w_int = inte[np.array([bool(a & b) for a, b in zip(inte["src"], inte["tgt"])], dtype=bool)]
                s_out, s_in = g[g["edge_scope"] == "outflow"], g[g["edge_scope"] == "inflow"]
            else:
                s_int = inte[has("src", inte)]
                w_int = s_int[has("tgt", s_int)]
                s_out = g[(g["edge_scope"] == "outflow").to_numpy() & has("src", g)]
                s_in = g[(g["edge_scope"] == "inflow").to_numpy() & has("tgt", g)]
            rows.append({"scope": scope, "year": int(y), "internal_citations": len(s_int),
                         "within_lab": len(w_int), "to_other_labs": len(s_int) - len(w_int),
                         "indian_out": len(s_out), "indian_in": len(s_in)})
    return pd.DataFrame(rows)


def institution_network(pairs: pd.DataFrame, partner_cluster: dict[str, str], labs: list[str], k: int, seed: int = 42):
    """Institution-level co-authorship network (Indian institutions): nodes = our labs plus the k partners with most
    joint papers; an edge's weight is the number of distinct papers on which authors of the two institutions co-wrote,
    also given per year. AcSIR (the CSIR student academy) is left out as a registration affiliation, not a collaborator."""
    r = pairs[(pairs["indian_link"] == "TRUE")][["paper_doi", "inst_a", "inst_b", "year"]].copy()
    r = r[(r["inst_a"] != ACSIR) & (r["inst_b"] != ACSIR) & (r["inst_a"] != r["inst_b"])]
    r["year"] = pd.to_numeric(r["year"], errors="coerce")
    r["u"] = [min(a, b) for a, b in zip(r["inst_a"], r["inst_b"])]
    r["v"] = [max(a, b) for a, b in zip(r["inst_a"], r["inst_b"])]
    r = r.drop_duplicates(["paper_doi", "u", "v"])
    deg = Counter()
    for u, v in zip(r["u"], r["v"]):
        deg[u] += 1; deg[v] += 1
    partners = [n for n, _ in deg.most_common() if n not in labs][:k]
    nodes = [*labs, *partners]
    keep = set(nodes)
    r = r[r["u"].isin(keep) & r["v"].isin(keep)]
    edges = []
    for (u, v), g in r.groupby(["u", "v"]):
        edges.append({"s": u, "t": v, "w": int(g["paper_doi"].nunique()),
                      "by_year": {str(int(y)): int(x) for y, x in g.groupby("year")["paper_doi"].nunique().items()}})
    G = nx.Graph()
    G.add_nodes_from(nodes)
    for e in edges:
        G.add_edge(e["s"], e["t"], weight=e["w"])
    pos = nx.spring_layout(G, weight="weight", seed=seed, k=1.6 / max(1, np.sqrt(len(nodes))), iterations=200)
    nd = [{"id": n, "kind": "lab" if n in labs else "partner", "cluster": "CSIR" if n in labs else partner_cluster.get(n, "Other"),
           "papers": int(deg[n]), "x": float(pos[n][0]) * 500, "y": float(pos[n][1]) * 500} for n in nodes]
    return {"nodes": nd, "edges": edges, "years": sorted(int(y) for y in r["year"].dropna().unique())}


# --------------------------------------------------------------------------- 4. heavy citing institutions

def citer_table(ic: pd.DataFrame, ownership: dict, p2, labs: list[str]) -> pd.DataFrame:
    """Institutions citing our labs, with ownership and two flags. `ic` is the submitted indian_connections.csv."""
    x = ic[(ic["partner_is_csir_academy"] != "TRUE") & (ic["partner_in_group"] != "TRUE")].copy()
    for c in ("shared_papers", "cites_in", "cites_out"):
        x[c] = pd.to_numeric(x[c], errors="coerce").fillna(0).astype(int)
    parts = []
    for scope, g in [*((l, x[x["your_inst"] == l]) for l in labs), ("ALL", x)]:
        a = g.groupby(["partner_openalex_id", "partner_inst", "partner_cluster"], as_index=False)[
            ["cites_in", "cites_out", "shared_papers"]].sum()
        a.insert(0, "scope", scope)
        parts.append(a)
    t = pd.concat(parts, ignore_index=True)
    t["cites_per_shared_paper"] = t["cites_in"] / t["shared_papers"].clip(lower=1)
    t["in_out_ratio"] = t["cites_in"] / t["cites_out"].replace(0, np.nan)
    own = t["partner_openalex_id"].map(lambda i: ownership.get(i, {}).get("ownership"))
    fallback = t["partner_cluster"].map({"CSIR": "government", "ICMR": "government", "DAE": "government", "DBT": "government",
                                         "IIT": "government", "NIT": "government", "Central University": "government",
                                         "IISc/TIFR/IISER": "government", "Premier Science": "government",
                                         "NIPER": "government", "Government": "government", "Industry": "private"})
    t["ownership"] = own.fillna(fallback).fillna("unclassified")
    t["ownership_source"] = np.where(own.notna(), "classification file", np.where(fallback.notna(), "cluster rule", "none"))
    t["flag_heavy"] = t["cites_in"] >= p2.citer_min_cites
    t["flag_citation_heavy_vs_collab"] = t["flag_heavy"] & (t["cites_per_shared_paper"] >= p2.citer_ratio_min)
    t["flag_non_government"] = t["flag_heavy"] & (t["ownership"] == "private") & (t["cites_per_shared_paper"] >= p2.citer_ratio_min)
    return t.sort_values(["scope", "cites_in"], ascending=[True, False]).reset_index(drop=True)


def citer_evidence(edges: pd.DataFrame, works: dict, cited_authors: dict, cited_title: dict, ids: dict) -> pd.DataFrame:
    """Indicators for why an institution cites us so much, from its citing papers.

    edges: columns partner, citing_doi, cited_doi (one row per citation to one of our papers).
    works: citing_doi -> {'authors': [(id, name)], 'journal': str, 'type': str, 'year': int}
    cited_authors: our paper doi -> set of OpenAlex author ids on it.
    """
    rows = []
    for partner, g in edges.groupby("partner"):
        cp = g.drop_duplicates("citing_doi")
        ws = [works[x] for x in cp["citing_doi"] if x in works]
        n = len(cp)
        au = Counter(); jr = Counter(); yr = Counter(); rev = 0
        for w in ws:
            for aid, nm in w["authors"]:
                au[(aid, nm)] += 1
            jr[w.get("journal") or "?"] += 1
            yr[w.get("year")] += 1
            rev += int(w.get("type") == "review")
        shared = 0
        for _, r in g.drop_duplicates(["citing_doi", "cited_doi"]).iterrows():
            w = works.get(r["citing_doi"])
            if w and {a for a, _ in w["authors"]} & cited_authors.get(r["cited_doi"], set()):
                shared += 1
        cited = Counter(g["cited_doi"])
        tc = cited.most_common(1)[0] if cited else (None, 0)
        (top_au, top_au_n) = au.most_common(1)[0] if au else (("", ""), 0)
        tj, tjn = jr.most_common(1)[0] if jr else ("", 0)
        ty, tyn = yr.most_common(1)[0] if yr else (None, 0)
        rows.append({"partner_openalex_id": ids.get(partner, ""), "partner_inst": partner, "citations": len(g),
                     "citing_papers": n, "citations_per_citing_paper": len(g) / n if n else np.nan,
                     "our_papers_cited": g["cited_doi"].nunique(),
                     "top_cited_paper": cited_title.get(tc[0], ""), "top_cited_paper_share": tc[1] / len(g) if len(g) else np.nan,
                     "top_citing_author": top_au[1], "top_citing_author_papers": top_au_n,
                     "top_citing_author_share": top_au_n / n if n else np.nan,
                     "citations_with_shared_author": shared, "shared_author_share": shared / len(g) if len(g) else np.nan,
                     "top_citing_journal": tj, "top_citing_journal_share": tjn / n if n else np.nan,
                     "top_citing_year": ty, "top_citing_year_share": tyn / n if n else np.nan,
                     "review_share": rev / n if n else np.nan, "citing_papers_found": len(ws)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- size-normalised heavy citers

def citer_normalised(t: pd.DataFrame, output: pd.DataFrame, p2) -> pd.DataFrame:
    """Adds a size-normalised view to the citer table.

    `output` has one row per partner_openalex_id: works_all (articles and reviews of the institution in the window) and
    works_ls (the same, in the labs' main fields). Raw citation counts reward big institutions, so for every scope the
    institutions that gave at least `citer_norm_min_cites` citations and have at least `citer_norm_min_works` papers in
    those fields are compared on
      rate_per_1000   = citations to the scope per 1,000 papers in the labs' fields
      expected_cites  = papers in the labs' fields x the pooled rate of that comparison group
      obs_exp         = cites_in / expected_cites
      rate_z          = robust z-score (median and MAD) of log10(rate_per_1000) within the group
      rate_vs_gov     = rate / median rate of the government institutions in the group
    `flag_norm_outlier` is rate_z >= citer_norm_z; `flag_non_government_norm` keeps only private institutions.
    Institutions outside the comparison group get NaN, never a made-up value.
    """
    t = t.drop(columns=[c for c in t.columns if c in ("works_all", "works_ls")], errors="ignore")
    t = t.merge(output[["partner_openalex_id", "works_all", "works_ls"]], on="partner_openalex_id", how="left")
    for c in ("rate_per_1000", "rate_all_per_1000", "expected_cites", "obs_exp", "rate_z", "rate_vs_gov", "rate_pctile"):
        t[c] = np.nan
    t["norm_group"] = False
    t["flag_norm_outlier"] = False
    for scope, idx in t.groupby("scope").groups.items():
        g = t.loc[idx]
        g = g[(g["cites_in"] >= p2.citer_norm_min_cites) & (g["works_ls"] >= p2.citer_norm_min_works)]
        if len(g) < 5:
            continue
        rate = g["cites_in"] / g["works_ls"] * 1000
        logr = np.log10(rate.clip(lower=1e-9))
        mad = float(np.median(np.abs(logr - logr.median())))
        z = (logr - logr.median()) / (1.4826 * mad) if mad > 0 else logr * np.nan
        pooled = g["cites_in"].sum() / g["works_ls"].sum()
        gov = rate[g["ownership"] == "government"]
        t.loc[g.index, "norm_group"] = True
        t.loc[g.index, "rate_per_1000"] = rate
        t.loc[g.index, "rate_all_per_1000"] = g["cites_in"] / g["works_all"].clip(lower=1) * 1000
        t.loc[g.index, "expected_cites"] = g["works_ls"] * pooled
        t.loc[g.index, "obs_exp"] = g["cites_in"] / (g["works_ls"] * pooled)
        t.loc[g.index, "rate_z"] = z
        t.loc[g.index, "rate_pctile"] = rate.rank(pct=True) * 100
        if len(gov):
            t.loc[g.index, "rate_vs_gov"] = rate / float(gov.median())
    t["flag_norm_outlier"] = t["norm_group"] & (t["rate_z"] >= p2.citer_norm_z)
    t["flag_non_government_norm"] = t["flag_norm_outlier"] & (t["ownership"] == "private")
    return t


def norm_summary(t: pd.DataFrame, p2) -> dict:
    """Headline findings of the normalised analysis (scope ALL) with simple sensitivity checks."""
    a = t[(t["scope"] == "ALL") & t["norm_group"]].copy()
    flagged = t[(t["scope"] == "ALL") & t["flag_non_government"]]
    assessed = flagged[flagged["norm_group"]]
    raw_rank = a["cites_in"].rank(ascending=False)
    norm_rank = a["rate_per_1000"].rank(ascending=False)
    out = {
        "compared": int(len(a)), "min_cites": p2.citer_norm_min_cites, "min_works": p2.citer_norm_min_works, "z": p2.citer_norm_z,
        "flagged_before": int(len(flagged)), "flagged_assessed": int(len(assessed)),
        "flagged_not_assessed": sorted(flagged.loc[~flagged["norm_group"], "partner_inst"]),
        "flagged_still_outliers": int(assessed["flag_norm_outlier"].sum()),
        "still_outliers": sorted(assessed.loc[assessed["flag_norm_outlier"], "partner_inst"]),
        "no_longer_outliers": sorted(assessed.loc[~assessed["flag_norm_outlier"], "partner_inst"]),
        "new_outliers_any_ownership": sorted(a.loc[a["flag_norm_outlier"] & ~a["partner_inst"].isin(flagged["partner_inst"]), "partner_inst"]),
        "median_rate": {k: float(v) for k, v in a.groupby("ownership")["rate_per_1000"].median().items()},
        "n_by_ownership": {k: int(v) for k, v in a.groupby("ownership").size().items()},
        "rank_corr_raw_vs_normalised": float(raw_rank.corr(norm_rank, method="spearman")) if len(a) > 2 else None,
        "outliers_by_ownership": {k: int(v) for k, v in a[a["flag_norm_outlier"]].groupby("ownership").size().items()},
    }
    # sensitivity: stricter / looser z, and the all-fields denominator instead of the labs' fields
    sens = {}
    for z in (1.5, 2.0, 2.5, 3.0):
        sens[f"z>={z}"] = int((assessed["rate_z"] >= z).sum())
    lr = np.log10((a["cites_in"] / a["works_all"].clip(lower=1) * 1000).clip(lower=1e-9))
    mad = float(np.median(np.abs(lr - lr.median())))
    zz = (lr - lr.median()) / (1.4826 * mad) if mad > 0 else lr * np.nan
    sens["all_fields_denominator_outliers_among_flagged"] = int((zz[assessed.index] >= p2.citer_norm_z).sum())
    out["sensitivity_flagged_outliers"] = sens
    return out



# --------------------------------------------------------------------------- departments

def department_table(d: pd.DataFrame, labs: list[str], p2, fac: pd.DataFrame) -> pd.DataFrame:
    """One row per (lab, department): output, quality, citations and collaboration, with consortium effects shown apart.

    A paper shared by several faculty of one department counts once for that department. Departments with fewer than three
    faculty are marked `small`: their ratios move with one person."""
    x = d.copy()
    x["department"] = x["department"].replace("", "Unknown")
    flagged = set(fac.loc[fac["flag"].fillna("") != "", "faculty_id"]) if "flag" in fac else set()
    t5, t10 = p2.if_thresholds
    rows = []
    for (lab, dept), g in x.groupby(["institution", "department"]):
        p = g.drop_duplicates("openalex_id")
        j = p[p["is_journal"]]
        kq = j[j["quartile"].isin(["Q1", "Q2", "Q3", "Q4"])]
        q1 = kq[kq["is_q1"]]
        hyper = p[p["n_authors"] >= p2.hyper_author_min]
        nh = p[p["n_authors"] < p2.hyper_author_min]
        cit = float(p["citations"].sum())
        facs = list(g["faculty_id"].unique())
        union = set().union(*p["collab_all"]) if len(p) else set()
        union_nh = set().union(*nh["collab_all"]) if len(nh) else set()
        rows.append({
            "lab": lab, "department": dept, "faculty": len(facs), "papers": len(p), "papers_per_faculty": len(p) / len(facs),
            "q1_papers": len(q1), "q1_share": _share(len(q1), len(kq)),
            f"q1_if_gt{t5}": int((q1["impact_factor"] > t5).sum()), f"q1_if_gt{t10}": int((q1["impact_factor"] > t10).sum()),
            "mean_if": float(j["impact_factor"].mean()) if j["impact_factor"].notna().any() else float("nan"),
            "citations": int(cit), "cites_per_paper": cit / len(p) if len(p) else float("nan"),
            "cit_share_hyper": _share(hyper["citations"].sum(), cit),
            "collab_inst": len(union), "collab_inst_excl_hyper": len(union_nh),
            "flagged_faculty": sum(f in flagged for f in facs), "small": len(facs) < 3})
    return pd.DataFrame(rows).sort_values(["lab", "papers"], ascending=[True, False]).reset_index(drop=True)


# --------------------------------------------------------------------------- sensitivity to the impact-factor source

def if_sensitivity(d: pd.DataFrame, impact: pd.DataFrame, p2) -> list[dict]:
    """Q1 papers above each impact-factor line (all labs) when every journal takes its value from one source instead.

    Where a source does not list a journal the next source is used, so every variant covers the same papers."""
    t5, t10 = p2.if_thresholds
    imp = impact.drop_duplicates("issn_n").set_index("issn_n")
    final = imp["impact_factor"]
    variants = [
        ("As used: JCR, else Scimago, else OpenAlex", final),
        ("OpenAlex 2-year mean citedness for every journal", imp["if_openalex_proxy"].fillna(final)),
        ("Scimago cites per document where listed, else OpenAlex", imp["if_scimago"].fillna(imp["if_openalex_proxy"]).fillna(final)),
        ("JCR where listed, else no value", imp["if_jcr"]),
    ]
    p = d.drop_duplicates("openalex_id")
    p = p[p["is_journal"] & p["is_q1"]]
    out = []
    for name, ser in variants:
        v = p["issn_n"].map(ser)
        out.append({"source": name, "journals_with_value_share": float(v.notna().mean()) if len(p) else float("nan"),
                    f"q1_if_gt{t5}": int((v > t5).sum()), f"q1_if_gt{t10}": int((v > t10).sum())})
    return out


# --------------------------------------------------------------------------- author and affiliation checks

def quality_summary(main: pd.DataFrame, roster: pd.DataFrame, overrides: pd.DataFrame, labs: list[str]) -> dict:
    """Counts that show how the faculty list, the author matches and the affiliations were checked."""
    fa = main.drop_duplicates("faculty_id")
    ids = {}
    for fid, s in zip(fa["faculty_id"], fa["author_openalex_ids"]):
        ids[fid] = {i for i in str(s).split(";") if i}
    owner: dict[str, set] = {}
    for fid, s in ids.items():
        for i in s:
            owner.setdefault(i, set()).add(fid)
    have = set(fa["faculty_id"])
    per_lab = []
    for lab in labs:
        r = roster[roster["institution"] == lab]
        per_lab.append({"lab": lab, "roster": len(r), "current": int((r["status"] == "current").sum()), "former": int((r["status"] == "former").sum()),
                        "with_papers": int(r["faculty_id"].isin(have).sum()), "without_papers": int((~r["faculty_id"].isin(have)).sum())})
    rows = len(main)
    return {
        "per_lab": per_lab, "roster": len(roster), "faculty_with_papers": len(have), "faculty_without_papers": int(len(roster) - len(set(roster["faculty_id"]) & have)),
        "rows": rows, "affiliation_lineage_rows": int((main["affil_method"] == "lineage").sum()), "affiliation_text_rows": int((main["affil_method"] == "raw_string").sum()),
        "dept_from_website_rows": int((main["dept_source"] == "website").sum()), "dept_from_openalex_rows": int((main["dept_source"] == "openalex").sum()),
        "quartile_sjr_rows": int((main["quartile_source"] == "sjr").sum()), "quartile_none_rows": int((main["quartile_source"] == "none").sum()),
        "roster_with_orcid": int((roster["orcid"] != "").sum()), "roster_with_profile_dois": int((roster["profile_dois"] != "").sum()),
        "manual_match_decisions": len(overrides), "duplicate_roster_names": int(roster["name"].duplicated().sum()),
        "faculty_in_more_than_one_lab": int((main.groupby("faculty_id")["institution"].nunique() > 1).sum()),
        "openalex_ids_shared_by_two_faculty": int(sum(len(v) > 1 for v in owner.values())),
        "faculty_without_openalex_id": int(sum(1 for s in ids.values() if not s)),
    }
