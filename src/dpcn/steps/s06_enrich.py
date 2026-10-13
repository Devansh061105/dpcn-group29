"""S06: enrich the dataset works (guide §7, S06; plan D8, D20).

  quartile    Scimago (SJR) best quartile of the publication year, joined on ISSN (issn_l, then any ISSN), then on
              the normalised journal title. Years after the latest SJR file use the latest one. Conference papers
              get a CORE rank (A*/A/B/C) when the venue is in the CORE export. Unknown -> NA.
  department  from the roster; when the website gives none (all of IMTECH), the faculty member's most frequent
              OpenAlex subfield, marked dept_source=openalex.

Inputs: data/manual/sjr/scimagojr_<YEAR>.csv (';'-separated, columns Title, Issn, SJR Best Quartile; the full
download or a subset with the same header), data/manual/core/CORE2023.csv (no header), optional
data/manual/quartile_overrides.csv (issn,quartile).
Outputs (data/interim/): quartiles.parquet, faculty_dept.parquet, s06_summary.json.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter

import pandas as pd
from rapidfuzz import fuzz

from ..names import norm
from ..netdata import read_works
from . import StepFailed

log = logging.getLogger("dpcn.s06")

QUARTILES = {"Q1", "Q2", "Q3", "Q4"}
CORE_RANKS = {"A*", "A", "B", "C"}


def issn_norm(x) -> str:
    return re.sub(r"[^0-9X]", "", x.upper()) if isinstance(x, str) else ""


# --------------------------------------------------------------------------- SJR

def load_sjr(sjr_dir) -> dict[int, dict]:
    """year -> {"issn": {issn: quartile}, "title": {norm title: quartile}}; unranked ('-') journals are skipped."""
    out: dict[int, dict] = {}
    for path in sorted(sjr_dir.glob("scimagojr_*.csv")):
        m = re.search(r"(\d{4})", path.stem)
        if not m:
            continue
        df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, usecols=["Title", "Issn", "SJR Best Quartile"])
        by_issn, by_title = {}, {}
        for title, issns, q in df.itertuples(index=False):
            if q not in QUARTILES:
                continue
            for i in issns.split(","):
                i = issn_norm(i)
                if len(i) == 8:
                    by_issn.setdefault(i, q)
            by_title.setdefault(norm(title), q)
        out[int(m.group(1))] = {"issn": by_issn, "title": by_title}
    return out


def sjr_quartile(sjr: dict[int, dict], year: int, issns: list[str], title: str) -> tuple[str, int | None]:
    """(quartile, SJR year used) for a journal paper; ('NA', None) when no SJR year knows the journal.
    The paper's own year is tried first, then the neighbouring years (journals enter and leave SJR)."""
    if not sjr:
        return "NA", None
    latest = max(sjr)
    y = min(year, latest)
    keys = [issn_norm(i) for i in issns if issn_norm(i)]
    t = norm(title or "")
    for yy in (y, y - 1, y + 1, y - 2):
        tab = sjr.get(yy)
        if not tab:
            continue
        for k in keys:
            if k in tab["issn"]:
                return tab["issn"][k], yy
        if t and t in tab["title"]:
            return tab["title"][t], yy
    return "NA", None


# --------------------------------------------------------------------------- CORE

