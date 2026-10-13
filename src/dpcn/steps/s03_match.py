"""S03: match roster faculty to OpenAlex author IDs (guide §7 S03; plan D2, D4).

Evidence, strongest first:
  orcid   roster ORCID == author ORCID (decisive)
  doi     the person's own profile page lists a paper; the author on it whose name fits is them
  auto    name match against authors who have lab-affiliated papers in the window, accepted only when
          unambiguous (no merged profile, no initials-only name, no clash between different people)
  manual  a human decision in data/review/faculty_match_review.csv or data/manual/faculty_match_overrides.csv

Anything else goes to the review sheet. Re-running keeps every accept/reject already written there.

    python -m dpcn run s03             # match, write review sheet
    python -m dpcn run s03 --no-titles # skip the sample-title lookups (saves ~0.03 USD)
"""
from __future__ import annotations

import argparse
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import pandas as pd

from ..corpus import build_author_pool
from ..names import initials_compatible, name_score, weak_name_match
from ..openalex import batches, short_id
from . import StepFailed
from .s02_candidates import SELECT as AUTHOR_SELECT, candidate_row

log = logging.getLogger("dpcn.s03")

REVIEW_COLS = ["faculty_id", "name", "institution", "person_status", "cand_author_id", "cand_name", "score", "reason",
               "n_lab_works_window", "works_count", "years_at_lab_window", "at_lab_now", "suspect_merged",
               "orcid", "accepted_ids", "sample_titles", "decision"]
MAP_COLS = ["faculty_id", "name", "institution", "author_id", "cand_name", "method", "score",
            "n_lab_works_window", "works_count", "evidence"]
DOMINANT_MIN = 10     # lab papers the leading same-name profile needs ...
DOMINANT_RATIO = 5    # ... and its lead over the next different person
METHOD_RANK = {"orcid": 0, "manual": 1, "doi": 2, "auto": 3}


@dataclass
class Cand:
    author_id: str
    name: str
    alternatives: list = field(default_factory=list)
    orcid: str = ""
    works_count: int = 0
    n_lab_works: int = 0           # qualifying papers carrying this lab's affiliation, 2016-2026
    years_at_lab_window: int = 0   # affiliation years from the author profile
    at_lab_now: bool = False
    suspect_merged: bool = False

    @property
    def names(self) -> list[str]:
        """Names to match against. Alternatives of a merged profile are unreliable, so ignored."""
        return [self.name] + ([] if self.suspect_merged else list(self.alternatives))

    def compatible(self, roster_name: str) -> bool:
        return any(initials_compatible(roster_name, n) for n in self.names)


@dataclass
class Decision:
    accepted: dict = field(default_factory=dict)   # author_id -> {"method", "score", "evidence"}
    review: list = field(default_factory=list)     # {"cand", "score", "reason"}


def _components(cands: list[Cand]) -> list[list[Cand]]:
    """Group candidates whose names could be the same person (split profiles)."""
    comps: list[list[Cand]] = []
    for c in cands:
        hits = [g for g in comps if any(initials_compatible(c.name, o.name) for o in g)]
        merged = [c] + [o for g in hits for o in g]
        comps = [g for g in comps if not any(g is h for h in hits)] + [merged]
    return comps


