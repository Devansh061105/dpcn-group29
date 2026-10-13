"""S12: statistics tables and figures (guide §7, S12; plan §7.3, D9, D10).

Every table is computed from the submitted outputs/submission/group29_data.csv (plus the network outputs of
S09-S11), so each number in the report and the dashboard can be reproduced from the submission.

  Q1 fraction (D9)  Q1 papers / journal papers with a known quartile; coverage reported beside it
  h-index (D10)     window h-index from the faculty member's dataset papers; lifetime h from OpenAlex for context
  CAGR              (P_2025 / P_2016)^(1/9) - 1; 2026 is a partial year

Outputs: outputs/stats/*.csv, outputs/figures/*.png.
"""
from __future__ import annotations

import json
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import StepFailed  # noqa: E402

log = logging.getLogger("dpcn.s12")

# categorical slots 1-4 and an ordinal one-hue ramp for quartiles, both checked with the dataviz palette validator
LAB_COLORS = {"CSIR-CCMB": "#2a78d6", "CSIR-IGIB": "#eb6834", "CSIR-IMTECH": "#1baf7a", "CSIR-CDRI": "#eda100",
              "ALL": "#52514e"}
Q_COLORS = {"Q1": "#104281", "Q2": "#256abf", "Q3": "#5598e7", "Q4": "#86b6ef", "NA": "#c3c2b7"}
QS = ["Q1", "Q2", "Q3", "Q4"]
CORE = ["A*", "A", "B", "C"]


def h_index(cits) -> int:
    c = sorted((int(x) for x in cits), reverse=True)
    return sum(1 for i, x in enumerate(c, 1) if x >= i)


def cagr(p0: float, p1: float, years: int) -> float | None:
    return (p1 / p0) ** (1 / years) - 1 if p0 > 0 and p1 > 0 else None


def has_foreign(s: str) -> bool:
    """coauthor_institutes_all lists 'Name (CC)'; any country other than IN means a foreign co-author."""
    return any(part.rstrip().endswith(")") and not part.rstrip().endswith("(IN)") and "(" in part
               for part in (s or "").split("; ") if part)


def scopes(df: pd.DataFrame, labs: list[str]):
    """(scope name, unique-paper frame) for each lab and for all labs together."""
    for lab in labs:
        yield lab, df[df["institution"] == lab].drop_duplicates("openalex_id")
    yield "ALL", df.drop_duplicates("openalex_id")


def share_table(papers: pd.DataFrame, col: str, scope: str, top: int = 10) -> pd.DataFrame:
    vc = papers[col].replace("", "Unknown").value_counts()
    head = vc.head(top)
    rest = vc.iloc[top:].sum()
    if rest:
        head = pd.concat([head, pd.Series({"Other": rest})])
    return pd.DataFrame({"scope": scope, col: head.index, "papers": head.values,
                         "share": (head.values / max(len(papers), 1)).round(4)})


