"""S01: faculty roster (guide §7, S01; plan D2/A6).

Workflow:
    python -m dpcn run s01 --scrape all     # scrape lab websites -> data/review/roster_<lab>_scraped.csv
    (review the scraped files; set keep=TRUE/FALSE on REVIEW rows)
    python -m dpcn run s01 --merge          # add keep=TRUE rows to data/manual/faculty_roster.csv
    (edit faculty_roster.csv by hand: fix names, add former faculty, etc.)
    python -m dpcn run s01                  # validate the master roster -> data/interim/roster.parquet

    python -m dpcn run s01 --add-uncovered  # add scientists ticked in data/review/uncovered_lab_authors.csv (after s05)

--merge never deletes or overwrites existing roster rows; it only appends new people and fills
blank fields (orcid, department, profile evidence) on people already present.
"""
from __future__ import annotations

import argparse
import logging
import re
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from ..names import clean_name, norm
from ..web import WebFetcher
from . import StepFailed

log = logging.getLogger("dpcn.s01")

SCRAPED_COLS = ["institution", "name", "name_note", "designation", "department", "expertise",
                "profile_url", "orcid", "profile_dois", "profile_pmids", "keep", "source_url", "scraped_at"]
ROSTER_COLS = ["faculty_id", "name", "designation", "department", "institution", "profile_url", "orcid",
               "status", "source", "notes", "expertise", "profile_dois", "profile_pmids"]

_KEEP = re.compile(r"scientist|director|fellow|emeritus|professor|\bhead\b", re.I)
_DROP = re.compile(r"technical|technician|technology officer|administrat|business|manager|librar|"
                   r"project (associate|assistant)|section officer|controller|finance|purchase|store|"
                   r"secretary|steno|clerk|multi.?tasking", re.I)
