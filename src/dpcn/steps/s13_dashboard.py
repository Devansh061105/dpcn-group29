"""S13: interactive dashboard, one self-contained HTML file (guide §8; plan §7.7, D21).

    python -m dpcn run s13          libraries inlined: the file opens offline, nothing to install
    python -m dpcn run s13 --cdn    libraries loaded from a CDN (small file, needs internet)

Reads only outputs/stats, outputs/networks and the submitted group29_data.csv, so the dashboard always matches
the submission. Template, script and styles live in src/dpcn/dashboard/.
Output: outputs/submission/group29_dashboard.html
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import networkx as nx
import pandas as pd
import requests

from . import StepFailed

log = logging.getLogger("dpcn.s13")

SRC = Path(__file__).resolve().parent.parent / "dashboard"
LIBS = {   # pinned versions (guide §8)
    "plotly": ("js", "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"),
    "tabulator_js": ("js", "https://cdnjs.cloudflare.com/ajax/libs/tabulator/6.3.0/js/tabulator.min.js"),
    "tabulator_css": ("css", "https://cdnjs.cloudflare.com/ajax/libs/tabulator/6.3.0/css/tabulator_simple.min.css"),
    "cytoscape": ("js", "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"),
}


def records(df: pd.DataFrame) -> list[dict]:
    """JSON-safe records (NaN -> null)."""
    return json.loads(df.to_json(orient="records", force_ascii=False))


def library(cfg, name: str, url: str) -> str:
    cache = cfg.paths.cache / "web" / "vendor" / url.rsplit("/", 1)[-1]
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        cache.write_bytes(r.content)
    return cache.read_text(encoding="utf-8")


def authorship_by_lab(cfg, main: pd.DataFrame, au_sum: dict) -> dict:
    """Collaboration-tab headline numbers for each lab, from the exported graphs and pair file ("ALL" = S10 summary)."""
    net = cfg.paths.networks
    Gf = nx.read_gexf(net / "authorship_faculty.gexf")
    Gi = nx.read_gexf(net / "authorship_internal.gexf")
    pairs = pd.read_csv(cfg.paths.submission / "authorship_network.csv", usecols=["inst_a", "inst_b", "indian_link"],
                        dtype=str, keep_default_na=False)
    papers = main.drop_duplicates(["openalex_id", "institution"])
    big = papers[pd.to_numeric(papers["n_authors"], errors="coerce") > cfg.networks.max_authors_for_pairs]
    fg, ig = au_sum["faculty_graph"], au_sum["internal_graph"]
    out = {"ALL": {"fac_nodes": fg["nodes"], "fac_isolates": fg["isolates"], "fac_edges": fg["edges"],
                   "fac_cross": fg["cross_lab_edges"], "communities": fg["communities"],
                   "modularity": fg["modularity"], "int_nodes": ig["nodes"], "int_edges": ig["edges"],
                   "int_modularity": ig["modularity"], "pair_rows": au_sum["pairs_rows"],
                   "indian_rows": au_sum["indian_link_rows"],
                   "skipped": au_sum["papers_skipped_over_max_authors"]}}
    for lab in cfg.lab_by_short:
        fac = {n for n, d in Gf.nodes(data=True) if d.get("lab") == lab}
        f_edges = [(a, b, d) for a, b, d in Gf.edges(data=True) if a in fac or b in fac]
        comms = pd.Series([Gf.nodes[n].get("community") for n in fac]).value_counts()
        inte = {n for n, d in Gi.nodes(data=True) if d.get("lab") == lab}
        rows = (pairs["inst_a"] == lab) | (pairs["inst_b"] == lab)
        out[lab] = {"fac_nodes": len(fac), "fac_isolates": sum(1 for n in fac if Gf.degree(n) == 0),
                    "fac_edges": len(f_edges), "fac_cross": sum(1 for *_, d in f_edges if d.get("cross_lab")),
                    "communities": int(len(comms)), "largest_comm": int(comms.iloc[0]) if len(comms) else 0,
                    "int_nodes": len(inte), "int_edges": sum(1 for a, b in Gi.edges() if a in inte or b in inte),
                    "pair_rows": int(rows.sum()), "indian_rows": int((rows & (pairs["indian_link"] == "TRUE")).sum()),
                    "skipped": int((big["institution"] == lab).sum())}
    return out


def bundle(cfg) -> dict:
    st, net = cfg.paths.stats, cfg.paths.networks
    need = ["inst_summary", "inst_year_counts", "inst_quartile", "inst_top_journals", "faculty_metrics",
            "hindex_hist", "top_cited_papers", "core_ranks", "dept_metrics", "citation_pagerank_top",
            "citation_indegree_dist", "citation_flow_year", "citation_flow_summary", "top_citing_institutes",
            "top_citing_papers", "authorship_centrality", "communities", "hub_authors", "partner_ranking",
            "cross_cluster_summary", "lab_citation_matrix"]
    missing = [n for n in need if not (st / f"{n}.csv").exists()]
    if missing:
        raise StepFailed(f"missing stats tables {missing} - run s09 to s12 first")
    T = {n: pd.read_csv(st / f"{n}.csv", keep_default_na=False, na_values=[""]) for n in need}

    main = pd.read_csv(cfg.paths.submission / f"group{cfg.group}_data.csv", dtype=str, keep_default_na=False)
    papers = main.drop_duplicates(["openalex_id", "institution"])
    areas = []
    for scope, p in [*((l, papers[papers.institution == l]) for l in cfg.lab_by_short),
                     ("ALL", main.drop_duplicates("openalex_id"))]:
        g = p.replace({"field": {"": "Unknown"}, "subfield": {"": "Unknown"}}).groupby(["field", "subfield"]).size()
        areas += [{"scope": scope, "field": f, "subfield": s, "papers": int(n)} for (f, s), n in g.items()]

    partners = T["partner_ranking"]
    partners = partners[partners["rank"] <= 30]
    cit_sum = json.loads((st / "citation_network_summary.json").read_text())
    au_sum = json.loads((st / "authorship_network_summary.json").read_text())
    meta = json.loads((cfg.paths.submission / "metadata.json").read_text())
    mat = T["lab_citation_matrix"].set_index(T["lab_citation_matrix"].columns[0])
    return {
        "meta": {"group": cfg.group, "labs": [l["short"] for l in cfg.labs],
                 "lab_names": {l["short"]: f"{l['name']}, {l['city']}" for l in cfg.labs},
                 "collected": meta.get("collection_date", ""), "window": [cfg.window.start, cfg.window.end],
                 "partial_year": cfg.window.partial_year, "rows": meta.get("rows"),
                 "max_authors_for_pairs": cfg.networks.max_authors_for_pairs},
        "summary": records(T["inst_summary"]), "trend": records(T["inst_year_counts"]),
        "quartiles": records(T["inst_quartile"]), "top_journals": records(T["inst_top_journals"]),
        "faculty": records(T["faculty_metrics"]), "hindex": records(T["hindex_hist"]),
        "areas": areas, "top_cited": records(T["top_cited_papers"]), "core": records(T["core_ranks"]),
        "departments": records(T["dept_metrics"]),
        "citation_graph": json.loads((net / "citation_dash.json").read_text()),
        "pagerank_top": records(T["citation_pagerank_top"]), "indegree": records(T["citation_indegree_dist"]),
        "citation_summary": cit_sum, "lab_matrix": {"labs": list(mat.columns), "z": mat.values.tolist()},
        "flow_year": records(T["citation_flow_year"]), "flow_summary": records(T["citation_flow_summary"]),
        "top_citing_insts": records(T["top_citing_institutes"]), "top_citing_papers": records(T["top_citing_papers"]),
        "authorship": json.loads((net / "authorship_dash.json").read_text()), "authorship_summary": au_sum,
        "authorship_by_lab": authorship_by_lab(cfg, main, au_sum),
        "centrality": records(T["authorship_centrality"]), "communities": records(T["communities"]),
        "hubs": records(T["hub_authors"]), "partners": records(partners),
        "cross_cluster": records(T["cross_cluster_summary"]),
    }


def run(cfg, oa, argv=()) -> None:
    ap = argparse.ArgumentParser(prog="s13")
    ap.add_argument("--cdn", action="store_true", help="load libraries from a CDN instead of inlining them")
    args, _ = ap.parse_known_args(list(argv))
    data = json.dumps(bundle(cfg), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (SRC / "template.html").read_text(encoding="utf-8")
    if args.cdn:
        head = "\n".join(f'<link rel="stylesheet" href="{u}">' if k == "css" else f'<script src="{u}"></script>'
                         for k, u in LIBS.values())
    else:
        head = "\n".join(f"<style>{library(cfg, n, u)}</style>" if k == "css" else
                         f"<script>{library(cfg, n, u)}</script>" for n, (k, u) in LIBS.items())
    html = (html.replace("/*__STYLES__*/", (SRC / "styles.css").read_text(encoding="utf-8"))
                .replace("<!--__LIBS__-->", head)
                .replace("/*__APP__*/", (SRC / "app.js").read_text(encoding="utf-8"))
                .replace("__DATA__", data))
    out = cfg.paths.submission / f"group{cfg.group}_dashboard.html"
    out.write_text(html, encoding="utf-8")
    mb = out.stat().st_size / 1e6
    print(f"\n{cfg.rel(out)}: {mb:.1f} MB ({'CDN libraries' if args.cdn else 'self-contained, opens offline'})")
    if mb > 15:
        raise StepFailed(f"dashboard is {mb:.1f} MB (limit 15 MB); trim the network views")