def decide(name: str, cands: list[Cand], orcid_ids=(), doi_ids=None, auto_score: float = 92,
           review_min: float = 70, max_review: int = 5) -> Decision:
    """Pure decision logic for one roster person. `cands` must include every orcid/doi author."""
    doi_ids = doi_ids or {}
    by_id = {c.author_id: c for c in cands}
    d = Decision()
    wrong_orcid = []
    for aid in orcid_ids:
        c = by_id.get(aid)
        if c is not None and name_score(name, c.names) < review_min:
            wrong_orcid.append(c)         # web pages sometimes carry someone else's ORCID
            continue
        d.accepted[aid] = {"method": "orcid", "score": 100.0, "evidence": "roster ORCID matches"}
    for aid, n in doi_ids.items():
        d.accepted.setdefault(aid, {"method": "doi", "score": 100.0,
                                    "evidence": f"author on {n} paper(s) listed on the person's profile page"})
    anchors = [by_id[a] for a in d.accepted if a in by_id]

    eligible, blocked = [], []     # blocked: (score, cand, reason)
    for c in cands:
        if c.author_id in d.accepted:
            continue
        s = name_score(name, c.names)
        if s < review_min or (c.n_lab_works == 0 and c.years_at_lab_window == 0):
            continue                                      # no name fit, or no tie to this lab at all
        if not initials_compatible(name, c.name):
            # alternates of unflagged profiles can still be a merge of several people (Sachin/Sanjay Kumar)
            blocked.append((s, c, "matches only an alternate name" if c.compatible(name) else "names not compatible"))
        elif c.suspect_merged:
            blocked.append((s, c, "merged profile (many affiliations/works)"))
        elif weak_name_match(name, c.name):
            blocked.append((s, c, "initials-only name"))
        elif c.n_lab_works == 0:
            blocked.append((s, c, "no lab-affiliated papers in 2016-2026"))
        elif s < auto_score:
            blocked.append((s, c, "score below auto threshold"))
        else:
            eligible.append((s, c))

    if anchors:   # evidence-based IDs exist: only same-person-compatible profiles may join them
        joins = [any(initials_compatible(c.name, a.name) for a in anchors) for _, c in eligible]
        keep = [sc for sc, ok in zip(eligible, joins) if ok]
        blocked += [(s, c, "clashes with evidence-matched profile") for (s, c), ok in zip(eligible, joins) if not ok]
    else:
        comps = _components([c for _, c in eligible])
        keep, note = eligible, ""
        if len(comps) > 1:
            comps.sort(key=lambda g: -max(c.n_lab_works for c in g))
            lead, rest = max(c.n_lab_works for c in comps[0]), max(c.n_lab_works for c in comps[1])
            if lead >= DOMINANT_MIN and lead >= DOMINANT_RATIO * rest:   # a faculty member out-publishes a namesake
                lead_ids = {c.author_id for c in comps[0]}
                keep = [(s, c) for s, c in eligible if c.author_id in lead_ids]
                note = f"; dominant: {lead} lab papers vs at most {rest} for other same-name profiles"
                blocked += [(s, c, "minor same-name profile (a dominant one was accepted)")
                            for s, c in eligible if c.author_id not in lead_ids]
            else:
                keep = []
                blocked += [(s, c, "ambiguous: several different people match") for s, c in eligible]
    for s, c in keep:
        d.accepted[c.author_id] = {"method": "auto", "score": round(s, 1),
                                   "evidence": f"{c.n_lab_works} lab papers; name score {s:.0f}" +
                                   (note if not anchors else "")}

    blocked += [(name_score(name, c.names), c, "ORCID on the web page belongs to a differently named author")
                for c in wrong_orcid]
    blocked.sort(key=lambda t: (-t[0], -t[1].n_lab_works))
    if d.accepted:
        blocked = [t for t in blocked if t[0] >= auto_score]
    d.review = [{"cand": c, "score": s, "reason": r} for s, c, r in blocked[:max_review]]
    return d


# --------------------------------------------------------------------------- evidence gathering

def profile_evidence(oa, roster: pd.DataFrame) -> dict[str, Counter]:
    """faculty_id -> Counter(author_id -> n papers) from DOIs/PMIDs listed on the person's own profile page."""
    by_doi, by_pmid = defaultdict(list), defaultdict(list)
    skipped = 0
    for _, r in roster.iterrows():
        for d in filter(None, r["profile_dois"].split(";")):
            if any(ch in d for ch in ",|"):
                skipped += 1                      # would break OpenAlex's filter syntax
            else:
                by_doi[d.lower()].append(r["faculty_id"])
        for p in filter(None, r["profile_pmids"].split(";")):
            by_pmid[p].append(r["faculty_id"])
    works_doi, works_pmid = {}, {}
    for b in batches(sorted(by_doi), 50):
        flt = "doi:" + "|".join(f"https://doi.org/{d}" for d in b)
        for w in oa.paginate("works", flt, select="id,doi,authorships", per_page=200):
            works_doi[(w.get("doi") or "").replace("https://doi.org/", "").lower()] = w
    for b in batches(sorted(by_pmid), 50):
        for w in oa.paginate("works", "pmid:" + "|".join(b), select="id,ids,authorships", per_page=200):
            works_pmid[(w.get("ids") or {}).get("pmid", "").rsplit("/", 1)[-1]] = w
    log.info("profile papers: %d DOIs (%d found in OpenAlex, %d skipped), %d PMIDs (%d found)",
             len(by_doi), len(works_doi), skipped, len(by_pmid), len(works_pmid))

    names = dict(zip(roster["faculty_id"], roster["name"]))
    ev: dict[str, Counter] = defaultdict(Counter)
    seen: set[tuple[str, str]] = set()
    for source, wmap in ((by_doi, works_doi), (by_pmid, works_pmid)):
        for key, fids in source.items():
            w = wmap.get(key)
            if not w:
                continue
            for fid in fids:
                if (fid, w["id"]) in seen:
                    continue
                seen.add((fid, w["id"]))
                hits = [a for a in w.get("authorships") or []
                        if (a.get("author") or {}).get("id")
                        and initials_compatible(names[fid], a["author"].get("display_name") or "")]
                if len(hits) == 1:   # two same-initials authors on one paper: no evidence either way
                    ev[fid][short_id(hits[0]["author"]["id"])] += 1
    return ev


