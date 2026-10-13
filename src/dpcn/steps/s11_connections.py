"""S11: indian_connections.csv, citation flow and topic Jaccard (guide §7, S11; plan A8, D11, D12, D19).

Per (our lab L, Indian partner institution P):
  shared_papers            dataset papers of L with P among the co-author institutions
  cites_in / cites_out     citation edges from a work carrying P to a paper of L / from a paper of L to such a work
  total_citations          cites_in + cites_out (plan A8; shared_papers_citations holds the other reading)
  jaccard_topics           |T_L & T_P| / |T_L | T_P| over each side's top-100 OpenAlex topics (top-30 partners of L)

Flow statistics count citation edges (not edge x institution): a citation is "from another Indian institute"
when the citing work carries at least one partner institution of the cited lab.

Outputs: outputs/submission/indian_connections.csv; outputs/stats/partner_ranking.csv, cross_cluster_summary.csv,
citation_flow_summary.csv, citation_flow_year.csv, top_citing_institutes.csv, top_citing_papers.csv.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict

import pandas as pd

from ..netdata import load_context
from ..openalex import short_id
from . import StepFailed

log = logging.getLogger("dpcn.s11")

COLUMNS = ["your_inst", "partner_inst", "shared_papers", "total_citations", "cites_in", "cites_out",
           "shared_papers_citations", "partner_openalex_id", "partner_cluster", "cross_cluster", "pair_label",
           "partner_in_group", "partner_is_csir_academy", "jaccard_topics", "jaccard_subfields"]


def jaccard(a: set, b: set) -> float | None:
    return round(len(a & b) / len(a | b), 4) if a and b else None


def top_keys(oa, cfg, inst_id: str, key: str, k: int) -> set:
    flt = f"authorships.institutions.lineage:{inst_id},{cfg.year_filter}"
    groups = oa.group_by("works", flt, key)
    groups = [g for g in groups if g.get("key") and g["key"] != "unknown"]
    return {short_id(g["key"]) for g in sorted(groups, key=lambda g: -g["count"])[:k]}


def run(cfg, oa, argv=()) -> None:
    ctx = load_context(cfg)
    reg = ctx.reg
    edges_path = cfg.paths.interim / "cit_edges.parquet"
    if not edges_path.exists():
        raise StepFailed("data/interim/cit_edges.parquet missing - run s09 first")
    edges = pd.read_parquet(edges_path)
    cited = ctx.works.set_index("work_id")["cited_by_count"].to_dict()

    shared, shared_cit = Counter(), Counter()
    for wid, lab in ctx.links[["work_id", "institution"]].drop_duplicates().itertuples(index=False):
        for p in set(ctx.partners(wid, lab)):
            shared[lab, p] += 1
            shared_cit[lab, p] += cited.get(wid, 0)

    cites_in, cites_out = Counter(), Counter()
    flow_rows = []                                   # one row per (lab, direction, edge) for flow statistics
    citing_papers = defaultdict(Counter)             # lab -> citing work -> number of the lab's papers it cites
    for s, t, year in edges[["src", "tgt", "year"]].itertuples(index=False):
        for lab in ctx.labs_of.get(t, ()):           # s cites a paper of lab
            ps = set(ctx.partners(s, lab))
            for p in ps:
                cites_in[lab, p] += 1
            if ps:
                flow_rows.append((lab, "in", year))
                citing_papers[lab][s] += 1
        for lab in ctx.labs_of.get(s, ()):           # a paper of lab cites t
            ps = set(ctx.partners(t, lab))
            for p in ps:
                cites_out[lab, p] += 1
            if ps:
                flow_rows.append((lab, "out", year))

    pairs = set(shared) | set(cites_in) | set(cites_out)
    in_group = {l["openalex_id"] for l in cfg.labs}
    rows = []
    for lab, p in pairs:
        cl = reg.cluster(p)
        rows.append({"your_inst": lab, "partner_inst": reg.label(p), "shared_papers": shared[lab, p],
                     "total_citations": cites_in[lab, p] + cites_out[lab, p], "cites_in": cites_in[lab, p],
                     "cites_out": cites_out[lab, p], "shared_papers_citations": shared_cit[lab, p],
                     "partner_openalex_id": p, "partner_cluster": cl, "cross_cluster": cl != cfg.cluster_label,
                     "pair_label": f"{cfg.cluster_label}↔{cl}", "partner_in_group": p in in_group or bool(reg.our_lab(p)),
                     "partner_is_csir_academy": reg.is_academy(p), "jaccard_topics": None, "jaccard_subfields": None})
    df = pd.DataFrame(rows, columns=COLUMNS)

    # ---- Jaccard topic similarity for each lab's top partners by shared papers (D19)
    k_top, k_partners = cfg.connections.jaccard_top_k_topics, cfg.connections.jaccard_top_partners
    cache: dict[tuple, set] = {}

    def topics(iid, key):
        if (iid, key) not in cache:
            cache[iid, key] = top_keys(oa, cfg, iid, key, k_top)
        return cache[iid, key]
    for lab in cfg.labs:
        lid = lab["openalex_id"]
        sel = df[(df["your_inst"] == lab["short"]) & (df["shared_papers"] > 0)].nlargest(k_partners, "shared_papers")
        for i, r in sel.iterrows():
            df.at[i, "jaccard_topics"] = jaccard(topics(lid, "primary_topic.id"), topics(r.partner_openalex_id, "primary_topic.id"))
            df.at[i, "jaccard_subfields"] = jaccard(topics(lid, "primary_topic.subfield.id"),
                                                    topics(r.partner_openalex_id, "primary_topic.subfield.id"))
        log.info("%s: Jaccard computed for %d partners | %s", lab["short"], len(sel), oa.report())

    df = df.sort_values(["your_inst", "shared_papers", "total_citations"], ascending=[True, False, False])
    for c in ("cross_cluster", "partner_in_group", "partner_is_csir_academy"):
        df[c] = df[c].map({True: "TRUE", False: "FALSE"})
    sub, stats = cfg.paths.submission, cfg.paths.stats
    sub.mkdir(parents=True, exist_ok=True)
    stats.mkdir(parents=True, exist_ok=True)
    df.to_csv(sub / "indian_connections.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ---- statistics
    rank = df[df["shared_papers"] > 0].copy()
    rank["rank"] = rank.groupby("your_inst")["shared_papers"].rank(method="first", ascending=False).astype(int)
    rank.sort_values(["your_inst", "rank"]).to_csv(stats / "partner_ranking.csv", index=False, encoding="utf-8",
                                                   lineterminator="\n")
    cc = (df.groupby(["your_inst", "pair_label"]).agg(partners=("partner_inst", "count"),
                                                      shared_papers=("shared_papers", "sum"),
                                                      cites_in=("cites_in", "sum"), cites_out=("cites_out", "sum"))
            .reset_index().sort_values(["your_inst", "shared_papers"], ascending=[True, False]))
    cc.to_csv(stats / "cross_cluster_summary.csv", index=False, encoding="utf-8", lineterminator="\n")

    flow = pd.DataFrame(flow_rows, columns=["lab", "direction", "year"])
    fs = flow.groupby(["lab", "direction"]).size().unstack(fill_value=0).reindex(columns=["in", "out"], fill_value=0)
    fs = fs.rename(columns={"in": "cites_in", "out": "cites_out"}).reset_index()
    fs["impact_ratio"] = (fs["cites_in"] / fs["cites_out"].where(fs["cites_out"] > 0)).round(3)
    fs.to_csv(stats / "citation_flow_summary.csv", index=False, lineterminator="\n")
    fy = (flow[flow["year"].between(cfg.window.start, cfg.window.end)]
          .groupby(["lab", "year", "direction"]).size().unstack(fill_value=0)
          .reindex(columns=["in", "out"], fill_value=0).reset_index())
    fy.to_csv(stats / "citation_flow_year.csv", index=False, lineterminator="\n")

    tci = (df[df["cites_in"] > 0].sort_values("cites_in", ascending=False).groupby("your_inst").head(10)
             [["your_inst", "partner_inst", "partner_cluster", "cites_in", "cites_out", "shared_papers"]])
    tci.to_csv(stats / "top_citing_institutes.csv", index=False, encoding="utf-8", lineterminator="\n")

    info = {}
    for d in (ctx.inflow, ctx.works):
        for r in d.itertuples():
            info.setdefault(r.work_id, {"title": r.title, "year": r.year, "cited_by_count": r.cited_by_count,
                                        "source_name": getattr(r, "source_name", "")})
    tp = []
    for lab, cnt in citing_papers.items():
        best = sorted(cnt, key=lambda w: -(info.get(w, {}).get("cited_by_count") or 0))[:10]
        for w in best:
            i = info.get(w, {})
            tp.append({"lab": lab, "citing_work": f"https://openalex.org/{w}", "doi": ctx.doi.get(w, ""),
                       "title": " ".join((i.get("title") or "").split()), "year": i.get("year"),
                       "journal": i.get("source_name") or "", "cited_by_count": i.get("cited_by_count"),
                       "lab_papers_cited": cnt[w],
                       "institutions": "; ".join(reg.label(p) for p in ctx.partners(w, lab))})
    pd.DataFrame(tp).to_csv(stats / "top_citing_papers.csv", index=False, encoding="utf-8", lineterminator="\n")

    print(f"\nindian_connections.csv: {len(df)} (lab, partner) rows; with shared papers: {int((df.shared_papers > 0).sum())}")
    print("Citation flow (edges from/to works with another Indian institution):")
    print(fs.to_string(index=False))
    for lab, g in rank.groupby("your_inst"):
        print(f"{lab} top partners: " + "; ".join(f"{r.partner_inst} ({r.shared_papers})" for r in g.head(5).itertuples()))