def build_tables(cfg, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    labs = [l["short"] for l in cfg.labs]
    y0, y1, ycagr = cfg.window.start, cfg.window.end, cfg.window.cagr_end
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)
    T: dict[str, pd.DataFrame] = {}

    # ---- institution level
    summ, years, quart, journals, fields, subfields, domains, cited = [], [], [], [], [], [], [], []
    for scope, p in scopes(df, labs):
        j = p[p["type"] == "journal"]
        known = j[j["quartile"].isin(QS)]
        per_year = p.groupby("year").size().reindex(range(y0, y1 + 1), fill_value=0)
        fac = df if scope == "ALL" else df[df["institution"] == scope]
        n_fac = fac["faculty_id"].nunique()
        n_roster = len(roster) if scope == "ALL" else int((roster["institution"] == scope).sum())
        summ.append({
            "scope": scope, "roster_faculty": n_roster, "faculty_with_papers": n_fac, "papers": len(p),
            "journal_papers": len(j), "conference_papers": int((p["type"] == "conference").sum()),
            "citations": int(p["citations"].sum()), "mean_citations": round(p["citations"].mean(), 2),
            "median_citations": float(p["citations"].median()), "pct_uncited": round((p["citations"] == 0).mean(), 4),
            "q1_fraction": round((known["quartile"] == "Q1").mean(), 4) if len(known) else None,
            "q1_of_all_journal": round((j["quartile"] == "Q1").mean(), 4) if len(j) else None,
            "quartile_coverage": round(len(known) / len(j), 4) if len(j) else None,
            "institutional_h": h_index(p["citations"]),
            f"cagr_{y0}_{ycagr}": None if (c := cagr(per_year[y0], per_year[ycagr], ycagr - y0)) is None else round(c, 4),
            "mean_authors": round(p["n_authors"].mean(), 2),
            "pct_foreign_collab": round(p["coauthor_institutes_all"].map(has_foreign).mean(), 4),
            "pct_indian_partner_collab": round((p["coauthor_institutes"] != "").mean(), 4),
            "pct_cites_indian": round((fac.groupby("openalex_id")["cites_indian_inst"].first() == "TRUE").mean(), 4),
            "pct_cited_by_indian": round((fac.groupby("openalex_id")["cited_by_indian_inst"].first() == "TRUE").mean(), 4),
            "papers_per_faculty": round(len(p) / n_fac, 2) if n_fac else None,
            "citations_per_faculty": round(p["citations"].sum() / n_fac, 1) if n_fac else None,
        })
        cit_year = p.groupby("year")["citations"].sum().reindex(range(y0, y1 + 1), fill_value=0)
        for y in range(y0, y1 + 1):
            years.append({"scope": scope, "year": y, "papers": int(per_year[y]), "citations": int(cit_year[y]),
                          "partial": y == cfg.window.partial_year})
        qc = j["quartile"].where(j["quartile"].isin(QS), "NA").value_counts()
        for q in QS + ["NA"]:
            quart.append({"scope": scope, "quartile": q, "papers": int(qc.get(q, 0)),
                          "share_of_journal": round(qc.get(q, 0) / max(len(j), 1), 4),
                          "share_of_known": round(qc.get(q, 0) / max(len(known), 1), 4) if q != "NA" else None})
        g = j.groupby("journal_name").agg(papers=("openalex_id", "size"), citations=("citations", "sum"),
                                          quartile=("quartile", lambda s: s.mode().iloc[0] if len(s) else "NA"))
        g = g.sort_values(["papers", "citations"], ascending=False).head(5 if scope != "ALL" else 10).reset_index()
        g.insert(0, "scope", scope)
        g.insert(1, "rank", range(1, len(g) + 1))
        journals.append(g)
        fields.append(share_table(p, "field", scope))
        subfields.append(share_table(p, "subfield", scope))
        domains.append(share_table(p, "domain", scope, top=5))
        top = p.sort_values("citations", ascending=False).head(10)
        cited.append(pd.DataFrame({"scope": scope, "rank": range(1, len(top) + 1), "title": top["title"],
                                   "journal": top["journal_name"], "year": top["year"], "citations": top["citations"],
                                   "doi": top["doi"], "labs": top["openalex_id"].map(
                                       df.groupby("openalex_id")["institution"].agg(lambda s: "; ".join(sorted(set(s)))))}))
    T["inst_summary"] = pd.DataFrame(summ)
    T["inst_year_counts"] = pd.DataFrame(years)
    T["inst_quartile"] = pd.DataFrame(quart)
    T["inst_top_journals"] = pd.concat(journals, ignore_index=True)
    T["inst_fields"] = pd.concat(fields, ignore_index=True)
    T["inst_subfields"] = pd.concat(subfields, ignore_index=True)
    T["inst_domains"] = pd.concat(domains, ignore_index=True)
    T["top_cited_papers"] = pd.concat(cited, ignore_index=True)

    # ---- faculty level
    cand = pd.read_parquet(cfg.paths.interim / "author_candidates.parquet")
    life_h = cand.groupby("author_id")["h_index"].max().to_dict()
    cent_path = cfg.paths.stats / "authorship_centrality.csv"
    cent = pd.read_csv(cent_path).set_index("faculty_id") if cent_path.exists() else pd.DataFrame()
    fac_rows = []
    for fid, g in df.groupby("faculty_id"):
        j = g[g["type"] == "journal"]
        known = j[j["quartile"].isin(QS)]
        ids = sorted({a for s in g["author_openalex_ids"] for a in str(s).split(";") if a})
        hl = [life_h[a] for a in ids if a in life_h]
        topj = j["journal_name"].value_counts()
        row = {"faculty_id": fid, "name": g["author"].iloc[0], "lab": g["institution"].iloc[0],
               "department": g["department"].iloc[0], "dept_source": g["dept_source"].iloc[0],
               "designation": g["designation"].iloc[0], "status": g["faculty_status"].iloc[0],
               "papers": len(g), "citations": int(g["citations"].sum()),
               "cites_per_paper": round(g["citations"].mean(), 2), "h_window": h_index(g["citations"]),
               "h_lifetime": max(hl) if hl else None, "h_lifetime_multi_id": len(hl) > 1,
               "top_journal": topj.index[0] if len(topj) else "", "top_journal_papers": int(topj.iloc[0]) if len(topj) else 0,
               "q1_fraction": round((known["quartile"] == "Q1").mean(), 4) if len(known) else None,
               "first_year": int(g["year"].min()), "last_year": int(g["year"].max()),
               "corresponding_papers": int((g["is_corresponding"] == "TRUE").sum())}
        if fid in cent.index:
            for c in ("degree", "strength", "betweenness", "community", "betweenness_internal", "n_partner_insts"):
                row[c] = cent.at[fid, c]
        fac_rows.append(row)
    fm = pd.DataFrame(fac_rows).sort_values(["lab", "papers"], ascending=[True, False])
    T["faculty_metrics"] = fm

    dept = (fm.groupby(["lab", "department"])
              .agg(faculty=("faculty_id", "count"), mean_h_window=("h_window", "mean"),
                   median_h_window=("h_window", "median"), dept_source=("dept_source", "first")).reset_index())
    dp = df.drop_duplicates(["openalex_id", "institution", "department"])
    agg = []
    for (lab, d), g in dp.groupby(["institution", "department"]):
        j = g[(g["type"] == "journal") & g["quartile"].isin(QS)]
        agg.append({"lab": lab, "department": d, "papers": g["openalex_id"].nunique(),
                    "citations": int(g.drop_duplicates("openalex_id")["citations"].sum()),
                    "q1_fraction": round((j["quartile"] == "Q1").mean(), 4) if len(j) else None})
    dept = dept.merge(pd.DataFrame(agg), on=["lab", "department"], how="left")
    dept["mean_h_window"] = dept["mean_h_window"].round(2)
    T["dept_metrics"] = dept.sort_values(["lab", "papers"], ascending=[True, False])

    bins = list(range(0, int(fm["h_window"].max()) + 10, 5))
    hist = []
    for scope in labs + ["ALL"]:
        h = fm["h_window"] if scope == "ALL" else fm.loc[fm["lab"] == scope, "h_window"]
        cnt, edges = np.histogram(h, bins=bins)
        for c, lo in zip(cnt, edges[:-1]):
            hist.append({"scope": scope, "bin": f"{int(lo)}-{int(lo) + 4}", "bin_start": int(lo), "faculty": int(c)})
        hist.append({"scope": scope, "bin": "summary", "bin_start": -1, "faculty": len(h),
                     "mean": round(h.mean(), 2), "median": float(h.median()), "max": int(h.max()) if len(h) else 0})
    T["hindex_hist"] = pd.DataFrame(hist)

    core = []
    for scope, p in scopes(df, labs):
        c = p[p["type"] == "conference"]
        for r in CORE + ["NA"]:
            core.append({"scope": scope, "rank": r, "papers": int((c["quartile"] == r).sum()) if r != "NA"
                         else int((~c["quartile"].isin(CORE)).sum()), "conference_papers": len(c)})
    T["core_ranks"] = pd.DataFrame(core)
    return T


