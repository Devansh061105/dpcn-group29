"""S20: benchmark - how do our four labs compare with other Indian biology institutes?

Every institute (our four labs and the peers in data/manual/peer_institutes.csv) is measured with one identical
OpenAlex query: works with an author whose affiliation lineage includes the institute, published in the window,
type article or review, not retracted. This is WHOLE-INSTITUTE output (students, postdocs, staff and every affiliate
the lineage rolls up), not the faculty-only corpus the rest of the pipeline builds.

  B1 benchmark            papers, papers per year and CAGR, citations per paper, median and mean FWCI (bootstrap CI),
                          top-10% and top-1% shares (OpenAlex citation_normalized_percentile, Wilson CI),
                          international collaboration, open access and review shares, h-index of the window's papers,
                          Gini of citations, effective number of papers (sum c)^2 / sum c^2, subfield count and
                          Shannon entropy; rank of every institute on each main metric
  B2 specialisation vs India  revealed comparative advantage RCA = institute share of a subfield / India's share,
                          India = all works with an Indian affiliation (same type, retraction and year filters)
  B3 gravity model        joint papers and citations between each lab and each Indian partner institution, Poisson
                          regression on log(distance + 10 km), log(partner size) and lab fixed effects; distance
                          elasticity of collaboration vs citation (with a test of their difference)

Outputs: outputs/stats/research_benchmark*.csv, research_rca_india.csv, research_gravity.csv and
research_benchmark.json. Randomness (bootstrap) is seeded.
"""
from __future__ import annotations

import json
import logging
import math

import numpy as np
import pandas as pd
from scipy import stats

from ..openalex import batches, short_id
from . import StepFailed
from .s17_research import SEED, gini, json_safe, wilson

log = logging.getLogger("dpcn.s20")

PEER_FILE = "peer_institutes.csv"
WORK_TYPES = "article|review"
SELECT_FIELDS = ["id", "publication_year", "cited_by_count", "fwci", "citation_normalized_percentile",
                 "countries_distinct_count", "institutions_distinct_count", "open_access", "primary_topic", "type"]
RCA_MIN_PAPERS = 15
N_BOOT = 1000
DIST_OFFSET_KM = 10.0
MAIN_METRICS = ["papers", "cagr", "citations_per_paper", "mean_fwci", "median_fwci", "top10_share", "top1_share",
                "intl_share", "oa_share", "h_index"]
SUMMARY_RANKS = ["mean_fwci", "top10_share", "citations_per_paper", "intl_share", "oa_share", "cagr"]



# --------------------------------------------------------------------------- institutes

def institutes(cfg) -> pd.DataFrame:
    ours = pd.DataFrame([{"group": "ours", "short": l["short"], "name": l["name"], "city": l["city"], "type": "CSIR lab",
                          "openalex_id": l["openalex_id"], "why_chosen": "one of our four labs"} for l in cfg.labs])
    pf = cfg.paths.manual / PEER_FILE
    if not pf.exists():
        raise StepFailed(f"{cfg.rel(pf)} missing (columns short, name, city, type, openalex_id, why_chosen)")
    peers = pd.read_csv(pf, dtype=str).dropna(subset=["openalex_id"])
    peers = peers[~peers["openalex_id"].isin(ours["openalex_id"])].assign(group="peer")
    t = pd.concat([ours, peers[ours.columns]], ignore_index=True)
    if t["short"].duplicated().any() or t["openalex_id"].duplicated().any():
        raise StepFailed(f"duplicate short name or OpenAlex ID in {cfg.rel(pf)}")
    return t


def verify(oa, t: pd.DataFrame) -> pd.DataFrame:
    """Check each ID resolves to an Indian institution (entity lookups are free) and keep its geo and size."""
    rows = []
    for r in t.itertuples():
        e = oa.entity(f"institutions/{r.openalex_id}", select="id,display_name,country_code,type,geo,works_count")
        geo = e.get("geo") or {}
        if e.get("country_code") != "IN":
            log.warning("%s (%s) resolves to %s in %s - dropped", r.short, r.openalex_id, e.get("display_name"),
                        e.get("country_code"))
        rows.append({"openalex_id": r.openalex_id, "oa_display_name": e.get("display_name"),
                     "oa_country": e.get("country_code"), "oa_type": e.get("type"), "lat": geo.get("latitude"),
                     "lon": geo.get("longitude"), "oa_works_count": e.get("works_count")})
    v = t.merge(pd.DataFrame(rows), on="openalex_id")
    return v[v["oa_country"] == "IN"].reset_index(drop=True)


