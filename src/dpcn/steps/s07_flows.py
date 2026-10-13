"""S07: Indian citation in-flow and out-flow (guide §7, S07; plan D11, D13).

  out-flow  works with an Indian author that our papers cite:  cited_by:<100 ids>,institutions.country_code:IN
  in-flow   works with an Indian author (2016-2026) citing us: cites:<100 ids>,institutions.country_code:IN,...

The query set is every type-filtered lab-corpus paper plus any dataset paper outside the corpus, in a fixed order,
so a roster change (which changes the dataset) re-uses the cached batches; S09 keeps only edges touching the
dataset. Edges themselves are built in S09.

Outputs (data/interim/): outflow_works.parquet, inflow_works.parquet (Indian institution ids per work; for in-flow
also the referenced works that are in the query set), institutions.parquet (extended with every new institution
seen), s07_summary.json.
"""
from __future__ import annotations

import json
import logging

import pandas as pd

from ..institutions import InstitutionRegistry
from ..openalex import batches, short_id
from . import StepFailed

log = logging.getLogger("dpcn.s07")

OUT_SELECT = "id,doi,title,publication_year,cited_by_count,authorships"
IN_SELECT = "id,doi,title,publication_year,cited_by_count,primary_location,authorships,referenced_works"


def registry_from_frame(cfg, df: pd.DataFrame) -> InstitutionRegistry:
    reg = InstitutionRegistry(cfg)
    for r in df.itertuples():
        reg.insts[r.inst_id] = {"display_name": r.display_name, "country_code": r.country_code, "type": r.type,
                                "ror": r.ror, "lineage": list(r.lineage)}
    return reg


def indian_insts(w: dict, reg: InstitutionRegistry) -> list[str]:
    """Every Indian institution on the work (our labs and umbrella bodies included; filtering happens later)."""
    out = []
    for a in w.get("authorships") or []:
        for inst in a.get("institutions") or []:
            iid = reg.add(inst)
            if iid and reg.is_indian(iid) and iid not in out:
                out.append(iid)
    return out


def disambiguate(cfg, oa, reg: InstitutionRegistry) -> dict[str, str]:
    """'Name (City)' for Indian institutions that share a display name (e.g. the NIPER campuses), from single
    institution lookups (free). Written to data/interim/institution_labels.json and used by every label."""
    by_name: dict[str, list] = {}
    for iid, info in reg.insts.items():
        if info["country_code"] == "IN" and not reg.our_lab(iid):
            by_name.setdefault(info["display_name"], []).append(iid)
    out = {}
    for name, ids in by_name.items():
        if len(ids) < 2:
            continue
        for iid in ids:
            try:
                geo = (oa.entity(f"institutions/{iid}", select="id,geo") or {}).get("geo") or {}
            except RuntimeError:          # a retired OpenAlex record (HTTP 404)
                geo = {}
            city = geo.get("city") or iid
            out[iid] = f"{name} ({city})"
        if len(set(out[i] for i in ids)) < len(ids):          # same city too: fall back to the id
            for iid in ids:
                out[iid] = f"{name} ({iid})"
    return out


def query_ids(cfg) -> list[str]:
    it = cfg.paths.interim
    corpus = sorted(set(pd.read_parquet(it / "lab_corpus_kept.parquet")["work_id"]))
    extra = sorted(set(pd.read_parquet(it / "works.parquet")["work_id"]) - set(corpus))
    return corpus + extra


def run(cfg, oa, argv=()) -> None:
    it = cfg.paths.interim
    for p in ("works.parquet", "lab_corpus_kept.parquet", "institutions.parquet"):
        if not (it / p).exists():
            raise StepFailed(f"data/interim/{p} missing - run s05 first")
    reg = registry_from_frame(cfg, pd.read_parquet(it / "institutions.parquet"))
    ids = query_ids(cfg)
    qset = set(ids)
    n_batches = -(-len(ids) // cfg.openalex.or_batch)
    log.info("query set: %d works (%d batches of %d)", len(ids), n_batches, cfg.openalex.or_batch)

    out_rows: dict[str, dict] = {}
    in_rows: dict[str, dict] = {}
    for bi, b in enumerate(batches(ids, cfg.openalex.or_batch), 1):
        flt = f"cited_by:{'|'.join(b)},institutions.country_code:IN"
        for w in oa.paginate("works", flt, select=OUT_SELECT, per_page=cfg.openalex.per_page):
            wid = short_id(w["id"])
            if wid not in out_rows:
                out_rows[wid] = {"work_id": wid, "doi": w.get("doi"), "title": w.get("title"),
                                 "year": w.get("publication_year"), "cited_by_count": w.get("cited_by_count") or 0,
                                 "inst_ids": indian_insts(w, reg)}
        flt = f"cites:{'|'.join(b)},institutions.country_code:IN,{cfg.year_filter}"
        for w in oa.paginate("works", flt, select=IN_SELECT, per_page=cfg.openalex.per_page):
            wid = short_id(w["id"])
            refs = {short_id(r) for r in w.get("referenced_works") or []} & qset
            if wid in in_rows:
                in_rows[wid]["refs_ours"] = sorted(set(in_rows[wid]["refs_ours"]) | refs)
                continue
            src = (w.get("primary_location") or {}).get("source") or {}
            in_rows[wid] = {"work_id": wid, "doi": w.get("doi"), "title": w.get("title"),
                            "year": w.get("publication_year"), "cited_by_count": w.get("cited_by_count") or 0,
                            "source_name": src.get("display_name"), "inst_ids": indian_insts(w, reg),
                            "refs_ours": sorted(refs)}
        if bi % 10 == 0 or bi == n_batches:
            log.info("batch %d/%d: %d out-flow works, %d in-flow works so far | %s",
                     bi, n_batches, len(out_rows), len(in_rows), oa.report())

    outflow = pd.DataFrame(list(out_rows.values()))
    inflow = pd.DataFrame(list(in_rows.values()))
    outflow.to_parquet(it / "outflow_works.parquet", index=False)
    inflow.to_parquet(it / "inflow_works.parquet", index=False)
    reg.to_frame().to_parquet(it / "institutions.parquet", index=False)
    labels = disambiguate(cfg, oa, reg)
    (it / "institution_labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("%d institutions share a display name; labelled with their city", len(labels))

    # ---- acceptance: every lab cites and is cited by Indian work
    works = pd.read_parquet(it / "works.parquet")
    links = pd.read_parquet(it / "faculty_papers.parquet")
    out_ids, ours = set(outflow["work_id"]), set(works["work_id"])
    cited_ours = {r for refs in inflow["refs_ours"] for r in refs} & ours
    summary = {"query_works": len(ids), "outflow_works": len(outflow), "inflow_works": len(inflow), "labs": {}}
    print(f"\nIndian works cited by the query set: {len(outflow)}; Indian 2016-2026 works citing it: {len(inflow)}")
    for lab, g in links.groupby("institution"):
        w = works[works["work_id"].isin(set(g["work_id"]))]
        n_out = sum(len(set(r) & out_ids) for r in w["referenced_works"])
        n_in = len(set(w["work_id"]) & cited_ours)
        summary["labs"][lab] = {"refs_to_indian_works": n_out, "papers_cited_by_indian_works": n_in,
                                "sum_cited_by_count": int(w["cited_by_count"].sum())}
        print(f"  {lab:<12} references to Indian works: {n_out:>6}   dataset papers cited by Indian works: {n_in:>5}")
        if n_out == 0 or n_in == 0:
            raise StepFailed(f"{lab}: no Indian out-flow or in-flow found; check the queries")
    (it / "s07_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