# --------------------------------------------------------------------------- figures

def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figures(cfg, T: dict, fig_dir) -> None:
    labs = [l["short"] for l in cfg.labs]
    stats = cfg.paths.stats
    yc = T["inst_year_counts"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for lab in labs:
        d = yc[yc["scope"] == lab]
        ax.plot(d["year"], d["papers"], marker="o", color=LAB_COLORS[lab], label=lab)
    ax.axvspan(cfg.window.partial_year - 0.5, cfg.window.partial_year + 0.5, color="#ddd", alpha=.6, lw=0)
    ax.text(cfg.window.partial_year, ax.get_ylim()[1] * .95, "partial", ha="center", fontsize=8, color="#666")
    ax.set(xlabel="Year", ylabel="Papers", title="Publications per year")
    ax.legend(frameon=False, ncol=4, fontsize=8)
    _save(fig, fig_dir / "trend.png")

    q = T["inst_quartile"]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    scopes_ = labs + ["ALL"]
    left = np.zeros(len(scopes_))
    colors = Q_COLORS
    for qq in QS + ["NA"]:
        vals = np.array([q[(q.scope == s) & (q.quartile == qq)]["share_of_journal"].iloc[0] for s in scopes_])
        ax.barh(scopes_, vals, left=left, color=colors[qq], label=qq)
        left += vals
    ax.set(xlabel="Share of journal papers", title="Journal quartile distribution (SJR)")
    ax.legend(ncol=5, frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(.5, -.35))
    ax.invert_yaxis()
    _save(fig, fig_dir / "quartiles.png")

    fm = T["faculty_metrics"]
    fig, axes = plt.subplots(1, len(labs), figsize=(11, 3), sharey=True)
    bins = list(range(0, int(fm["h_window"].max()) + 6, 5))
    for ax, lab in zip(axes, labs):
        ax.hist(fm.loc[fm.lab == lab, "h_window"], bins=bins, color=LAB_COLORS[lab])
        ax.set_title(lab, fontsize=9)
        ax.set_xlabel("h-index (2016-2026)")
    axes[0].set_ylabel("Faculty")
    _save(fig, fig_dir / "hindex_hist.png")

    tj = T["inst_top_journals"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 5.5))
    for ax, lab in zip(axes.flat, labs):
        d = tj[tj.scope == lab].iloc[::-1]
        ax.barh([s[:40] for s in d["journal_name"]], d["papers"], color=LAB_COLORS[lab])
        ax.set_title(lab, fontsize=9)
        ax.tick_params(axis="y", labelsize=7)
    _save(fig, fig_dir / "top_journals.png")

    f = T["inst_fields"]
    fields = [x for x in f[f.scope == "ALL"]["field"] if x != "Other"][:8] + ["Other"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    left = np.zeros(len(labs))
    cmap = plt.get_cmap("tab10")
    for i, fl in enumerate(fields):
        vals = []
        for lab in labs:
            d = f[(f.scope == lab)]
            vals.append(d[d["field"] == fl]["share"].sum() if fl != "Other"
                        else 1 - d[d["field"].isin(fields[:-1])]["share"].sum())
        ax.barh(labs, vals, left=left, color=cmap(i), label=fl[:28])
        left += np.array(vals)
    ax.invert_yaxis()
    ax.set(xlabel="Share of papers", title="Research areas (OpenAlex field)")
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(.5, -.55))
    _save(fig, fig_dir / "fields.png")

    pr = pd.read_csv(stats / "citation_pagerank_top.csv")
    d = pr[pr.scope == "ALL"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh([t[:55] for t in d["title"].fillna("")], d["pagerank"], color="#555")
    ax.set(xlabel="PageRank (internal citation graph)", title="Most influential papers")
    ax.tick_params(axis="y", labelsize=7)
    _save(fig, fig_dir / "pagerank_top10.png")

    ind = pd.read_csv(stats / "citation_indegree_dist.csv")
    ind = ind[ind.in_degree > 0]
    fig, ax = plt.subplots(figsize=(5, 3.8))
    ax.loglog(ind["in_degree"], ind["papers"], "o", color="#2a6fdb")
    ax.set(xlabel="In-degree (citations from our corpus)", ylabel="Papers", title="In-degree distribution")
    _save(fig, fig_dir / "indegree_dist.png")

    fy = pd.read_csv(stats / "citation_flow_year.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=False)
    for ax, direction, title in ((axes[0], "in", "Cited by other Indian institutes"),
                                 (axes[1], "out", "Citing other Indian institutes")):
        for lab in labs:
            d = fy[fy.lab == lab]
            ax.plot(d["year"], d[direction], marker=".", color=LAB_COLORS[lab], label=lab)
        ax.set(title=title, xlabel="Citing year")
    axes[0].legend(frameon=False, fontsize=7)
    _save(fig, fig_dir / "flow_year.png")

    tci = pd.read_csv(stats / "top_citing_institutes.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11, 5.5))
    for ax, lab in zip(axes.flat, labs):
        d = tci[tci.your_inst == lab].iloc[::-1]
        ax.barh([s[:38] for s in d["partner_inst"]], d["cites_in"], color=LAB_COLORS[lab])
        ax.set_title(f"{lab}: top citing Indian institutes", fontsize=9)
        ax.tick_params(axis="y", labelsize=7)
    _save(fig, fig_dir / "top_citing_insts.png")

    pr_ = pd.read_csv(stats / "partner_ranking.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11, 5.5))
    for ax, lab in zip(axes.flat, labs):
        d = pr_[pr_.your_inst == lab].head(10).iloc[::-1]
        ax.barh([s[:38] for s in d["partner_inst"]], d["shared_papers"], color=LAB_COLORS[lab])
        ax.set_title(f"{lab}: co-authorship partners", fontsize=9)
        ax.tick_params(axis="y", labelsize=7)
    _save(fig, fig_dir / "partners.png")

    cc = pd.read_csv(stats / "cross_cluster_summary.csv")
    piv = cc.pivot_table(index="pair_label", columns="your_inst", values="shared_papers", aggfunc="sum", fill_value=0)
    piv = piv.loc[piv.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(8, 4))
    left = np.zeros(len(piv))
    for lab in labs:
        if lab in piv:
            ax.barh(piv.index, piv[lab], left=left, color=LAB_COLORS[lab], label=lab)
            left += piv[lab].values
    ax.set(xlabel="Shared papers (lab x partner)", title="Co-authorship by partner cluster")
    ax.legend(frameon=False, fontsize=7)
    _save(fig, fig_dir / "cross_cluster.png")

    gexf = cfg.paths.networks / "authorship_faculty.gexf"
    if gexf.exists():
        G = nx.read_gexf(gexf)
        G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
        pos = nx.spring_layout(G, seed=42, weight="weight", k=1.8 / max(len(G), 1) ** 0.5)
        comm = nx.get_node_attributes(G, "community")
        fig, ax = plt.subplots(figsize=(8, 7))
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=.25, width=.6)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=[10 + 6 * G.degree(n) for n in G],
                               node_color=[int(comm.get(n, 0)) for n in G], cmap="tab20")
        ax.set_title("Faculty co-authorship network (colour = Louvain community)")
        ax.axis("off")
        _save(fig, fig_dir / "authorship_faculty.png")


def run(cfg, oa, argv=()) -> None:
    path = cfg.paths.submission / f"group{cfg.group}_data.csv"
    if not path.exists():
        raise StepFailed(f"{cfg.rel(path)} missing - run s08 first")
    df = pd.read_csv(path, dtype={"doi": str, "issn": str}, keep_default_na=False)
    for c in ("year", "citations", "n_authors"):
        df[c] = df[c].astype(int)
    T = build_tables(cfg, df)
    cfg.paths.stats.mkdir(parents=True, exist_ok=True)
    for name, t in T.items():
        t.to_csv(cfg.paths.stats / f"{name}.csv", index=False, encoding="utf-8", lineterminator="\n")
    fig_dir = cfg.paths.figures
    fig_dir.mkdir(parents=True, exist_ok=True)
    figures(cfg, T, fig_dir)
    s = T["inst_summary"].set_index("scope")
    print("\n" + s[["faculty_with_papers", "papers", "citations", "q1_fraction", "quartile_coverage", "institutional_h",
                    f"cagr_{cfg.window.start}_{cfg.window.cagr_end}", "pct_indian_partner_collab"]].to_string())
    log.info("Wrote %d tables to %s and figures to %s", len(T), cfg.rel(cfg.paths.stats), cfg.rel(fig_dir))
    (cfg.paths.stats / "s12_summary.json").write_text(json.dumps({"tables": sorted(T)}, indent=2), encoding="utf-8")
