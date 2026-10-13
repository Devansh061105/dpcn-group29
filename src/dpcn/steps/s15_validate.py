"""S15: validate the deliverables and package them (guide §7, S15; plan §11).

    python -m dpcn run s15            all checks, then README.txt and the two zip files
    python -m dpcn run s15 --only main  checks on group29_data.csv only

Every check prints PASS/FAIL; any FAIL stops packaging.
"""
from __future__ import annotations

import argparse
import json
import logging
import zipfile

import pandas as pd

from . import StepFailed
from .s08_main_csv import EXTRA, REQUIRED

log = logging.getLogger("dpcn.s15")

NET_REQ = {
    "citation_network.csv": ["source_doi", "target_doi", "source_inst", "target_inst", "year"],
    "authorship_network.csv": ["author_a", "author_b", "paper_doi", "inst_a", "inst_b", "year"],
    "indian_connections.csv": ["your_inst", "partner_inst", "shared_papers", "total_citations"],
}
QUARTILE_VALUES = {"Q1", "Q2", "Q3", "Q4", "A*", "A", "B", "C", "NA"}


class Checks:
    def __init__(self):
        self.rows = []

    def __call__(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))

    def report(self) -> bool:
        for name, ok, detail in self.rows:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        return all(ok for _, ok, _ in self.rows)


def check_main(cfg, sub, C: Checks) -> pd.DataFrame:
    labs = [l["short"] for l in cfg.labs]
    m = pd.read_csv(sub / f"group{cfg.group}_data.csv", dtype=str, keep_default_na=False)
    C("main: required columns first, in order", list(m.columns[:len(REQUIRED)]) == REQUIRED)
    empty = [c for c in REQUIRED if c != "issn" and (m[c] == "").all() and c != "coauthor_institutes"]
    C("main: no required column entirely empty", not empty, ", ".join(empty))
    C("main: group == 29", (m["group"] == str(cfg.group)).all())
    C("main: institution within the four labs", m["institution"].isin(labs).all())
    C("main: all assigned institutions present", set(m["institution"]) == set(labs))
    yrs = m["year"].astype(int)
    C("main: years within 2016-2026", yrs.between(cfg.window.start, cfg.window.end).all())
    missing = [f"{lab}:{y}" for lab in labs for y in range(cfg.window.start, cfg.window.end + 1)
               if not ((m["institution"] == lab) & (yrs == y)).any()]
    C("main: every lab has every year", not missing, ", ".join(missing))
    C("main: type is journal/conference", m["type"].isin(["journal", "conference"]).all())
    C("main: quartile values", m["quartile"].isin(QUARTILE_VALUES).all())
    for b in ("cites_indian_inst", "cited_by_indian_inst"):
        C(f"main: {b} is TRUE/FALSE", m[b].isin(["TRUE", "FALSE"]).all())
    C("main: DOI is a doi.org or OpenAlex URL", m["doi"].str.match(r"^https://(doi\.org/10\.|openalex\.org/W)").all())
    C("main: citations are non-negative integers", m["citations"].str.fullmatch(r"\d+").all())
    C("main: issn blank for conference rows", (m.loc[m["type"] == "conference", "issn"] == "").all())
    C("main: no duplicate (paper, faculty, institution)", not m.duplicated(["openalex_id", "faculty_id", "institution"]).any())
    own = [r for r in m.itertuples() if r.institution in (r.coauthor_institutes or "").split("; ")]
    C("main: coauthor_institutes never lists the row's own lab", not own, f"{len(own)} rows")
    return m


def check_networks(cfg, sub, m: pd.DataFrame, C: Checks) -> None:
    labs = set(l["short"] for l in cfg.labs)
    for f, cols in NET_REQ.items():
        df = pd.read_csv(sub / f, dtype=str, keep_default_na=False, nrows=5)
        C(f"{f}: required columns first, in order", list(df.columns[:len(cols)]) == cols)
    dois = set(m["doi"])
    cit = pd.read_csv(sub / "citation_network.csv", dtype=str, keep_default_na=False)
    internal = cit[cit["edge_scope"] == "internal"]
    C("citation: internal endpoints exist in the main CSV",
      internal["source_doi"].isin(dois).all() and internal["target_doi"].isin(dois).all())
    C("citation: outflow sources / inflow targets are ours",
      cit.loc[cit.edge_scope == "outflow", "source_doi"].isin(dois).all()
      and cit.loc[cit.edge_scope == "inflow", "target_doi"].isin(dois).all())
    C("citation: no self-loops", not (cit["source_doi"] == cit["target_doi"]).any())
    C("citation: cross-institute edges only outside the corpus",
      (cit.loc[cit.edge_scope != "internal", "cross_institute"] == "TRUE").all())

    au = pd.read_csv(sub / "authorship_network.csv", dtype=str, keep_default_na=False)
    C("authorship: canonical order author_a_id < author_b_id", (au["author_a_id"] < au["author_b_id"]).all())
    C("authorship: no self-loops", not (au["author_a_id"] == au["author_b_id"]).any())
    C("authorship: paper_doi exists in the main CSV", au["paper_doi"].isin(dois).all())
    C("authorship: at least one endpoint at one of our labs", (au["inst_a"].isin(labs) | au["inst_b"].isin(labs)).all())

    ic = pd.read_csv(sub / "indian_connections.csv", dtype=str, keep_default_na=False)
    C("connections: your_inst within our labs", ic["your_inst"].isin(labs).all())
    C("connections: partner_inst != your_inst", (ic["your_inst"] != ic["partner_inst"]).all())
    C("connections: total_citations = cites_in + cites_out",
      (ic["total_citations"].astype(int) == ic["cites_in"].astype(int) + ic["cites_out"].astype(int)).all())

    # consistency: the flags in the main CSV agree with the edges they summarise (D14 per row)
    out_src = set(cit.loc[cit.edge_scope.isin(["outflow", "internal"]), "source_doi"])
    flagged = set(m.loc[m["cites_indian_inst"] == "TRUE", "doi"])
    C("consistency: every cites_indian_inst=TRUE paper has an outgoing edge", flagged <= out_src,
      f"{len(flagged - out_src)} without")
    in_tgt = set(cit["target_doi"])
    flagged = set(m.loc[m["cited_by_indian_inst"] == "TRUE", "doi"])
    C("consistency: every cited_by_indian_inst=TRUE paper has an incoming edge", flagged <= in_tgt,
      f"{len(flagged - in_tgt)} without")
    stats = cfg.paths.stats
    if (stats / "inst_summary.csv").exists():
        s = pd.read_csv(stats / "inst_summary.csv")
        C("scope: statistics tables hold only our labs", set(s["scope"]) <= labs | {"ALL"})


