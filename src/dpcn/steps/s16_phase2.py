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

import argparse
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


def read_aliases(path) -> dict[str, tuple[str, str]]:
    """issn -> (issn to look up instead, kind) from data/manual/issn_aliases.csv (old ISSNs, renamed journals)."""
    if not path.exists():
        return {}
    a = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {P.norm_issn(r.issn): (P.norm_issn(r.maps_to_issn), r.kind) for r in a.itertuples()}


def journal_impact(cfg, oa, main: pd.DataFrame, previous: pd.DataFrame | None = None,
                   refresh_fallbacks: bool = False) -> pd.DataFrame:
    """One row per ISSN in the dataset: JCR value if supplied, else Scimago cites/doc, else the OpenAlex proxy; all are kept.

    JCR lookup tries, in order: the paper's ISSN, an alias from issn_aliases.csv (old ISSN or a renamed journal's
    successor), every other ISSN OpenAlex lists for the same source, the normalised title, and a clipped JCR title
    (the 2025 list cuts long names) that is a prefix of ours. Fallback values (Scimago, OpenAlex proxy) drift as those
    sources update; unless `refresh_fallbacks`, a journal that had a fallback value in `previous` keeps it, so re-runs
    on any machine give the same numbers.
    """
    j = main[(main["type"] == "journal") & (main["issn"] != "")].drop_duplicates("issn")[["issn", "journal_name"]].copy()
    j["issn_n"] = j["issn"].map(P.norm_issn)
    proxy: dict[str, float] = {}
    meta: dict[str, tuple] = {}
    siblings: dict[str, list[str]] = {}
    for b in batches(sorted(j["issn"]), 50):
        for s in oa.paginate("sources", "issn:" + "|".join(b), select="id,display_name,issn,summary_stats", per_page=200):
            v = (s.get("summary_stats") or {}).get("2yr_mean_citedness")
            all_issn = [P.norm_issn(x) for x in s.get("issn") or []]
            for x in all_issn:
                siblings[x] = all_issn
                if v is not None:
                    proxy[x] = float(v)
                    meta[x] = (short_id(s["id"]), s.get("display_name"))
    j["if_openalex_proxy"] = j["issn_n"].map(proxy)
    j["openalex_source_id"] = j["issn_n"].map(lambda x: meta.get(x, ("", ""))[0])
    jcr = read_jcr(cfg.root / cfg.phase2.jcr_file)
    aliases = read_aliases(cfg.paths.manual / "issn_aliases.csv")
    by_issn = jcr[jcr["issn_n"] != ""].drop_duplicates("issn_n").set_index("issn_n")
    by_title = jcr[jcr["title_n"] != ""].drop_duplicates("title_n").set_index("title_n")
    clipped = [t for t in by_title.index if len(t) >= 25]
    j["if_jcr"], j["jcr_label"], j["jcr_match"] = np.nan, "", ""
    for i, r in j.iterrows():
        hit, how = None, ""
        tries = [(r["issn_n"], "issn")]
        if r["issn_n"] in aliases:
            tries.append((aliases[r["issn_n"]][0], aliases[r["issn_n"]][1]))
        tries += [(x, "openalex_issn") for x in siblings.get(r["issn_n"], []) if x != r["issn_n"]]
        for key, kind in tries:
            if key in by_issn.index:
                hit, how = by_issn.loc[key], kind
                break
        t = P.norm_title(r["journal_name"])
        if hit is None and t in by_title.index:
            hit, how = by_title.loc[t], "title"
        if hit is None and len(t) >= 25:
            pre = [c for c in clipped if t.startswith(c)]
            if len(pre) == 1:
                hit, how = by_title.loc[pre[0]], "title_prefix"
        if hit is not None:
            label = hit["jcr_label"] + (" (successor title)" if how == "successor" else "")
            j.at[i, "if_jcr"], j.at[i, "jcr_label"], j.at[i, "jcr_match"] = hit["jcr_value"], label, how
    sci = read_scimago(cfg.root / cfg.phase2.scimago_dir).drop_duplicates("issn_n").set_index("issn_n")
    j["if_scimago"] = j["issn_n"].map(sci["sci_value"])
    j["scimago_label"] = j["issn_n"].map(sci["sci_label"]).fillna("")
    j["impact_factor"] = j["if_jcr"].fillna(j["if_scimago"]).fillna(j["if_openalex_proxy"])
    j["if_source"] = np.select([j["if_jcr"].notna(), j["if_scimago"].notna(), j["if_openalex_proxy"].notna()],
                               [j["jcr_label"], j["scimago_label"], PROXY], default="")
    if previous is not None and not refresh_fallbacks and len(previous):
        prev = previous.drop_duplicates("issn_n").set_index("issn_n")
        prev_fb = prev[~prev["if_source"].fillna("").str.startswith("JCR") & prev["impact_factor"].notna()]
        frozen = j["if_jcr"].isna() & j["issn_n"].isin(prev_fb.index)
        j.loc[frozen, "impact_factor"] = j.loc[frozen, "issn_n"].map(prev_fb["impact_factor"])
        j.loc[frozen, "if_source"] = j.loc[frozen, "issn_n"].map(prev_fb["if_source"])
        log.info("kept the previous fallback impact factor for %d journals (pass --refresh-fallbacks to re-fetch)",
                 int(frozen.sum()))
    return j.sort_values("journal_name").reset_index(drop=True)