# --------------------------------------------------------------------------- works

def work_filter(cfg, inst_id: str) -> str:
    return (f"authorships.institutions.lineage:{inst_id},{cfg.year_filter},type:{WORK_TYPES},is_retracted:false")


def fetch_works(cfg, oa, inst_id: str, fields: list[str]) -> pd.DataFrame:
    rows = []
    for w in oa.paginate("works", work_filter(cfg, inst_id), select=",".join(fields), per_page=cfg.openalex.per_page):
        pct = w.get("citation_normalized_percentile") or {}
        oa_ = w.get("open_access") or {}
        pt = w.get("primary_topic") or {}
        sf, fd = pt.get("subfield") or {}, pt.get("field") or {}
        rows.append({"work_id": short_id(w["id"]), "year": w.get("publication_year"),
                     "citations": w.get("cited_by_count") or 0, "fwci": w.get("fwci"),
                     "pct": pct.get("value"), "top10": pct.get("is_in_top_10_percent") if pct else None,
                     "top1": pct.get("is_in_top_1_percent") if pct else None,
                     "n_countries": w.get("countries_distinct_count"), "n_insts": w.get("institutions_distinct_count"),
                     "is_oa": oa_.get("is_oa"), "type": w.get("type"),
                     "subfield_id": short_id(sf.get("id")), "subfield": sf.get("display_name"),
                     "field": fd.get("display_name")})
    d = pd.DataFrame(rows).drop_duplicates("work_id")
    d["fwci"] = pd.to_numeric(d["fwci"], errors="coerce")
    return d


def check_fields(cfg, oa, inst_id: str) -> list[str]:
    """Drop select fields the API rejects (checked one page at a time; normally all are accepted)."""
    fields = list(SELECT_FIELDS)
    try:
        oa.get("works", filter=work_filter(cfg, inst_id), per_page=cfg.openalex.per_page, cursor="*",
               select=",".join(fields))
        return fields
    except RuntimeError as e:
        log.warning("full select rejected (%s); testing fields one by one", str(e).splitlines()[0])
    ok = ["id"]
    for f in SELECT_FIELDS[1:]:
        try:
            oa.get("works", filter=work_filter(cfg, inst_id), per_page=1, select=f"id,{f}")
            ok.append(f)
        except RuntimeError:
            log.warning("OpenAlex rejects select field %s - dropped", f)
    return ok


# --------------------------------------------------------------------------- B1 metrics

def h_index(c: np.ndarray) -> int:
    c = np.sort(np.asarray(c))[::-1]
    return int((c >= np.arange(1, len(c) + 1)).sum())


def trend_growth(yc: pd.Series, start: int, end: int) -> float:
    """Annual growth from a log-linear fit of papers on year (uses every complete year, not just the end points)."""
    ys = np.arange(start, end + 1)
    n = np.array([yc.get(y, 0) for y in ys], dtype=float)
    if (n <= 0).any():
        return np.nan
    return float(np.exp(np.polyfit(ys, np.log(n), 1)[0]) - 1)


