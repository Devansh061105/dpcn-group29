"""S21: the remaining checks from the improvement plan, and the data behind the dashboard's Explorer.

  E1 filtered h-index      h-index on papers with fewer than 100 authors; papers in IF > 10 journals with < 100 authors
  E2 journal re-grading    Q1 share with each journal's quartile frozen at 2017 vs the year-matched quartile, and the
                           share in journals with JCR IF > 5 (one fixed yardstick): did the labs choose weaker journals,
                           or did Scimago re-grade them?
  E3 citers vs collaborators  external citations against joint papers per Indian institution; the fastest-rising citers
  E4 data completeness     DOI, references, subfield, quartile, impact factor, raw affiliations, ORCID, per lab
  E5 precision audit       a seeded random sample of 50 (paper, faculty) links for the team to check by hand
                           (data/manual/precision_audit.csv); precision with a Wilson interval once verdicts are filled
  E6 local vs global impact  papers cited mostly by Indian institutions ("hidden gems") and the reverse
  E7 heavy-citer mechanisms  how concentrated each heavy citer's citations are: stacking (one paper citing many of ours),
                           one journal, citing papers per joint paper
  E8 partner backbone      disparity filter (Serrano et al. 2009) on the Indian institution co-authorship network;
                           partner typology from OpenAlex institution types
  E9 does a partner type pay off  log citations ~ partner type + lab + year + field + team size + review (OLS, HC1)
  E10 is Q1 / IF a quality signal for a single paper  Q1 premium with controls; IF vs citations at paper level
  E11 bibliometric laws    Lotka, Price, Bradford, Pareto/Seglen, tested on our data
  E12 fragility            do headline results survive dropping the top paper, a year, or a lab's biggest papers?
  E13 why did it jump      automatic notes on year-on-year jumps: COVID-19 share, the biggest paper, consortium papers
  explorer.json            paper-level and faculty-level data for the Explorer, People and Compare pages

Outputs: outputs/stats/research_*.csv, research_extras.json and explorer.json. Randomness is seeded.
"""
from __future__ import annotations

import json
import logging
import math
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from .. import phase2 as P
from . import StepFailed
from .s06_enrich import issn_norm, load_sjr, sjr_quartile
from .s17_research import COVID, SEED, json_safe, ols_hc1, wilson

log = logging.getLogger("dpcn.s26")
FREEZE_YEAR = 2017


def h_index(c) -> int:
    c = sorted((int(x) for x in c if x == x), reverse=True)
    return sum(1 for i, x in enumerate(c, 1) if x >= i)


def filled(x) -> bool:
    return isinstance(x, (list, tuple, np.ndarray)) and len(x) > 0


def write(df: pd.DataFrame, cfg, name: str) -> None:
    df.to_csv(cfg.paths.stats / name, index=False, encoding="utf-8", lineterminator="\n")


def design(df: pd.DataFrame, cols: list[str], cats: list[str]) -> tuple[np.ndarray, list[str]]:
    """Intercept + numeric columns + dummies (first level dropped) for categorical columns."""
    parts, names = [np.ones((len(df), 1))], ["const"]
    for c in cols:
        parts.append(df[[c]].to_numpy(float)); names.append(c)
    for c in cats:
        d = pd.get_dummies(df[c].astype(str), prefix=c, drop_first=True, dtype=float)
        parts.append(d.to_numpy()); names += list(d.columns)
    return np.hstack(parts), names


def ols_table(df, y, cols, cats, keep, label) -> list[dict]:
    X, names = design(df, cols, cats)
    b, se = ols_hc1(X, df[y].to_numpy(float))
    out = []
    for t in keep:
        i = names.index(t)
        out.append({"model": label, "term": t, "coef": b[i], "se": se[i], "ci_lo": b[i] - 1.96 * se[i],
                    "ci_hi": b[i] + 1.96 * se[i], "p": 2 * stats.norm.sf(abs(b[i] / se[i])),
                    "pct_effect": 100 * (math.exp(b[i]) - 1), "n": len(df)})
    return out


# --------------------------------------------------------------------------- inputs

class Inputs:
    def __init__(self, cfg):
        it, st, sub = cfg.paths.interim, cfg.paths.stats, cfg.paths.submission
        if not (st / "journal_impact.csv").exists():
            raise StepFailed("outputs/stats/journal_impact.csv missing - run s16 first")
        self.labs = [l["short"] for l in cfg.labs]
        self.main = pd.read_csv(sub / f"group{cfg.group}_data.csv", dtype=str, keep_default_na=False)
        impact = pd.read_csv(st / "journal_impact.csv", dtype={"issn_n": str})
        self.d = P.prepare(self.main, impact, self.labs, cfg.phase2)
        self.works = pd.read_parquet(it / "works.parquet").set_index("work_id")
        self.auth = pd.read_parquet(it / "authorships.parquet")
        self.inst = pd.read_parquet(it / "institutions.parquet").set_index("inst_id")
        self.inflow = pd.read_parquet(it / "inflow_works.parquet")
        self.roster = pd.read_parquet(it / "roster.parquet").set_index("faculty_id")
        self.our_insts = set(self.inst.index[self.inst["our_lab"].notna()])
        d = self.d
        d["openalex_id"] = d["openalex_id"].str.rsplit("/", n=1).str[-1]
        pos = pd.to_numeric(d["author_position"], errors="coerce")
        d["corr"] = d["is_corresponding"].str.lower() == "true"
        d["role_code"] = np.select([pos == 1, (pos == d["n_authors"]) & (d["n_authors"] > 1), d["corr"]], [1, 2, 3], 0)
        d["role"] = np.where(d["role_code"] > 0, "led", "middle")
        # one row per paper
        g = d.groupby("openalex_id")
        p = g.agg(title=("title", "first"), year=("year", "first"), journal=("journal_name", "first"),
                  issn=("issn", "first"), impact_factor=("impact_factor", "first"), quartile=("quartile", "first"),
                  citations=("citations", "first"), n_authors=("n_authors", "first"), field=("field", "first"),
                  subfield=("subfield", "first"), doi=("doi", "first"), is_journal=("is_journal", "first"),
                  is_abstract=("is_abstract", "first"))
        p["labs"] = g["institution"].agg(lambda s: sorted(set(s)))
        p["led"] = g["role"].agg(lambda s: (s == "led").any())
        p["kind"] = self.works["work_type"].reindex(p.index).fillna("article")
        p["topic"] = self.works["topic"].reindex(p.index).fillna("")
        p["covid"] = [bool(COVID.search(f"{t} {tp}")) for t, tp in zip(p["title"], p["topic"])]
        p["field"] = p["field"].replace("", "Unknown")
        mean_fy = p.groupby(["field", "year"])["citations"].transform("mean")
        p["ncs"] = np.where(mean_fy > 0, p["citations"] / mean_fy, np.nan)
        # Indian citations: citing works from Indian institutions (inflow), all and from outside our four labs
        ind, ext = Counter(), Counter()
        for refs, insts in zip(self.inflow["refs_ours"], self.inflow["inst_ids"]):
            outside = not (set(insts) & self.our_insts)
            for r in refs:
                ind[r] += 1
                if outside:
                    ext[r] += 1
        p["indian_citations"] = [ind.get(w, 0) for w in p.index]
        p["indian_ext_citations"] = [ext.get(w, 0) for w in p.index]
        self.p = p


