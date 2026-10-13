"""S02: author candidates (guide §7, S02).

Pulls every OpenAlex author with an affiliation to each lab, with the years they were affiliated.
S03 matches roster names against this pool. Output: data/interim/author_candidates.parquet

Acceptance: for every lab, rows fetched == OpenAlex's reported count (no truncated paging).
"""
from __future__ import annotations

import logging

import pandas as pd

from ..openalex import short_id
from . import StepFailed

log = logging.getLogger("dpcn.s02")

SELECT = ("id,display_name,display_name_alternatives,orcid,works_count,cited_by_count,summary_stats,"
          "affiliations,last_known_institutions")

# A profile this broad is almost certainly several people merged by OpenAlex (e.g. 161 affiliations).
# S03 should only accept such a candidate with strong evidence (ORCID / matching titles).
MERGED_MIN_AFFILIATIONS = 40
MERGED_MIN_WORKS = 1500

COLUMNS = ["lab", "author_id", "display_name", "alternatives", "orcid", "works_count", "cited_by_count",
           "h_index", "i10_index", "years_at_lab", "n_years_at_lab", "n_years_at_lab_window",
           "first_year_at_lab", "last_year_at_lab", "n_affiliations", "last_known_ids", "last_known_names",
           "at_lab_now", "suspect_merged"]


def candidate_row(a: dict, lab: dict, y0: int, y1: int) -> dict:
    """Flatten one OpenAlex author record for `lab` (a dict from institutions.yaml)."""
    lab_id = lab["openalex_id"]
    years = sorted({y for aff in a.get("affiliations") or []
                    if short_id((aff.get("institution") or {}).get("id")) == lab_id
                    for y in aff.get("years") or []})
    in_window = [y for y in years if y0 <= y <= y1]
    last_known = a.get("last_known_institutions") or []
    last_ids = [short_id(i.get("id")) for i in last_known]
    stats = a.get("summary_stats") or {}
    n_aff = len(a.get("affiliations") or [])
    works = a.get("works_count") or 0
    return {
        "lab": lab["short"],
        "author_id": short_id(a["id"]),
        "display_name": a.get("display_name") or "",
        "alternatives": [n for n in (a.get("display_name_alternatives") or []) if n],
        "orcid": (a.get("orcid") or "").rsplit("/", 1)[-1],
        "works_count": works,
        "cited_by_count": a.get("cited_by_count") or 0,
        "h_index": stats.get("h_index") or 0,
        "i10_index": stats.get("i10_index") or 0,
        "years_at_lab": years,
        "n_years_at_lab": len(years),
        "n_years_at_lab_window": len(in_window),
        "first_year_at_lab": years[0] if years else None,
        "last_year_at_lab": years[-1] if years else None,
        "n_affiliations": n_aff,
        "last_known_ids": last_ids,
        "last_known_names": [i.get("display_name") or "" for i in last_known],
        "at_lab_now": lab_id in last_ids,
        "suspect_merged": n_aff >= MERGED_MIN_AFFILIATIONS or works >= MERGED_MIN_WORKS,
    }


def fetch_lab(cfg, oa, lab: dict) -> pd.DataFrame:
    flt = f"affiliations.institution.id:{lab['openalex_id']}"
    expected = oa.count("authors", flt)
    rows = [candidate_row(a, lab, cfg.window.start, cfg.window.end)
            for a in oa.paginate("authors", flt, select=SELECT, sort="works_count:desc")]
    df = pd.DataFrame(rows, columns=COLUMNS)
    if len(df) != expected or df["author_id"].duplicated().any():
        raise StepFailed(f"{lab['short']}: fetched {len(df)} authors "
                         f"({df['author_id'].duplicated().sum()} duplicates), OpenAlex reports {expected}")
    return df


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("lab", sort=False)
    return pd.DataFrame({
        "authors": g.size(),
        "years_in_window>=1": g["n_years_at_lab_window"].apply(lambda s: (s >= 1).sum()),
        "at_lab_now": g["at_lab_now"].sum(),
        "with_orcid": g["orcid"].apply(lambda s: (s != "").sum()),
        "suspect_merged": g["suspect_merged"].sum(),
    }).astype(int)


def run(cfg, oa, argv=()) -> None:
    frames = [fetch_lab(cfg, oa, lab) for lab in cfg.labs]
    df = pd.concat(frames, ignore_index=True)
    out = cfg.paths.interim / "author_candidates.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print()
    print(summarise(df).to_string())
    print(f"\nTotal candidate rows: {len(df)} ({df['author_id'].nunique()} distinct authors)\n")
    log.info("Wrote %s", cfg.rel(out))
