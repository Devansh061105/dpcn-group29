"""Lab corpus: every OpenAlex work with an authorship affiliated (by lineage) to a lab, 2016-2026.

S03 mines it for the authors who really publish under each lab's name; S04 reuses the same cached
pages, so the two steps must use identical request parameters (keep them in this one function).
"""
from __future__ import annotations

from typing import Iterator

import pandas as pd

from .openalex import WORK_SELECT, short_id


def lab_filter(cfg, lab: dict) -> str:
    return f"authorships.institutions.lineage:{lab['openalex_id']},{cfg.year_filter}"


def iter_lab_works(cfg, oa, lab: dict) -> Iterator[dict]:
    yield from oa.paginate("works", lab_filter(cfg, lab), select=WORK_SELECT)


def authorship_at_lab(authorship: dict, lab_id: str) -> bool:
    """True if any institution on this authorship has the lab in its lineage."""
    return any(lab_id == short_id(i) for inst in authorship.get("institutions") or []
               for i in (inst.get("lineage") or [inst.get("id")]))


def build_author_pool(cfg, oa, lab: dict) -> tuple[pd.DataFrame, int]:
    """Authors with at least one lab-affiliated authorship in the corpus.

    Returns (pool, n_works). Columns: lab, author_id, name, orcid, n_lab_works_window (works of a
    qualifying type), n_lab_works_all (any type), first_year, last_year.
    """
    lab_id = lab["openalex_id"]
    ok_types = set(cfg.work_filter.include_work_types)
    agg: dict[str, dict] = {}
    n_works = 0
    for w in iter_lab_works(cfg, oa, lab):
        n_works += 1
        year = w.get("publication_year")
        qualifies = w.get("type") in ok_types and not w.get("is_retracted")
        for a in w.get("authorships") or []:
            au = a.get("author") or {}
            if not au.get("id") or not authorship_at_lab(a, lab_id):
                continue
            rec = agg.setdefault(short_id(au["id"]), {
                "name": au.get("display_name") or "", "orcid": (au.get("orcid") or "").rsplit("/", 1)[-1],
                "all": set(), "ok": set(), "years": set()})
            rec["all"].add(w["id"])
            rec["years"].add(year)
            if qualifies:
                rec["ok"].add(w["id"])
    rows = [{"lab": lab["short"], "author_id": aid, "name": r["name"], "orcid": r["orcid"],
             "n_lab_works_window": len(r["ok"]), "n_lab_works_all": len(r["all"]),
             "first_year": min(r["years"]), "last_year": max(r["years"])} for aid, r in agg.items()]
    cols = ["lab", "author_id", "name", "orcid", "n_lab_works_window", "n_lab_works_all", "first_year", "last_year"]
    return pd.DataFrame(rows, columns=cols), n_works
