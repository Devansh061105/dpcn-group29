"""S20: extra OpenAlex data for the paper (funders, countries, careers, ties before 2016, who cites the labs worldwide).

    python -m dpcn run s20

About 700 list calls (well under a dollar of the daily OpenAlex budget); every response is cached in data/cache, and the
results are saved as small tables in outputs/stats/enrich_*.csv, so step s21 reruns from committed files.

  enrich_work_funders.csv      funders named on each dataset paper (OpenAlex `funders`)
  enrich_work_countries.csv    countries of all authors on each paper, and whether it has a foreign co-author
  enrich_faculty_career.csv    each faculty member's first publication year anywhere and output before 2016
  enrich_prior_ties.csv        faculty pairs who co-authored before 2016 (papers with at most 50 authors)
  enrich_world_citers.csv      citing works by country and by field, per lab (2016-2026 citing works)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations

import pandas as pd

from ..openalex import batches, short_id
from . import StepFailed

log = logging.getLogger("dpcn.s20")


def run(cfg, oa, argv=()) -> None:
    st = cfg.paths.stats
    f = cfg.paths.submission / "group29_data.csv"
    if not f.exists():
        raise StepFailed("group29_data.csv missing - run s08 first")
    d = pd.read_csv(f, dtype=str, keep_default_na=False)
    works = sorted({short_id(w) for w in d["openalex_id"]})
    max_auth = cfg.networks.max_authors_for_pairs

    # 1. funders and author countries of every dataset paper
    fund, ctry = [], []
    for b in batches(works, 50):
        for w in oa.paginate("works", "openalex_id:" + "|".join(b), select="id,funders,authorships", per_page=100):
            wid = "https://openalex.org/" + short_id(w["id"])
            for fu in w.get("funders") or []:
                fund.append({"openalex_id": wid, "funder_id": short_id(fu.get("id")), "funder": fu.get("display_name")})
            cs = sorted({c for a in w.get("authorships") or [] for c in (a.get("countries") or [])})
            ctry.append({"openalex_id": wid, "countries": ";".join(cs), "n_countries": len(cs),
                         "foreign_countries": len([c for c in cs if c != "IN"]), "international": any(c != "IN" for c in cs)})
    pd.DataFrame(fund).to_csv(st / "enrich_work_funders.csv", index=False, lineterminator="\n")
    pd.DataFrame(ctry).to_csv(st / "enrich_work_countries.csv", index=False, lineterminator="\n")
    log.info("funders on %d papers; countries for %d papers", len({r['openalex_id'] for r in fund}), len(ctry))

    # 2. careers: first publication year anywhere and output before the window, per faculty member
    ids = d.groupby("faculty_id")["author_openalex_ids"].agg(lambda s: sorted({x for v in s for x in v.split(";") if x}))
    owner = {a: fid for fid, aa in ids.items() for a in aa}
    car = []
    for fid, aa in ids.items():
        g = oa.group_by("works", "author.id:" + "|".join(aa[:50]), "publication_year")
        years = {int(r["key"]): r["count"] for r in g if str(r["key"]).isdigit()}
        car.append({"faculty_id": fid, "first_year_any": min(years) if years else None,
                    "works_before_window": sum(n for y, n in years.items() if y < cfg.window.start),
                    "works_total": sum(years.values())})
    pd.DataFrame(car).to_csv(st / "enrich_faculty_career.csv", index=False, lineterminator="\n")
    log.info("careers for %d faculty", len(car))

    # 3. ties between faculty before the window (papers with at most max_auth authors)
    pairs = defaultdict(lambda: [9999, 0])
    seen = set()
    for b in batches(sorted(owner), 40):
        flt = "author.id:" + "|".join(b) + f",publication_year:1980-{cfg.window.start - 1}"
        for w in oa.paginate("works", flt, select="id,publication_year,authorships"):
            if w["id"] in seen:
                continue
            seen.add(w["id"])
            au = w.get("authorships") or []
            if len(au) > max_auth:
                continue
            fs = sorted({owner[short_id((a.get("author") or {}).get("id"))] for a in au
                         if short_id((a.get("author") or {}).get("id")) in owner})
            for a, c in combinations(fs, 2):
                pairs[(a, c)][0] = min(pairs[(a, c)][0], w["publication_year"])
                pairs[(a, c)][1] += 1
    pd.DataFrame([{"a": a, "b": c, "first_year": v[0], "papers": v[1]} for (a, c), v in pairs.items()]) \
        .to_csv(st / "enrich_prior_ties.csv", index=False, lineterminator="\n")
    log.info("%d faculty pairs co-authored before %d (%d older papers)", len(pairs), cfg.window.start, len(seen))

    # 4. who cites each lab worldwide: citing works (2016-2026) grouped by country and by field
    rows = []
    for lab, g in d.groupby("institution"):
        lw = sorted({short_id(w) for w in g["openalex_id"]})
        acc = {"country": defaultdict(int), "field": defaultdict(int)}
        total = 0
        for b in batches(lw, 80):
            flt = "cites:" + "|".join(b) + f",publication_year:{cfg.window.start}-{cfg.window.end}"
            total += oa.count("works", flt)
            for key, kind in (("authorships.countries", "country"), ("primary_topic.field.id", "field")):
                for r in oa.group_by("works", flt, key):
                    acc[kind][(r["key"], r.get("key_display_name") or r["key"])] += r["count"]
        for kind, dd in acc.items():
            for (k, name), n in dd.items():
                rows.append({"lab": lab, "kind": kind, "key": short_id(str(k)) or k, "name": name, "citing_works": n,
                             "citing_works_total_batches": total})
    pd.DataFrame(rows).to_csv(st / "enrich_world_citers.csv", index=False, lineterminator="\n")
    log.info("world citers: %d rows", len(rows))