README = """DPCN Research Mapping Project - Group {group}
Institutions: {labs}
Window: {y0}-{y1} ({partial} is a partial year). Data collected from OpenAlex on {date}.

FILES
{files}

KEY DECISIONS
- Faculty (D2/D25): scientists listed on each lab's website, plus scientists identified from lab-affiliated
  authorship (frequent last/corresponding author) and confirmed by the team; matched to OpenAlex author IDs.
- A paper counts for a faculty member only if their own authorship carries the lab affiliation (D4).
- One row per paper x faculty member x lab (D5); paper-level statistics deduplicate on openalex_id.
- Types (D7): journal articles/reviews/letters and conference papers; no preprints, chapters, errata.
- Quartile (D8): Scimago SJR best quartile of the publication year, joined on ISSN then title; CORE rank for
  conference papers; NA when unknown.
- h-index (D10): window h-index from the dataset; OpenAlex lifetime h shown for context.
- Indian partner (D11): an Indian institution other than the row's lab; umbrella bodies (CSIR HQ, Government of
  India, ministries, DAE/DBT HQ) and AcSIR (CSIR's degree academy) are not counted.
- Citation network (D13/D14): internal edges between dataset papers, plus edges to/from other Indian works when
  the two papers' Indian institutions differ. year = citing paper's year.
- Authorship network (D15/D16): every pair on every dataset paper with <= {max_auth} authors where at least one
  author is at one of our labs; faculty-only and lab-internal graphs are analysed.
- indian_connections total_citations (A8) = cites_in + cites_out; shared_papers_citations is also given.

EXTRA COLUMNS in {main}: {extra}
"""


def package(cfg, sub, m: pd.DataFrame) -> None:
    meta = json.loads((sub / "metadata.json").read_text()) if (sub / "metadata.json").exists() else {}
    week2 = [f"group{cfg.group}_data.csv", *NET_REQ, "metadata.json", "README.txt"]
    week3 = [f"group{cfg.group}_dashboard.html", f"group{cfg.group}_report.pptx", f"group{cfg.group}_report.pdf"]
    files = []
    for f in week2[:4]:
        n = sum(1 for _ in open(sub / f, encoding="utf-8")) - 1
        files.append(f"  {f:<28} {n:>8} rows")
    files += [f"  {f}" for f in week3 if (sub / f).exists() or (cfg.paths.report / f).exists()]
    text = README.format(group=cfg.group, labs=", ".join(l["short"] for l in cfg.labs), y0=cfg.window.start,
                         y1=cfg.window.end, partial=cfg.window.partial_year, date=meta.get("collection_date", ""),
                         files="\n".join(files), max_auth=cfg.networks.max_authors_for_pairs,
                         main=f"group{cfg.group}_data.csv", extra=", ".join(EXTRA))
    (sub / "README.txt").write_text(text, encoding="utf-8")
    with zipfile.ZipFile(sub / f"group{cfg.group}_week2.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in week2:
            z.write(sub / f, f)
    w3 = [(p, p.name) for f in week3 for p in (sub / f, cfg.paths.report / f) if p.exists()]
    if w3:
        with zipfile.ZipFile(sub / f"group{cfg.group}_week3.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for p, name in dict((n, (p, n)) for p, n in w3).values():
                z.write(p, name)
    log.info("Packaged %s (and week3 with %d files)", f"group{cfg.group}_week2.zip", len(w3))


def run(cfg, oa, argv=()) -> None:
    ap = argparse.ArgumentParser(prog="s15")
    ap.add_argument("--only", choices=["main"])
    args, _ = ap.parse_known_args(list(argv))
    sub = cfg.paths.submission
    C = Checks()
    m = check_main(cfg, sub, C)
    if args.only != "main":
        check_networks(cfg, sub, m, C)
    print()
    ok = C.report()
    if not ok:
        raise StepFailed("validation failed; nothing packaged")
    if args.only != "main":
        package(cfg, sub, m)
