"""S09: citation network (guide §7, S09; plan D13, D14).

Edges (paper A cites paper B):
  internal  dataset paper -> dataset paper (the analysis graph G_int: in-degree, PageRank, components)
  outflow   dataset paper -> Indian work outside the dataset, exported only when it crosses institutions
  inflow    Indian 2016-2026 work outside the dataset -> dataset paper, exported only when it crosses institutions

An edge crosses institutions (D14) when the other paper carries an Indian partner institution of the lab on our
side (plan D11: not the lab itself, no umbrella bodies, no AcSIR); this is the test behind the two flags in the
main CSV. Foreign-only references are not exported.

Outputs: outputs/submission/citation_network.csv; outputs/networks/citation_internal.gexf, citation_nodes.csv,
citation_dash.json; outputs/stats/citation_pagerank_top.csv, citation_indegree_dist.csv,
lab_citation_matrix.csv, citation_network_summary.json; data/interim/cit_edges.parquet.
"""
from __future__ import annotations

import json
import logging
from collections import Counter

import networkx as nx
import pandas as pd

from ..netdata import load_context

log = logging.getLogger("dpcn.s09")

COLUMNS = ["source_doi", "target_doi", "source_inst", "target_inst", "year", "source_openalex_id",
           "target_openalex_id", "edge_scope", "cross_institute", "target_year"]


def crosses(ctx, s: str, t: str) -> bool:
    """D14: the edge links one of our labs to another Indian institution - the citing work carries a partner
    institution of a lab of the cited paper, or the cited work carries a partner of a lab of the citing paper.
    The same test sets cites_indian_inst / cited_by_indian_inst in the main CSV, so flags and edges agree."""
    return (any(ctx.partners(s, lab) for lab in ctx.labs_of.get(t, ()))
            or any(ctx.partners(t, lab) for lab in ctx.labs_of.get(s, ())))


def build_edges(ctx) -> tuple[list[tuple], Counter]:
    """(source, target, scope, cross) for every edge kept, plus counts of edges dropped as not crossing."""
    out_ids = set(ctx.outflow["work_id"]) - ctx.ours
    edges, dropped = [], Counter()
    for w in ctx.works.itertuples():
        for r in dict.fromkeys(w.referenced_works):
            if r == w.work_id:
                continue
            if r in ctx.ours:
                edges.append((w.work_id, r, "internal", crosses(ctx, w.work_id, r)))
            elif r in out_ids:
                if crosses(ctx, w.work_id, r):
                    edges.append((w.work_id, r, "outflow", True))
                else:
                    dropped["outflow"] += 1
    for c in ctx.inflow.itertuples():
        if c.work_id in ctx.ours:
            continue
        for r in dict.fromkeys(c.refs_ours):
            if r in ctx.ours:
                if crosses(ctx, c.work_id, r):
                    edges.append((c.work_id, r, "inflow", True))
                else:
                    dropped["inflow"] += 1
    return edges, dropped


def dashboard_subgraph(G: nx.DiGraph, pr: dict, k: int) -> nx.DiGraph:
    ranked = sorted(pr, key=lambda n: -pr[n])
    keep: list = []
    seen: set = set()
    for seed in ranked:
        if len(keep) >= k:
            break
        if G.degree(seed) == 0:
            continue
        for n in [seed, *sorted(set(G.predecessors(seed)) | set(G.successors(seed)), key=lambda n: -pr[n])]:
            if n not in seen and len(keep) < k:
                seen.add(n)
                keep.append(n)
    S = G.subgraph(keep).copy()
    S.remove_nodes_from([n for n in list(S) if S.degree(n) == 0])
    return S


def short_title(t: str, n: int = 60) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"


