"""S05: normalise, filter, deduplicate (guide §7, S05; plan D4, D5, D6, D7).

Reads the raw works from S04 and decides what belongs in the dataset:

  1. type filter (D7): journal articles/reviews/letters and conference papers; no preprints, chapters,
     errata, datasets, retractions
  2. faculty link (D4): a paper counts for a faculty member only if THEIR authorship carries the lab, either
     through the institution lineage or, failing that, because the raw affiliation text names the lab
  3. duplicates: same DOI (or same long title and year) collapse to one paper

Outputs (data/interim/): works, authorships, faculty_papers, institutions, lab_corpus_kept (all .parquet) and
s05_summary.json. Also prints diagnostics, including the IMTECH 2026 spike flagged in S00.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import pandas as pd

from ..institutions import InstitutionRegistry
from ..names import norm
from ..openalex import short_id
from . import StepFailed
from .s04_works import raw_dir, read_jsonl

log = logging.getLogger("dpcn.s05")


# --------------------------------------------------------------------------- pure decision functions

def classify_work(w: dict, include_types) -> tuple[str | None, str | None]:
    """(kind, None) for a work to keep, ('journal'|'conference'); (None, reason) for one to drop (plan D7)."""
    if w.get("is_retracted"):
        return None, "retracted"
    wtype = w.get("type")
    if wtype not in include_types:
        return None, f"type: {wtype}"
    src = (w.get("primary_location") or {}).get("source") or {}
    stype = src.get("type")
    if wtype == "conference-paper" or stype == "conference":
        return "conference", None
    if stype == "journal":
        return "journal", None
    return None, f"source: {stype or 'none'}"


def alias_regex(lab: dict) -> re.Pattern:
    """Matches the lab's name or acronym inside a raw affiliation string."""
    return re.compile("|".join(rf"\b{re.escape(a)}\b" for a in lab["aliases"]), re.I)


def authorship_lab_method(a: dict, lab_id: str, rx: re.Pattern) -> str | None:
    """'lineage' if OpenAlex resolved an institution under the lab, 'raw_string' if only the text names it."""
    for inst in a.get("institutions") or []:
        if lab_id == short_id(inst.get("id")) or lab_id in [short_id(x) for x in inst.get("lineage") or []]:
            return "lineage"
    if any(rx.search(s or "") for s in a.get("raw_affiliation_strings") or []):
        return "raw_string"
    return None


def faculty_links(w: dict, fac_by_author: dict, labs: dict) -> list[dict]:
    """One link per faculty member whose own authorship on this paper carries their lab (D4)."""
    best: dict[str, dict] = {}
    for a in w.get("authorships") or []:
        aid = short_id((a.get("author") or {}).get("id"))
        if aid not in fac_by_author:
            continue
        fid, lab = fac_by_author[aid]
        method = authorship_lab_method(a, labs[lab]["id"], labs[lab]["rx"])
        if method and (fid not in best or (best[fid]["affil_method"] == "raw_string" and method == "lineage")):
            best[fid] = {"faculty_id": fid, "institution": lab, "affil_method": method}
    return list(best.values())


def profile_year_links(w: dict, fac_by_author: dict, years_at: dict) -> list[dict]:
    """Weaker link: the faculty member's authorship has no institution at all, but their own profile puts
    them at the lab in the paper's year. Only offered when work_filter.link_by_profile_years is on."""
    best: dict[str, dict] = {}
    for a in w.get("authorships") or []:
        aid = short_id((a.get("author") or {}).get("id"))
        if aid not in fac_by_author or a.get("institutions"):
            continue
        fid, lab = fac_by_author[aid]
        if w.get("publication_year") in years_at.get((lab, aid), ()):
            best.setdefault(fid, {"faculty_id": fid, "institution": lab, "affil_method": "profile_years"})
    return list(best.values())


def dedupe_key(m: dict) -> str:
    doi = (m.get("doi") or "").lower().replace("https://doi.org/", "").strip()
    if doi:
        return "doi:" + doi
    t = norm(m.get("title") or "")
    return f"title:{t}|{m.get('year')}" if len(t) >= 25 else "id:" + m["work_id"]