def fetch_authors(oa, ids: list[str]) -> dict[str, dict]:
    out = {}
    for b in batches(sorted(set(ids)), 100):
        for a in oa.paginate("authors", "openalex:" + "|".join(b), select=AUTHOR_SELECT, per_page=200):
            out[short_id(a["id"])] = a
    return out


def fetch_by_orcid(oa, orcids: list[str]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for b in batches(sorted(set(orcids)), 50):
        for a in oa.paginate("authors", "orcid:" + "|".join(f"https://orcid.org/{o}" for o in b),
                             select=AUTHOR_SELECT, per_page=200):
            out[(a.get("orcid") or "").rsplit("/", 1)[-1]].append(a)
    return out


def sample_titles(oa, author_id: str) -> str:
    d = oa.get("works", filter=f"authorships.author.id:{author_id}", sort="publication_year:desc",
               per_page=3, select="title,publication_year")
    return " | ".join(f"{(w.get('title') or '')[:70]} ({w.get('publication_year')})" for w in d["results"])


# --------------------------------------------------------------------------- run

def _read_decisions(cfg) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for path in (cfg.paths.review / "faculty_match_review.csv", cfg.paths.manual / "faculty_match_overrides.csv"):
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        col = "cand_author_id" if "cand_author_id" in df else "author_id"
        for _, r in df.iterrows():
            dec = r.get("decision", "").strip().lower()
            if dec in ("accept", "reject") and r[col]:
                out[(r["faculty_id"], short_id(r[col]))] = dec
    return out


def _cand(rec: dict | None, aid: str, lab: dict, cfg, n_lab_works: int, fallback_name: str = "") -> Cand:
    if rec is None:
        return Cand(aid, fallback_name, n_lab_works=n_lab_works)
    r = candidate_row(rec, lab, cfg.window.start, cfg.window.end)
    return Cand(aid, r["display_name"], r["alternatives"], r["orcid"], r["works_count"], n_lab_works,
                r["n_years_at_lab_window"], r["at_lab_now"], r["suspect_merged"])


def run(cfg, oa, argv=()) -> None:
    ap = argparse.ArgumentParser(prog="dpcn run s03")
    ap.add_argument("--no-titles", action="store_true", help="skip sample-title lookups for review rows")
    args = ap.parse_args(list(argv))

    for p in (cfg.paths.manual / "faculty_roster.csv", cfg.paths.interim / "author_candidates.parquet"):
        if not p.exists():
            raise StepFailed(f"{cfg.rel(p)} missing - run s01 and s02 first")
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)
    s02 = pd.read_parquet(cfg.paths.interim / "author_candidates.parquet")
    decisions = _read_decisions(cfg)
    m = cfg.matching

    # 1. who publishes under each lab's name (shared with S04 through the request cache)
    pools = {}
    for lab in cfg.labs:
        pool, n_works = build_author_pool(cfg, oa, lab)
        pools[lab["short"]] = pool
        log.info("%s: %d lab works, %d authors with lab-affiliated papers", lab["short"], n_works, len(pool))
    corpus = pd.concat(pools.values(), ignore_index=True)
    corpus.to_parquet(cfg.paths.interim / "lab_author_pool.parquet", index=False)
    lab_works = {(r.lab, r.author_id): r.n_lab_works_window for r in corpus.itertuples()}
    s02_by = {(r.lab, r.author_id): r for r in s02.itertuples()}

    # 2. evidence: ORCID, profile-page papers, earlier human decisions
    ev_doi = profile_evidence(oa, roster)
    orcid_authors = fetch_by_orcid(oa, [o for o in roster["orcid"] if o])
    manual_accept = defaultdict(list)
    for (fid, aid), dec in decisions.items():
        if dec == "accept":
            manual_accept[fid].append(aid)

    # 3. candidate list per person (prefilter by display name, then enrich the ones we keep)
    person_ids: dict[str, set[str]] = {}
    need_details: set[str] = set()
    for r in roster.itertuples():
        pool = pools[r.institution]
        ids = set(pool.loc[pool["name"].map(lambda n: name_score(r.name, [n])) >= m.review_min_score, "author_id"])
        ids |= set(s02.loc[(s02.lab == r.institution) &
                           s02["display_name"].map(lambda n: name_score(r.name, [n])) >= m.review_min_score, "author_id"])
        ids |= {short_id(a["id"]) for a in orcid_authors.get(r.orcid, [])} if r.orcid else set()
        ids |= set(ev_doi.get(r.faculty_id, {}))
        ids |= set(manual_accept.get(r.faculty_id, []))
        person_ids[r.faculty_id] = ids
        need_details |= {i for i in ids if (r.institution, i) not in s02_by}
    details = fetch_authors(oa, list(need_details))
    log.info("fetched details for %d authors outside the S02 pool", len(details))

    def build(lab_short: str, aid: str) -> Cand | None:
        lab = cfg.lab_by_short[lab_short]
        n = int(lab_works.get((lab_short, aid), 0))
        if (lab_short, aid) in s02_by:
            x = s02_by[(lab_short, aid)]
            return Cand(aid, x.display_name, list(x.alternatives), x.orcid, int(x.works_count), n,
                        int(x.n_years_at_lab_window), bool(x.at_lab_now), bool(x.suspect_merged))
        if aid in details:
            return _cand(details[aid], aid, lab, cfg, n)
        return None

    # 4. decide
    results: dict[str, Decision] = {}
    cand_of: dict[tuple[str, str], Cand] = {}
    for r in roster.itertuples():
        cands = [c for c in (build(r.institution, i) for i in person_ids[r.faculty_id]) if c]
        for c in cands:
            cand_of[(r.faculty_id, c.author_id)] = c
        orcid_ids = [short_id(a["id"]) for a in orcid_authors.get(r.orcid, [])] if r.orcid else []
        results[r.faculty_id] = decide(r.name, cands, orcid_ids, dict(ev_doi.get(r.faculty_id, {})),
                                       m.auto_accept_score, m.review_min_score)

    # 5. one author must not belong to two people unless there is hard evidence for both
    claims = defaultdict(list)
    for fid, d in results.items():
        for aid, info in d.accepted.items():
            claims[aid].append(fid)
    name_of = dict(zip(roster["faculty_id"], roster["name"]))
    for aid, fids in claims.items():
        if len(fids) > 1:
            for fid in fids:
                if results[fid].accepted[aid]["method"] in ("auto", "doi") and (fid, aid) in cand_of:
                    info = results[fid].accepted.pop(aid)
                    others = ", ".join(f for f in fids if f != fid)
                    results[fid].review.append({"cand": cand_of[(fid, aid)], "score": info["score"],
                                                "reason": f"also claimed by {others}"})

    # 6. human decisions win
    for (fid, aid), dec in decisions.items():
        if fid not in results:
            continue
        if dec == "reject":
            results[fid].accepted.pop(aid, None)
        elif (fid, aid) in cand_of:
            results[fid].accepted[aid] = {"method": "manual", "score": 100.0, "evidence": "human decision"}
        else:
            log.warning("accept for %s / %s ignored: author not found in OpenAlex", fid, aid)

    # 7. write outputs
    roster_by = roster.set_index("faculty_id")
    map_rows, review_rows = [], []
    titles_cache: dict[str, str] = {}
    for fid, d in results.items():
        p = roster_by.loc[fid]
        for aid, info in d.accepted.items():
            c = cand_of.get((fid, aid))
            if c is None:
                log.warning("%s: author %s accepted but not found in OpenAlex; skipped", fid, aid)
                continue
            map_rows.append({"faculty_id": fid, "name": p["name"], "institution": p["institution"],
                             "author_id": aid, "cand_name": c.name, "method": info["method"], "score": info["score"],
                             "n_lab_works_window": c.n_lab_works, "works_count": c.works_count,
                             "evidence": info["evidence"]})
        shown = {x["cand"].author_id for x in d.review}
        rows = list(d.review)
        rows += [{"cand": cand_of[(fid, aid)], "score": name_score(p["name"], cand_of[(fid, aid)].names),
                  "reason": "human decision"}
                 for (f, aid), dec in decisions.items()
                 if f == fid and (fid, aid) in cand_of and aid not in shown]
        if not d.accepted and not rows:
            review_rows.append({"faculty_id": fid, "name": p["name"], "institution": p["institution"],
                                "person_status": "UNMATCHED", "reason": "no candidate found", "decision": ""})
        for x in rows:
            c = x["cand"]
            if not args.no_titles and c.author_id not in titles_cache:
                titles_cache[c.author_id] = sample_titles(oa, c.author_id)
            review_rows.append({
                "faculty_id": fid, "name": p["name"], "institution": p["institution"],
                "person_status": "matched" if d.accepted else "UNMATCHED", "cand_author_id": c.author_id, "cand_name": c.name, "score": round(x["score"], 1),
                "reason": x["reason"], "n_lab_works_window": c.n_lab_works, "works_count": c.works_count,
                "years_at_lab_window": c.years_at_lab_window, "at_lab_now": c.at_lab_now,
                "suspect_merged": c.suspect_merged, "orcid": c.orcid,
                "accepted_ids": ";".join(d.accepted), "sample_titles": titles_cache.get(c.author_id, ""),
                "decision": decisions.get((fid, c.author_id), "")})

    fam = pd.DataFrame(map_rows, columns=MAP_COLS)
    rev = pd.DataFrame(review_rows, columns=REVIEW_COLS).fillna("")
    # people who still need a decision first, strongest candidate first
    rev["_s"] = pd.to_numeric(rev["score"], errors="coerce").fillna(-1)
    rev = (rev.sort_values(["person_status", "institution", "faculty_id", "_s"], ascending=[False, True, True, False],
                           kind="stable").drop(columns="_s").reset_index(drop=True))
    cfg.paths.interim.mkdir(parents=True, exist_ok=True)
    cfg.paths.review.mkdir(parents=True, exist_ok=True)
    fam.to_parquet(cfg.paths.interim / "faculty_author_map.parquet", index=False)
    rev.to_csv(cfg.paths.review / "faculty_match_review.csv", index=False, encoding="utf-8", lineterminator="\n")

    # people on lab papers for years who are not on the roster: possible missing faculty
    matched_ids = set(zip(fam["institution"], fam["author_id"]))
    gaps = corpus.merge(s02[["lab", "author_id", "n_years_at_lab_window", "at_lab_now", "suspect_merged"]],
                        on=["lab", "author_id"], how="left")
    gaps = gaps[~gaps.apply(lambda r: (r["lab"], r["author_id"]) in matched_ids, axis=1)
                & (gaps["n_years_at_lab_window"].fillna(0) >= 6) & (gaps["n_lab_works_window"] >= 15)
                & ~gaps["suspect_merged"].fillna(False).astype(bool)]
    gaps = gaps.sort_values(["lab", "n_lab_works_window"], ascending=[True, False]).groupby("lab").head(100)
    gaps.to_csv(cfg.paths.review / "roster_gaps.csv", index=False, encoding="utf-8", lineterminator="\n")

    report(cfg, roster, fam, rev, gaps)