def boot_mean_ci(x: np.ndarray, rng) -> tuple[float, float]:
    if len(x) == 0:
        return np.nan, np.nan
    means = np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(N_BOOT)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def metrics(d: pd.DataFrame, cfg, rng) -> dict:
    start, cagr_end = int(cfg.window.start), int(cfg.window.cagr_end)
    n = len(d)
    yc = d["year"].value_counts()
    full = d[d["year"] <= cagr_end]
    p0, p1 = yc.get(start, 0), yc.get(cagr_end, 0)
    c = d["citations"].to_numpy(dtype=float)
    f = d["fwci"].dropna().to_numpy(dtype=float)
    lo, hi = boot_mean_ci(f, rng)
    pc = d.dropna(subset=["pct"])
    k10, k1 = int(pc["top10"].astype(bool).sum()), int(pc["top1"].astype(bool).sum())
    t10, t1 = wilson(k10, len(pc)), wilson(k1, len(pc))
    nc = d["n_countries"].dropna()
    intl, oa_ = int((nc > 1).sum()), int(d["is_oa"].fillna(False).astype(bool).sum())
    il, ol = wilson(intl, len(nc)), wilson(oa_, n)
    sf = d["subfield"].dropna().value_counts()
    p = sf.to_numpy() / sf.sum() if len(sf) else np.array([])
    return {
        "papers": n, "papers_complete_years": len(full),
        "papers_per_year": len(full) / (cagr_end - start + 1),
        "papers_first_year": int(p0), "papers_cagr_end_year": int(p1),
        "cagr": (p1 / p0) ** (1 / (cagr_end - start)) - 1 if p0 > 0 and p1 > 0 else np.nan,
        "trend_growth": trend_growth(yc, start, cagr_end),
        "citations": int(c.sum()), "citations_per_paper": c.mean() if n else np.nan,
        "fwci_coverage": len(f) / n if n else np.nan,
        "mean_fwci": f.mean() if len(f) else np.nan, "mean_fwci_lo": lo, "mean_fwci_hi": hi,
        "median_fwci": float(np.median(f)) if len(f) else np.nan,
        "percentile_coverage": len(pc) / n if n else np.nan,
        "top10_share": k10 / len(pc) if len(pc) else np.nan, "top10_lo": t10[0], "top10_hi": t10[1],
        "top1_share": k1 / len(pc) if len(pc) else np.nan, "top1_lo": t1[0], "top1_hi": t1[1],
        "intl_share": intl / len(nc) if len(nc) else np.nan, "intl_lo": il[0], "intl_hi": il[1],
        "oa_share": oa_ / n if n else np.nan, "oa_lo": ol[0], "oa_hi": ol[1],
        "review_share": (d["type"] == "review").mean() if n else np.nan,
        "mean_institutions_per_paper": d["n_insts"].mean(),
        "h_index": h_index(c), "gini_citations": gini(c),
        "effective_papers": c.sum() ** 2 / (c ** 2).sum() if (c ** 2).sum() else np.nan,
        "n_subfields": int(len(sf)), "subfield_entropy": float(-(p * np.log(p)).sum()) if len(p) else np.nan,
    }


