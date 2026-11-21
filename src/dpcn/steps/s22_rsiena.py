"""S22: stochastic actor-oriented model (RSiena) of the faculty co-authorship network.

    python -m dpcn run s22            full estimation (several minutes)
    python -m dpcn run s22 --quick    short estimation, for a smoke test

Needs R with the RSiena and jsonlite packages. Rscript is found from the DPCN_RSCRIPT environment variable, then PATH,
then a conda environment named dpcn-r (see README). The step writes the waves to data/interim/rsiena/, runs
src/dpcn/r/siena_faculty.R and saves outputs/stats/siena_estimates.csv and siena_fit.json.

Design: faculty active through the whole window (first paper by the end of wave 1, a paper in the last wave) are the
actors; a tie in a wave means at least one joint paper (at most networks.max_authors_for_pairs authors) in that wave's
years, so ties can form and dissolve between waves. Effects: rate, density (degree), transitive triads, degree
(popularity / activity), same lab, same department, topic similarity (cosine of subfield profiles over the window),
seniority and output (papers in the wave) of both actors. modelType 2 = forcing (one actor can create or end a tie).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from . import StepFailed
from .s18_netmodels import Data

log = logging.getLogger("dpcn.s22")
SEED = 42
WAVES = [(2016, 2018), (2019, 2021), (2022, 2025)]


def find_rscript() -> str:
    cands = [os.environ.get("DPCN_RSCRIPT"), shutil.which("Rscript")]
    for base in (Path.home() / "Miniconda3", Path.home() / "miniconda3", Path.home() / "anaconda3"):
        cands += [str(base / "envs" / "dpcn-r" / "Scripts" / "Rscript.exe"), str(base / "envs" / "dpcn-r" / "bin" / "Rscript")]
    for c in cands:
        if c and Path(c).exists():
            return c
    raise StepFailed("Rscript not found: install R with RSiena (conda env 'dpcn-r') or set DPCN_RSCRIPT")


def export(D: Data, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    actors = [f for f in D.faculty if D.first[f] <= WAVES[0][1] and D.last[f] >= WAVES[-1][0]]
    ix = {f: i for i, f in enumerate(actors)}
    ev = D.events
    ties = []
    for k, (a0, a1) in enumerate(WAVES, 1):
        A = np.zeros((len(actors), len(actors)), int)
        sub = ev[ev["year"].between(a0, a1)]
        for a, b in zip(sub["a"], sub["b"]):
            if a in ix and b in ix:
                A[ix[a], ix[b]] = A[ix[b], ix[a]] = 1
        np.savetxt(out / f"wave{k}.csv", A, fmt="%d", delimiter=",")
        ties.append(int(A.sum() // 2))
    labs = sorted(set(D.lab.values()))
    depts = sorted({f"{D.lab[f]}|{D.dept.get(f, '')}" for f in actors})
    sen = pd.Series([D.seniority.get(f) for f in actors], dtype=float)
    py = D.papers_by_year
    nodes = pd.DataFrame({"faculty_id": actors, "lab": [labs.index(D.lab[f]) + 1 for f in actors],
                          "dept": [depts.index(f"{D.lab[f]}|{D.dept.get(f, '')}") + 1 for f in actors],
                          "seniority": sen.fillna(sen.median()).to_numpy()})
    for k, (a0, a1) in enumerate(WAVES[:-1], 1):
        nodes[f"output_w{k}"] = [np.log1p(sum(py.get((f, y), 0) for y in range(a0, a1 + 1))) for f in actors]
    nodes.to_csv(out / "nodes.csv", index=False)
    T = D.topic_matrix(WAVES[-1][1], actors)
    np.savetxt(out / "topic.csv", T @ T.T, fmt="%.6f", delimiter=",")
    # Jaccard index of tie change between consecutive waves (RSiena needs enough stability, ideally above 0.2-0.3)
    jac = []
    for k in range(1, len(WAVES)):
        A = np.loadtxt(out / f"wave{k}.csv", delimiter=",")
        B = np.loadtxt(out / f"wave{k + 1}.csv", delimiter=",")
        both = np.triu((A > 0) & (B > 0), 1).sum()
        either = np.triu((A > 0) | (B > 0), 1).sum()
        jac.append(both / either if either else np.nan)
    return {"actors": len(actors), "ties_per_wave": ties, "jaccard_between_waves": jac, "waves": [f"{a}-{b}" for a, b in WAVES]}


def run(cfg, oa, argv=()) -> None:
    quick = "--quick" in argv
    rs = find_rscript()
    D = Data(cfg)
    inp = cfg.paths.interim / "rsiena"
    meta = export(D, inp)
    log.info("RSiena data: %d actors, ties per wave %s, Jaccard %s", meta["actors"], meta["ties_per_wave"],
             [round(j, 3) for j in meta["jaccard_between_waves"]])
    script = Path(__file__).resolve().parents[1] / "r" / "siena_faculty.R"
    out = cfg.paths.stats
    cmd = [rs, str(script), str(inp), str(out), str(SEED), "1" if quick else "0"]
    log.info("running %s", " ".join(cmd[1:]))
    env = dict(os.environ)
    root = Path(rs).resolve().parent.parent          # conda env root when Rscript lives in <env>/Scripts
    if (root / "conda-meta").exists():               # conda's R needs the environment's DLL folders on PATH
        extra = [root, root / "Library" / "mingw-w64" / "bin", root / "Library" / "usr" / "bin", root / "Library" / "bin",
                 root / "Scripts", root / "bin", root / "Lib" / "R" / "bin" / "x64"]
        env["PATH"] = os.pathsep.join([str(x) for x in extra if x.exists()] + [env.get("PATH", "")])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200, env=env)
    if r.returncode != 0 or not (out / "siena_estimates.csv").exists():
        raise StepFailed(f"RSiena failed (exit {r.returncode}):\n{r.stderr[-2000:]}")
    fit = json.loads((out / "siena_fit.json").read_text(encoding="utf-8"))
    fit["_design"] = meta
    (out / "siena_fit.json").write_text(json.dumps(fit, indent=1), encoding="utf-8")
    est = pd.read_csv(out / "siena_estimates.csv")
    for m, f in fit.items():
        if not m.startswith("_"):
            log.info("%s: max convergence ratio %.3f (good below 0.25)", m, f["tconv_max"])
    log.info("wrote siena_estimates.csv (%d rows) and siena_fit.json", len(est))
