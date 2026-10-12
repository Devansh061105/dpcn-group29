"""Command line entry point.

    python -m dpcn list
    python -m dpcn run s00
    python -m dpcn run all [--from s04]
"""
from __future__ import annotations

import argparse
import importlib
import logging
import sys
import time

from .config import load_config
from .openalex import BudgetExceeded, OpenAlex
from .steps import StepFailed

# Ordered pipeline (guide §7). A step whose module doesn't exist yet is reported as not implemented.
STEPS: list[tuple[str, str]] = [
    ("s00", "s00_verify"),
    ("s01", "s01_roster"),
    ("s02", "s02_candidates"),
    ("s03", "s03_match"),
    ("s04", "s04_works"),
    ("s05", "s05_normalise"),
    ("s06", "s06_enrich"),
    ("s07", "s07_flows"),
    ("s08", "s08_main_csv"),
    ("s09", "s09_citation"),
    ("s10", "s10_authorship"),
    ("s11", "s11_connections"),
    ("s12", "s12_stats"),
    ("s13", "s13_dashboard"),
    ("s14", "s14_report"),
    ("s15", "s15_validate"),
]
STEP_IDS = [s for s, _ in STEPS]


def _load_step(module_name: str):
    try:
        return importlib.import_module(f"dpcn.steps.{module_name}")
    except ModuleNotFoundError as e:
        if e.name == f"dpcn.steps.{module_name}":
            return None
        raise


def _run_one(step_id: str, cfg, oa, argv: list[str]) -> None:
    module_name = dict(STEPS)[step_id]
    mod = _load_step(module_name)
    if mod is None:
        raise StepFailed(f"{step_id} ({module_name}) is not implemented yet")
    log = logging.getLogger("dpcn")
    log.info("=== %s: %s ===", step_id, module_name)
    t0 = time.time()
    mod.run(cfg, oa, argv)
    log.info("=== %s done in %.1fs | %s ===", step_id, time.time() - t0, oa.report())


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")

    p = argparse.ArgumentParser(prog="dpcn", description="DPCN Group 29 pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list pipeline steps and whether they are implemented")
    r = sub.add_parser("run", help="run one step, or all steps")
    r.add_argument("step", choices=STEP_IDS + ["all"])
    r.add_argument("--from", dest="start", choices=STEP_IDS, help="with 'all': first step to run")
    args, extra = p.parse_known_args(argv)

    if args.cmd == "list":
        for sid, mod in STEPS:
            status = "ready" if _load_step(mod) else "not implemented"
            print(f"{sid}  {mod:<18} {status}")
        return 0

    cfg = load_config()
    oa = OpenAlex.from_config(cfg)
    if not cfg.api_key:
        logging.warning("OPENALEX_API_KEY not set: daily budget is $0.10 (~1,000 list calls). "
                        "Copy .env.example to .env and add your free key.")

    todo = STEP_IDS[STEP_IDS.index(args.start or "s00"):] if args.step == "all" else [args.step]
    try:
        for sid in todo:
            _run_one(sid, cfg, oa, extra)
    except (StepFailed, BudgetExceeded) as e:
        logging.error("%s", e)
        return 1
    return 0