def benchmark(cfg, insts: pd.DataFrame, works: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    rows, yearly, fields = [], [], []
    for r in insts.itertuples():
        d = works[r.short]
        rows.append({"group": r.group, "short": r.short, "name": r.name, "city": r.city, "type": r.type,
                     "openalex_id": r.openalex_id, **metrics(d, cfg, rng)})
        for y, g in d.groupby("year"):
            pc = g.dropna(subset=["pct"])
            yearly.append({"short": r.short, "year": int(y), "papers": len(g), "mean_fwci": g["fwci"].mean(),
                           "top10_share": pc["top10"].astype(bool).mean() if len(pc) else np.nan})
        fc = d["field"].fillna("Unknown").value_counts()
        for fd, k in fc.items():
            fields.append({"short": r.short, "field": fd, "papers": int(k), "share": k / len(d)})
    b = pd.DataFrame(rows)
    for m in MAIN_METRICS:
        b[f"rank_{m}"] = b[m].rank(ascending=False, method="min").astype("Int64")
    return b, pd.DataFrame(yearly), pd.DataFrame(fields)


# --------------------------------------------------------------------------- B2 RCA vs India

def group_by_all(oa, path: str, flt: str, key: str) -> list[dict]:
    """oa.group_by returns at most 200 groups; page through the rest with a cursor."""
    out, cursor = [], "*"
    while cursor:
        d = oa.get(path, filter=flt, group_by=key, per_page=200, cursor=cursor)
        out.extend(d["group_by"])
        cursor = d["meta"].get("next_cursor") if d["group_by"] else None
    return out


def rca_india(cfg, oa, insts: pd.DataFrame, works: dict) -> tuple[pd.DataFrame, int]:
    years = f"publication_year:{cfg.window.start}-{cfg.window.cagr_end}"
    flt = f"institutions.country_code:IN,{years},type:{WORK_TYPES},is_retracted:false"
    g = group_by_all(oa, "works", flt, "primary_topic.subfield.id")
    india = pd.Series({short_id(x["key"]): x["count"] for x in g if str(x["key"]).startswith("http")}, dtype=float)
    names = {short_id(x["key"]): x["key_display_name"] for x in g}
    india_share = india / india.sum()
    rows = []
    for r in insts.itertuples():
        d = works[r.short]
        d = d[(d["year"] <= int(cfg.window.cagr_end)) & d["subfield_id"].notna()]
        vc = d["subfield_id"].value_counts()
        for sid, k in vc.items():
            if k < RCA_MIN_PAPERS:
                continue
            s, i = k / len(d), india_share.get(sid, np.nan)
            rows.append({"short": r.short, "subfield": names.get(sid) or d.loc[d["subfield_id"] == sid, "subfield"].iat[0],
                         "papers": int(k), "share": s, "india_share": i, "rca": s / i if i else np.nan,
                         "subfield_id": sid})
    out = pd.DataFrame(rows).sort_values(["short", "rca"], ascending=[True, False])
    return out, int(india.sum())


# --------------------------------------------------------------------------- B3 gravity model

def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def poisson_irls(X: np.ndarray, y: np.ndarray, iters: int = 100):
    """Poisson GLM (log link) by IRLS. Returns coefficients, the inverse Fisher information and the per-row
    score contributions (for sandwich standard errors)."""
    b = np.zeros(X.shape[1])
    b[0] = np.log(max(y.mean(), 1e-9))
    for _ in range(iters):
        mu = np.exp(np.clip(X @ b, -30, 30))
        H = (X * mu[:, None]).T @ X
        step = np.linalg.solve(H, X.T @ (y - mu))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    mu = np.exp(np.clip(X @ b, -30, 30))
    Ainv = np.linalg.inv((X * mu[:, None]).T @ X)
    return b, Ainv, X * (y - mu)[:, None], mu


def partner_geo(cfg, oa, ids: list[str]) -> pd.DataFrame:
    rows = []
    for b in batches(sorted(ids), cfg.openalex.or_batch):
        d = oa.get("institutions", filter=f"openalex:{'|'.join(b)}", select="id,geo,works_count", per_page=100)
        for e in d["results"]:
            geo = e.get("geo") or {}
            rows.append({"inst_id": short_id(e["id"]), "lat": geo.get("latitude"), "lon": geo.get("longitude"),
                         "works_count": e.get("works_count")})
    return pd.DataFrame(rows, columns=["inst_id", "lat", "lon", "works_count"])


def gravity(cfg, oa, insts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    it = cfg.paths.interim
    for f in ("institutions.parquet", "authorships.parquet", "faculty_papers.parquet", "inflow_works.parquet"):
        if not (it / f).exists():
            raise StepFailed(f"data/interim/{f} missing - run s05 to s09 first")
    labs = {l["openalex_id"]: l["short"] for l in cfg.labs}
    inst = pd.read_parquet(it / "institutions.parquet")
    inst = inst[(inst["country_code"] == "IN") & inst["our_lab"].isna() & ~inst["is_umbrella"] & ~inst["is_academy"]
                & ~inst["inst_id"].isin(labs)
                & ~inst["lineage"].map(lambda L: bool(set(L if L is not None else []) & set(labs)))]
    cand = set(inst["inst_id"])

    fp = pd.read_parquet(it / "faculty_papers.parquet")[["work_id", "institution"]].drop_duplicates()
    auth = pd.read_parquet(it / "authorships.parquet")[["work_id", "inst_ids"]].explode("inst_ids").dropna()
    auth = auth.rename(columns={"inst_ids": "partner"}).drop_duplicates()
    joint = fp.merge(auth[auth["partner"].isin(cand)], on="work_id").drop_duplicates(["institution", "partner", "work_id"])
    joint = joint.groupby(["institution", "partner"]).size().rename("joint_papers")

    inflow = pd.read_parquet(it / "inflow_works.parquet")[["work_id", "inst_ids", "refs_ours"]]
    ci = inflow[["work_id", "inst_ids"]].explode("inst_ids").dropna().drop_duplicates()
    ci = ci.rename(columns={"inst_ids": "partner"})
    ci = ci[ci["partner"].isin(cand)]
    cr = inflow[["work_id", "refs_ours"]].explode("refs_ours").dropna().rename(columns={"refs_ours": "cited"})
    cr = cr.merge(fp.rename(columns={"work_id": "cited"}), on="cited")
    cit = ci.merge(cr, on="work_id").drop_duplicates(["work_id", "cited", "institution", "partner"])
    cit = cit.groupby(["institution", "partner"]).size().rename("citations")

    partners = sorted(set(joint.index.get_level_values("partner")) | set(cit.index.get_level_values("partner")))
    geo = partner_geo(cfg, oa, partners + list(labs))
    geo = geo.dropna(subset=["lat", "lon"])
    geo = geo[pd.to_numeric(geo["works_count"], errors="coerce") > 0].set_index("inst_id")
    lab_geo = {labs[i]: geo.loc[i] for i in labs if i in geo.index}
    if len(lab_geo) < len(labs):
        raise StepFailed("could not geolocate all four labs through OpenAlex")
    P = [p for p in partners if p in geo.index]
    pairs = pd.MultiIndex.from_product([[l["short"] for l in cfg.labs], P], names=["institution", "partner"])
    g = pd.DataFrame(index=pairs).join(joint).join(cit).fillna(0).reset_index()
    g["distance_km"] = haversine_km(g["institution"].map(lambda s: lab_geo[s]["lat"]).astype(float),
                                    g["institution"].map(lambda s: lab_geo[s]["lon"]).astype(float),
                                    g["partner"].map(geo["lat"]).astype(float), g["partner"].map(geo["lon"]).astype(float))
    g["partner_works"] = g["partner"].map(geo["works_count"]).astype(float)
    g["partner_name"] = g["partner"].map(inst.set_index("inst_id")["display_name"])

    lab_names = [l["short"] for l in cfg.labs]
    X = np.column_stack([np.ones(len(g)), np.log(g["distance_km"] + DIST_OFFSET_KM), np.log(g["partner_works"]),
                         *[(g["institution"] == s).astype(float) for s in lab_names[1:]]])
    terms = ["const", "log_distance", "log_partner_works", *[f"lab[{s}]" for s in lab_names[1:]]]
    rows, fits = [], {}
    for outcome in ("joint_papers", "citations"):
        y = g[outcome].to_numpy(dtype=float)
        b, Ainv, S, mu = poisson_irls(X, y)
        V = Ainv @ (S.T @ S) @ Ainv                       # robust (sandwich): Poisson counts are overdispersed
        se, se_m = np.sqrt(np.diag(V)), np.sqrt(np.diag(Ainv))
        fits[outcome] = (b, Ainv, S)
        disp = float(((y - mu) ** 2 / mu).sum() / (len(y) - len(b)))
        for j, t in enumerate(terms):
            z = b[j] / se[j]
            rows.append({"outcome": outcome, "term": t, "coef": b[j], "se": se[j], "ci_lo": b[j] - 1.96 * se[j],
                         "ci_hi": b[j] + 1.96 * se[j], "p": 2 * stats.norm.sf(abs(z)), "n": len(y),
                         "se_model": se_m[j], "dispersion": disp, "total_count": int(y.sum())})
    # difference of the two distance elasticities: both fits share the pairs, so the covariance comes from the
    # cross-product of their score contributions (seemingly-unrelated sandwich)
    (bj, Aj, Sj), (bc, Ac, Sc) = fits["joint_papers"], fits["citations"]
    Vjc = Aj @ (Sj.T @ Sc) @ Ac
    Vj, Vc = Aj @ (Sj.T @ Sj) @ Aj, Ac @ (Sc.T @ Sc) @ Ac
    k = 1
    diff = bj[k] - bc[k]
    sd = math.sqrt(Vj[k, k] + Vc[k, k] - 2 * Vjc[k, k])
    rows.append({"outcome": "joint_papers - citations", "term": "log_distance", "coef": diff, "se": sd,
                 "ci_lo": diff - 1.96 * sd, "ci_hi": diff + 1.96 * sd, "p": 2 * stats.norm.sf(abs(diff / sd)),
                 "n": len(g), "se_model": np.nan, "dispersion": np.nan, "total_count": np.nan})
    info = {"partners": len(P), "pairs": len(g), "candidates_in_institutions_parquet": len(cand),
            "partners_without_geo": len(partners) - len(P),
            "joint_papers_total": int(g["joint_papers"].sum()), "citations_total": int(g["citations"].sum()),
            "median_distance_km": float(g["distance_km"].median())}
    return pd.DataFrame(rows), g, info


# --------------------------------------------------------------------------- summary

def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def findings(b: pd.DataFrame, rca: pd.DataFrame, grav: pd.DataFrame, n_all: int) -> list[str]:
    ours, peers = b[b["group"] == "ours"], b[b["group"] == "peer"]
    out = []
    best = ours.loc[ours["mean_fwci"].idxmax()]
    out.append(f"Among our labs, {best.short} has the highest mean FWCI ({best.mean_fwci:.2f}, 95% CI "
               f"{best.mean_fwci_lo:.2f}-{best.mean_fwci_hi:.2f}), ranking {best.rank_mean_fwci} of {n_all} institutes; "
               f"the peer median is {peers['mean_fwci'].median():.2f}.")
    top, topm = b.loc[b["mean_fwci"].idxmax()], b.loc[b["median_fwci"].idxmax()]
    above = int((ours["mean_fwci"] > peers["mean_fwci"].median()).sum())
    om = ours.sort_values("median_fwci", ascending=False)
    out.append(f"{above} of our 4 labs {'has' if above == 1 else 'have'} a mean FWCI above the peer median; the top "
               f"mean belongs to {top.short} ({top.mean_fwci:.2f}, citation Gini {top.gini_citations:.2f}, i.e. driven "
               f"by a few very highly cited papers), while on the outlier-robust median FWCI the leader is "
               f"{topm.short} ({topm.median_fwci:.2f}) and our labs rank "
               + ", ".join(f"{r.short} {r.rank_median_fwci}" for r in om.itertuples()) + f" of {n_all}.")
    t10 = ours.sort_values("top10_share", ascending=False)
    out.append(f"Our labs' share of papers in the global top 10% by citations ranges from {pct(t10.top10_share.iat[-1])} "
               f"({t10.short.iat[-1]}) to {pct(t10.top10_share.iat[0])} ({t10.short.iat[0]}), against a peer median "
               f"of {pct(peers['top10_share'].median())}.")
    big = ours.loc[ours["papers"].idxmax()]
    out.append(f"{big.short} has the largest output of all {n_all} institutes ({big.papers:,} articles and reviews, "
               f"{big.papers_per_year:.0f} a year, {big.papers / b.loc[b['group'] == 'peer', 'papers'].median():.1f} times "
               f"the median peer), yet ranks {big.rank_mean_fwci} of {n_all} on mean FWCI." if big.rank_papers == 1 else
               f"{big.short} is our largest lab ({big.papers:,} articles and reviews, {big.papers_per_year:.0f} a year), "
               f"ranking {big.rank_papers} of {n_all} institutes by output.")
    g = ours.sort_values("cagr", ascending=False)
    out.append(f"Output growth from the first year to the last complete year runs from {pct(g.cagr.iat[-1])} a year "
               f"({g.short.iat[-1]}) to {pct(g.cagr.iat[0])} a year ({g.short.iat[0]}) in our labs, against a peer "
               f"median of {pct(peers['cagr'].median())}; a log-linear trend over all complete years gives "
               f"{pct(ours['trend_growth'].min())} to {pct(ours['trend_growth'].max())} for our labs vs "
               f"{pct(peers['trend_growth'].median())} for the median peer.")
    out.append(f"International co-authorship is {pct(ours['intl_share'].min())}-{pct(ours['intl_share'].max())} of "
               f"papers in our labs and {pct(peers['intl_share'].median())} at the median peer; open access is "
               f"{pct(ours['oa_share'].min())}-{pct(ours['oa_share'].max())} vs {pct(peers['oa_share'].median())}.")
    lo = ours.loc[ours["gini_citations"].idxmax()]
    out.append(f"Citations are concentrated everywhere (Gini {b['gini_citations'].min():.2f}-{b['gini_citations'].max():.2f}); "
               f"in {lo.short} (Gini {lo.gini_citations:.2f}) a few papers carry the totals, the citation weight of "
               f"only {lo.effective_papers:.0f} 'effective' papers out of {lo.papers:,}.")
    sp = []
    for s in ours["short"]:
        r = rca[rca["short"] == s].head(1)
        if len(r):
            sp.append(f"{s} in {r.subfield.iat[0]} (RCA {r.rca.iat[0]:.1f})")
    if sp:
        out.append("Relative to all Indian output, the strongest specialisations are " + "; ".join(sp) + ".")
    gj = grav[(grav["outcome"] == "joint_papers") & (grav["term"] == "log_distance")].iloc[0]
    gc = grav[(grav["outcome"] == "citations") & (grav["term"] == "log_distance")].iloc[0]
    gd = grav[grav["outcome"] == "joint_papers - citations"].iloc[0]
    out.append(f"Within India, joint papers fall with distance with elasticity {gj.coef:.2f} (95% CI {gj.ci_lo:.2f} to "
               f"{gj.ci_hi:.2f}) and citations with {gc.coef:.2f} ({gc.ci_lo:.2f} to {gc.ci_hi:.2f}): "
               + ("collaboration decays with distance more steeply than citation" if gd.coef < 0 and gd.p < 0.05 else
                  "the two decay rates are not clearly different" if gd.p >= 0.05 else
                  "citation decays with distance more steeply than collaboration")
               + f" (difference {gd.coef:.2f}, p = {gd.p:.2g}).")
    return out


def run(cfg, oa, argv=()) -> None:
    st = cfg.paths.stats
    st.mkdir(parents=True, exist_ok=True)
    insts = verify(oa, institutes(cfg))
    log.info("institutes: %d ours + %d peers", (insts["group"] == "ours").sum(), (insts["group"] == "peer").sum())
    fields = check_fields(cfg, oa, insts["openalex_id"].iat[0])
    works = {}
    for r in insts.itertuples():
        works[r.short] = fetch_works(cfg, oa, r.openalex_id, fields)
        log.info("%-11s %5d works | %s", r.short, len(works[r.short]), oa.report())

    b, yearly, flds = benchmark(cfg, insts, works)
    b.to_csv(st / "research_benchmark.csv", index=False, lineterminator="\n")
    yearly.to_csv(st / "research_benchmark_yearly.csv", index=False, lineterminator="\n")
    flds.to_csv(st / "research_benchmark_fields.csv", index=False, lineterminator="\n")

    rca, india_total = rca_india(cfg, oa, insts, works)
    rca.to_csv(st / "research_rca_india.csv", index=False, lineterminator="\n")

    grav, pairs, ginfo = gravity(cfg, oa, insts)
    grav.to_csv(st / "research_gravity.csv", index=False, lineterminator="\n")

    n_all = len(b)
    ours = b[b["group"] == "ours"]
    el = {o: grav[(grav["outcome"] == o) & (grav["term"] == "log_distance")].iloc[0].to_dict()
          for o in ("joint_papers", "citations", "joint_papers - citations")}
    summary = {
        "scope": ("Whole-institute output: every OpenAlex article or review with an author whose affiliation lineage "
                  "includes the institute (students, postdocs, staff, visiting and honorary affiliates), not the "
                  "faculty-only corpus used elsewhere in this project."),
        "window": {"start": int(cfg.window.start), "end": int(cfg.window.end), "partial_year": cfg.window.partial_year,
                   "cagr": f"{cfg.window.start}->{cfg.window.cagr_end}"},
        "query": work_filter(cfg, "<id>"), "select": fields,
        "institutes": insts[["group", "short", "name", "city", "type", "openalex_id", "oa_display_name"]]
                      .merge(b[["short", "papers"]], on="short").to_dict("records"),
        "peers_skipped": [],
        "ranks_of_our_labs": {r.short: {m: {"value": getattr(r, m), "rank": int(getattr(r, f"rank_{m}")), "of": n_all}
                                        for m in SUMMARY_RANKS} for r in ours.itertuples()},
        "fwci_coverage": dict(zip(b["short"], b["fwci_coverage"])),
        "percentile_coverage": dict(zip(b["short"], b["percentile_coverage"])),
        "peer_medians": {m: float(b.loc[b["group"] == "peer", m].median()) for m in MAIN_METRICS + ["review_share"]},
        "gravity": {"distance_elasticity_joint_papers": el["joint_papers"],
                    "distance_elasticity_citations": el["citations"],
                    "difference": el["joint_papers - citations"], **ginfo,
                    "reference": "inspiration: another group reported -0.70 (joint papers) vs -0.17 (citations)"},
        "rca_top5": {s: rca[rca["short"] == s].head(5)[["subfield", "papers", "share", "india_share", "rca"]]
                     .to_dict("records") for s in b["short"]},
        "india_reference_works": india_total,
        "findings": findings(b, rca, grav, n_all),
        "caveats": [
            "FWCI and citation percentiles are OpenAlex's own field-and-year normalisations; they are missing for "
            f"a few papers (FWCI coverage {b['fwci_coverage'].min():.1%}-{b['fwci_coverage'].max():.1%} across "
            "institutes), are recomputed by OpenAlex over time, and recent years have had little time to accumulate "
            "citations.",
            "Lineage counts include students, postdocs, project staff and every affiliate rolled up to the institute, "
            "and child institutions in the OpenAlex hierarchy; output is not comparable with our faculty-only corpus.",
            "Peers differ in size, mission (basic vs translational vs plant or toxicology) and field mix; FWCI and "
            "percentiles normalise by field, raw citations and h-index do not, and h-index grows with output.",
            "RCA is measured against ALL Indian output, which is dominated by engineering, physical and computer "
            "sciences, so most life-science subfields have RCA far above 1 and small niche subfields (a few dozen "
            "papers) can top the list; compare institutes within a subfield rather than reading the absolute level.",
            f"{cfg.window.end} is a partial year: it is counted in totals but excluded from CAGR, papers per year and RCA.",
            "Gravity model: partner institutions are those already linked to our faculty corpus by co-authorship or "
            "citation (zeros only arise across labs), coordinates are OpenAlex's city-level geocodes, and partner size "
            "is OpenAlex's all-time works count; standard errors are robust (sandwich) because counts are overdispersed.",
            "OpenAlex affiliation parsing is imperfect: missing or wrong institution links move papers between institutes.",
        ],
        "methods": {
            "works_query": "authorships.institutions.lineage:<id>, publication_year window, type article|review, "
                           "is_retracted:false; identical for all institutes",
            "papers_per_year": f"mean over {cfg.window.start}-{cfg.window.cagr_end}",
            "trend_growth": f"exp(slope) - 1 of log(papers) on year, {cfg.window.start}-{cfg.window.cagr_end}",
            "cagr": f"(papers {cfg.window.cagr_end} / papers {cfg.window.start})^(1/{int(cfg.window.cagr_end) - int(cfg.window.start)}) - 1",
            "fwci": f"mean and median over papers with FWCI; mean CI = percentile bootstrap, {N_BOOT} resamples, seed {SEED}",
            "top_shares": "citation_normalized_percentile.is_in_top_10_percent / is_in_top_1_percent over papers with a "
                          "percentile; Wilson 95% CI",
            "intl_share": "countries_distinct_count > 1; Wilson CI", "oa_share": "open_access.is_oa; Wilson CI",
            "concentration": "Gini of paper citations; effective papers = (sum c)^2 / sum c^2",
            "diversity": "distinct primary-topic subfields; Shannon entropy (natural log) of subfield shares",
            "ranks": "1 = highest among all institutes (ours + peers), ties share the lower rank",
            "rca": f"(institute share of subfield) / (India share), {cfg.window.start}-{cfg.window.cagr_end}, primary "
                   f"topic subfield; India = institutions.country_code:IN with the same type and retraction filters "
                   f"(group_by paged by cursor); subfields with >= {RCA_MIN_PAPERS} institute papers",
            "gravity": f"Poisson GLM by IRLS: count ~ log(distance_km + {DIST_OFFSET_KM:g}) + log(partner works_count) "
                       "+ lab fixed effects, over every (lab, partner) pair for Indian partner institutions (not our "
                       "labs or their children, not umbrella or academy rows) that co-author with or cite any lab; "
                       "joint papers = faculty-corpus papers of the lab with an author at the partner; citations = "
                       "(citing paper, cited lab paper) links from inflow works with an author at the partner; "
                       "robust sandwich SEs; difference test uses the cross-score covariance of the two fits",
        },
        "openalex": oa.report().split(" | budget")[0],
    }
    (st / "research_benchmark.json").write_text(json.dumps(json_safe(summary), indent=2, default=float, allow_nan=False),
                                                encoding="utf-8")

    show = ["group", "short", "papers", "papers_per_year", "cagr", "trend_growth", "citations_per_paper", "fwci_coverage", "mean_fwci",
            "median_fwci", "top10_share", "top1_share", "intl_share", "oa_share", "h_index", "gini_citations"]
    print("\n" + b.sort_values("mean_fwci", ascending=False)[show].round(3).to_string(index=False))
    print("\nGravity (distance elasticity):")
    print(grav[grav["term"] == "log_distance"][["outcome", "coef", "ci_lo", "ci_hi", "p", "n"]].round(3).to_string(index=False))
    print("\nFindings:")
    for f in summary["findings"]:
        print(" -", f)
