"""Institution registry: which affiliations are ours, Indian, umbrella bodies, and which cluster a partner is in.

Built from every institution object seen on authorships (plan D11, D12). Rules live in
config/cluster_rules.yaml; hand corrections in data/manual/institution_overrides.csv
(columns: openalex_id, cluster, short_name; either may be blank).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .openalex import short_id

COLUMNS = ["inst_id", "display_name", "country_code", "type", "ror", "lineage", "cluster",
           "is_umbrella", "is_academy", "our_lab", "label"]


class InstitutionRegistry:
    def __init__(self, cfg, overrides: dict[str, dict] | None = None):
        r = cfg.rules
        self.cfg = cfg
        self.umbrella = set(r.get("umbrella_ids", []))
        self.academy = set(r.get("csir_academy_ids", []))
        self.name_rules = [(re.compile(p, re.I), c) for p, c in r.get("name_rules", [])]
        self.late_rules = [(re.compile(p, re.I), c) for p, c in r.get("name_rules_late", [])]
        self.lineage_rules = dict(r.get("lineage_rules", {}))
        self.type_rules = dict(r.get("type_rules", {}))
        self.default = r.get("default", "Other")
        self.overrides = overrides if overrides is not None else self._load_overrides(cfg.paths.manual)
        self.count_academy = bool(cfg.connections.count_csir_academy_as_partner)
        self.insts: dict[str, dict] = {}

    @staticmethod
    def _load_overrides(manual_dir: Path) -> dict[str, dict]:
        path = Path(manual_dir) / "institution_overrides.csv"
        if not path.exists():
            return {}
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        return {short_id(r["openalex_id"]): {"cluster": r.get("cluster", ""), "short_name": r.get("short_name", "")}
                for _, r in df.iterrows() if r.get("openalex_id")}

    # ------------------------------------------------------------------ building
    def add(self, inst: dict) -> str | None:
        """Register an institution object from an authorship; returns its short id."""
        iid = short_id(inst.get("id"))
        if not iid:
            return None
        if iid not in self.insts:
            self.insts[iid] = {
                "display_name": inst.get("display_name") or "",
                "country_code": inst.get("country_code") or "",
                "type": inst.get("type") or "",
                "ror": (inst.get("ror") or "").rsplit("/", 1)[-1],
                "lineage": [short_id(x) for x in inst.get("lineage") or []] or [iid],
            }
        return iid

    # ------------------------------------------------------------------ questions
    def _get(self, iid: str) -> dict:
        return self.insts.get(iid, {"display_name": "", "country_code": "", "type": "", "ror": "", "lineage": [iid]})

    def is_indian(self, iid: str) -> bool:
        return self._get(iid)["country_code"] == "IN"

    def is_umbrella(self, iid: str) -> bool:
        return iid in self.umbrella

    def is_academy(self, iid: str) -> bool:
        return iid in self.academy

    def our_lab(self, iid: str) -> str | None:
        """Short name of our lab that this institution is, or belongs to (by lineage)."""
        for x in [iid, *self._get(iid)["lineage"]]:
            if x in self.cfg.lab_by_id:
                return self.cfg.lab_by_id[x]["short"]
        return None

    def cluster(self, iid: str) -> str:
        """First match wins: override, our lab, name rules, lineage rules, late name rules, type, default."""
        ov = self.overrides.get(iid)
        if ov and ov.get("cluster"):
            return ov["cluster"]
        if self.our_lab(iid):
            return self.cfg.cluster_label
        info = self._get(iid)
        for rx, cluster in self.name_rules:
            if rx.search(info["display_name"]):
                return cluster
        for lid in info["lineage"]:
            if lid in self.lineage_rules:
                return self.lineage_rules[lid]
        for rx, cluster in self.late_rules:
            if rx.search(info["display_name"]):
                return cluster
        return self.type_rules.get(info["type"], self.default)

    def label(self, iid: str) -> str:
        lab = self.our_lab(iid)
        if lab:
            return lab
        ov = self.overrides.get(iid)
        if ov and ov.get("short_name"):
            return ov["short_name"]
        return self._get(iid)["display_name"] or iid

    def partner_ok(self, iid: str, own_lab: str | None = None) -> bool:
        """An Indian institution that counts as a partner of `own_lab`: not an umbrella body, not the lab
        itself, and (unless configured otherwise) not the CSIR academy that registers PhD students."""
        if not self.is_indian(iid) or self.is_umbrella(iid):
            return False
        if self.is_academy(iid) and not self.count_academy:
            return False
        return own_lab is None or self.our_lab(iid) != own_lab

    # ------------------------------------------------------------------ export
    def to_frame(self) -> pd.DataFrame:
        rows = [{"inst_id": iid, **info, "cluster": self.cluster(iid), "is_umbrella": self.is_umbrella(iid),
                 "is_academy": self.is_academy(iid), "our_lab": self.our_lab(iid), "label": self.label(iid)}
                for iid, info in self.insts.items()]
        return pd.DataFrame(rows, columns=COLUMNS)
