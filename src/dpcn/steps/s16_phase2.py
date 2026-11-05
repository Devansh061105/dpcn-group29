"""S16: Phase II analyses (instructor's additional directions).

    python -m dpcn run s16

Reads only the submitted deliverables (group29_data.csv, the three network files) and outputs/stats, so the numbers
stay on the same snapshot as the submission. New data comes from three small lookups, all cached:
  * journal impact factors: a JCR file if the team supplies one (data/manual/jcr/jcr_impact_factors.csv), else
    Scimago's 2-year citations per document (free download in data/manual/sjr_full, Scopus data), else OpenAlex's
    2-year mean citedness (the classic impact-factor formula, but current-year and not Clarivate's), with the
    source recorded per journal;
  * the citing papers of the institutions that cite the labs most (authors, journals), to look for reasons;
  * institution ownership comes from a hand-made file (data/manual/institution_ownership.csv), never guessed in code.
Writes outputs/stats/p2_*.csv, journal_impact.csv, p2_summary.json and outputs/networks/inst_network.json.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

import numpy as np
import pandas as pd

from .. import phase2 as P
from ..openalex import batches, short_id
from . import StepFailed

log = logging.getLogger("dpcn.s16")
PROXY = "OpenAlex 2-year mean citedness (proxy)"


# --------------------------------------------------------------------------- impact factors

def read_jcr(path) -> pd.DataFrame:
    """Team-supplied JCR export. Flexible headers; needs an impact factor and an ISSN or a journal title."""
    if not path.exists():
        return pd.DataFrame(columns=["issn_n", "title_n", "jcr_value", "jcr_label"])
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    cols = {re.sub(r"[^a-z]", "", c.lower()): c for c in df.columns}
    pick = lambda *names: next((cols[n] for n in names if n in cols), None)
    c_if = pick("impactfactor", "jif", "if", "journalimpactfactor")
    c_issn, c_e = pick("issn"), pick("eissn")
    c_title = pick("journal", "journalname", "title", "fulljournaltitle")
    c_year = pick("jcryear", "year")
    if not c_if or not (c_issn or c_title):
        raise StepFailed(f"{path}: needs an 'impact_factor' column and an 'issn' or 'journal' column")
    rows = []
    for _, r in df.iterrows():
        v = pd.to_numeric(r[c_if], errors="coerce")
        if pd.isna(v):
            continue
        label = f"JCR {r[c_year]}" if c_year and r[c_year] else "JCR"
        for key in filter(None, [r[c_issn] if c_issn else "", r[c_e] if c_e else ""]):
            rows.append({"issn_n": P.norm_issn(key), "title_n": "", "jcr_value": float(v), "jcr_label": label})
        if c_title and r[c_title]:
            rows.append({"issn_n": "", "title_n": P.norm_title(r[c_title]), "jcr_value": float(v), "jcr_label": label})
    return pd.DataFrame(rows, columns=["issn_n", "title_n", "jcr_value", "jcr_label"])


def read_scimago(folder) -> pd.DataFrame:
    """Scimago 'Citations / Doc. (2years)' from the newest scimagojr_<year>.csv in the folder (free download, Scopus data)."""
    files = sorted(folder.glob("scimagojr_*.csv")) if folder.exists() else []
    empty = pd.DataFrame(columns=["issn_n", "sci_value", "sci_label"])
    if not files:
        return empty
    f = max(files, key=lambda p: (re.search(r"(\d{4})", p.stem) or [None, "0"])[1])
    df = pd.read_csv(f, sep=";", dtype=str, keep_default_na=False)
    c_val = next((c for c in df.columns if re.match(r"(cites|citations)\s*/\s*doc\.?\s*\(2", c.lower())), None)
    c_issn = next((c for c in df.columns if c.lower() == "issn"), None)
    if not c_val or not c_issn:
        raise StepFailed(f"{f}: needs 'Citations / Doc. (2years)' and 'Issn' columns (download the full table from scimagojr.com)")
    year = (re.search(r"(\d{4})", f.stem) or [None, ""])[1]
    label = f"Scimago Cites/Doc (2y) {year}".strip()
    rows = []
    for v, issns in zip(pd.to_numeric(df[c_val].str.replace(",", ".", regex=False), errors="coerce"), df[c_issn]):
        if pd.isna(v):
            continue
        for i in filter(None, (P.norm_issn(x) for x in str(issns).split(","))):
            rows.append({"issn_n": i, "sci_value": float(v), "sci_label": label})
    return pd.DataFrame(rows, columns=["issn_n", "sci_value", "sci_label"])


def journal_impact(cfg, oa, main: pd.DataFrame) -> pd.DataFrame:
    """One row per ISSN in the dataset: JCR value if supplied, else Scimago cites/doc, else the OpenAlex proxy; all are kept."""
    j = main[(main["type"] == "journal") & (main["issn"] != "")].drop_duplicates("issn")[["issn", "journal_name"]].copy()
    j["issn_n"] = j["issn"].map(P.norm_issn)
    proxy: dict[str, float] = {}
    meta: dict[str, tuple] = {}
    for b in batches(sorted(j["issn"]), 50):
        for s in oa.paginate("sources", "issn:" + "|".join(b), select="id,display_name,issn,summary_stats", per_page=200):
            v = (s.get("summary_stats") or {}).get("2yr_mean_citedness")
            for x in s.get("issn") or []:
                if v is not None:
                    proxy[P.norm_issn(x)] = float(v)
                    meta[P.norm_issn(x)] = (short_id(s["id"]), s.get("display_name"))
    j["if_openalex_proxy"] = j["issn_n"].map(proxy)
    j["openalex_source_id"] = j["issn_n"].map(lambda x: meta.get(x, ("", ""))[0])
    jcr = read_jcr(cfg.root / cfg.phase2.jcr_file)
    by_issn = jcr[jcr["issn_n"] != ""].drop_duplicates("issn_n").set_index("issn_n")
    by_title = jcr[jcr["title_n"] != ""].drop_duplicates("title_n").set_index("title_n")
    j["if_jcr"], j["jcr_label"] = np.nan, ""
    for i, r in j.iterrows():
        hit = by_issn.loc[r["issn_n"]] if r["issn_n"] in by_issn.index else (
            by_title.loc[P.norm_title(r["journal_name"])] if P.norm_title(r["journal_name"]) in by_title.index else None)
        if hit is not None:
            j.at[i, "if_jcr"], j.at[i, "jcr_label"] = hit["jcr_value"], hit["jcr_label"]
    sci = read_scimago(cfg.root / cfg.phase2.scimago_dir).drop_duplicates("issn_n").set_index("issn_n")
    j["if_scimago"] = j["issn_n"].map(sci["sci_value"])
    j["scimago_label"] = j["issn_n"].map(sci["sci_label"]).fillna("")
    j["impact_factor"] = j["if_jcr"].fillna(j["if_scimago"]).fillna(j["if_openalex_proxy"])
    j["if_source"] = np.select([j["if_jcr"].notna(), j["if_scimago"].notna(), j["if_openalex_proxy"].notna()],
                               [j["jcr_label"], j["scimago_label"], PROXY], default="")
    return j.sort_values("journal_name").reset_index(drop=True)


# --------------------------------------------------------------------------- heavy citing institutions

def load_ownership(cfg) -> dict:
    path = cfg.root / cfg.phase2.ownership_file
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {r["openalex_id"]: {"ownership": r["ownership"], "basis": r.get("basis", ""), "verified": r.get("verified", "")}
            for _, r in df.iterrows() if r["openalex_id"]}


def citing_works(oa, dois: list[str]) -> dict:
    """citing doi -> authors, journal, type, year (cached lookups, 50 DOIs per call)."""
    out = {}
    ok = [d for d in dois if "," not in d and "|" not in d]
    for b in batches(sorted(set(ok)), 50):
        flt = "doi:" + "|".join(b)
        for w in oa.paginate("works", flt, select="id,doi,type,publication_year,primary_location,authorships", per_page=200):
            out[(w.get("doi") or "").lower()] = {
                "authors": [(short_id((a.get("author") or {}).get("id")), (a.get("author") or {}).get("display_name") or "")
                            for a in w.get("authorships") or [] if (a.get("author") or {}).get("id")],
                "journal": (((w.get("primary_location") or {}).get("source")) or {}).get("display_name"),
                "type": w.get("type"), "year": w.get("publication_year")}
    return out


def citer_evidence(cfg, oa, citers: pd.DataFrame, cit: pd.DataFrame, main: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    allc = citers[citers["scope"] == "ALL"].sort_values("cites_in", ascending=False)
    chosen = pd.concat([allc.head(cfg.phase2.citer_detail_top), allc[allc["flag_non_government"]]]).drop_duplicates("partner_inst")
    names = set(chosen["partner_inst"])
    inflow = cit[cit["edge_scope"] == "inflow"]
    rows = []
    for src, tgt, sdoi in zip(inflow["source_inst"], inflow["target_doi"], inflow["source_doi"]):
        for lab in set(str(src).split("; ")) & names:
            rows.append((lab, str(sdoi).lower(), str(tgt).lower()))
    edges = pd.DataFrame(rows, columns=["partner", "citing_doi", "cited_doi"])
    log.info("examining %d citing institutions: %d citations from %d distinct citing papers",
             len(names), len(edges), edges["citing_doi"].nunique())
    works = citing_works(oa, list(edges["citing_doi"].unique()))
    log.info("found author/journal details for %d of %d citing papers", len(works), edges["citing_doi"].nunique())
    authors: dict[str, set] = defaultdict(set)
    for doi, ids in zip(main["doi"].str.lower(), main["author_openalex_ids"]):
        authors[doi] |= {x for x in str(ids).split(";") if x}
    for doi, a, b in zip(pairs["paper_doi"].str.lower(), pairs["author_a_id"], pairs["author_b_id"]):
        authors[doi] |= {x[2:] for x in (a, b) if x.startswith("A:")}
    titles = dict(zip(main["doi"].str.lower(), main["title"]))
    ev = P.citer_evidence(edges, works, authors, titles, dict(zip(allc["partner_inst"], allc["partner_openalex_id"])))
    keep = ["partner_inst", "ownership", "ownership_source", "cites_in", "shared_papers", "cites_per_shared_paper",
            "flag_heavy", "flag_citation_heavy_vs_collab", "flag_non_government"]
    return allc[keep].merge(ev.drop(columns=["partner_openalex_id"]), on="partner_inst", how="inner").sort_values(
        "cites_in", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- checks

def check(cfg, main, ov, yearly, fac, classes, hyper, citers, ic) -> dict:
    p2 = cfg.phase2
    problems = []
    papers_all = main["openalex_id"].nunique()
    a = ov.set_index("scope")
    if a.loc["ALL", "papers"] != papers_all:
        problems.append("overview papers != unique papers in the dataset")
    for scope, row in a.iterrows():
        if sum(row[f"papers_{c}"] for c in P.class_order(p2)) != row["papers"]:
            problems.append(f"{scope}: author classes do not add up to the papers")
        if not (row["q1_if_gt10"] <= row["q1_if_gt5"] <= row["q1_papers"]):
            problems.append(f"{scope}: Q1 IF counts are not nested")
        if yearly[yearly["scope"] == scope]["papers"].sum() != row["papers"]:
            problems.append(f"{scope}: yearly papers do not add up")
    if len(fac) != main["faculty_id"].nunique():
        problems.append("faculty table does not cover every faculty member")
    if (fac["citations_from_hyper"] > fac["citations"]).any() or (fac["citations_excl_hyper"] < 0).any():
        problems.append("faculty hyperauthored citations exceed total citations")
    if hyper.shape[0] != int(a.loc["ALL", f"papers_{p2.hyper_author_min}-{p2.mega_author_min - 1}"]
                             + a.loc["ALL", f"papers_{p2.mega_author_min}+"]):
        problems.append("hyperauthored paper list disagrees with the class counts")
    tot = classes[classes["scope"] == "ALL"]["share_of_citations"].sum()
    if abs(tot - 1) > 1e-6:
        problems.append("citation shares by author class do not sum to 1")
    src = ic[(ic["partner_is_csir_academy"] != "TRUE") & (ic["partner_in_group"] != "TRUE")]
    if int(pd.to_numeric(src["cites_in"]).sum()) != int(citers[citers["scope"] != "ALL"]["cites_in"].sum()):
        problems.append("citing-institution table loses citations relative to indian_connections.csv")
    if problems:
        raise StepFailed("S16 integrity check failed: " + "; ".join(problems))
    cov = float(a.loc["ALL", "if_coverage"])
    if cov < 0.8:
        log.warning("only %.0f%% of journal papers have an impact factor; check data/manual/jcr and the ISSNs", 100 * cov)
    return {"if_coverage": cov, "papers": int(papers_all)}


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    sub, st, net = cfg.paths.submission, cfg.paths.stats, cfg.paths.networks
    g = cfg.group
    for f in (sub / f"group{g}_data.csv", sub / "authorship_network.csv", sub / "citation_network.csv",
              sub / "indian_connections.csv", st / "faculty_metrics.csv"):
        if not f.exists():
            raise StepFailed(f"{cfg.rel(f)} missing - run s08 to s12 first")
    p2, labs = cfg.phase2, [l["short"] for l in cfg.labs]
    main = pd.read_csv(sub / f"group{g}_data.csv", dtype=str, keep_default_na=False)
    pairs = pd.read_csv(sub / "authorship_network.csv", dtype=str, keep_default_na=False)
    cit = pd.read_csv(sub / "citation_network.csv", dtype=str, keep_default_na=False)
    ic = pd.read_csv(sub / "indian_connections.csv", dtype=str, keep_default_na=False)
    fm = pd.read_csv(st / "faculty_metrics.csv", keep_default_na=False, na_values=[""])
    summ = pd.read_csv(st / "inst_summary.csv", keep_default_na=False, na_values=[""])

    impact = journal_impact(cfg, oa, main)
    impact.to_csv(st / "journal_impact.csv", index=False, encoding="utf-8", lineterminator="\n")
    d = P.prepare(main, impact, labs, p2)

    roster = dict(zip(summ["scope"], summ["roster_faculty"]))
    ov = P.overview_table(d, labs, p2, roster)
    yearly = P.yearly_table(d, labs, p2)
    fac = P.faculty_table(d, labs, p2, fm)
    jour = P.journals_table(d, labs)
    top30 = P.top_papers_by_if(d, labs, 30)
    ftop = P.faculty_top_papers(d, 10)
    classes = P.author_class_table(d, labs, p2)
    ifhist = P.if_histogram(d, labs)
    hyper = P.hyper_papers(d, labs, p2)
    fac_lab = dict(zip(fac["faculty_id"], fac["lab"]))
    tnet = P.temporal_faculty_network(pairs, fac_lab, labs)
    tcit = P.temporal_citations(cit, labs)
    cluster = dict(zip(ic["partner_inst"], ic["partner_cluster"]))
    inet = P.institution_network(pairs, cluster, labs, p2.inst_network_nodes)
    citers = P.citer_table(ic, load_ownership(cfg), p2, labs)
    evidence = citer_evidence(cfg, oa, citers, cit, main, pairs)

    info = check(cfg, main, ov, yearly, fac, classes, hyper, citers, ic)
    out = {"overview": ov, "yearly": yearly, "faculty": fac, "journals": jour, "top30_papers": top30,
           "faculty_top10": ftop, "author_classes": classes, "if_histogram": ifhist, "hyper_papers": hyper, "temporal_network": tnet,
           "temporal_citations": tcit, "citers": citers, "citer_evidence": evidence}
    for name, df in out.items():
        df.to_csv(st / f"p2_{name}.csv", index=False, encoding="utf-8", lineterminator="\n")
    (net / "inst_network.json").write_text(json.dumps(inet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    summary = {**info, "thresholds": {k: getattr(p2, k) for k in vars(p2) if not k.endswith("_file")},
               "if_sources": impact["if_source"].replace("", "none").value_counts().to_dict(),
               "journals": len(impact), "tables": {k: len(v) for k, v in out.items()},
               "flagged_faculty_hyper": int(fac["flag_hyper"].sum()), "flagged_faculty_multi": int(fac["flag_multi"].sum()),
               "hyperauthored_papers": len(hyper),
               "flagged_citers_non_government": int(citers[(citers.scope == "ALL")]["flag_non_government"].sum())}
    (st / "p2_summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    report(ov, fac, hyper, citers, impact, summary)


def report(ov, fac, hyper, citers, impact, summary) -> None:
    a = ov.set_index("scope")
    print("\nInstitutional overview (Phase II)")
    cols = ["papers", "q1_papers", "q1_if_gt5", "q1_if_gt10", "papers_<10", "papers_10-99", "papers_100-999",
            "papers_1000+", "collab_inst_all", "if_coverage", "if_borderline_share"]
    print(a[[c for c in cols if c in a]].round(3).to_string())
    print(f"\nImpact-factor sources (journals): {summary['if_sources']}")
    print(f"Faculty flagged: {summary['flagged_faculty_hyper']} with >= 25% of citations from 100+ author papers, "
          f"{summary['flagged_faculty_multi']} with >= 60% from 10+ author papers")
    print(f"Hyperauthored papers (100+ authors): {len(hyper)}")
    allc = citers[citers.scope == "ALL"]
    print(f"Heavy citing institutions: {int(allc.flag_heavy.sum())}; heavy relative to collaboration: "
          f"{int(allc.flag_citation_heavy_vs_collab.sum())}; flagged non-government: {int(allc.flag_non_government.sum())}")