_DOI = re.compile(r"10\.\d{4,9}/[^\s<>\"']+")
_ORCID = re.compile(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
_PMID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")


def keep_flag(designation: str) -> str:
    """Plan A6: scientists/PIs are faculty; technical/admin staff are not; unclear -> REVIEW."""
    d = designation or ""
    if not d.strip():
        return "REVIEW"
    if _DROP.search(d) and not re.search(r"scientist", d, re.I):
        return "FALSE"
    return "TRUE" if _KEEP.search(d) else "REVIEW"


def _dois(text: str) -> str:
    found = set()
    for m in _DOI.findall(text):
        m = re.sub(r"[^!-~].*$", "", m).rstrip(".,;:)]}").lower()   # cut mojibake tails like '.â'
        m = re.sub(r"\.s\d{3}$", "", m)                                    # supplementary-file suffix '.s001'
        found.add(m)
    return ";".join(sorted(found))


def _orcid(text: str) -> str:
    m = _ORCID.search(text)
    return m.group(1) if m else ""


def _pmids(text: str) -> str:
    return ";".join(sorted(set(_PMID.findall(text)), key=int))


def _txt(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def _row(lab, raw_name, scientist_list=False, **kw) -> dict:
    """`scientist_list=True` when the source page lists scientists only (blank designation => keep)."""
    name, note = clean_name(raw_name)
    row = {c: "" for c in SCRAPED_COLS}
    row.update(institution=lab["short"], name=name, name_note=note, scraped_at=date.today().isoformat(), **kw)
    row["keep"] = "TRUE" if scientist_list and not row["designation"].strip() else keep_flag(row["designation"])
    return row


def parse_igib_role(role) -> tuple[str, str]:
    """(designation, department) from IGIB's `p.profile-role`.

    Normal pages: 'Scientist-E | <a>Decision Unit 1: ...</a>'. The Director's page nests an <h3>, so the
    designation comes out as 'Director; Scientist-G'. Parse with html.parser, which doesn't auto-close <p>.
    """
    if role is None:
        return "", ""
    head = " ".join(role.get_text(" ", strip=True).split("|")[0].split())
    h3 = role.find("h3")
    if h3 and head.startswith(_txt(h3)) and head != _txt(h3):
        head = f"{_txt(h3)}; {head[len(_txt(h3)):].strip()}"
    du = role.select_one('a[href*="du-"]')
    return head, _txt(du)


# --------------------------------------------------------------------------- scrapers

def scrape_ccmb(web: WebFetcher, lab: dict) -> list[dict]:
    base = lab["website"].rstrip("/")
    list_url = f"{base}/dept_people/all-faculty"
    soup = BeautifulSoup(web.get(list_url), "lxml")
    rows = []
    for card in soup.select('a.custom-card[href*="people-details"]'):
        url = urljoin(base + "/", card["href"])
        card_desig = _txt(card.select_one(".card-text"))
        html = web.get(url)
        p = BeautifulSoup(html, "lxml")
        positions = [_txt(d) for d in p.select(".profile-position")]
        name = _txt(p.select_one(".profile-Name h3")) or _txt(card.select_one(".card-title"))
        rows.append(_row(lab, name, designation=positions[0] if positions else card_desig,
                         department=positions[1] if len(positions) > 1 else "",
                         profile_url=url, orcid=_orcid(html), profile_dois=_dois(html),
                         source_url=list_url))
    return rows


def scrape_igib(web: WebFetcher, lab: dict) -> list[dict]:
    base = lab["website"].rstrip("/")
    list_url = f"{base}/ScientistDirectory.html"
    html = web.get(list_url)
    people = re.findall(r"name:\s*'([^']+)'.*?url:\s*'([^']*)'.*?areas:\s*\[([^\]]*)\]", html, re.S)
    rows = []
    for raw_name, rel, areas in people:
        url = urljoin(list_url, rel)
        expertise = "; ".join(a.strip().strip("'\"") for a in areas.split(",") if a.strip())
        try:
            phtml = web.get(url)
        except Exception as e:   # broken profile link: keep the person, flag for review
            log.warning("IGIB profile failed for %s: %s", raw_name, e)
            rows.append(_row(lab, raw_name, True, expertise=expertise, profile_url=url, source_url=list_url))
            continue
        p = BeautifulSoup(phtml, "html.parser")
        designation, department = parse_igib_role(p.select_one("p.profile-role"))
        rows.append(_row(lab, _txt(p.select_one(".profile-name")) or raw_name, True,
                         designation=designation, department=department,
                         expertise=expertise, profile_url=url,
                         orcid=_orcid(phtml), profile_dois=_dois(phtml), profile_pmids=_pmids(phtml),
                         source_url=list_url))
    return rows


IMTECH_SCIENTISTS = ("/en/research-official-website-of-csir-institute-of-microbial-technology-"
                     "ministry-of-science-technology-government-of-india/scientists")


def scrape_imtech(web: WebFetcher, lab: dict) -> list[dict]:
    base = lab["website"].rstrip("/")
    list_url = base + IMTECH_SCIENTISTS     # the default (non-/en/) site serves Hindi
    soup = BeautifulSoup(web.get(list_url), "lxml")
    rows = []
    for card in soup.select("div.profile-card"):
        a = card.select_one("div.data a")
        if not a:
            continue
        url = a["href"]
        html = web.get(url)
        p = BeautifulSoup(html, "lxml")
        top = p.select_one(".top-profile")
        rows.append(_row(lab, _txt(top.select_one("h4")) if top else _txt(a),
                         designation=_txt(top.select_one("p")) if top else "",
                         expertise=_txt(card.select_one("div.buttons")), profile_url=url,
                         orcid=_orcid(html), profile_dois=_dois(html), source_url=list_url))
    return rows


def scrape_cdri(web: WebFetcher, lab: dict) -> list[dict]:
    base = lab["website"].rstrip("/")
    first = BeautifulSoup(web.get(f"{base}/ScientistDivisionWise?division=bsb"), "lxml")
    divisions = []
    for btn in first.select("input.div-btn"):
        m = re.search(r"ScientistDivisionWise\.aspx\?division=(\w+)", btn.get("onclick", ""))
        if m:
            divisions.append((m.group(1), " ".join(btn.get("value", "").split())))
        else:
            log.info("CDRI: skipping non-division tab %r", btn.get("value"))
    rows = []
    for code, div_name in divisions:
        url = f"{base}/ScientistDivisionWise?division={code}"
        soup = BeautifulSoup(web.get(url), "lxml")
        for card in soup.select("div.prodet-1"):
            # profile pages are ASP.NET postbacks with no URL, so the division page is the profile_url
            rows.append(_row(lab, _txt(card.select_one("h2")), designation=_txt(card.select_one("h5")),
                             department=div_name, profile_url=url, source_url=url))
    return rows


SCRAPERS = {"ccmb": ("CSIR-CCMB", scrape_ccmb), "igib": ("CSIR-IGIB", scrape_igib),
            "imtech": ("CSIR-IMTECH", scrape_imtech), "cdri": ("CSIR-CDRI", scrape_cdri)}


def _dedupe(rows: list[dict]) -> list[dict]:
    """One row per person per lab; a person listed in several divisions gets departments joined."""
    out: dict[str, dict] = {}
    for r in rows:
        k = norm(r["name"])
        if k in out:
            prev = out[k]
            if r["department"] and r["department"] not in prev["department"]:
                prev["department"] = "; ".join(x for x in (prev["department"], r["department"]) if x)
        else:
            out[k] = r
    return list(out.values())


def scrape(cfg, which: str, refresh: bool) -> None:
    web = WebFetcher(cfg.paths.cache / "web", refresh=refresh)
    keys = list(SCRAPERS) if which == "all" else [which]
    for key in keys:
        short, fn = SCRAPERS[key]
        if short not in cfg.lab_by_short:
            log.info("%s is not in config/institutions.yaml; skipping", short)
            continue
        rows = _dedupe(fn(web, cfg.lab_by_short[short]))
        if not rows:
            raise StepFailed(f"{short}: scraper found no people - the site layout may have changed")
        df = pd.DataFrame(rows, columns=SCRAPED_COLS)
        out = cfg.paths.review / f"roster_{key}_scraped.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False, encoding="utf-8", lineterminator="\n")
        counts = df["keep"].value_counts().to_dict()
        log.info("%s: %d people (keep=TRUE %d, REVIEW %d, FALSE %d), %d with ORCID, %d with DOIs -> %s",
                 short, len(df), counts.get("TRUE", 0), counts.get("REVIEW", 0), counts.get("FALSE", 0),
                 (df["orcid"] != "").sum(), (df["profile_dois"] != "").sum(), cfg.rel(out))
    log.info("web pages: %d fetched, %d from cache", web.live, web.cached)


# --------------------------------------------------------------------------- merge + validate

def _roster_path(cfg):
    return cfg.paths.manual / "faculty_roster.csv"


def _read_roster(cfg) -> pd.DataFrame:
    path = _roster_path(cfg)
    if not path.exists():
        return pd.DataFrame(columns=ROSTER_COLS)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in ROSTER_COLS:
        if c not in df:
            df[c] = ""
    return df


def _unique_map(s: pd.Series) -> dict:
    """value -> row index, for non-empty values that occur exactly once."""
    s = s[s != ""]
    return {v: i for i, v in s.items() if (s == v).sum() == 1}


def _prefix(short: str) -> str:
    return short.split("-", 1)[-1]


def merge(cfg) -> None:
    roster = _read_roster(cfg)
    added = filled = 0
    review_left = 0
    for key, (short, _) in SCRAPERS.items():
        f = cfg.paths.review / f"roster_{key}_scraped.csv"
        if short not in cfg.lab_by_short or not f.exists():
            continue
        sc = pd.read_csv(f, dtype=str, keep_default_na=False)
        review_left += (sc["keep"] == "REVIEW").sum()
        lab_rows = roster["institution"] == short
        existing = {norm(n): i for i, n in roster.loc[lab_rows, "name"].items()}
        by_orcid = _unique_map(roster.loc[lab_rows, "orcid"])
        by_url = _unique_map(roster.loc[lab_rows, "profile_url"])   # survives hand-corrected names
        scraped_urls = sc["profile_url"].value_counts()
        ids = roster.loc[lab_rows, "faculty_id"].str.extract(r"-(\d+)$")[0].dropna().astype(int)
        next_n = (ids.max() if len(ids) else 0) + 1
        for _, s in sc[sc["keep"] == "TRUE"].iterrows():
            i = by_orcid.get(s["orcid"]) if s["orcid"] else None
            if i is None and s["profile_url"] and scraped_urls[s["profile_url"]] == 1:   # not CDRI's shared division URL
                i = by_url.get(s["profile_url"])
            if i is None:
                i = existing.get(norm(s["name"]))
            if i is not None:   # already on the roster: only fill blanks
                for c in ("designation", "department", "profile_url", "orcid", "expertise",
                          "profile_dois", "profile_pmids"):
                    if not roster.at[i, c] and s[c]:
                        roster.at[i, c] = s[c]
                        filled += 1
                continue
            roster.loc[len(roster)] = {
                "faculty_id": f"{_prefix(short)}-{next_n:03d}", "name": s["name"],
                "designation": s["designation"], "department": s["department"], "institution": short,
                "profile_url": s["profile_url"], "orcid": s["orcid"], "status": "current",
                "source": "website", "notes": s["name_note"], "expertise": s["expertise"],
                "profile_dois": s["profile_dois"], "profile_pmids": s["profile_pmids"]}
            existing[norm(s["name"])] = len(roster) - 1
            next_n += 1
            added += 1
    roster = roster.sort_values(["institution", "faculty_id"], kind="stable")[ROSTER_COLS]
    path = _roster_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    roster.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    log.info("Merged into %s: %d added, %d blank fields filled, %d total rows",
             cfg.rel(path), added, filled, len(roster))
    if review_left:
        log.warning("%d scraped rows are still keep=REVIEW - decide TRUE/FALSE in data/review/roster_*_scraped.csv "
                    "and re-run --merge", review_left)


def add_uncovered(cfg) -> None:
    """Append people confirmed in data/review/uncovered_lab_authors.csv (S05) to the roster.

    A reviewer sets `add` to TRUE and `status` to current/former on the rows that are real scientists. Each is
    added to faculty_roster.csv and pre-accepted for its OpenAlex author in faculty_match_overrides.csv, so S03
    needs no further matching. Safe to repeat: authors already accepted are skipped.
    """
    src = cfg.paths.review / "uncovered_lab_authors.csv"
    if not src.exists():
        raise StepFailed(f"{cfg.rel(src)} not found - run s05 first")
    unc = pd.read_csv(src, dtype=str, keep_default_na=False)
    sel = unc[unc["add"].str.strip().str.upper().isin(["TRUE", "YES", "Y", "1"])]
    bad = sel[~sel["status"].str.strip().str.lower().isin(["current", "former"])]
    if len(bad):
        raise StepFailed("set status to 'current' or 'former' for: " + ", ".join(bad["name"] + " [" + bad["lab"] + "]"))

    roster = _read_roster(cfg)
    ov_path = cfg.paths.manual / "faculty_match_overrides.csv"
    ov = (pd.read_csv(ov_path, dtype=str, keep_default_na=False) if ov_path.exists()
          else pd.DataFrame(columns=["faculty_id", "author_id", "decision"]))
    accepted = set(ov.loc[ov["decision"] == "accept", "author_id"])
    added, skipped = [], []
    for _, r in sel.iterrows():
        short = r["lab"]
        if short not in cfg.lab_by_short:
            raise StepFailed(f"unknown lab {short!r} in {cfg.rel(src)}")
        name = " ".join(r["name"].split())
        in_lab = roster["institution"] == short
        if r["author_id"] in accepted:
            continue
        if norm(name) in set(roster.loc[in_lab, "name"].map(norm)):
            skipped.append(name)
            continue
        ids = roster.loc[in_lab, "faculty_id"].str.extract(r"-(\d+)$")[0].dropna().astype(int)
        fid = f"{_prefix(short)}-{(ids.max() if len(ids) else 0) + 1:03d}"
        roster.loc[len(roster)] = {
            "faculty_id": fid, "name": name, "designation": "", "department": "", "institution": short,
            "profile_url": "", "orcid": r.get("orcid", ""), "status": r["status"].strip().lower(),
            "source": "uncovered-author list (S05)", "notes": r.get("note", "") or f"OpenAlex {r['author_id']}",
            "expertise": "", "profile_dois": "", "profile_pmids": ""}
        ov.loc[len(ov)] = {"faculty_id": fid, "author_id": r["author_id"], "decision": "accept"}
        accepted.add(r["author_id"])
        added.append(f"{fid} {name}")
    roster = roster.sort_values(["institution", "faculty_id"], kind="stable")[ROSTER_COLS]
    roster.to_csv(_roster_path(cfg), index=False, encoding="utf-8", lineterminator="\n")
    ov_path.parent.mkdir(parents=True, exist_ok=True)
    ov.to_csv(ov_path, index=False, encoding="utf-8", lineterminator="\n")
    log.info("Added %d people to the roster%s", len(added), (": " + ", ".join(added)) if added else "")
    if skipped:
        log.warning("Not added (a person with this name is already on that lab's roster; fix their match in "
                    "faculty_match_review.csv instead): %s", ", ".join(skipped))
    if added:
        log.info("Next: python -m dpcn run s03, then s04 and s05 to include their papers")


def validate(cfg) -> pd.DataFrame:
    path = _roster_path(cfg)
    if not path.exists():
        raise StepFailed(f"{cfg.rel(path)} not found. Run `python -m dpcn run s01 --scrape all`, "
                         "review data/review/roster_*_scraped.csv, then `python -m dpcn run s01 --merge`.")
    df = _read_roster(cfg)
    errors = []
    if df["faculty_id"].duplicated().any():
        errors.append(f"duplicate faculty_id: {sorted(df.loc[df.faculty_id.duplicated(), 'faculty_id'])}")
    bad_id = ~df["faculty_id"].str.match(r"^[A-Z]+-\d{3}$")
    if bad_id.any():
        errors.append(f"faculty_id not like 'CCMB-001': {df.loc[bad_id, 'faculty_id'].tolist()}")
    bad_inst = ~df["institution"].isin(cfg.lab_by_short)
    if bad_inst.any():
        errors.append(f"unknown institution: {sorted(set(df.loc[bad_inst, 'institution']))}")
    if (df["name"].str.strip() == "").any():
        errors.append("rows with empty name")
    bad_status = ~df["status"].isin(["current", "former"])
    if bad_status.any():
        errors.append(f"status must be current/former: {df.loc[bad_status, 'faculty_id'].tolist()}")
    keyed = df.assign(_k=df["name"].map(norm))
    dup = keyed.duplicated(["institution", "_k"], keep=False)
    if dup.any():
        errors.append(f"same person twice in a lab: {keyed.loc[dup, ['faculty_id', 'name']].values.tolist()}")
    missing = [s for s in cfg.lab_by_short if s not in set(df["institution"])]
    if missing:
        errors.append(f"labs with no faculty: {missing}")
    if errors:
        raise StepFailed("faculty_roster.csv failed validation:\n  - " + "\n  - ".join(errors))

    summary = df.groupby("institution").agg(
        faculty=("faculty_id", "size"),
        current=("status", lambda s: (s == "current").sum()),
        with_orcid=("orcid", lambda s: (s != "").sum()),
        with_dois=("profile_dois", lambda s: (s != "").sum()),
        with_pmids=("profile_pmids", lambda s: (s != "").sum()),
        no_department=("department", lambda s: (s == "").sum()),
    )
    print()
    print(summary.to_string())
    print(f"\nTotal faculty: {len(df)}\n")
    return df


def run(cfg, oa, argv=()) -> None:
    ap = argparse.ArgumentParser(prog="dpcn run s01")
    ap.add_argument("--scrape", choices=[*SCRAPERS, "all"], help="scrape lab website(s) into data/review/")
    ap.add_argument("--refresh", action="store_true", help="with --scrape: ignore cached HTML")
    ap.add_argument("--merge", action="store_true", help="append keep=TRUE scraped rows to the master roster")
    ap.add_argument("--add-uncovered", action="store_true",
                    help="add the people ticked in data/review/uncovered_lab_authors.csv (written by s05)")
    args = ap.parse_args(list(argv))

    if args.scrape:
        scrape(cfg, args.scrape, args.refresh)
    if args.merge:
        merge(cfg)
    if args.add_uncovered:
        add_uncovered(cfg)
    if args.scrape and not args.merge:
        log.info("Next: review data/review/roster_*_scraped.csv, then `python -m dpcn run s01 --merge`")
        return
    df = validate(cfg)
    out = cfg.paths.interim / "roster.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Wrote %s (%d faculty)", cfg.rel(out), len(df))
