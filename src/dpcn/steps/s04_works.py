"""S04: fetch works (guide §7, S04).

Two raw collections, both limited to 2016-2026 and stored as gzip JSON lines under data/interim/works_raw/:
  faculty.jsonl.gz     every paper by an accepted author ID, at ANY affiliation. Wider than the lab corpus: it also
                       catches papers where OpenAlex lost the lab's institution link but the raw affiliation text
                       names it (S05 decides, plan D4)
  lab_<short>.jsonl.gz papers with an authorship affiliated to the lab (same cached requests S03 used)

Papers listing exactly 100 authors are re-fetched individually, because list queries cut the author list at 100.
"""
from __future__ import annotations

import gzip
import json
import logging

import pandas as pd

from ..corpus import iter_lab_works
from ..openalex import WORK_SELECT, batches, short_id
from . import StepFailed

log = logging.getLogger("dpcn.s04")

AUTHOR_CAP = 100   # OpenAlex list endpoints return at most this many authorships per work


def raw_dir(cfg):
    return cfg.paths.interim / "works_raw"


def full_authorships(oa, w: dict) -> bool:
    """Replace a possibly truncated author list with the full one (single-work lookups are free)."""
    if len(w.get("authorships") or []) < AUTHOR_CAP:
        return False
    full = oa.entity(f"works/{short_id(w['id'])}", select="id,authorships")
    if len(full.get("authorships") or []) > len(w["authorships"]):
        w["authorships"] = full["authorships"]
        return True
    return False


def write_jsonl(path, works, oa, seen: set[str] | None = None) -> tuple[int, int]:
    """Write works (skipping ids in `seen`), fixing truncated author lists. Returns (written, fixed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    n = fixed = 0
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for w in works:
            wid = short_id(w["id"])
            if seen is not None:
                if wid in seen:
                    continue
                seen.add(wid)
            fixed += full_authorships(oa, w)
            f.write(json.dumps(w, separators=(",", ":")) + "\n")
            n += 1
    tmp.replace(path)
    return n, fixed


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def faculty_works(cfg, oa, author_ids: list[str]):
    types = "|".join(cfg.work_filter.include_work_types)
    for b in batches(author_ids, cfg.openalex.or_batch):
        flt = f"authorships.author.id:{'|'.join(b)},{cfg.year_filter},type:{types}"
        yield from oa.paginate("works", flt, select=WORK_SELECT, per_page=cfg.openalex.per_page)


def run(cfg, oa, argv=()) -> None:
    map_path = cfg.paths.interim / "faculty_author_map.parquet"
    if not map_path.exists():
        raise StepFailed(f"{cfg.rel(map_path)} missing - run s03 first")
    ids = sorted(set(pd.read_parquet(map_path)["author_id"]))
    out = raw_dir(cfg)
    summary = {"author_ids": len(ids), "labs": {}}

    n, fixed = write_jsonl(out / "faculty.jsonl.gz", faculty_works(cfg, oa, ids), oa, seen=set())
    summary["faculty_works"], summary["faculty_truncated_fixed"] = n, fixed
    log.info("faculty collection: %d works from %d author IDs (%d truncated author lists fixed)", n, len(ids), fixed)

    s00 = cfg.paths.interim / "s00_verification.json"
    s00_counts = ({x["short"]: x["works_in_window"] for x in json.loads(s00.read_text())["labs"]}
                  if s00.exists() else {})
    for lab in cfg.labs:
        n, fixed = write_jsonl(out / f"lab_{lab['short']}.jsonl.gz", iter_lab_works(cfg, oa, lab), oa)
        expect = s00_counts.get(lab["short"])
        summary["labs"][lab["short"]] = {"works": n, "truncated_fixed": fixed, "s00_count": expect}
        note = "" if expect is None else f" (S00 saw {expect}; OpenAlex adds records daily)"
        log.info("%s lab corpus: %d works, %d truncated fixed%s", lab["short"], n, fixed, note)
        if expect and abs(n - expect) > max(5, 0.02 * expect):
            raise StepFailed(f"{lab['short']}: {n} works fetched but S00 counted {expect}; investigate before continuing")

    (cfg.paths.interim / "s04_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Wrote raw works under %s", cfg.rel(out))
