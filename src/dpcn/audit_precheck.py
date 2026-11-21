"""First-pass evidence for the hand-checked precision audit (data/manual/precision_audit.csv).

For every sampled (paper, faculty) link it records three independent signals, so the person checking can confirm or
overrule each row quickly:

  precheck_byline       the faculty member's surname is on the paper's author list at Crossref (a second source,
                        independent of OpenAlex); "unavailable" when Crossref has no author list
  precheck_affiliation  the OpenAlex raw affiliation text of that author on that paper names the lab
  precheck_name         the OpenAlex author name on the paper agrees with the roster name (surname + first initial)
  precheck              "consistent" when all available signals agree, otherwise "look closely"

It never fills `verdict` or `checked_by`: those stay with the team member who opens the paper.

    python -m dpcn.audit_precheck
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/manual/precision_audit.csv"
CACHE = ROOT / "data/cache/crossref"
LAB_PATTERNS = {
    "CSIR-CCMB": r"cellular\s*(and|&)\s*molecular\s*biology|\bccmb\b",
    "CSIR-IGIB": r"genomics\s*(and|&)\s*integrative\s*biology|\bigib\b",
    "CSIR-IMTECH": r"microbial\s*technology|\bimtech\b",
    "CSIR-CDRI": r"central\s*drug\s*research|\bcdri\b",
}


def plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", " ", s.lower())


def surname_and_initial(name: str) -> tuple[str, str]:
    parts = [p for p in plain(name).split() if p]
    if not parts:
        return "", ""
    return parts[-1], parts[0][0]


OFFLINE = {"crossref": False}


def crossref_authors(doi: str) -> list[dict] | None:
    doi = doi.replace("https://doi.org/", "").strip()
    if not doi or OFFLINE["crossref"]:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(doi.lower().encode()).hexdigest() + ".json.gz")
    if f.exists():
        data = json.loads(gzip.decompress(f.read_bytes()))
    else:
        try:
            r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=10,
                             headers={"User-Agent": "dpcn-group29-precision-audit/1.0"})
        except requests.RequestException:
            OFFLINE["crossref"] = True          # no network to Crossref: leave the byline check to the person checking
            return None
        time.sleep(0.3)
        data = r.json() if r.status_code == 200 else {"message": {}}
        f.write_bytes(gzip.compress(json.dumps(data).encode()))
    return data.get("message", {}).get("author")


def main() -> None:
    a = pd.read_csv(AUDIT, dtype=str, keep_default_na=False)
    auth = pd.read_parquet(ROOT / "data/interim/authorships.parquet")
    oa_name = auth.dropna(subset=["faculty_id"]).set_index(["work_id", "faculty_id"])["author_name"].to_dict()
    out = {k: [] for k in ("precheck_byline", "precheck_affiliation", "precheck_name", "precheck")}
    for r in a.itertuples():
        sur, ini = surname_and_initial(r.name)
        authors = crossref_authors(r.doi)
        if not authors:
            byline = "not checked" if OFFLINE["crossref"] else "unavailable"
        else:
            fams = {plain(x.get("family", "")).strip() for x in authors} | {plain(x.get("name", "")).split()[-1] for x in authors if x.get("name")}
            fams |= {w for x in authors for w in plain(x.get("family", "") + " " + x.get("given", "")).split()}
            byline = "yes" if sur in fams else "no"
        aff = "yes" if re.search(LAB_PATTERNS.get(r.lab, "$^"), r.raw_affiliation, re.I) else ("no text" if not r.raw_affiliation else "no")
        wid = r.openalex_id.rsplit("/", 1)[-1]
        on = oa_name.get((wid, r.faculty_id), "")
        s2, i2 = surname_and_initial(on)
        name = "yes" if s2 == sur and i2 == ini else ("partly" if s2 == sur or sur in plain(on).split() else "no")
        sig = [byline, aff, name]
        ok = all(x in ("yes", "unavailable", "not checked", "partly") for x in sig) and aff == "yes"
        for k, v in zip(out, sig + ["consistent" if ok else "look closely"]):
            out[k].append(v)
    for k, v in out.items():
        a[k] = v
    cols = [c for c in a.columns if not c.startswith("precheck")] + list(out)
    a[cols].to_csv(AUDIT, index=False, encoding="utf-8", lineterminator="\n")
    print(a["precheck"].value_counts().to_dict())
    print(a[a["precheck"] != "consistent"][["audit_id", "name", "lab", "precheck_byline", "precheck_affiliation", "precheck_name"]].to_string())


if __name__ == "__main__":
    main()
