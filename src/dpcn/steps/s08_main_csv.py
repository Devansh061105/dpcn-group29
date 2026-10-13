"""S08: build outputs/submission/group29_data.csv (guide §7, S08; plan §2.3, D5, D6, D11).

One row per (paper x faculty member x lab). The 14 required columns come first, in the order of the instruction
note, then extra columns that make every statistic reproducible from this file alone.

  coauthor_institutes   Indian partner institutions on the paper other than the row's lab (no umbrella bodies,
                        no AcSIR by default)
  cites_indian_inst     TRUE if a referenced work carries such a partner institution
  cited_by_indian_inst  TRUE if a citing work (2016-2026) carries such a partner institution
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone

import pandas as pd

from ..netdata import load_context
from . import StepFailed

log = logging.getLogger("dpcn.s08")

REQUIRED = ["group", "institution", "author", "title", "year", "type", "journal_name", "issn", "doi",
            "citations", "quartile", "coauthor_institutes", "cites_indian_inst", "cited_by_indian_inst"]
EXTRA = ["openalex_id", "author_openalex_ids", "faculty_id", "department", "dept_source", "designation",
         "faculty_status", "domain", "field", "subfield", "primary_topic", "n_authors", "author_position",
         "is_corresponding", "coauthor_institutes_all", "quartile_source", "sjr_year_used", "affil_method"]
_TAG = re.compile(r"<[^>]+>")


def clean_title(t: str | None) -> str:
    return " ".join(_TAG.sub("", t or "").split())


def tf(x: bool) -> str:
    return "TRUE" if x else "FALSE"


def git_commit(root) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def build(ctx) -> pd.DataFrame:
    cfg, reg = ctx.cfg, ctx.reg
    it = cfg.paths.interim
    quart = pd.read_parquet(it / "quartiles.parquet").set_index("work_id")
    dept = pd.read_parquet(it / "faculty_dept.parquet").set_index("faculty_id")
    roster = ctx.roster.set_index("faculty_id")
    works = ctx.works.set_index("work_id")

    # citing / cited partner institutions per work (any Indian institution; partner test per row below)
    cited_by: dict[str, set] = {}
    for c in ctx.inflow.itertuples():
        for r in c.refs_ours:
            if r in ctx.ours and r != c.work_id:          # OpenAlex lists some papers among their own references
                cited_by.setdefault(r, set()).update(c.inst_ids)
    # internal citations count too: an in-dataset paper citing ours is also an Indian citing work
    for w in ctx.works.itertuples():
        for r in w.referenced_works:
            if r in ctx.ours and r != w.work_id:
                cited_by.setdefault(r, set()).update(ctx.inst.get(w.work_id, []))
    ref_insts: dict[str, set] = {}
    for w in ctx.works.itertuples():
        s = set()
        for r in w.referenced_works:
            if r != w.work_id:
                s.update(ctx.inst.get(r, []))
        ref_insts[w.work_id] = s

    # per paper: author info for each faculty member, and all institutions
    a = ctx.authorships
    fac_auth = {}
    for r in a[a["faculty_id"].notna()].itertuples():
        d = fac_auth.setdefault((r.work_id, r.faculty_id), {"ids": [], "pos": r.position_idx, "corr": False})
        d["ids"].append(r.author_id)
        d["corr"] |= bool(r.is_corresponding)
    all_insts: dict[str, set] = {}
    for wid, ids in zip(a["work_id"], a["inst_ids"]):
        all_insts.setdefault(wid, set()).update(ids)

    def label_all(i):
        info = reg._get(i)
        return reg.label(i) if reg.our_lab(i) else f"{info['display_name'] or i} ({info['country_code'] or '?'})"

    rows = []
    for l in ctx.links.itertuples():
        w = works.loc[l.work_id]
        lab = l.institution
        q = quart.loc[l.work_id]
        fr = roster.loc[l.faculty_id]
        fa = fac_auth.get((l.work_id, l.faculty_id), {"ids": [], "pos": None, "corr": False})
        partners = sorted({reg.label(i) for i in ctx.partners(l.work_id, lab)})
        issns = [w.issn_l] if isinstance(w.issn_l, str) and w.issn_l else list(w.issns)
        own = {i for i in all_insts.get(l.work_id, ()) if reg.our_lab(i) == lab}
        rows.append({
            "group": cfg.group, "institution": lab, "author": fr["name"], "title": clean_title(w.title),
            "year": int(w.year), "type": w.kind, "journal_name": w.source_name or "",
            "issn": (issns[0] if issns and w.kind == "journal" else "") or "",
            "doi": ctx.doi[l.work_id], "citations": int(w.cited_by_count), "quartile": q["quartile"],
            "coauthor_institutes": "; ".join(partners),
            "cites_indian_inst": tf(any(reg.partner_ok(i, own_lab=lab) for i in ref_insts[l.work_id])),
            "cited_by_indian_inst": tf(any(reg.partner_ok(i, own_lab=lab) for i in cited_by.get(l.work_id, ()))),
            "openalex_id": f"https://openalex.org/{l.work_id}", "author_openalex_ids": ";".join(fa["ids"]),
            "faculty_id": l.faculty_id, "department": dept.loc[l.faculty_id, "department"],
            "dept_source": dept.loc[l.faculty_id, "dept_source"], "designation": fr["designation"],
            "faculty_status": fr["status"], "domain": w.domain or "", "field": w.field or "",
            "subfield": w.subfield or "", "primary_topic": w.topic or "", "n_authors": int(w.n_authors),
            "author_position": "" if fa["pos"] is None else int(fa["pos"]) + 1,
            "is_corresponding": tf(fa["corr"]),
            "coauthor_institutes_all": "; ".join(sorted({label_all(i) for i in all_insts.get(l.work_id, ())
                                                         if i not in own and not reg.is_umbrella(i)})),
            "quartile_source": q["quartile_source"],
            "sjr_year_used": "" if pd.isna(q["sjr_year_used"]) else int(q["sjr_year_used"]),
            "affil_method": l.affil_method,
        })
    df = pd.DataFrame(rows, columns=REQUIRED + EXTRA)
    return df.sort_values(["institution", "author", "year", "title"], kind="stable").reset_index(drop=True)


def run(cfg, oa, argv=()) -> None:
    for p in ("quartiles.parquet", "faculty_dept.parquet"):
        if not (cfg.paths.interim / p).exists():
            raise StepFailed(f"data/interim/{p} missing - run s06 first")
    ctx = load_context(cfg)
    df = build(ctx)
    sub = cfg.paths.submission
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"group{cfg.group}_data.csv"
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")

    per_lab = {}
    for lab, g in df.groupby("institution"):
        per_lab[lab] = {"rows": len(g), "papers": g["openalex_id"].nunique(), "faculty": g["faculty_id"].nunique(),
                        "cites_indian_inst_true": int((g["cites_indian_inst"] == "TRUE").sum()),
                        "cited_by_indian_inst_true": int((g["cited_by_indian_inst"] == "TRUE").sum())}
    s05 = json.loads((cfg.paths.interim / "s05_summary.json").read_text())
    meta = {"group": cfg.group, "institutions": [l["short"] for l in cfg.labs],
            "collection_date": s05.get("run_at", "")[:10],
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "OpenAlex (api.openalex.org), Scimago SJR, CORE2023",
            "window": [cfg.window.start, cfg.window.end], "partial_year": cfg.window.partial_year,
            "rows": len(df), "unique_papers": df["openalex_id"].nunique(), "per_institution": per_lab,
            "git_commit": git_commit(cfg.root)}
    (sub / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\n{cfg.rel(path)}: {len(df)} rows, {df['openalex_id'].nunique()} unique papers")
    print(pd.DataFrame(per_lab).T.to_string())
    print("quartile:", df.drop_duplicates("openalex_id")["quartile"].value_counts().to_dict())