def load_core(path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.reader(f):
            if len(r) >= 5 and r[4].strip() in CORE_RANKS:
                rows.append({"title": norm(r[1]), "acronym": r[2].strip(), "rank": r[4].strip()})
    return rows


def core_rank(core: list[dict], venue: str) -> str:
    """CORE rank of a conference venue by acronym (as a whole word in the venue name) or title similarity >= 90."""
    if not venue or not core:
        return "NA"
    v = norm(venue)
    for c in core:
        if c["acronym"] and len(c["acronym"]) >= 3 and re.search(rf"\b{re.escape(c['acronym'])}\b", venue):
            return c["rank"]
    best = max(core, key=lambda c: fuzz.token_set_ratio(v, c["title"]))
    return best["rank"] if fuzz.token_set_ratio(v, best["title"]) >= 90 else "NA"


# --------------------------------------------------------------------------- department

def departments(roster: pd.DataFrame, links: pd.DataFrame, works: pd.DataFrame) -> pd.DataFrame:
    """Roster department, else the modal OpenAlex subfield of the person's dataset papers (plan D20)."""
    sub = links.merge(works[["work_id", "subfield"]], on="work_id")
    modal = {fid: Counter(g["subfield"].dropna()).most_common(1)[0][0]
             for fid, g in sub.groupby("faculty_id") if g["subfield"].notna().any()}
    rows = []
    for r in roster.itertuples():
        dept = (r.department or "").strip()
        if dept:
            rows.append({"faculty_id": r.faculty_id, "department": dept, "dept_source": "website"})
        else:
            rows.append({"faculty_id": r.faculty_id, "department": modal.get(r.faculty_id, "Unknown"),
                         "dept_source": "openalex" if r.faculty_id in modal else "none"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    it = cfg.paths.interim
    if not (it / "works.parquet").exists():
        raise StepFailed("data/interim/works.parquet missing - run s05 first")
    works = read_works(it)
    links = pd.read_parquet(it / "faculty_papers.parquet")
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)

    sjr = load_sjr(cfg.path(cfg.quartile.sjr_dir))
    if cfg.quartile.mode == "latest" and sjr:
        sjr = {max(sjr): sjr[max(sjr)]}
    core = load_core(cfg.path(cfg.quartile.core_file))
    ov_path = cfg.paths.manual / "quartile_overrides.csv"
    overrides = ({issn_norm(r["issn"]): r["quartile"] for r in csv.DictReader(open(ov_path, encoding="utf-8"))}
                 if ov_path.exists() else {})
    if not sjr:
        log.warning("No SJR files in %s: every journal quartile will be NA", cfg.quartile.sjr_dir)
    log.info("SJR years loaded: %s; CORE ranked venues: %d; quartile overrides: %d",
             sorted(sjr), len(core), len(overrides))

    rows = []
    for w in works.itertuples():
        if w.kind == "conference":
            q = core_rank(core, w.source_name or "")
            rows.append({"work_id": w.work_id, "quartile": q, "quartile_source": "core" if q != "NA" else "none",
                         "sjr_year_used": None})
            continue
        issns = ([w.issn_l] if isinstance(w.issn_l, str) else []) + list(w.issns)
        ov = next((overrides[issn_norm(i)] for i in issns if issn_norm(i) in overrides), None)
        if ov:
            rows.append({"work_id": w.work_id, "quartile": ov, "quartile_source": "override", "sjr_year_used": None})
            continue
        q, y = sjr_quartile(sjr, int(w.year), issns, w.source_name or "")
        rows.append({"work_id": w.work_id, "quartile": q, "quartile_source": "sjr" if q != "NA" else "none",
                     "sjr_year_used": y})
    quart = pd.DataFrame(rows)
    quart["sjr_year_used"] = quart["sjr_year_used"].astype("Int64")
    dept = departments(roster, links, works)

    quart.to_parquet(it / "quartiles.parquet", index=False)
    dept.to_parquet(it / "faculty_dept.parquet", index=False)

    # ---- report
    j = works[["work_id", "kind", "source_name"]].merge(quart, on="work_id")
    per_lab = links[["work_id", "institution"]].drop_duplicates().merge(j, on="work_id")
    summary = {"sjr_years": sorted(sjr), "labs": {}}
    print("\nQuartile coverage of journal papers (target >= 85%)")
    for lab, g in per_lab[per_lab["kind"] == "journal"].groupby("institution"):
        known = g["quartile"].isin(QUARTILES)
        dist = g.loc[known, "quartile"].value_counts().reindex(sorted(QUARTILES), fill_value=0).to_dict()
        summary["labs"][lab] = {"journal_papers": len(g), "coverage": round(known.mean(), 4), **dist}
        print(f"  {lab:<12} {len(g):>5} papers  coverage {known.mean():6.1%}  " +
              "  ".join(f"{k}:{v}" for k, v in dist.items()))
    conf = j[j["kind"] == "conference"]
    summary["conference_papers"] = len(conf)
    summary["conference_ranked"] = int(conf["quartile"].isin(CORE_RANKS).sum())
    print(f"Conference papers: {len(conf)}, CORE-ranked: {summary['conference_ranked']}")
    miss = j[(j["kind"] == "journal") & (j["quartile"] == "NA")]["source_name"].value_counts().head(20)
    if len(miss):
        print("Top journals with no quartile (add to data/manual/quartile_overrides.csv if SJR has them):")
        for s, c in miss.items():
            print(f"  {c:>4}  {s}")
    ds = dept["dept_source"].value_counts().to_dict()
    summary["dept_source"] = ds
    print(f"Department source: {ds}")
    (it / "s06_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