def run(cfg, oa, argv=()) -> None:
    ctx = load_context(cfg)
    edges, dropped = build_edges(ctx)
    lab_str = lambda w: "; ".join(ctx.inst_labels(w))
    rows = [{"source_doi": ctx.doi[s], "target_doi": ctx.doi[t], "source_inst": lab_str(s), "target_inst": lab_str(t),
             "year": ctx.year.get(s), "source_openalex_id": f"https://openalex.org/{s}",
             "target_openalex_id": f"https://openalex.org/{t}", "edge_scope": sc,
             "cross_institute": "TRUE" if cr else "FALSE", "target_year": ctx.year.get(t)} for s, t, sc, cr in edges]
    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("year", "target_year"):
        df[c] = df[c].astype("Int64")
    sub = cfg.paths.submission
    sub.mkdir(parents=True, exist_ok=True)
    df.to_csv(sub / "citation_network.csv", index=False, encoding="utf-8", lineterminator="\n")
    pd.DataFrame(edges, columns=["src", "tgt", "scope", "cross_institute"]).assign(
        year=lambda d: d["src"].map(ctx.year)).to_parquet(cfg.paths.interim / "cit_edges.parquet", index=False)

    # ---- G_int analysis
    works = ctx.works.set_index("work_id")
    G = nx.DiGraph()
    for w in ctx.works.itertuples():
        labs = sorted(ctx.labs_of.get(w.work_id, ()))
        G.add_node(w.work_id, label=short_title(w.title), lab=labs[0] if len(labs) == 1 else "Multi-lab",
                   labs=";".join(labs), year=int(w.year), field=w.field or "", citations=int(w.cited_by_count),
                   doi=ctx.doi[w.work_id])
    G.add_edges_from((s, t) for s, t, sc, _ in edges if sc == "internal")
    pr = nx.pagerank(G, alpha=cfg.networks.pagerank_alpha)
    indeg, outdeg = dict(G.in_degree()), dict(G.out_degree())
    nx.set_node_attributes(G, pr, "pagerank")
    nx.set_node_attributes(G, indeg, "indeg")
    nx.set_node_attributes(G, outdeg, "outdeg")
    wccs = sorted(nx.weakly_connected_components(G), key=len, reverse=True)

    net = cfg.paths.networks
    stats = cfg.paths.stats
    net.mkdir(parents=True, exist_ok=True)
    stats.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(G, net / "citation_internal.gexf")
    nodes = pd.DataFrame([{"work_id": n, **d} for n, d in G.nodes(data=True)])
    nodes["title"] = nodes["work_id"].map(works["title"])
    nodes["journal"] = nodes["work_id"].map(works["source_name"])
    nodes.to_csv(net / "citation_nodes.csv", index=False, encoding="utf-8", lineterminator="\n")

    cols = ["work_id", "title", "journal", "year", "labs", "citations", "indeg", "pagerank", "doi"]
    top = [nodes.sort_values("pagerank", ascending=False).head(10).assign(scope="ALL")[cols + ["scope"]]]
    for lab in cfg.lab_by_short:
        sub_n = nodes[nodes["labs"].str.split(";").apply(lambda x: lab in x)]
        top.append(sub_n.sort_values("pagerank", ascending=False).head(10).assign(scope=lab)[cols + ["scope"]])
    pd.concat(top).to_csv(stats / "citation_pagerank_top.csv", index=False, encoding="utf-8", lineterminator="\n")

    dist = Counter(indeg.values())
    pd.DataFrame(sorted(dist.items()), columns=["in_degree", "papers"]).to_csv(
        stats / "citation_indegree_dist.csv", index=False, lineterminator="\n")

    shorts = list(cfg.lab_by_short)
    mat = pd.DataFrame(0, index=shorts, columns=shorts)
    for s, t in G.edges():
        for a in ctx.labs_of.get(s, ()):
            for b in ctx.labs_of.get(t, ()):
                mat.loc[a, b] += 1
    mat.index.name = "citing_lab \\ cited_lab"
    mat.to_csv(stats / "lab_citation_matrix.csv", lineterminator="\n")

    n, m = G.number_of_nodes(), G.number_of_edges()
    scope_counts = df["edge_scope"].value_counts().to_dict()
    summary = {"nodes": n, "internal_edges": m, "density": nx.density(G),
               "weak_components": len(wccs), "largest_wcc": len(wccs[0]) if wccs else 0,
               "isolates": sum(1 for x in G if G.degree(x) == 0),
               "share_indeg_0": sum(1 for v in indeg.values() if v == 0) / n if n else 0,
               "mean_indeg": m / n if n else 0, "max_indeg": max(indeg.values()) if indeg else 0,
               "reciprocity": nx.reciprocity(G) if m else 0, "exported_edges": scope_counts,
               "cross_institute_edges": int((df["cross_institute"] == "TRUE").sum()),
               "dropped_not_cross": dict(dropped)}
    (stats / "citation_network_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- dashboard subgraph: top PageRank papers plus the papers citing or cited by them (plan §7.4), up to
    # networks.dashboard_citation_nodes, without isolates; positions precomputed
    S = dashboard_subgraph(G, pr, cfg.networks.dashboard_citation_nodes)
    from .s10_authorship import layout
    xy = layout(S, k_scale=4.0)
    dash = {"nodes": [{"id": x, "label": S.nodes[x]["label"], "lab": S.nodes[x]["lab"], "labs": S.nodes[x]["labs"],
                       "year": S.nodes[x]["year"], "pr": round(pr[x], 6), "indeg": indeg[x],
                       "cit": S.nodes[x]["citations"], "doi": S.nodes[x]["doi"],
                       "x": xy[x][0], "y": xy[x][1]} for x in S],
            "edges": [{"s": a, "t": b} for a, b in S.edges()]}
    (net / "citation_dash.json").write_text(json.dumps(dash), encoding="utf-8")

    print(f"\ncitation_network.csv: {len(df)} edges {scope_counts}; cross-institute: {summary['cross_institute_edges']}; "
          f"dropped (same institutions): {dict(dropped)}")
    print(f"G_int: {n} nodes, {m} edges, density {summary['density']:.5f}, largest WCC {summary['largest_wcc']}, "
          f"in-degree 0: {summary['share_indeg_0']:.1%}, reciprocity {summary['reciprocity']:.3f}")
    print("Lab citation matrix (rows cite columns):")
    print(mat.to_string())
