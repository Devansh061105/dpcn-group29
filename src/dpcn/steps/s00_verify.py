"""S00: verify our institutions in OpenAlex and report the API budget (guide §7, S00).

Fails if a lab's ROR or country doesn't match the config, or it has no works in the window.
Warns (doesn't fail) if the work count drifted beyond `verify.count_tolerance` from the
reconnaissance figure; record any drift in docs/qa_log.md.
Writes data/interim/s00_verification.json.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ..openalex import short_id
from . import StepFailed

log = logging.getLogger("dpcn.s00")

INST_SELECT = "id,display_name,ror,country_code,type,works_count,lineage"


def _norm(s: str) -> str:
    return " ".join((s or "").lower().replace("&", "and").split())


def verify_lab(cfg, oa, lab: dict) -> dict:
    iid = lab["openalex_id"]
    inst = oa.entity(f"institutions/{iid}", select=INST_SELECT)
    works_filter = f"authorships.institutions.lineage:{iid},{cfg.year_filter}"
    count = oa.count("works", works_filter)
    by_year = {g["key"]: g["count"] for g in oa.group_by("works", works_filter, "publication_year")}
    expected = lab.get("expected_works_2016_2026")

    problems, warnings = [], []
    ror = (inst.get("ror") or "").rstrip("/").rsplit("/", 1)[-1]
    if ror != lab["ror"]:
        problems.append(f"ROR mismatch: OpenAlex {ror!r} vs config {lab['ror']!r}")
    if inst.get("country_code") != "IN":
        problems.append(f"country_code is {inst.get('country_code')!r}, expected 'IN'")
    if count == 0:
        problems.append("no works in the window")
    if _norm(inst.get("display_name")) != _norm(lab["name"]):
        warnings.append(f"name differs: OpenAlex {inst.get('display_name')!r} vs config {lab['name']!r}")
    drift = None
    if expected:
        drift = (count - expected) / expected
        if abs(drift) > cfg.verify.count_tolerance:
            warnings.append(f"work count {count} drifted {drift:+.1%} from expected {expected}")
    missing_years = [y for y in range(cfg.window.start, cfg.window.end + 1) if str(y) not in by_year]
    if missing_years:
        warnings.append(f"no works in years {missing_years}")

    return {
        "short": lab["short"],
        "openalex_id": iid,
        "display_name": inst.get("display_name"),
        "ror": ror,
        "type": inst.get("type"),
        "lineage": [short_id(x) for x in inst.get("lineage", [])],
        "works_count_all_time": inst.get("works_count"),
        "works_in_window": count,
        "expected_in_window": expected,
        "drift": drift,
        "works_by_year": dict(sorted(by_year.items())),
        "problems": problems,
        "warnings": warnings,
    }


def run(cfg, oa, argv=()) -> None:
    results = [verify_lab(cfg, oa, lab) for lab in cfg.labs]

    years = list(range(cfg.window.start, cfg.window.end + 1))
    print()
    print(f"{'Lab':<12} {'OpenAlex ID':<12} {'ROR':<10} {'Works':>6} {'Expected':>8} {'Drift':>7}  Status")
    for r in results:
        drift = f"{r['drift']:+.1%}" if r["drift"] is not None else "-"
        status = "FAIL" if r["problems"] else ("WARN" if r["warnings"] else "OK")
        print(f"{r['short']:<12} {r['openalex_id']:<12} {r['ror']:<10} {r['works_in_window']:>6} "
              f"{r['expected_in_window'] or '-':>8} {drift:>7}  {status}")
    print()
    print("Works by year (all types; " + f"{cfg.window.partial_year} is partial)")
    print(f"{'Lab':<12} " + " ".join(f"{y:>5}" for y in years))
    for r in results:
        print(f"{r['short']:<12} " + " ".join(f"{r['works_by_year'].get(str(y), 0):>5}" for y in years))
    print()

    for r in results:
        for w in r["warnings"]:
            log.warning("%s: %s", r["short"], w)
        for p in r["problems"]:
            log.error("%s: %s", r["short"], p)

    out = cfg.paths.interim / "s00_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "group": cfg.group,
        "has_api_key": bool(cfg.api_key),
        "window": [cfg.window.start, cfg.window.end],
        "labs": results,
    }, indent=2), encoding="utf-8")
    log.info("Wrote %s", cfg.rel(out))
    log.info("API key: %s", "set" if cfg.api_key else "NOT set ($0.10/day budget)")

    failed = [r["short"] for r in results if r["problems"]]
    if failed:
        raise StepFailed(f"S00 verification failed for: {', '.join(failed)}")