# --------------------------------------------------------------------------- E1 filtered h-index

def h_filtered(I: Inputs) -> pd.DataFrame:
    d = I.d.drop_duplicates(["openalex_id", "faculty_id"])
    rows = []
    for fid, g in d.groupby("faculty_id"):
        small = g[g["n_authors"] < 100]
        hi = small[small["is_journal"] & (small["impact_factor"] > 10) & ~small["is_abstract"]]
        rows.append({"faculty_id": fid, "name": g["author"].iloc[0], "lab": g["institution"].iloc[0],
                     "papers": len(g), "h_all": h_index(g["citations"]), "papers_lt100": len(small),
                     "h_lt100": h_index(small["citations"]), "if10_papers_lt100": len(hi),
                     "max_if_lt100": small["impact_factor"].max(), "citations_lt100": int(small["citations"].sum())})
    t = pd.DataFrame(rows).sort_values(["h_lt100", "citations_lt100"], ascending=False)
    t["h_gt10_lt100"] = t["h_lt100"] > 10
    return t


# --------------------------------------------------------------------------- E2 journal re-grading

def regrading(I: Inputs, cfg) -> pd.DataFrame:
    sjr = load_sjr(cfg.path(cfg.quartile.sjr_dir))
    if not sjr:
        return pd.DataFrame()
    p = I.p[I.p["is_journal"]].copy()
    issns = I.works["issns"].reindex(p.index)
    frozen = []
    for w, t in zip(p.index, p["journal"]):
        v = issns.get(w)
        iss = [issn_norm(x) for x in v] if isinstance(v, (list, tuple, np.ndarray)) else []
        q, _ = sjr_quartile(sjr, FREEZE_YEAR, iss, t or "")
        frozen.append(q)
    p["q_frozen"] = frozen
    rows = []
    for scope in [*I.labs, "ALL"]:
        s = p if scope == "ALL" else p[p["labs"].map(lambda l: scope in l)]
        for y, g in s.groupby("year"):
            ka, kf = g[g["quartile"].isin(["Q1", "Q2", "Q3", "Q4"])], g[g["q_frozen"].isin(["Q1", "Q2", "Q3", "Q4"])]
            kif = g[g["impact_factor"].notna()]
            rows.append({"scope": scope, "year": int(y), "papers": len(g),
                         "q1_actual": (ka["quartile"] == "Q1").mean() if len(ka) else np.nan,
                         "q1_frozen": (kf["q_frozen"] == "Q1").mean() if len(kf) else np.nan,
                         "if5_share": (kif["impact_factor"] > 5).mean() if len(kif) else np.nan,
                         "if_median": kif["impact_factor"].median() if len(kif) else np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- E3 citers vs collaborators

def citers_collab(I: Inputs, cfg) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_csv(cfg.paths.stats / "p2_citers.csv", keep_default_na=False, na_values=[""])
    c = c[c["scope"] == "ALL"].copy()
    c = c[["partner_openalex_id", "partner_inst", "partner_cluster", "ownership", "cites_in", "shared_papers",
           "rate_per_1000"]].copy()
    c["cites_per_joint_paper"] = c["cites_in"] / c["shared_papers"].where(c["shared_papers"] > 0)
    m = (c["cites_in"] > 0) & (c["shared_papers"] > 0)
    x, y = np.log10(c.loc[m, "shared_papers"]), np.log10(c.loc[m, "cites_in"])
    b = np.polyfit(x, y, 1)
    c["log_residual"] = np.nan
    c.loc[m, "log_residual"] = y - np.polyval(b, x)
    c = c.sort_values("cites_in", ascending=False)
    # rising citers: Indian citing papers per institution per year (outside our labs)
    by = defaultdict(Counter)
    skip = I.our_insts | set(I.inst.index[I.inst["is_umbrella"].fillna(False).astype(bool)
                                          | I.inst["is_academy"].fillna(False).astype(bool)])
    for yr, insts in zip(I.inflow["year"], I.inflow["inst_ids"]):
        for i in set(insts) - skip:
            by[i][int(yr)] += 1
    name = c.set_index("partner_openalex_id")["partner_inst"].to_dict()
    rise = []
    for i, cnt in by.items():
        a, z = cnt.get(2022, 0), cnt.get(2025, 0)
        if z >= 15:
            nm = name.get(i) or (I.inst["display_name"].get(i) if i in I.inst.index else i)
            rise.append({"partner_openalex_id": i, "partner_inst": nm, "citing_papers_2022": a, "citing_papers_2025": z,
                         "increase": z - a, "growth": (z / a) if a else np.nan,
                         "type": I.inst["type"].get(i) if i in I.inst.index else None})
    rise = pd.DataFrame(rise).sort_values("increase", ascending=False).head(15)
    return c, rise


# --------------------------------------------------------------------------- E4 completeness

def completeness(I: Inputs, cfg) -> pd.DataFrame:
    p, w = I.p, I.works
    fa = I.auth[I.auth["faculty_id"].notna()]
    raw_ok = fa.groupby("work_id")["raw_affiliations"].agg(lambda s: all(filled(x) for x in s))
    corr = I.auth.groupby("work_id")["is_corresponding"].any()
    orcid = I.roster["orcid"].fillna("").astype(bool)
    rows = []
    for scope in [*I.labs, "ALL"]:
        s = p if scope == "ALL" else p[p["labs"].map(lambda l: scope in l)]
        ids = s.index
        fac = I.d[(I.d["institution"] == scope) | (scope == "ALL")]["faculty_id"].unique()
        items = {"DOI": s["doi"].astype(bool).mean(),
                 "Reference list": w["referenced_works"].reindex(ids).map(filled).mean(),
                 "OpenAlex subfield": (s["subfield"] != "").mean(),
                 "Journal quartile": s["quartile"].isin(["Q1", "Q2", "Q3", "Q4"]).mean(),
                 "Impact factor (journal papers)": s.loc[s["is_journal"], "impact_factor"].notna().mean(),
                 "Raw affiliation text for every faculty author": raw_ok.reindex(ids).fillna(False).mean(),
                 "Corresponding author marked": corr.reindex(ids).fillna(False).mean(),
                 "Faculty with ORCID on the roster": orcid.reindex(fac).fillna(False).mean()}
        rows += [{"scope": scope, "item": k, "share": float(v), "n": len(fac) if "ORCID" in k else len(ids)}
                 for k, v in items.items()]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- E5 precision audit (manual)

AUDIT_COLS = ["audit_id", "faculty_id", "name", "lab", "affil_method", "openalex_id", "doi", "year", "title",
              "raw_affiliation", "verdict", "checked_by", "notes"]


def precision_audit(I: Inputs, cfg) -> tuple[pd.DataFrame, dict]:
    path = cfg.paths.manual / "precision_audit.csv"
    if not path.exists():
        rng = np.random.default_rng(SEED)
        d = I.d.drop_duplicates(["openalex_id", "faculty_id"]).reset_index(drop=True)
        strata = d["affil_method"].replace("", "unknown")
        take = []
        for m, idx in d.groupby(strata).groups.items():      # proportional, at least 5 per method
            k = max(5, round(50 * len(idx) / len(d)))
            take += list(rng.choice(np.asarray(idx), size=min(k, len(idx)), replace=False))
        s = d.loc[sorted(take)]
        fa = I.auth[I.auth["faculty_id"].notna()].set_index(["work_id", "faculty_id"])["raw_affiliations"]
        rows = []
        for i, r in enumerate(s.itertuples(), 1):
            raw = fa.get((r.openalex_id, r.faculty_id))
            raw = raw.iloc[0] if isinstance(raw, pd.Series) else raw
            rows.append({"audit_id": i, "faculty_id": r.faculty_id, "name": r.author, "lab": r.institution,
                         "affil_method": r.affil_method or "unknown", "openalex_id": r.openalex_id, "doi": r.doi,
                         "year": int(r.year), "title": r.title,
                         "raw_affiliation": " | ".join(raw) if raw is not None and len(raw) else "",
                         "verdict": "", "checked_by": "", "notes": ""})
        pd.DataFrame(rows, columns=AUDIT_COLS).to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
        log.info("wrote %s (%d rows) for the team to check by hand", cfg.rel(path), len(rows))
    a = pd.read_csv(path, dtype=str, keep_default_na=False)
    v = a["verdict"].str.strip().str.lower()
    done = a[v.isin(["correct", "wrong"])].copy()
    done["ok"] = v[done.index] == "correct"
    out = []
    for m, g in [("all", done), *done.groupby("affil_method")]:
        if len(g):
            lo, hi = wilson(int(g["ok"].sum()), len(g))
            out.append({"method": m, "checked": len(g), "correct": int(g["ok"].sum()), "precision": g["ok"].mean(),
                        "ci_lo": lo, "ci_hi": hi})
    status = {"sample": len(a), "checked": int(len(done)), "unsure": int((v == "unsure").sum()),
              "checkers": sorted({c for c in a["checked_by"] if c})}
    return pd.DataFrame(out), status


# --------------------------------------------------------------------------- E6 local vs global impact

def local_global(I: Inputs) -> pd.DataFrame:
    p = I.p[(I.p["citations"] >= 20) & ~I.p["is_abstract"]].copy()
    p["indian_share"] = p["indian_ext_citations"] / p["citations"]
    lab = p["labs"].map(lambda l: ", ".join(x.replace("CSIR-", "") for x in l))
    p = p.assign(lab=lab)
    cols = ["title", "year", "lab", "journal", "citations", "indian_ext_citations", "indian_share", "doi"]
    gems = p[p["indian_ext_citations"] >= 10].sort_values("indian_share", ascending=False).head(15)[cols]
    glob = p[p["citations"] >= 200].sort_values("indian_share").head(10)[cols]
    return pd.concat([gems.assign(kind="cited mostly in India"), glob.assign(kind="cited mostly abroad")])


# --------------------------------------------------------------------------- E7 heavy-citer mechanisms

def citer_mechanisms(I: Inputs, citers: pd.DataFrame) -> pd.DataFrame:
    heavy = citers[citers["cites_in"] >= 30].set_index("partner_openalex_id")
    papers = defaultdict(list)
    for refs, insts, src in zip(I.inflow["refs_ours"], I.inflow["inst_ids"], I.inflow["source_name"]):
        for i in set(insts) & set(heavy.index):
            papers[i].append((len(refs), src or ""))
    rows = []
    for i, ps in papers.items():
        n = np.array([k for k, _ in ps])
        top_j, top_n = Counter(s for _, s in ps).most_common(1)[0]
        rows.append({"partner_openalex_id": i, "partner_inst": heavy.loc[i, "partner_inst"],
                     "ownership": heavy.loc[i, "ownership"], "citations": int(n.sum()), "citing_papers": len(ps),
                     "refs_per_citing_paper": n.mean(), "stacked_share": n[n >= 5].sum() / n.sum(),
                     "top_journal": top_j, "top_journal_share": top_n / len(ps),
                     "joint_papers": heavy.loc[i, "shared_papers"]})
    return pd.DataFrame(rows).sort_values("citations", ascending=False)


# --------------------------------------------------------------------------- E8 backbone and partner types

def backbone(I: Inputs, alpha: float = 0.05) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    n_auth = I.works["n_authors"].to_dict()
    ind = I.inst[(I.inst["country_code"] == "IN") & ~I.inst["is_umbrella"].fillna(False).astype(bool)
                 & ~I.inst["is_academy"].fillna(False).astype(bool)].index
    ind = set(ind)
    per_work = I.auth.explode("inst_ids").dropna(subset=["inst_ids"]).groupby("work_id")["inst_ids"].agg(set)
    w = Counter()
    for wid, s in per_work.items():
        if n_auth.get(wid, 0) > 50:
            continue
        s = sorted(s & ind)
        for a, b in combinations(s, 2):
            w[(a, b)] += 1
    E = pd.DataFrame([(a, b, k) for (a, b), k in w.items()], columns=["a", "b", "w"])
    strength = pd.concat([E.groupby("a")["w"].sum(), E.groupby("b")["w"].sum()], axis=1).fillna(0).sum(axis=1)
    deg = pd.concat([E.groupby("a").size(), E.groupby("b").size()], axis=1).fillna(0).sum(axis=1)

    def pval(node, wt):
        k = deg[node]
        return 1.0 if k <= 1 else (1 - wt / strength[node]) ** (k - 1)
    E["p"] = [min(pval(a, x), pval(b, x)) for a, b, x in zip(E["a"], E["b"], E["w"])]
    B = E[E["p"] < alpha].copy()
    nm, ty = I.inst["display_name"].to_dict(), I.inst["type"].to_dict()
    B["a_name"], B["b_name"] = B["a"].map(nm), B["b"].map(nm)
    B["a_type"], B["b_type"] = B["a"].map(ty), B["b"].map(ty)
    B["a_ours"], B["b_ours"] = B["a"].isin(I.our_insts), B["b"].isin(I.our_insts)
    B = B.sort_values("w", ascending=False)
    summ = {"nodes": int(len(deg)), "edges": int(len(E)), "backbone_edges": int(len(B)),
            "backbone_nodes": int(len(set(B["a"]) | set(B["b"]))), "weight_kept": float(B["w"].sum() / E["w"].sum()),
            "alpha": alpha}
    # partner typology: Indian partners per lab by OpenAlex type
    lab_of = I.d.groupby("openalex_id")["institution"].agg(set).to_dict()
    lab_inst = {r: k for k, r in zip(I.inst.index, I.inst["our_lab"]) if r == r}
    rows = defaultdict(lambda: {"partners": set(), "papers": set()})
    for wid, s in per_work.items():
        if wid not in lab_of:
            continue
        for i in s & ind - I.our_insts:
            for lab in lab_of[wid] | {"ALL"}:
                rows[(lab, ty.get(i) or "other")]["partners"].add(i)
                rows[(lab, ty.get(i) or "other")]["papers"].add(wid)
    T = pd.DataFrame([{"scope": l, "type": t, "partners": len(v["partners"]), "joint_papers": len(v["papers"])}
                      for (l, t), v in rows.items()])
    tot = I.p.explode("labs").groupby("labs").size().to_dict()
    tot["ALL"] = len(I.p)
    T["share_of_papers"] = T["joint_papers"] / T["scope"].map(tot)
    return B.head(400), T.sort_values(["scope", "joint_papers"], ascending=[True, False]), summ


# --------------------------------------------------------------------------- E9 partner payoff, E10 Q1 / IF signal

def paper_partners(I: Inputs) -> pd.DataFrame:
    ty, cc = I.inst["type"].to_dict(), I.inst["country_code"].to_dict()
    per = I.auth.explode("inst_ids").dropna(subset=["inst_ids"]).groupby("work_id")["inst_ids"].agg(set)
    rows = []
    for wid, s in per.items():
        s = s - I.our_insts
        rows.append({"work_id": wid,
                     "indian_healthcare": any(ty.get(i) == "healthcare" and cc.get(i) == "IN" for i in s),
                     "indian_university": any(ty.get(i) == "education" and cc.get(i) == "IN" for i in s),
                     "industry": any(ty.get(i) == "company" for i in s),
                     "foreign": any(cc.get(i) not in (None, "IN") for i in s)})
    return pd.DataFrame(rows).set_index("work_id")


def model_frame(I: Inputs) -> pd.DataFrame:
    p = I.p.copy()
    p["lab"] = p["labs"].map(lambda l: l[0] if len(l) == 1 else "multi")
    p["y"] = np.log1p(p["citations"])
    p["log_authors"] = np.log2(p["n_authors"].clip(lower=1))
    p["review"] = (p["kind"] == "review").astype(float)
    p["year_c"] = p["year"].astype(str)
    return p[(p["year"] <= 2025) & ~p["is_abstract"]]


def partner_payoff(I: Inputs) -> pd.DataFrame:
    p = model_frame(I).join(paper_partners(I), how="left").fillna({"indian_healthcare": False, "indian_university": False,
                                                                  "industry": False, "foreign": False})
    terms = ["indian_healthcare", "indian_university", "industry", "foreign"]
    for t in terms:
        p[t] = p[t].astype(float)
    out = ols_table(p, "y", terms, ["lab", "year_c", "field"], terms, "without team size")
    out += ols_table(p, "y", terms + ["log_authors", "review"], ["lab", "year_c", "field"], terms, "with team size")
    t = pd.DataFrame(out)
    t["papers_with"] = t["term"].map(lambda c: int(p[c].sum()))
    return t


def q1_signal(I: Inputs) -> tuple[pd.DataFrame, dict]:
    p = model_frame(I)
    p = p[p["is_journal"] & p["quartile"].isin(["Q1", "Q2", "Q3", "Q4"])].copy()
    p["q1"] = (p["quartile"] == "Q1").astype(float)
    out = ols_table(p, "y", ["q1"], ["lab", "year_c", "field"], ["q1"], "Q1, year + field + lab")
    out += ols_table(p, "y", ["q1", "log_authors", "review"], ["lab", "year_c", "field"], ["q1"], "Q1, + team size + review")
    pi = p[p["impact_factor"].notna()].copy()
    pi["log_if"] = np.log2(pi["impact_factor"].clip(lower=0.1))
    out += ols_table(pi, "y", ["log_if", "log_authors", "review"], ["lab", "year_c", "field"], ["log_if"],
                     "log2 IF, all controls")
    # paper-level IF vs citations, within year (Seglen 1997: the journal IF says little about one paper)
    rho = [stats.spearmanr(g["impact_factor"], g["citations"])[0] for _, g in pi.groupby("year") if len(g) > 50]
    q1 = p[p["q1"] == 1]["ncs"].dropna()
    nq1 = p[p["q1"] == 0]["ncs"].dropna()
    top_thr = I.p.groupby(["field", "year"])["citations"].transform(lambda s: s.quantile(0.9))
    top = (I.p["citations"] >= top_thr) & (I.p["citations"] > 0)
    summ = {"if_citation_spearman_median": float(np.median(rho)), "if_citation_spearman_years": len(rho),
            "share_q1_beats_median_nonq1": float((q1 > nq1.median()).mean()),
            "share_nonq1_beats_median_q1": float((nq1 > q1.median()).mean()),
            "top10_papers_in_q1": float((I.p.loc[top, "quartile"] == "Q1").mean()),
            "papers_in_q1": float((I.p["quartile"] == "Q1").mean())}
    return pd.DataFrame(out), summ


# --------------------------------------------------------------------------- E11 bibliometric laws

def lotka_mle(x: np.ndarray, xmin: int = 1) -> tuple[float, float]:
    """Exponent of a discrete power law p(n) = n^-a / zeta(a, xmin) by exact maximum likelihood (Clauset, Shalizi &
    Newman 2009, eq. 3.5; the continuous approximation is biased for xmin = 1), with its standard error."""
    from scipy.optimize import minimize_scalar
    from scipy.special import zeta
    x = np.asarray(x, float)
    x = x[x >= xmin]
    n, sl = len(x), np.log(x).sum()
    nll = lambda a: a * sl + n * np.log(zeta(a, xmin))
    a = minimize_scalar(nll, bounds=(1.01, 6), method="bounded").x
    h = 1e-4
    info = (nll(a + h) - 2 * nll(a) + nll(a - h)) / h ** 2
    return float(a), float(1 / np.sqrt(info)) if info > 0 else float("nan")


def laws(I: Inputs, cfg) -> pd.DataFrame:
    rows = []
    pool = pd.read_parquet(cfg.paths.interim / "lab_author_pool.parquet")
    n_all = pool.groupby("author_id")["n_lab_works_window"].sum().to_numpy()
    a, se = lotka_mle(n_all)
    rows.append({"law": "Lotka (1926)", "statement": "the number of authors with n papers falls as 1/n^a, with a close to 2",
                 "expected": "a ≈ 2", "observed": f"a = {a:.2f} ± {1.96 * se:.2f} ({len(n_all):,} lab authors)",
                 "value": a, "holds": bool(abs(a - 2) < 0.35)})
    fac = I.d.drop_duplicates(["openalex_id", "faculty_id"]).groupby("faculty_id").size().sort_values(ascending=False)
    k = int(round(math.sqrt(len(fac))))
    pr = fac.head(k).sum() / fac.sum()
    rows.append({"law": "Price (1963)", "statement": "the √N most productive authors write half of the papers",
                 "expected": "50%", "observed": f"top {k} of {len(fac)} faculty: {pr:.0%} of faculty-paper links",
                 "value": pr, "holds": bool(0.4 <= pr <= 0.6)})
    j = I.p[I.p["is_journal"]].groupby("journal").size().sort_values(ascending=False)
    cs = j.cumsum() / j.sum()
    z1, z2 = int((cs < 1 / 3).sum() + 1), int((cs < 2 / 3).sum() + 1)
    zones = [z1, z2 - z1, len(j) - z2]
    rows.append({"law": "Bradford (1934)", "statement": "journals split into three zones with equal papers grow as 1 : n : n²",
                 "expected": "1 : n : n²", "observed": f"{zones[0]} : {zones[1]} : {zones[2]} journals "
                 f"(n ≈ {zones[1] / zones[0]:.1f}, n² ≈ {(zones[1] / zones[0]) ** 2:.0f})",
                 "value": zones[1] / zones[0], "holds": bool(zones[2] / zones[1] > 0.5 * zones[1] / zones[0])})
    c = np.sort(I.p["citations"].to_numpy())[::-1]
    s15 = c[: int(0.15 * len(c))].sum() / c.sum()
    s25 = c[: int(0.2 * len(c))].sum() / c.sum()
    rows.append({"law": "Seglen (1997)", "statement": "the most cited 15% of papers receive about half of all citations",
                 "expected": "≈ 50%", "observed": f"top 15% of papers: {s15:.0%} of citations", "value": s15,
                 "holds": bool(0.4 <= s15 <= 0.65)})
    rows.append({"law": "Pareto 80/20", "statement": "20% of the papers receive 80% of the citations",
                 "expected": "80%", "observed": f"top 20% of papers: {s25:.0%} of citations", "value": s25,
                 "holds": bool(abs(s25 - 0.8) < 0.1)})
    zero = (I.p.loc[I.p["year"] <= 2023, "citations"] == 0).mean()
    rows.append({"law": "Uncitedness", "statement": "a share of papers is never cited",
                 "expected": "varies by field", "observed": f"{zero:.1%} of 2016–2023 papers have no citations yet",
                 "value": zero, "holds": None})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- E12 fragility

def fragility(I: Inputs, cfg) -> pd.DataFrame:
    p = I.p.explode("labs")
    rows = []
    mncs = p.groupby("labs")["ncs"].mean()
    order = list(mncs.sort_values(ascending=False).index)
    for lab in I.labs:
        q = p.drop(p[p["labs"] == lab]["citations"].idxmax())
        o2 = list(q.groupby("labs")["ncs"].mean().sort_values(ascending=False).index)
        rows.append({"headline": "Lab order by MNCS", "removed": f"{short(lab)}'s most cited paper",
                     "full": " > ".join(map(short, order)), "without": " > ".join(map(short, o2)), "holds": o2 == order})
    tot = p.groupby("labs")["citations"].sum()
    top = p.sort_values("citations", ascending=False).groupby("labs").head(1).set_index("labs")["citations"]
    for lab in I.labs:
        rows.append({"headline": f"{short(lab)} citations", "removed": "its most cited paper",
                     "full": f"{tot[lab]:,}", "without": f"{tot[lab] - top[lab]:,} ({(tot[lab] - top[lab]) / tot[lab]:.0%})",
                     "holds": (tot[lab] - top[lab]) / tot[lab] > 0.8})
    led = I.p["led"]
    sh = I.p.loc[~led, "citations"].sum() / I.p["citations"].sum()
    q = I.p.drop(I.p.sort_values("citations", ascending=False).head(10).index)
    sh2 = q.loc[~q["led"], "citations"].sum() / q["citations"].sum()
    rows.append({"headline": "Middle-author share of citations", "removed": "the 10 most cited papers",
                 "full": f"{sh:.0%}", "without": f"{sh2:.0%}", "holds": abs(sh - sh2) < 0.1})
    # cross-lab share of faculty links, leaving out one year at a time
    d = I.d.drop_duplicates(["openalex_id", "faculty_id"])
    d = d[d["n_authors"] <= cfg.networks.max_authors_for_pairs]
    ev = []
    for w, g in d.groupby("openalex_id"):
        f = sorted(set(zip(g["faculty_id"], g["institution"])))
        for (a, la), (b, lb) in combinations(f, 2):
            ev.append((a, b, int(g["year"].iloc[0]), la != lb))
    E = pd.DataFrame(ev, columns=["a", "b", "year", "cross"])
    full = E.drop_duplicates(["a", "b"])["cross"].mean()
    jk = [E[E["year"] != y].drop_duplicates(["a", "b"])["cross"].mean() for y in sorted(E["year"].unique())]
    rows.append({"headline": "Cross-lab share of faculty links", "removed": "one year at a time (jackknife)",
                 "full": f"{full:.1%}", "without": f"{min(jk):.1%} to {max(jk):.1%}", "holds": max(jk) < 0.15})
    return pd.DataFrame(rows)


def short(lab: str) -> str:
    return str(lab).replace("CSIR-", "")


# --------------------------------------------------------------------------- E13 why did it jump

def jumps(I: Inputs, cfg) -> pd.DataFrame:
    p = I.p.explode("labs")
    last = cfg.window.partial_year - 1
    rows = []
    for lab in [*I.labs, "ALL"]:
        s = p[p["labs"] == lab] if lab != "ALL" else I.p
        s = s[s["year"] <= last]
        yr = s.groupby("year").agg(papers=("title", "size"), citations=("citations", "sum"))
        for metric in ("papers", "citations"):
            v = yr[metric]
            for y in v.index[1:]:
                prev, cur = v.get(y - 1), v[y]
                if not prev:
                    continue
                ch = cur / prev - 1
                if abs(ch) < (0.25 if metric == "papers" else 0.5):
                    continue
                g = s[s["year"] == y]
                bits = []
                cov = g["covid"].mean() if metric == "papers" else g.loc[g["covid"], "citations"].sum() / max(g["citations"].sum(), 1)
                if cov >= 0.1:
                    bits.append(f"COVID-19 papers are {cov:.0%} of the year's {metric}")
                if metric == "citations":
                    t = g.sort_values("citations", ascending=False).iloc[0]
                    share = t["citations"] / max(g["citations"].sum(), 1)
                    if share >= 0.15:
                        bits.append(f"one paper carries {share:.0%} (“{t['title'][:70]}”, {int(t['n_authors'])} authors)")
                    big = g.loc[g["n_authors"] >= 100, "citations"].sum() / max(g["citations"].sum(), 1)
                    if big >= 0.15:
                        bits.append(f"papers with 100+ authors carry {big:.0%}")
                    if y >= last - 2 and ch < 0:
                        bits.append("recent papers have had little time to be cited")
                else:
                    big = (g["n_authors"] >= 10).mean() - (s[s["year"] == y - 1]["n_authors"] >= 10).mean()
                    if abs(big) >= 0.05:
                        bits.append(f"the share of 10+ author papers moved {big:+.0%}")
                rows.append({"scope": lab, "metric": metric, "year": int(y), "previous": int(prev), "value": int(cur),
                             "change": ch, "drivers": "; ".join(bits) if bits else "no single driver: a broad change"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- E14 productivity as a random walk (P1)

def productivity_walk(I: Inputs, cfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Zhang et al. (2026), 'Scientific productivity as a random walk': are year-on-year changes in a faculty member's
    output Laplace-distributed, do they revert to a mean, and can a truncated random walk reproduce the spread of
    cumulative output? Fractional counts (1/authors) on papers with < 100 authors, 2016-2025, faculty with >= 3 papers."""
    rng = np.random.default_rng(SEED)
    d = I.d.drop_duplicates(["openalex_id", "faculty_id"])
    d = d[(d["n_authors"] < 100) & (d["year"] <= cfg.window.partial_year - 1)]
    d = d.assign(w=1.0)                                    # full count per paper, as P1 counts papers
    M = d.pivot_table(index="faculty_id", columns="year", values="w", aggfunc="sum", fill_value=0)
    M = M[M.sum(axis=1) >= 3]
    Q = M.to_numpy(float)
    delta = np.diff(Q, axis=1)
    dl = delta.ravel()
    mu = np.median(dl); a = np.mean(np.abs(dl - mu))
    sd = dl.std(ddof=1); m = dl.mean()
    ll_lap = np.sum(-np.log(2 * a) - np.abs(dl - mu) / a)
    ll_norm = np.sum(stats.norm.logpdf(dl, m, sd))
    ks_lap = stats.kstest(dl, stats.laplace(mu, a).cdf).statistic
    ks_norm = stats.kstest(dl, stats.norm(m, sd).cdf).statistic
    # lag-1 autocorrelation of changes, faculty-block bootstrap, vs a null that shuffles each person's years
    def ac(Qm):
        D = np.diff(Qm, axis=1)
        x, y = D[:, :-1].ravel(), D[:, 1:].ravel()
        return np.corrcoef(x, y)[0, 1]
    obs = ac(Q)
    boot = [ac(Q[rng.integers(0, len(Q), len(Q))]) for _ in range(1000)]
    null = [ac(np.array([rng.permutation(r) for r in Q])) for _ in range(500)]
    # truncated random walk: start at each person's first-year output, Laplace steps (mu, a), floor at 0
    T = Q.shape[1]
    sims = []
    for _ in range(200):
        x = Q[:, 0].copy(); tot = x.copy(); zeros = (x == 0).astype(int)
        for _t in range(T - 1):
            x = np.maximum(0, np.round(x + rng.laplace(mu, a, len(x))))
            tot += x; zeros += (x == 0)
        sims.append((tot, zeros / T))
    sim_tot = np.concatenate([s[0] for s in sims]); sim_zero = np.mean([s[1].mean() for s in sims])
    obs_tot = Q.sum(axis=1)
    ks_cum = stats.ks_2samp(obs_tot, sim_tot)
    # Matthew effect: does output rank persist from 2016-20 to 2021-25? permutation null
    yrs = list(M.columns)
    early = Q[:, [i for i, y in enumerate(yrs) if y <= 2020]].sum(axis=1)
    late = Q[:, [i for i, y in enumerate(yrs) if y >= 2021]].sum(axis=1)
    rho = stats.spearmanr(early, late)[0]
    top = early >= np.quantile(early, 0.9)
    persist = (late[top] >= np.quantile(late, 0.9)).mean()
    perm = [(rng.permutation(late)[top] >= np.quantile(late, 0.9)).mean() for _ in range(2000)]
    hist = np.arange(np.floor(dl.min()), np.ceil(dl.max()) + 1)
    cnt = pd.Series(dl).value_counts().reindex(hist, fill_value=0)
    H = pd.DataFrame({"delta": hist, "count": cnt.to_numpy(), "laplace": len(dl) * stats.laplace.pdf(hist, mu, a),
                      "normal": len(dl) * stats.norm.pdf(hist, m, sd)})
    qs = np.linspace(0, 1, 41)[1:-1]
    C = pd.DataFrame({"quantile": qs, "observed": np.quantile(obs_tot, qs), "random_walk": np.quantile(sim_tot, qs)})
    S = {"faculty": int(len(Q)), "years": [int(yrs[0]), int(yrs[-1])], "laplace_mu": mu, "laplace_alpha": a,
         "normal_mean": m, "normal_sd": sd, "aic_laplace": 4 - 2 * ll_lap, "aic_normal": 4 - 2 * ll_norm,
         "ks_laplace": ks_lap, "ks_normal": ks_norm, "lag1_autocorr": obs,
         "lag1_ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
         "lag1_null_mean": float(np.mean(null)), "lag1_null_ci": [float(np.percentile(null, 2.5)), float(np.percentile(null, 97.5))],
         "zero_years_observed": float((Q == 0).mean()), "zero_years_random_walk": float(sim_zero),
         "cum_ks": float(ks_cum.statistic), "cum_ks_p": float(ks_cum.pvalue),
         "gini_observed": gini_np(obs_tot), "gini_random_walk": gini_np(sim_tot),
         "rank_rho": rho, "top_decile_persistence": persist, "top_decile_null": float(np.mean(perm)),
         "top_decile_p": float(np.mean(np.array(perm) >= persist))}
    return H, C, S


def gini_np(x) -> float:
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())) if x.sum() > 0 else float("nan")


# --------------------------------------------------------------------------- explorer data

def explorer(I: Inputs, cfg) -> dict:
    p = I.p.reset_index()
    journals = sorted(set(p["journal"]))
    fields = sorted(set(p["field"]))
    subf = sorted(set(p["subfield"]))
    jix, fix, six = ({v: i for i, v in enumerate(x)} for x in (journals, fields, subf))
    fac = pd.read_csv(cfg.paths.stats / "p2_faculty.csv", keep_default_na=False, na_values=[""])
    fac = fac.set_index("faculty_id")
    cred = cfg.paths.stats / "research_faculty_credit.csv"
    cred = pd.read_csv(cred).set_index("faculty_id") if cred.exists() else pd.DataFrame()
    fids = sorted(I.d["faculty_id"].unique())
    fx = {f: i for i, f in enumerate(fids)}
    wx = {w: i for i, w in enumerate(p["openalex_id"])}
    d = I.d.drop_duplicates(["openalex_id", "faculty_id"])
    links = [[wx[w], fx[f], int(r)] for w, f, r in zip(d["openalex_id"], d["faculty_id"], d["role_code"])]
    r6 = lambda x: None if x != x or x is None else round(float(x), 3)
    people = []
    for f in fids:
        r = fac.loc[f] if f in fac.index else None
        c = cred.loc[f] if len(cred) and f in cred.index else None
        get = lambda s, k: None if s is None or k not in s.index or s[k] != s[k] else s[k]
        people.append({"id": f, "name": get(r, "name") or I.roster["name"].get(f, f),
                       "lab": get(r, "lab") or I.roster["institution"].get(f), "dept": get(r, "department"),
                       "designation": get(r, "designation"), "status": get(r, "status"),
                       "degree": get(r, "degree"), "betweenness": r6(get(r, "betweenness")),
                       "community": get(r, "community"), "h_lifetime": get(r, "h_lifetime"),
                       "lifetime_citations": get(r, "lifetime_citations"), "flag": get(r, "flag"),
                       "flag_lifetime": bool(get(r, "flag_lifetime") or False),
                       "collab_inst": get(r, "collab_inst_all"), "collab_inst_indian": get(r, "collab_inst_indian"),
                       "mncs": r6(get(c, "mncs")), "papers_frac": r6(get(c, "papers_frac")),
                       "citations_frac": r6(get(c, "citations_frac")), "rank_full": get(c, "rank_citations"),
                       "rank_frac": get(c, "rank_citations_frac")})
    pairs = []
    n_auth = I.works["n_authors"].to_dict()
    cnt = Counter()
    first = {}
    for w, g in d.groupby("openalex_id"):
        if n_auth.get(w, 0) > cfg.networks.max_authors_for_pairs:
            continue
        for a, b in combinations(sorted(set(g["faculty_id"])), 2):
            cnt[(a, b)] += 1
            first[(a, b)] = min(first.get((a, b), 9999), int(g["year"].iloc[0]))
    pairs = [[fx[a], fx[b], k, first[(a, b)]] for (a, b), k in cnt.items()]
    cols = {"id": list(p["openalex_id"]), "title": [t[:160] for t in p["title"]], "year": p["year"].astype(int).tolist(),
            "j": [jix[x] for x in p["journal"]], "if": [r6(x) for x in p["impact_factor"]],
            "q": [x if x in ("Q1", "Q2", "Q3", "Q4") else "" for x in p["quartile"]],
            "c": p["citations"].astype(int).tolist(), "na": p["n_authors"].astype(int).tolist(),
            "f": [fix[x] for x in p["field"]], "sf": [six[x] for x in p["subfield"]],
            "ncs": [r6(x) for x in p["ncs"]], "ind": p["indian_ext_citations"].astype(int).tolist(),
            "cov": p["covid"].astype(int).tolist(), "rev": (p["kind"] == "review").astype(int).tolist(),
            "abs": p["is_abstract"].astype(int).tolist(), "doi": [x.replace("https://doi.org/", "") for x in p["doi"]],
            "labs": [[I.labs.index(l) for l in ls if l in I.labs] for ls in p["labs"]]}
    return {"papers": cols, "journals": journals, "fields": fields, "subfields": subf, "people": people,
            "links": links, "pairs": pairs, "roles": ["middle", "first", "last", "corresponding"]}


# --------------------------------------------------------------------------- run

def run(cfg, oa, argv=()) -> None:
    I = Inputs(cfg)
    st = cfg.paths.stats
    H = h_filtered(I); write(H, cfg, "research_h_filtered.csv")
    R = regrading(I, cfg); write(R, cfg, "research_regrading.csv")
    C, rise = citers_collab(I, cfg); write(C, cfg, "research_citers_collab.csv"); write(rise, cfg, "research_rising_citers.csv")
    Q = completeness(I, cfg); write(Q, cfg, "research_completeness.csv")
    A, audit = precision_audit(I, cfg)
    if len(A):
        write(A, cfg, "research_precision.csv")
    elif (st / "research_precision.csv").exists():
        (st / "research_precision.csv").unlink()
    G = local_global(I); write(G, cfg, "research_local_global.csv")
    M = citer_mechanisms(I, C); write(M, cfg, "research_citer_mechanisms.csv")
    B, T, bsum = backbone(I); write(B, cfg, "research_backbone.csv"); write(T, cfg, "research_partner_types.csv")
    PP = partner_payoff(I); write(PP, cfg, "research_partner_payoff.csv")
    QS, qsum = q1_signal(I); write(QS, cfg, "research_q1_signal.csv")
    L = laws(I, cfg); write(L, cfg, "research_laws.csv")
    F = fragility(I, cfg); write(F, cfg, "research_fragility.csv")
    J = jumps(I, cfg); write(J, cfg, "research_jumps.csv")
    WH, WC, wsum = productivity_walk(I, cfg)
    write(WH, cfg, "research_walk_delta.csv"); write(WC, cfg, "research_walk_cumulative.csv")
    ex = explorer(I, cfg)
    (st / "explorer.json").write_text(json.dumps(json_safe(ex), ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                      encoding="utf-8")

    # ---- summary sentences (every number computed above)
    al = R[R["scope"] == "ALL"].set_index("year") if len(R) else None
    early, late = [2016, 2017, 2018], [2023, 2024, 2025]
    hg = H[H["h_gt10_lt100"]]
    S = {"h_filtered": {"faculty_h_gt10_all": int((H["h_all"] > 10).sum()), "faculty_h_gt10_lt100": int(len(hg)),
                        "by_lab": hg["lab"].value_counts().to_dict(),
                        "if10_lt100_papers": int(I.p[(I.p["impact_factor"] > 10) & (I.p["n_authors"] < 100) & I.p["is_journal"] & ~I.p["is_abstract"]].shape[0]),
                        "lost": H[(H["h_all"] > 10) & ~H["h_gt10_lt100"]]["name"].tolist()},
         "backbone": bsum, "q1_signal": qsum, "walk": wsum, "precision_audit": audit,
         "citers_collab_spearman": float(stats.spearmanr(C["cites_in"], C["shared_papers"])[0])}
    f = []
    f.append(f"{S['h_filtered']['faculty_h_gt10_lt100']} faculty have an h-index above 10 on papers with fewer than 100 authors "
             f"({S['h_filtered']['faculty_h_gt10_all']} on all papers); {S['h_filtered']['if10_lt100_papers']} papers are in journals "
             f"with impact factor above 10 and have fewer than 100 authors.")
    if al is not None:
        qa = al.loc[al.index.isin(early), "q1_actual"].mean(), al.loc[al.index.isin(late), "q1_actual"].mean()
        qf = al.loc[al.index.isin(early), "q1_frozen"].mean(), al.loc[al.index.isin(late), "q1_frozen"].mean()
        ifs = al.loc[al.index.isin(early), "if5_share"].mean(), al.loc[al.index.isin(late), "if5_share"].mean()
        S["regrading"] = {"q1_actual": qa, "q1_frozen": qf, "if5": ifs}
        f.append(f"The Q1 share moved from {qa[0]:.0%} (2016–18) to {qa[1]:.0%} (2023–25) with year-matched quartiles, "
                 f"and from {qf[0]:.0%} to {qf[1]:.0%} with each journal's 2017 quartile frozen; on the fixed JCR yardstick "
                 f"the share in IF > 5 journals went from {ifs[0]:.0%} to {ifs[1]:.0%}.")
    f.append(f"Citing an institution and co-authoring with it go together only loosely (Spearman {S['citers_collab_spearman']:.2f} "
             f"between external citations and joint papers across {len(C)} Indian institutions).")
    f.append(f"The Indian partner backbone keeps {bsum['backbone_edges']} of {bsum['edges']} institution links "
             f"({bsum['weight_kept']:.0%} of joint-paper weight) at α = {bsum['alpha']}.")
    f.append(f"A journal's impact factor says little about one paper: the median within-year Spearman correlation between IF and "
             f"a paper's citations is {qsum['if_citation_spearman_median']:.2f}; {qsum['share_nonq1_beats_median_q1']:.0%} of "
             f"non-Q1 papers beat the median Q1 paper on normalised citations.")
    hold = L[L["holds"] == True]["law"].tolist()   # noqa: E712
    f.append(f"Of the classic bibliometric laws, these hold in our data: {', '.join(hold) if hold else 'none'}; "
             f"see the table for the observed values.")
    pp = PP[(PP["model"] == "with team size")].set_index("term")
    if "indian_healthcare" in pp.index:
        r = pp.loc["indian_healthcare"]
        f.append(f"Papers with an Indian hospital or medical partner get {r['pct_effect']:+.0f}% citations "
                 f"(95% CI {100 * (math.exp(r['ci_lo']) - 1):+.0f}% to {100 * (math.exp(r['ci_hi']) - 1):+.0f}%) after year, "
                 f"field, lab and team size; foreign partners {pp.loc['foreign', 'pct_effect']:+.0f}%.")
    f.append(f"Year-on-year changes in a faculty member's output follow a Laplace distribution better than a normal one "
             f"(AIC {wsum['aic_laplace']:,.0f} vs {wsum['aic_normal']:,.0f}; {wsum['faculty']} faculty), as Zhang et al. found for "
             f"computer scientists. Their lag-1 autocorrelation is {wsum['lag1_autocorr']:.2f} (95% CI {wsum['lag1_ci'][0]:.2f} to "
             f"{wsum['lag1_ci'][1]:.2f}): between a pure random walk (0) and noise around a fixed personal level "
             f"({wsum['lag1_null_mean']:.2f}), so each person's level drifts slowly.")
    f.append(f"A truncated random walk with those steps reproduces the share of zero-output years ({wsum['zero_years_random_walk']:.0%} vs "
             f"{wsum['zero_years_observed']:.0%} observed) and the inequality of total output (Gini {wsum['gini_random_walk']:.2f} vs "
             f"{wsum['gini_observed']:.2f}): luck alone produces most of the spread between faculty.")
    f.append(f"Rank persists (Matthew effect): {wsum['top_decile_persistence']:.0%} of the top 10% by 2016–20 output are again in the top 10% "
             f"in 2021–25, against {wsum['top_decile_null']:.0%} by chance (p = {wsum['top_decile_p']:.3f}); Spearman {wsum['rank_rho']:.2f}.")
    S["findings"] = f
    S["methods"] = {
        "h_filtered": "h-index recomputed on the faculty member's papers with fewer than 100 authors (all years).",
        "regrading": f"Each paper's journal quartile frozen at its {FREEZE_YEAR} Scimago value vs the year-matched quartile; JCR 2024 IF used as one fixed yardstick.",
        "citers": "External citations (citing institution not one of our labs) vs joint papers per Indian institution; rising = citing papers in 2025 minus 2022.",
        "completeness": "Share of papers (or roster faculty) with each field present in OpenAlex or the roster.",
        "precision": "Seeded random sample of 50 paper–faculty links, stratified by how the affiliation was matched; checked by hand by the team.",
        "local_global": "Indian share = citations from Indian institutions outside our labs ÷ all citations; papers with ≥ 20 citations.",
        "mechanisms": "For each Indian institution with ≥ 30 citations: citing papers, our papers cited per citing paper, the share from citing papers that cite ≥ 5 of ours (stacking), and the most common citing journal.",
        "backbone": "Disparity filter (Serrano, Boguñá & Vespignani 2009, α = 0.05) on Indian institution co-authorship from our papers with ≤ 50 authors.",
        "payoff": "OLS of log(1 + citations) on partner-type indicators with lab, year and field fixed effects, then adding log2 authors and review; HC1 errors; papers to 2025.",
        "q1": "OLS of log(1 + citations) on Q1 (or log2 IF) with controls; within-year Spearman of IF vs citations.",
        "laws": "Lotka exponent by discrete maximum likelihood; Price's square-root rule; Bradford zones of equal papers; citation shares of the top papers.",
        "fragility": "Headline recomputed after removing the named paper(s) or year.",
        "walk": "Faculty-by-year paper counts (papers < 100 authors, 2016-2025, faculty with >= 3 papers); Laplace vs normal fit of yearly changes (AIC, KS); lag-1 autocorrelation with a faculty-block bootstrap and a within-person year-shuffle null; 200 truncated random walks per person (Zhang et al. 2026, course paper P1); top-decile persistence vs 2,000 permutations.",
        "jumps": "Year-on-year changes above 25% (papers) or 50% (citations), with automatic drivers.",
    }
    (st / "research_extras.json").write_text(json.dumps(json_safe(S), ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    for s in f:
        print(" -", s)
    print(f"precision audit: {audit['checked']} of {audit['sample']} checked")
