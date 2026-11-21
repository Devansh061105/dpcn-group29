"""Worksheet for task T-06 (joining years): data/manual/joining_years.csv.

Pre-fills the evidence a person needs to decide each faculty member's joining year, and leaves the decision blank:

  openalex_first_year_at_lab   first year OpenAlex places any of their author profiles at the lab (affiliation data
                               before about 2000 is sparse, so for senior staff this is an upper bound, not the date)
  first_paper_year             first OpenAlex paper anywhere (career start, from step s20)
  phd_year, last_postdoc_year, experience_years   read from the CCMB profile page ("Education & Experience")
  joined_year, source_url, checked_by, notes      for the team: the year they joined this lab, and where it says so

An existing worksheet is never overwritten: rows already filled keep their values; only empty evidence is refreshed.

    python -m dpcn.joining_worksheet
"""
from __future__ import annotations

import gzip
import hashlib
import html
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/manual/joining_years.csv"
CACHE = ROOT / "data/cache/web/profiles"
UA = {"User-Agent": "dpcn-group29-roster-check/1.0"}
COLS = ["faculty_id", "name", "lab", "status", "designation", "profile_url", "openalex_first_year_at_lab", "first_paper_year",
        "phd_year", "last_postdoc_year", "experience_years", "joined_year", "source_url", "checked_by", "notes"]


def page_text(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html.gz")
    if f.exists():
        raw = gzip.decompress(f.read_bytes()).decode("utf-8", "replace")
    else:
        try:
            raw = requests.get(url, timeout=25, headers=UA).text
        except requests.RequestException:
            return ""
        f.write_bytes(gzip.compress(raw.encode()))
        time.sleep(0.6)                                   # polite: one page at a time
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ; ", raw)))
    return re.sub(r"(\s*;\s*)+", " ; ", txt)


def ccmb_career(txt: str) -> dict:
    i = txt.find("Education & Experience ; P")
    sec = txt[i:i + 1500] if i >= 0 else ""
    out = {}
    m = re.search(r"Ph\.?\s?D[^;]*;(?:[^;]*;){0,2}\s*((?:19|20)\d\d)", sec)
    if m:
        out["phd_year"] = int(m.group(1))
    pd_years = [int(y) for y in re.findall(r"Post-?doctoral[^;]*;(?:[^;]*;){0,2}\s*((?:19|20)\d\d)", sec)]
    pd_years += [int(y) for y in re.findall(r"(?:Fellow|Postdoc)[^;]*;[^;]*;\s*((?:19|20)\d\d)", sec)]
    if pd_years:
        out["last_postdoc_year"] = max(pd_years)
    m = re.search(r"Experience:\s*;\s*(\d{1,2})\s*years", sec)
    if m:
        out["experience_years"] = int(m.group(1))
    return out


def main() -> None:
    it = ROOT / "data/interim"
    roster = pd.read_parquet(it / "roster.parquet")
    fmap = pd.read_parquet(it / "faculty_author_map.parquet")
    cand = pd.read_parquet(it / "author_candidates.parquet")
    lab_first = fmap.merge(cand[["lab", "author_id", "first_year_at_lab"]], left_on=["institution", "author_id"], right_on=["lab", "author_id"], how="left")
    lab_first = lab_first.groupby("faculty_id")["first_year_at_lab"].min()
    car = ROOT / "outputs/stats/enrich_faculty_career.csv"
    first_paper = pd.read_csv(car).set_index("faculty_id")["first_year_any"] if car.exists() else pd.Series(dtype=float)
    old = pd.read_csv(OUT, dtype=str, keep_default_na=False).set_index("faculty_id") if OUT.exists() else None
    rows = []
    for r in roster.itertuples():
        row = {"faculty_id": r.faculty_id, "name": r.name, "lab": r.institution, "status": r.status, "designation": r.designation,
               "profile_url": r.profile_url or "", "openalex_first_year_at_lab": lab_first.get(r.faculty_id),
               "first_paper_year": first_paper.get(r.faculty_id)}
        if r.institution == "CSIR-CCMB" and r.profile_url and "people-details" in r.profile_url:
            row.update(ccmb_career(page_text(r.profile_url)))
        for k in ("joined_year", "source_url", "checked_by", "notes"):
            row[k] = old.at[r.faculty_id, k] if old is not None and r.faculty_id in old.index else ""
        rows.append(row)
    df = pd.DataFrame(rows).reindex(columns=COLS)
    for c in ("openalex_first_year_at_lab", "first_paper_year", "phd_year", "last_postdoc_year", "experience_years"):
        df[c] = df[c].astype("Int64")
    df.to_csv(OUT, index=False, encoding="utf-8", lineterminator="\n")
    print(f"{len(df)} faculty; OpenAlex first year at lab for {df['openalex_first_year_at_lab'].notna().sum()}, "
          f"first paper for {df['first_paper_year'].notna().sum()}, CCMB website career data for {df['phd_year'].notna().sum()}; "
          f"joined_year filled for {(df['joined_year'].astype(str) != '').sum()}")


if __name__ == "__main__":
    main()