def report(cfg, roster, fam, rev, gaps) -> None:
    top = fam.assign(rank=fam["method"].map(METHOD_RANK)).sort_values("rank").drop_duplicates("faculty_id")
    status = roster.merge(top[["faculty_id", "method"]], on="faculty_id", how="left")
    status["method"] = status["method"].fillna("none")
    tab = status.pivot_table(index="institution", columns="method", values="faculty_id", aggfunc="count",
                             fill_value=0)
    for m in ("orcid", "manual", "doi", "auto", "none"):
        if m not in tab:
            tab[m] = 0
    tab = tab[["orcid", "manual", "doi", "auto", "none"]]
    tab.insert(0, "faculty", tab.sum(axis=1))
    tab["matched_%"] = (100 * (tab["faculty"] - tab["none"]) / tab["faculty"]).round(1)
    ids_per = fam.groupby("faculty_id").size()
    print("\nBest evidence per faculty member (columns: strongest method that matched them)")
    print(tab.to_string())
    print(f"\nFaculty with 2+ author IDs: {(ids_per > 1).sum()}   review rows: {len(rev)}   "
          f"possible roster gaps: {len(gaps)}")
    unmatched = status[status["method"] == "none"]
    print(f"Unmatched ({len(unmatched)}): " + ", ".join(f"{n} [{i.split('-')[0]}]" for n, i in
                                                         zip(unmatched["name"], unmatched["faculty_id"])))
    total = len(roster)
    pct = 100 * (total - len(unmatched)) / total
    log.info("matched %.1f%% of %d faculty (target >= 95%% after review)", pct, total)
    log.info("Review: data/review/faculty_match_review.csv (fill `decision` with accept/reject, re-run s03); "
             "gaps: data/review/roster_gaps.csv")
