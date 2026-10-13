"""Shared inputs for S08-S12: the dataset tables plus, for every work that can appear in a citation edge
(ours, out-flow, in-flow), the set of Indian institutions on it. Loaded once per step from data/interim/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .institutions import InstitutionRegistry
from .steps import StepFailed


@dataclass
class Context:
    cfg: object
    works: pd.DataFrame
    links: pd.DataFrame            # faculty_papers: work_id, faculty_id, institution, affil_method
    authorships: pd.DataFrame
    roster: pd.DataFrame
    reg: InstitutionRegistry
    outflow: pd.DataFrame
    inflow: pd.DataFrame
    ours: set = field(default_factory=set)
    inst: dict = field(default_factory=dict)       # work_id -> list of Indian institution ids
    labs_of: dict = field(default_factory=dict)    # work_id -> set of our labs with a faculty link
    year: dict = field(default_factory=dict)       # work_id -> publication year
    doi: dict = field(default_factory=dict)        # work_id -> DOI URL, or the OpenAlex URL when there is none

    def partners(self, wid: str, lab: str) -> list[str]:
        """Indian institutions on a work that count as partners of `lab` (plan D11)."""
        return [i for i in self.inst.get(wid, []) if self.reg.partner_ok(i, own_lab=lab)]

    def inst_labels(self, wid: str) -> list[str]:
        """Indian, non-umbrella institution labels on a work, our labs first (including a lab linked only
        through the raw affiliation text)."""
        ids = [i for i in self.inst.get(wid, []) if not self.reg.is_umbrella(i)]
        labs = sorted({self.reg.our_lab(i) for i in ids if self.reg.our_lab(i)} | self.labs_of.get(wid, set()))
        others = sorted({self.reg.label(i) for i in ids if not self.reg.our_lab(i)})
        return labs + others


def node_key(wid: str, doi: str | None) -> str:
    return doi if doi else f"https://openalex.org/{wid}"


TEXT_COLS = ["doi", "title", "source_id", "source_name", "source_type", "issn_l", "topic_id", "topic", "subfield_id",
             "subfield", "field", "domain", "pub_date"]


def read_works(interim) -> pd.DataFrame:
    """works.parquet with missing text values as None (not NaN, which is truthy and breaks `x or ''`)."""
    w = pd.read_parquet(interim / "works.parquet")
    for c in TEXT_COLS:
        if c in w:
            w[c] = w[c].astype(object).where(w[c].notna(), None)
    return w


def load_context(cfg, need_flows: bool = True) -> Context:
    from .steps.s07_flows import registry_from_frame   # avoid an import cycle at module load
    it = cfg.paths.interim
    needed = ["works", "faculty_papers", "authorships", "institutions"] + (["outflow_works", "inflow_works"] if need_flows else [])
    for n in needed:
        if not (it / f"{n}.parquet").exists():
            raise StepFailed(f"data/interim/{n}.parquet missing - run the earlier steps first")
    works = read_works(it)
    links = pd.read_parquet(it / "faculty_papers.parquet")
    auth = pd.read_parquet(it / "authorships.parquet")
    for c in ("author_id", "author_name", "raw_author_name", "faculty_id", "our_lab"):
        auth[c] = auth[c].astype(object).where(auth[c].notna(), None)
    reg =registry_from_frame(cfg, pd.read_parquet(it / "institutions.parquet"))
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)
    empty = pd.DataFrame(columns=["work_id", "doi", "title", "year", "cited_by_count", "inst_ids", "refs_ours"])
    outflow = pd.read_parquet(it / "outflow_works.parquet") if need_flows else empty
    inflow = pd.read_parquet(it / "inflow_works.parquet") if need_flows else empty

    ctx = Context(cfg, works, links, auth, roster, reg, outflow, inflow, ours=set(works["work_id"]))
    for df in (outflow, inflow):
        for r in df.itertuples():
            ctx.inst[r.work_id] = list(r.inst_ids)
            ctx.year[r.work_id] = r.year
            ctx.doi[r.work_id] = node_key(r.work_id, r.doi)
    ours_inst: dict[str, list] = {}
    for wid, ids in zip(auth["work_id"], auth["inst_ids"]):
        lst = ours_inst.setdefault(wid, [])
        lst.extend(i for i in ids if reg.is_indian(i) and i not in lst)
    for r in works.itertuples():
        ctx.inst[r.work_id] = ours_inst.get(r.work_id, [])
        ctx.year[r.work_id] = r.year
        ctx.doi[r.work_id] = node_key(r.work_id, r.doi)
    for wid, lab in zip(links["work_id"], links["institution"]):
        ctx.labs_of.setdefault(wid, set()).add(lab)
    return ctx