def resolve_duplicates(meta: dict[str, dict]) -> dict[str, str]:
    """loser work_id -> winner work_id. Prefer a record that has a faculty link, then more citations,
    then the earlier date; so a duplicate never removes a paper that has a lab link."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for m in meta.values():
        groups[dedupe_key(m)].append(m)
    out = {}
    for g in groups.values():
        if len(g) < 2:
            continue
        pool = [m for m in g if m["dataset"]] or g
        win = sorted(pool, key=lambda m: (-m["cited"], m["pub_date"] or "9999", m["work_id"]))[0]
        out.update({m["work_id"]: win["work_id"] for m in g if m is not win})
    return out


# --------------------------------------------------------------------------- flattening

def work_row(w: dict, kind: str, wid: str) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    pt = w.get("primary_topic") or {}
    return {
        "work_id": wid, "doi": w.get("doi"), "title": " ".join((w.get("title") or "").split()),
        "year": w.get("publication_year"), "pub_date": w.get("publication_date"), "work_type": w.get("type"),
        "kind": kind, "source_id": short_id(src.get("id")), "source_name": src.get("display_name"),
        "source_type": src.get("type"), "issn_l": src.get("issn_l"), "issns": list(src.get("issn") or []),
        "cited_by_count": w.get("cited_by_count") or 0, "n_authors": len(w.get("authorships") or []),
        "topic_id": short_id(pt.get("id")), "topic": pt.get("display_name"),
        "subfield_id": short_id((pt.get("subfield") or {}).get("id")), "subfield": (pt.get("subfield") or {}).get("display_name"),
        "field": (pt.get("field") or {}).get("display_name"), "domain": (pt.get("domain") or {}).get("display_name"),
        "referenced_works": [short_id(r) for r in w.get("referenced_works") or []],
    }


def check_integrity(cfg, works, authorships, links) -> None:
    """Acceptance checks; a failure here means the tables must not be used."""
    problems = []
    if works["work_id"].duplicated().any():
        problems.append("duplicate work_id in works")
    doi = works["doi"].dropna().str.lower()
    if doi.duplicated().any():
        problems.append(f"{int(doi.duplicated().sum())} duplicate DOIs in works")
    if not works["year"].between(cfg.window.start, cfg.window.end).all():
        problems.append("works outside the year window")
    if not works["kind"].isin(["journal", "conference"]).all():
        problems.append("kind is not journal/conference")
    ids = set(works["work_id"])
    if not set(links["work_id"]) <= ids or not set(authorships["work_id"]) <= ids:
        problems.append("faculty_papers or authorships reference a work not in works")
    if set(works["work_id"]) - set(links["work_id"]):
        problems.append("a dataset work has no faculty link")
    if links.duplicated(["work_id", "faculty_id"]).any():
        problems.append("duplicate (work, faculty) link")
    if problems:
        raise StepFailed("S05 integrity check failed: " + "; ".join(problems))


def uncovered_authors(cfg, labs: dict, kept_ids: set, dataset_ids: set, mapped: set, s02, top: int = 60) -> pd.DataFrame:
    """Authors with lab-affiliated authorships on type-filtered lab papers that have no matched faculty member.

    Ranked by how often they are last or corresponding author (the PI position). These are the people most
    likely missing from the roster (scientists who left, retired, or are not on the website list).
    """
    stats: dict[tuple, dict] = {}
    for lab, info in labs.items():
        for w in read_jsonl(raw_dir(cfg) / f"lab_{lab}.jsonl.gz"):
            wid = short_id(w["id"])
            if wid not in kept_ids or wid in dataset_ids:
                continue
            auths = w.get("authorships") or []
            for i, a in enumerate(auths):
                aid = short_id((a.get("author") or {}).get("id"))
                if not aid or aid in mapped or authorship_lab_method(a, info["id"], info["rx"]) != "lineage":
                    continue
                s = stats.setdefault((lab, aid), {"name": a["author"].get("display_name"), "papers": 0, "last_or_corr": 0,
                                                  "first": 0, "years": set()})
                s["papers"] += 1
                s["last_or_corr"] += int(i == len(auths) - 1 or bool(a.get("is_corresponding")))
                s["first"] += int(i == 0)
                s["years"].add(w.get("publication_year"))
    rows = [{"lab": lab, "author_id": aid, "name": s["name"], "uncovered_papers": s["papers"],
             "last_or_corresponding": s["last_or_corr"], "first_author": s["first"],
             "first_year": min(s["years"]), "last_year": max(s["years"])} for (lab, aid), s in stats.items()]
    df = pd.DataFrame(rows, columns=["lab", "author_id", "name", "uncovered_papers", "last_or_corresponding",
                                     "first_author", "first_year", "last_year"])
    prof = s02[["lab", "author_id", "orcid", "works_count", "at_lab_now", "suspect_merged"]]
    df = df.merge(prof, on=["lab", "author_id"], how="left")
    df = (df.sort_values(["lab", "last_or_corresponding", "uncovered_papers"], ascending=[True, False, False])
            .groupby("lab").head(top).reset_index(drop=True))
    for c in ("add", "status", "note"):
        df[c] = ""
    return df


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    raw = raw_dir(cfg)
    map_path = cfg.paths.interim / "faculty_author_map.parquet"
    for p in (map_path, raw / "faculty.jsonl.gz"):
        if not p.exists():
            raise StepFailed(f"{cfg.rel(p)} missing - run s03 and s04 first")
    fam = pd.read_parquet(map_path)
    fac_by_author = {r.author_id: (r.faculty_id, r.institution) for r in fam.itertuples()}
    labs = {l["short"]: {"id": l["openalex_id"], "rx": alias_regex(l)} for l in cfg.labs}
    include_types = set(cfg.work_filter.include_work_types)
    y0, y1 = cfg.window.start, cfg.window.end
    reg = InstitutionRegistry(cfg)
    s02 = pd.read_parquet(cfg.paths.interim / "author_candidates.parquet")
    years_at = {(r.lab, r.author_id): set(r.years_at_lab) for r in s02.itertuples()}
    use_profile_years = bool(getattr(cfg.work_filter, "link_by_profile_years", False))
    recoverable: set[str] = set()              # papers the profile-years rule would add (reported either way)

    meta: dict[str, dict] = {}                 # kept (type-ok) works, small records
    work_rows: dict[str, dict] = {}            # dataset works
    auth_rows: dict[str, list] = {}
    link_rows: dict[str, list] = {}
    seen: set[str] = set()
    drops: Counter = Counter()
    faculty_no_link = 0                        # faculty-collection papers with no lab-affiliated authorship by them

    def handle(w: dict, lab: str | None, from_faculty: bool) -> None:
        nonlocal faculty_no_link
        wid = short_id(w["id"])
        if wid in seen:
            m = meta.get(wid)
            if m:
                m["in_lab"] |= {lab} if lab else set()
                m["in_fac"] |= from_faculty
            return
        seen.add(wid)
        if not y0 <= (w.get("publication_year") or 0) <= y1:
            drops["year outside window"] += 1
            return
        kind, reason = classify_work(w, include_types)
        if reason:
            drops[reason] += 1
            return
        links = faculty_links(w, fac_by_author, labs)
        if not links:
            weak = profile_year_links(w, fac_by_author, years_at)
            if weak:
                recoverable.add(wid)
                if use_profile_years:
                    links = weak
        m = {"work_id": wid, "doi": w.get("doi"), "title": w.get("title"), "year": w.get("publication_year"),
             "pub_date": w.get("publication_date"), "cited": w.get("cited_by_count") or 0, "kind": kind,
             "source_name": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
             "in_lab": {lab} if lab else set(), "in_fac": from_faculty, "dataset": bool(links)}
        meta[wid] = m
        if not links:
            faculty_no_link += from_faculty and lab is None
            return
        row = work_row(w, kind, wid)
        row["truncated_fixed"] = len(w.get("authorships") or []) > 100
        work_rows[wid] = row
        link_rows[wid] = links
        rows = []
        lab_of_link = {l["faculty_id"]: l["institution"] for l in links}
        for i, a in enumerate(w.get("authorships") or []):
            au = a.get("author") or {}
            aid = short_id(au.get("id"))
            insts = [reg.add(x) for x in a.get("institutions") or []]
            insts = [x for x in insts if x]
            fid = fac_by_author.get(aid, (None, None))[0]
            our = next((reg.our_lab(x) for x in insts if reg.our_lab(x)), None) or lab_of_link.get(fid)
            rows.append({"work_id": wid, "position_idx": i, "author_id": aid, "author_name": au.get("display_name"),
                         "raw_author_name": a.get("raw_author_name"), "inst_ids": insts,
                         "country_codes": list(a.get("countries") or []),
                         "raw_affiliations": list(a.get("raw_affiliation_strings") or []),
                         "is_corresponding": bool(a.get("is_corresponding")), "faculty_id": fid, "our_lab": our})
        auth_rows[wid] = rows

    for lab in labs:
        for w in read_jsonl(raw / f"lab_{lab}.jsonl.gz"):
            handle(w, lab, False)
    n_lab_unique = len(seen)
    for w in read_jsonl(raw / "faculty.jsonl.gz"):
        handle(w, None, True)

    # ---- duplicates: a paper with a lab link must survive, with every link
    loser_to_winner = resolve_duplicates(meta)
    for loser, winner in loser_to_winner.items():
        if loser in link_rows:   # the winner is always a dataset work when any member of the group is
            have = {l["faculty_id"] for l in link_rows[winner]}
            link_rows[winner] += [l for l in link_rows[loser] if l["faculty_id"] not in have]
        meta[winner]["in_lab"] |= meta[loser]["in_lab"]
        meta[winner]["in_fac"] |= meta[loser]["in_fac"]
    drop_ids = set(loser_to_winner)
    final = [wid for wid in work_rows if wid not in drop_ids]
    for wid in drop_ids:
        meta.pop(wid, None)

    # ---- tables
    works = pd.DataFrame([{**work_rows[w], "in_faculty_corpus": meta[w]["in_fac"],
                           "in_lab_corpus": bool(meta[w]["in_lab"]), "lab_corpora": sorted(meta[w]["in_lab"])}
                          for w in final])
    authorships = pd.DataFrame([r for w in final for r in auth_rows[w]])
    links = pd.DataFrame([{"work_id": w, **l} for w in final for l in link_rows[w]])
    links = links.drop_duplicates(["work_id", "faculty_id"])
    keep_ids = set(final)
    lab_kept = pd.DataFrame([{"work_id": w, "lab": lab, "year": m["year"], "pub_date": m["pub_date"],
                              "source_name": m["source_name"], "in_dataset": w in keep_ids}
                             for w, m in meta.items() for lab in sorted(m["in_lab"])])
    institutions = reg.to_frame()

    check_integrity(cfg, works, authorships, links)
    unc = uncovered_authors(cfg, labs, set(meta), keep_ids, set(fac_by_author), s02)
    unc_path = cfg.paths.review / "uncovered_lab_authors.csv"
    unc_path.parent.mkdir(parents=True, exist_ok=True)
    unc.to_csv(unc_path, index=False, encoding="utf-8", lineterminator="\n")

    out = cfg.paths.interim
    works.to_parquet(out / "works.parquet", index=False)
    authorships.to_parquet(out / "authorships.parquet", index=False)
    links.to_parquet(out / "faculty_papers.parquet", index=False)
    institutions.to_parquet(out / "institutions.parquet", index=False)
    lab_kept.to_parquet(out / "lab_corpus_kept.parquet", index=False)

    summary = report(cfg, works, links, lab_kept, fam, drops, faculty_no_link, len(drop_ids), n_lab_unique,
                     institutions, authorships)
    summary["profile_years_rule"] = {"enabled": use_profile_years, "papers_it_would_add": len(recoverable - keep_ids)
                                     if not use_profile_years else 0, "papers_added": int(
                                         (links["affil_method"] == "profile_years").sum()) if use_profile_years else 0}
    state = "ON" if use_profile_years else f"off (would add about {len(recoverable)} papers; set work_filter.link_by_profile_years)"
    print(f"Profile-years rule (faculty authorship has no institution, profile says they were at the lab): {state}")
    print(f"Uncovered-author list for roster review: {cfg.rel(unc_path)} "
          f"({len(unc)} rows; fill `add` and `status`, then `python -m dpcn run s01 --add-uncovered`)")
    summary["run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out / "s05_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    log.info("Wrote works/authorships/faculty_papers/institutions/lab_corpus_kept to %s", cfg.rel(out))


def report(cfg, works, links, lab_kept, fam, drops, faculty_no_link, n_dupes, n_lab_unique, institutions, authorships):
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)
    years = list(range(cfg.window.start, cfg.window.end + 1))
    print(f"\nDropped by the inclusion rules (unique works): total {sum(drops.values())}")
    for k, v in drops.most_common(8):
        print(f"   {v:>6}  {k}")

    per = links.merge(works[["work_id", "year"]], on="work_id").drop_duplicates(["work_id", "institution"])
    tab = per.pivot_table(index="institution", columns="year", values="work_id", aggfunc="count", fill_value=0)
    tab = tab.reindex(columns=years, fill_value=0)
    print(f"\nDataset papers per lab and year ({cfg.window.partial_year} is partial)")
    print(tab.to_string())
    print(f"\nUnique dataset papers: {len(works)}   faculty-paper rows: {len(links)}   "
          f"authorship rows: {len(authorships)}   institutions seen: {len(institutions)}   duplicates merged: {n_dupes}")
    order = {"lineage": 0, "raw_string": 1, "profile_years": 2}
    strongest = links.assign(r=links["affil_method"].map(order)).groupby("work_id")["r"].min().map(
        {v: k for k, v in order.items()}).value_counts().to_dict()
    print(f"Kinds: {works['kind'].value_counts().to_dict()}   papers by strongest lab link: {strongest}")
    print(f"Faculty-collection papers with no lab-affiliated authorship by the faculty member (other affiliation, "
          f"e.g. before joining): {faculty_no_link}")

    cov = []
    for lab in cfg.lab_by_short:
        k = lab_kept[lab_kept["lab"] == lab]
        n = len(k)
        cov.append({"lab": lab, "lab_corpus_kept": n, "in_dataset": int(k["in_dataset"].sum()),
                    "coverage_%": round(100 * k["in_dataset"].mean(), 1) if n else 0.0})
    print("\nCoverage: share of the lab's type-filtered papers that have a matched faculty member")
    print(pd.DataFrame(cov).set_index("lab").to_string())

    fac_summary = {}
    for lab in cfg.lab_by_short:
        ids = roster.loc[roster["institution"] == lab, "faculty_id"]
        got = set(links.loc[links["institution"] == lab, "faculty_id"])
        missing = roster[roster["faculty_id"].isin(set(ids) - got)]
        fac_summary[lab] = {"faculty": len(ids), "with_papers": len(got & set(ids))}
        print(f"{lab}: {len(got & set(ids))} of {len(ids)} faculty have at least one dataset paper; "
              f"{len(missing)} have none (of which {len(set(missing['faculty_id']) - set(fam['faculty_id']))} unmatched in S03)")

    # IMTECH 2026 diagnostics (open item from S00)
    k = lab_kept[lab_kept["lab"] == "CSIR-IMTECH"]
    if len(k):
        print("\nIMTECH type-filtered lab papers by year: " + " ".join(f"{y}:{(k['year'] == y).sum()}" for y in years))
        k26 = k[k["year"] == 2026]
        months = k26["pub_date"].dropna().str[:7].value_counts().sort_index()
        print("IMTECH 2026 by publication month: " + ", ".join(f"{m}:{c}" for m, c in months.items()))
        for y in (2025, 2026):
            ky = k[k["year"] == y]
            top = ky["source_name"].value_counts().head(4)
            print(f"IMTECH {y} top journals: " + "; ".join(f"{s} ({c})" for s, c in top.items()) +
                  f" | in dataset: {ky['in_dataset'].mean():.0%}")
    return {"dataset_papers": len(works), "faculty_paper_rows": len(links), "drops": dict(drops),
            "duplicates_merged": n_dupes, "faculty_collection_no_lab_link": int(faculty_no_link),
            "coverage": cov, "faculty": fac_summary}