# --------------------------------------------------------------------------- heavy citing institutions

def load_ownership(cfg) -> dict:
    path = cfg.root / cfg.phase2.ownership_file
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    # "unknown" (researched, not established) counts as unclassified; "international" (e.g. ICGEB) is kept as its own class
    return {r["openalex_id"]: {"ownership": r["ownership"], "basis": r.get("basis", ""), "verified": r.get("verified", "")}
            for _, r in df.iterrows() if r["openalex_id"] and r["ownership"] not in ("", "unknown")}


def institution_output(cfg, oa, ids: list[str]) -> pd.DataFrame:
    """Papers (articles and reviews) of each citing institution in the study window, all fields and in the labs' fields.

    Counts come from OpenAlex through the institution's lineage (so its departments and colleges are included), one cached
    count call each; this is the denominator that turns raw citation counts into rates."""
    p2 = cfg.phase2
    window = f"publication_year:{cfg.window.start}-{cfg.window.end},type:article|review"
    fields = "|".join(str(f) for f in p2.citer_norm_fields)
    rows = []
    for i in ids:
        base = f"authorships.institutions.lineage:{i},{window}"
        rows.append({"partner_openalex_id": i, "works_all": oa.count("works", base),
                     "works_ls": oa.count("works", f"{base},primary_topic.field.id:{fields}")})
    return pd.DataFrame(rows, columns=["partner_openalex_id", "works_all", "works_ls"])


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
    fam = cfg.paths.interim / "faculty_author_map.parquet"
    members = set(pd.read_parquet(fam)["author_id"]) if fam.exists() else set()
    ev = P.citer_evidence(edges, works, authors, titles, dict(zip(allc["partner_inst"], allc["partner_openalex_id"])),
                          lab_member_ids=members)
    keep = ["partner_inst", "ownership", "ownership_source", "cites_in", "shared_papers", "cites_per_shared_paper",
            "flag_heavy", "flag_citation_heavy_vs_collab", "flag_non_government"]
    return allc[keep].merge(ev.drop(columns=["partner_openalex_id"]), on="partner_inst", how="inner").sort_values(
        "cites_in", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- lab-level totals including student papers

def lab_corpus(cfg, impact: pd.DataFrame, p2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Publication statistics per lab over EVERY lab-affiliated paper, including papers with no roster faculty member on
    them (students, postdocs, staff), as the instructor asked: students are left out of the faculty-only networks,
    not out of the publication statistics. Faculty-level tables stay faculty-based.

    Same inclusion rules as the dataset (types, cleaning, duplicates: data/interim/lab_corpus_kept.parquet from s05),
    same quartile source (Scimago, year-matched) and impact factors (JCR file by ISSN, else the journal_impact table)."""
    from .s04_works import raw_dir, read_jsonl
    from .s06_enrich import issn_norm, load_sjr, sjr_quartile
    kept = pd.read_parquet(cfg.paths.interim / "lab_corpus_kept.parquet")
    want = set(kept["work_id"])
    info = {}
    for lab in cfg.labs:
        for w in read_jsonl(raw_dir(cfg) / f"lab_{lab['short']}.jsonl.gz"):
            wid = short_id(w["id"])
            if wid in want and wid not in info:
                src = (w.get("primary_location") or {}).get("source") or {}
                issns = [x for x in [src.get("issn_l"), *(src.get("issn") or [])] if x]
                info[wid] = {"n_authors": len(w.get("authorships") or []), "citations": w.get("cited_by_count") or 0,
                             "issns": issns, "source_name": src.get("display_name") or "",
                             "is_journal": src.get("type") == "journal"}
    sjr = load_sjr(cfg.path(cfg.quartile.sjr_dir))
    jcr = read_jcr(cfg.root / p2.jcr_file)
    jcr_by = jcr[jcr["issn_n"] != ""].drop_duplicates("issn_n").set_index("issn_n")["jcr_value"].to_dict()
    imp_by = impact.drop_duplicates("issn_n").set_index("issn_n")["impact_factor"].to_dict()
    rows = []
    for r in kept.drop_duplicates(["work_id", "lab"]).itertuples():
        i = info.get(r.work_id)
        if i is None:
            continue
        keys = [P.norm_issn(x) for x in i["issns"]]
        iff = next((jcr_by[k] for k in keys if k in jcr_by), next((imp_by[k] for k in keys if k in imp_by), np.nan))
        q = sjr_quartile(sjr, int(r.year), i["issns"], i["source_name"])[0] if i["is_journal"] else "NA"
        rows.append({"work_id": r.work_id, "lab": r.lab, "year": int(r.year), "faculty_attributed": bool(r.in_dataset),
                     "n_authors": i["n_authors"], "citations": int(i["citations"]), "is_journal": i["is_journal"],
                     "quartile": q, "impact_factor": iff})
    c = pd.DataFrame(rows)
    t5, t10 = p2.if_thresholds
    out, yr = [], []
    for scope, g in [*((l, c[c["lab"] == l]) for l in [x["short"] for x in cfg.labs]), ("ALL", c.drop_duplicates("work_id"))]:
        for basis, h in (("all lab-affiliated papers", g), ("faculty-attributed papers", g[g["faculty_attributed"]]),
                         ("papers without a roster scientist", g[~g["faculty_attributed"]])):
            j = h[h["is_journal"]]
            known = j[j["quartile"].isin(["Q1", "Q2", "Q3", "Q4"])]
            q1 = j[j["quartile"] == "Q1"]
            out.append({"scope": scope, "basis": basis, "papers": len(h), "citations": int(h["citations"].sum()),
                        "journal_papers": len(j), "quartile_known_share": len(known) / len(j) if len(j) else np.nan,
                        "q1_papers": len(q1), "q1_share": len(q1) / len(known) if len(known) else np.nan,
                        f"q1_if_gt{t5}": int((q1["impact_factor"] > t5).sum()), f"q1_if_gt{t10}": int((q1["impact_factor"] > t10).sum()),
                        f"papers_lt{p2.multi_author_min}": int((h["n_authors"] < p2.multi_author_min).sum()),
                        f"papers_ge{p2.multi_author_min}": int((h["n_authors"] >= p2.multi_author_min).sum()),
                        "share_of_lab_papers": len(h) / len(g) if len(g) else np.nan})
        for y, h in g.groupby("year"):
            yr.append({"scope": scope, "year": int(y), "papers_all": len(h), "papers_faculty": int(h["faculty_attributed"].sum()),
                       "papers_without_roster_scientist": int((~h["faculty_attributed"]).sum())})
    return pd.DataFrame(out), pd.DataFrame(yr)


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
    col = "cites_in_external" if "cites_in_external" in src else "cites_in"     # the citer table counts outside citations
    if int(pd.to_numeric(src[col]).sum()) != int(citers[citers["scope"] != "ALL"]["cites_in"].sum()):
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

    ap = argparse.ArgumentParser(prog="s16")
    ap.add_argument("--allow-proxy", action="store_true", help="run without the licensed JCR file (numbers will differ)")
    ap.add_argument("--refresh-fallbacks", action="store_true", help="re-fetch Scimago/OpenAlex fallback impact factors")
    args, _ = ap.parse_known_args(list(argv))
    jcr_path = cfg.root / p2.jcr_file
    if not jcr_path.exists() and not args.allow_proxy:
        raise StepFailed(f"{cfg.rel(jcr_path)} is missing. Without it every impact factor falls back to Scimago/OpenAlex "
                         "values and the Q1 & IF counts change (about 1,221 -> 1,930 for IF > 5). Put the team's licensed "
                         "file there, or pass --allow-proxy to run anyway.")
    prev_path = st / "journal_impact.csv"
    previous = pd.read_csv(prev_path, dtype={"issn_n": str}) if prev_path.exists() else None
    impact = journal_impact(cfg, oa, main, previous, refresh_fallbacks=args.refresh_fallbacks)
    jcr_share = impact["if_source"].str.startswith("JCR").mean()
    if jcr_share < 0.8 and not args.allow_proxy:
        raise StepFailed(f"only {jcr_share:.0%} of journals matched the JCR file; check its format before using these numbers")
    impact.to_csv(st / "journal_impact.csv", index=False, encoding="utf-8", lineterminator="\n")
    review = impact[~impact["if_source"].str.startswith("JCR") & (impact["impact_factor"] > p2.if_thresholds[0])]
    review.to_csv(st / "if_fallback_review.csv", index=False, encoding="utf-8", lineterminator="\n")
    excl_path = cfg.paths.manual / "work_exclusions.csv"
    excl = pd.read_csv(excl_path, dtype=str, keep_default_na=False) if excl_path.exists() else pd.DataFrame(columns=["doi", "scope"])
    not_ranked = {x.lower().replace("https://doi.org/", "") for x in excl.loc[excl["scope"] == "top_lists", "doi"]}
    d = P.prepare(main, impact, labs, p2, not_ranked)

    roster = dict(zip(summ["scope"], summ["roster_faculty"]))
    ov = P.overview_table(d, labs, p2, roster)
    yearly = P.yearly_table(d, labs, p2)
    fac = P.faculty_table(d, labs, p2, fm)
    cand_path = cfg.paths.interim / "author_candidates.parquet"
    if cand_path.exists():
        fac = P.lifetime_flags(fac, main, pd.read_parquet(cand_path), p2)
    jour = P.journals_table(d, labs)
    top30 = P.top_papers_by_if(d, labs, 30)
    ftop = P.faculty_top_papers(d, 10)
    classes = P.author_class_table(d, labs, p2)
    ifhist = P.if_histogram(d, labs)
    hyper = P.hyper_papers(d, labs, p2)
    dept = P.department_table(d, labs, p2, fac)
    sens = P.if_sensitivity(d, impact, p2)
    roster = pd.read_csv(cfg.root / "data/manual/faculty_roster.csv", dtype=str, keep_default_na=False)
    overrides = pd.read_csv(cfg.root / "data/manual/faculty_match_overrides.csv", dtype=str, keep_default_na=False)
    quality = P.quality_summary(main, roster, overrides, labs)
    abstracts = sorted(d.loc[d["is_abstract"], ["openalex_id", "title"]].drop_duplicates("openalex_id")["title"])
    t5 = f"q1_if_gt{p2.if_thresholds[0]}"
    if sens[0][t5] != int(ov.set_index("scope").loc["ALL", t5]):
        raise StepFailed("impact-factor sensitivity does not reproduce the overview count for the source in use")
    fac_lab = dict(zip(fac["faculty_id"], fac["lab"]))
    tnet = P.temporal_faculty_network(pairs, fac_lab, labs)
    tcit = P.temporal_citations(cit, labs)
    cluster = dict(zip(ic["partner_inst"], ic["partner_cluster"]))
    inet = P.institution_network(pairs, cluster, labs, p2.inst_network_nodes)
    citers = P.citer_table(ic, load_ownership(cfg), p2, labs)
    evidence = citer_evidence(cfg, oa, citers, cit, main, pairs)
    ids = sorted(set(citers.loc[citers["cites_in"] >= p2.citer_norm_min_cites, "partner_openalex_id"]))
    output = institution_output(cfg, oa, ids)
    citers = P.citer_normalised(citers, output, p2)
    norm = P.norm_summary(citers, p2)

    corpus, corpus_year = lab_corpus(cfg, impact, p2)
    info = check(cfg, main, ov, yearly, fac, classes, hyper, citers, ic)
    out = {"overview": ov, "yearly": yearly, "faculty": fac, "journals": jour, "top30_papers": top30,
           "faculty_top10": ftop, "author_classes": classes, "if_histogram": ifhist, "hyper_papers": hyper, "temporal_network": tnet,
           "temporal_citations": tcit, "citers": citers, "citer_evidence": evidence, "departments": dept,
           "lab_corpus": corpus, "lab_corpus_yearly": corpus_year}
    for name, df in out.items():
        df.to_csv(st / f"p2_{name}.csv", index=False, encoding="utf-8", lineterminator="\n")
    (net / "inst_network.json").write_text(json.dumps(inet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    summary = {**info, "thresholds": {k: getattr(p2, k) for k in vars(p2) if not k.endswith("_file")},
               "if_sources": impact["if_source"].replace("", "none").value_counts().to_dict(),
               "journals": len(impact), "tables": {k: len(v) for k, v in out.items()},
               "flagged_faculty_hyper": int(fac["flag_hyper"].sum()), "flagged_faculty_multi": int(fac["flag_multi"].sum()),
               "flagged_faculty_lifetime": int(fac["flag_lifetime"].sum()) if "flag_lifetime" in fac else 0,
               "hyperauthored_papers": len(hyper),
               "flagged_citers_non_government": int(citers[(citers.scope == "ALL")]["flag_non_government"].sum()),
               "citer_normalised": norm, "if_sensitivity": sens, "quality": quality,
               "meeting_abstracts": {"papers": len(abstracts), "titles": abstracts}}
    (st / "p2_summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    report(ov, fac, hyper, citers, impact, summary)
    report_norm(summary["citer_normalised"])


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


def report_norm(n: dict) -> None:
    print(f"\nSize-normalised heavy citers (rate = citations to the labs per 1,000 papers in the labs' fields; "
          f"{n['compared']} institutions with >= {n['min_cites']} citations and >= {n['min_works']} such papers)")
    print(f"  flagged non-government before: {n['flagged_before']}; assessable: {n['flagged_assessed']}; still outliers (z >= {n['z']}): "
          f"{n['flagged_still_outliers']}")
    print(f"  median rate by ownership: { {k: round(v, 1) for k, v in n['median_rate'].items()} } (n = {n['n_by_ownership']})")
    print(f"  Spearman rank correlation raw vs normalised: {n['rank_corr_raw_vs_normalised']:.2f}")
    print(f"  flagged outliers by z cut-off / all-fields denominator: {n['sensitivity_flagged_outliers']}")
    print(f"  still outliers: {n['still_outliers']}")
    print(f"  no longer outliers: {n['no_longer_outliers']}")
    print(f"  not assessable: {n['flagged_not_assessed']}")
    print(f"  outliers not in the original flagged set: {n['new_outliers_any_ownership']}")
