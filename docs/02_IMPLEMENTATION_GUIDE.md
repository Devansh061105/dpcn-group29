# DPCN Research Mapping — Group 29 Implementation Guide

This guide is the *how*: environment, repository layout, configuration, shared modules, and a precise specification of each pipeline step (S00–S15), plus the dashboard, report, validation and runbook. Decision IDs (D1…D22) and ambiguity IDs (A1…A16) refer to [01_PROJECT_PLAN.md](01_PROJECT_PLAN.md).

---

## Contents

1. [Prerequisites and accounts](#1-prerequisites-and-accounts)
2. [Repository layout](#2-repository-layout)
3. [Environment setup](#3-environment-setup)
4. [Configuration files](#4-configuration-files)
5. [Shared library modules](#5-shared-library-modules)
6. [Interim data schemas](#6-interim-data-schemas)
7. [Pipeline steps S00–S15](#7-pipeline-steps-s00s15)
8. [Dashboard implementation (S13)](#8-dashboard-implementation-s13)
9. [Report implementation (S14)](#9-report-implementation-s14)
10. [Runbook, API budget and timing](#10-runbook-api-budget-and-timing)
11. [Testing](#11-testing)
12. [Troubleshooting](#12-troubleshooting)
13. [Conventions and git workflow](#13-conventions-and-git-workflow)

---

## 1. Prerequisites and accounts

| Item | Who | Notes |
|---|---|---|
| Python 3.12 (via Miniconda; 3.13 is installed but 3.12 has the widest wheel support, e.g. `leidenalg`) | Everyone | `conda create -n dpcn python=3.12` |
| Git | Everyone | One shared repo (GitHub private repo recommended) |
| **OpenAlex free account + API key** | Everyone | Create an account at openalex.org, then copy the API key from account settings. It gives $1/day ≈ 10,000 list calls. The key is sent as the `api_key` query parameter. Without a key the budget is $0.10/day. |
| Browser access to scimagojr.com | R2 | SJR blocks scripted downloads (Cloudflare). Download manually (S06). |
| Gephi 0.10+ (optional) | R3 | To open the `.gexf` exports and make extra figures |
| Microsoft PowerPoint or LibreOffice | R5 | Final touch-ups and PDF export of the report |

**Never commit `.env`.** Each person keeps their own key locally.

---

## 2. Repository layout

```
DPCN Assignment 2/
├── README.md
├── pyproject.toml              # makes `src/dpcn` installable (pip install -e .)
├── requirements.txt
├── .env.example                # OPENALEX_API_KEY=   OPENALEX_EMAIL=
├── .gitignore
├── config/
│   ├── settings.yaml           # window, thresholds, paths, switches
│   ├── institutions.yaml       # our 4 labs: IDs, ROR, aliases, websites
│   └── cluster_rules.yaml      # partner-cluster classification rules (D12)
├── data/
│   ├── cache/                  # raw OpenAlex JSON responses (gitignored, gzip)
│   ├── manual/                 # human-curated inputs (COMMITTED)
│   │   ├── faculty_roster.csv
│   │   ├── faculty_match_overrides.csv
│   │   ├── institution_overrides.csv
│   │   ├── sjr/scimagojr_2016.csv … scimagojr_2025.csv
│   │   └── core/CORE2023.csv
│   ├── interim/                # parquet tables between steps (gitignored)
│   └── review/                 # sheets for human review (committed)
├── outputs/
│   ├── submission/             # the files we hand in
│   ├── stats/                  # metric tables (csv/json)
│   ├── networks/               # gexf, node tables, dashboard graph json
│   ├── figures/                # png for the report
│   └── report/
├── src/dpcn/
│   ├── __init__.py
│   ├── __main__.py             # enables `python -m dpcn`
│   ├── cli.py                  # `run <step>|all [--from sXX]`
│   ├── config.py               # loads yaml + .env into a Config object
│   ├── openalex.py             # cached, budgeted API client
│   ├── names.py                # name normalisation and matching
│   ├── institutions.py         # registry, umbrella/academy flags, cluster classifier
│   ├── io.py                   # parquet/csv helpers, required-column writers
│   └── steps/
│       ├── s00_verify.py   s01_roster.py   s02_candidates.py  s03_match.py
│       ├── s04_works.py    s05_normalise.py s06_enrich.py     s07_flows.py
│       ├── s08_main_csv.py s09_citation.py s10_authorship.py  s11_connections.py
│       ├── s12_stats.py    s13_dashboard.py s14_report.py     s15_validate.py
├── dashboard_src/
│   ├── template.html.j2
│   ├── app.js
│   ├── styles.css
│   └── vendor/                 # optional inlined libs for an offline build
├── report_src/
│   └── findings.yaml           # human-written takeaways with {placeholders}
├── tests/
└── docs/
    ├── 01_PROJECT_PLAN.md
    ├── 02_IMPLEMENTATION_GUIDE.md
    └── qa_log.md
```

**Principle:** every step reads only from `data/manual`, `data/interim` or `outputs/*` and writes its own outputs. Steps are **idempotent**, so re-running is safe and costs nothing thanks to the cache.

---

## 3. Environment setup

```bash
conda create -n dpcn python=3.12 -y
```
```bash
conda activate dpcn
```
```bash
pip install -r requirements.txt
```
```bash
pip install -e .
```

**`requirements.txt`**
```
requests>=2.32
pandas>=2.2
pyarrow>=17
pyyaml>=6.0
python-dotenv>=1.0
rapidfuzz>=3.9
Unidecode>=1.3
beautifulsoup4>=4.12
lxml>=5.2
networkx>=3.3
scipy>=1.13          # nx.pagerank uses scipy
matplotlib>=3.9
jinja2>=3.1
python-pptx>=1.0
tqdm>=4.66
pytest>=8.0
# optional
python-igraph>=0.11
leidenalg>=0.10
```

**`pyproject.toml`** (minimal)
```toml
[project]
name = "dpcn"
version = "0.1.0"
requires-python = ">=3.11"
[tool.setuptools.packages.find]
where = ["src"]
```

**`.gitignore`**
```
.env
data/cache/
data/interim/
__pycache__/
*.pyc
.ipynb_checkpoints/
outputs/figures/*.tmp
```

---

## 4. Configuration files

### 4.1 `config/institutions.yaml`
```yaml
group: 29
cluster_label: CSIR            # our cluster for cross-cluster flags (D12)
institutions:
  - short: CSIR-CCMB
    name: Centre for Cellular and Molecular Biology
    city: Hyderabad
    openalex_id: I185638415
    ror: 05shq4n12
    website: https://www.ccmb.res.in
    aliases: ["ccmb", "cellular and molecular biology", "cellular & molecular biology"]
  - short: CSIR-IGIB
    name: Institute of Genomics and Integrative Biology
    city: New Delhi
    openalex_id: I177828482
    ror: 05ef28661
    website: https://www.igib.res.in
    aliases: ["igib", "genomics and integrative biology", "genomics & integrative biology"]
  - short: CSIR-IMTECH
    name: Institute of Microbial Technology
    city: Chandigarh
    openalex_id: I4210147764
    ror: 055rjs771
    website: https://www.imtech.res.in
    aliases: ["imtech", "microbial technology"]
  - short: CSIR-CDRI
    name: Central Drug Research Institute
    city: Lucknow
    openalex_id: I185249246
    ror: 04t8qjg16
    website: https://cdri.res.in
    aliases: ["cdri", "central drug research"]
```
To drop CDRI (A1), delete its block. Nothing else changes.

### 4.2 `config/settings.yaml`
```yaml
window: {start: 2016, end: 2026, partial_year: 2026, cagr_end: 2025}
openalex:
  base_url: https://api.openalex.org
  per_page: 200
  or_batch: 100                  # max values in one OR filter
  budget_stop_fraction: 0.90     # stop when 90% of daily $ used
  sleep_s: 0.12                  # politeness between live calls
  max_retries: 6
  cache_dir: data/cache/openalex  # lab-website HTML goes in data/cache/web
work_filter:
  include_work_types: [article, review, letter, conference-paper]
  include_source_types: [journal, conference]
  exclude_retracted: true
matching:
  auto_accept_score: 92
  review_min_score: 70
  min_years_at_lab_in_window: 1
networks:
  max_authors_for_pairs: 50      # D16
  pagerank_alpha: 0.85
  louvain_seed: 42
  louvain_resolution: 1.0
  betweenness_k_internal: 1000
  dashboard_citation_nodes: 300
  dashboard_internal_nodes: 600
connections:
  count_csir_academy_as_partner: false   # D11 (AcSIR)
  jaccard_top_k_topics: 100
  jaccard_top_partners: 30
quartile:
  mode: year_matched            # or: latest
  sjr_dir: data/manual/sjr
  core_file: data/manual/core/CORE2023.csv
paths:
  interim: data/interim
  manual: data/manual
  review: data/review
  submission: outputs/submission
  stats: outputs/stats
  networks: outputs/networks
  figures: outputs/figures
```

### 4.3 `config/cluster_rules.yaml` (D12)
Order matters: the first match wins.
```yaml
umbrella_ids:            # never partners; dropped from coauthor_institutes
  - I66760702    # CSIR (HQ/parent) when it appears as the institution itself
  - I2799351866  # Government of India
  - I4210134808  # Ministry of Science and Technology
  - I3149292468  # Department of Atomic Energy (HQ)
  - I3141573830  # Department of Biotechnology (HQ)
csir_academy_ids: [I99364266]   # AcSIR
name_rules:             # regex (case-insensitive) -> cluster; checked BEFORE lineage
  - ['Indian Institute of Information Technology|\bIIIT\b|Indian Institute of Information Technology, Design', 'IIIT']
  - ['Indian Institute of Technology|\bIIT\b', 'IIT']
  - ['National Institute of Technology|\bNIT\b', 'NIT']
  - ['Indian Institute of Science Education and Research|\bIISER\b', 'IISc/TIFR/IISER']
  - ['^Indian Institute of Science\b(?! Education)', 'IISc/TIFR/IISER']
  - ['Tata Institute of Fundamental Research|National Centre for Biological Sciences|International Centre for Theoretical Sciences', 'IISc/TIFR/IISER']
  - ['National Institute of Science Education and Research', 'DAE']
  - ['Indian Statistical Institute|Institute of Mathematical Sciences|Chennai Mathematical Institute|Harish-Chandra|S\. ?N\. Bose|Bose Institute|Saha Institute', 'Premier Science']
  - ['Jawaharlal Nehru University|University of Hyderabad|University of Delhi|Banaras Hindu University|Jadavpur University|Jamia Millia Islamia|Aligarh Muslim University|Pondicherry University|Visva-Bharati|Central University|Tezpur University|North-Eastern Hill University|Assam University|University of Allahabad|Guru Ghasidas|Harisingh Gour|Babasaheb Bhimrao Ambedkar|Hemvati Nandan Bahuguna|Rajiv Gandhi University|Nagaland University|Mizoram University|Manipur University|Tripura University|Sikkim University', 'Central University']
lineage_rules:          # lineage contains id -> cluster
  I66760702: CSIR
  I3149292468: DAE
  I37048141: ICMR
  I3141573830: DBT
name_rules_late:
  - ['All India Institute of Medical Sciences|Postgraduate Institute of Medical|Medical College|Hospital|\bAIIMS\b|\bPGIMER\b', 'Medical']
  - ['University|Vishwavidyalaya|Vidyapeeth', 'University (other)']
type_rules: {company: Industry, healthcare: Medical, government: Government, nonprofit: Other, facility: Other, education: University (other)}
default: Other
```
`data/manual/institution_overrides.csv` (`openalex_id,cluster,short_name`) is applied **first**. Use it for the top ~50 partners after eyeballing them.

### 4.4 `.env.example`
```
OPENALEX_API_KEY=
OPENALEX_EMAIL=you@research.iiit.ac.in
```

---

## 5. Shared library modules

### 5.1 `config.py`
Loads the three YAML files plus `.env` into one object `cfg` with attribute access: `cfg.window.start`, `cfg.labs` (a list of dicts), `cfg.lab_ids` (set of OpenAlex IDs), `cfg.lab_by_id[id]["short"]`, and `cfg.paths.*` as `pathlib.Path`. All paths resolve relative to the repo root (find it by walking up to `pyproject.toml`), so commands work from any directory, including paths with spaces.

### 5.2 `openalex.py`: cached, budgeted client (core of the project)

Requirements:
- **Cache every response** as gzip JSON under `data/cache/openalex/<sha1>.json.gz`. The key is `path + sorted(params)` **excluding `api_key`**, so different team members' keys share a cache.
- Send the `api_key` query parameter (D22). Read `X-RateLimit-Remaining-USD` / `X-RateLimit-Limit-USD` after each live call. **Abort** when usage is above `budget_stop_fraction`.
- Retry on 429/5xx with exponential backoff, honouring `Retry-After`. **Raise** on 400 (usually a malformed filter) and print the URL.
- Paginate with `cursor` (`per_page=200`). Pages chain deterministically from the cached first page, so a fully cached run makes zero calls.
- Provide a helper to build OR filters in batches of 100 short IDs (`W123`, `A456`, `I789`).

```python
# src/dpcn/openalex.py
import gzip, hashlib, json, time, logging
from pathlib import Path
import requests

log = logging.getLogger(__name__)

def short_id(x: str) -> str:
    return x.rsplit("/", 1)[-1] if x else x

def batches(seq, n=100):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

class BudgetExceeded(RuntimeError):
    pass

class OpenAlex:
    def __init__(self, api_key, cache_dir, base_url="https://api.openalex.org",
                 budget_stop_fraction=0.9, sleep_s=0.12, max_retries=6):
        self.key, self.base = api_key, base_url.rstrip("/")
        self.cache = Path(cache_dir); self.cache.mkdir(parents=True, exist_ok=True)
        self.stop_frac, self.sleep_s, self.max_retries = budget_stop_fraction, sleep_s, max_retries
        self.s = requests.Session()
        self.live_calls = 0
        self.cache_hits = 0
        self.last_budget = None          # (remaining_usd, limit_usd)

    def _cache_path(self, path, params):
        p = {k: v for k, v in params.items() if k != "api_key"}
        raw = path + "?" + "&".join(f"{k}={p[k]}" for k in sorted(p))
        return self.cache / (hashlib.sha1(raw.encode()).hexdigest() + ".json.gz")

    def get(self, path, **params):
        cp = self._cache_path(path, params)
        if cp.exists():
            self.cache_hits += 1
            with gzip.open(cp, "rt", encoding="utf-8") as f:
                return json.load(f)
        if self.last_budget:
            rem, lim = self.last_budget
            if lim and (1 - rem / lim) >= self.stop_frac:
                raise BudgetExceeded(f"OpenAlex budget {rem:.4f}/{lim} USD left; stopping.")
        q = dict(params)
        if self.key:
            q["api_key"] = self.key
        url = f"{self.base}/{path.lstrip('/')}"
        for attempt in range(self.max_retries):
            r = self.s.get(url, params=q, timeout=90)
            if r.status_code == 200:
                break
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.headers.get("Retry-After", 2 ** attempt))
                log.warning("HTTP %s, retry in %.1fs", r.status_code, wait)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {r.status_code} for {r.url}\n{r.text[:500]}")
        else:
            raise RuntimeError(f"Gave up after retries: {url}")
        self.live_calls += 1
        h = r.headers
        try:
            self.last_budget = (float(h.get("X-RateLimit-Remaining-USD")),
                                float(h.get("X-RateLimit-Limit-USD")))
        except (TypeError, ValueError):
            pass
        data = r.json()
        with gzip.open(cp, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        time.sleep(self.sleep_s)
        return data

    def paginate(self, path, filter, select=None, per_page=200, **extra):
        """Yield every result of a list query using cursor paging."""
        cursor = "*"
        while cursor:
            params = {"filter": filter, "per_page": per_page, "cursor": cursor, **extra}
            if select:
                params["select"] = select
            d = self.get(path, **params)
            yield from d["results"]
            cursor = d["meta"].get("next_cursor")
            if not d["results"]:
                break

    def count(self, path, filter):
        return self.get(path, filter=filter, per_page=1)["meta"]["count"]

    def group_by(self, path, filter, key, per_page=200):
        return self.get(path, filter=filter, group_by=key, per_page=per_page)["group_by"]

    def entity(self, path_with_id, select=None):
        """Single-entity lookup (free under OpenAlex pricing)."""
        return self.get(path_with_id, **({"select": select} if select else {}))

    def report(self):
        b = self.last_budget
        return f"live={self.live_calls} cached={self.cache_hits} budget_left={b}"
```

**Standard `select` for works** (keeps payloads small):
```
WORK_SELECT = "id,doi,title,publication_year,publication_date,type,cited_by_count,
               is_retracted,primary_location,authorships,referenced_works,primary_topic,topics"
```
(Write it as one comma-separated string with no spaces.)

**OpenAlex gotchas**

- `select` cannot be combined with `group_by`.
- OR filters take at most 100 values.
- List endpoints truncate `authorships` at 100. Detect `len(authorships) == 100` and re-fetch with a single-entity call `works/W…` (free) to get the full list.

### 5.3 `names.py`: normalisation and matching

```python
import re
from unidecode import unidecode
from rapidfuzz import fuzz

TITLES = {"dr", "prof", "professor", "mr", "mrs", "ms", "shri", "sh", "smt", "er"}

def norm(s: str) -> str:
    s = unidecode(s or "").lower()
    s = re.sub(r"[^a-z\s\-]", " ", s.replace(".", " "))
    toks = [t for t in re.split(r"[\s\-]+", s) if t and t not in TITLES]
    return " ".join(toks)

def tokens(s): return norm(s).split()

def initials_compatible(a: str, b: str) -> bool:
    """'r k mishra' ~ 'rakesh kumar mishra'; surnames must agree (fuzzy >= 90)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    # try surname = last token, and also first token (surname-first orderings)
    for sa, sb in ((ta[-1], tb[-1]), (ta[0], tb[-1]), (ta[-1], tb[0])):
        if fuzz.ratio(sa, sb) >= 90:
            ra = [t for t in ta if t != sa]
            rb = [t for t in tb if t != sb]
            short, long_ = (ra, rb) if len(ra) <= len(rb) else (rb, ra)
            if all(any(l == s or (len(s) == 1 and l.startswith(s)) or (len(l) == 1 and s.startswith(l))
                       for l in long_) for s in short):
                return True
    return False

def score(roster_name: str, cand_names: list[str]) -> float:
    """Best score over display_name + display_name_alternatives, 0..100."""
    best = 0.0
    for c in cand_names:
        s = fuzz.token_set_ratio(norm(roster_name), norm(c))
        if initials_compatible(roster_name, c):
            s = max(s, 90) + 5
        best = max(best, min(s, 100))
    return best
```

### 5.4 `institutions.py`: registry and classifier

```python
class InstitutionRegistry:
    """Built from every institution object seen in authorships (ours, in-flow, out-flow)."""
    def __init__(self, cfg, rules, overrides_df): ...
    def add(self, inst: dict): ...            # id, display_name, country_code, type, lineage, ror
    def is_indian(self, iid) -> bool
    def is_umbrella(self, iid) -> bool        # in rules.umbrella_ids
    def is_academy(self, iid) -> bool         # AcSIR
    def is_ours(self, iid) -> bool            # iid or its lineage contains one of our lab IDs
    def our_lab(self, iid) -> str | None      # 'CSIR-CCMB' etc.
    def cluster(self, iid) -> str             # overrides -> name_rules -> lineage_rules -> name_rules_late -> type_rules -> default
    def label(self, iid) -> str               # our short name, override short_name, or display_name
    def partner_ok(self, iid, own_lab=None) -> bool:
        """Indian, not umbrella, not own lab, and (AcSIR only if config allows)."""
```

**Paper-level Indian institution set** (used everywhere):
```python
def indian_insts(work, reg, cfg) -> set[str]:
    out = set()
    for a in work["authorships"]:
        for inst in a["institutions"]:
            iid = short_id(inst["id"])
            if reg.is_indian(iid) and not reg.is_umbrella(iid):
                lab = reg.our_lab(iid)
                out.add(lab or iid)          # collapse our labs' children to the lab short name
    return out
```

---

## 6. Interim data schemas

All interim files live in `data/interim/` as parquet. List-valued columns are stored as Arrow lists.

| Table | Key | Columns |
|---|---|---|
| `roster.parquet` | `faculty_id` | name, designation, department, institution, profile_url, orcid, status, source |
| `author_candidates.parquet` | (lab, author_id) | display_name, alternatives (list), orcid, works_count, h_index_lifetime, years_at_lab (list), last_known (list) |
| `faculty_author_map.parquet` | (faculty_id, author_id) | institution, score, method {orcid, auto, manual}, reviewed_by |
| `works_raw/*.jsonl.gz` | — | raw work JSON (faculty fetch and corpus fetch) |
| `works.parquet` | `work_id` | doi, title, year, pub_date, work_type, source_id, source_name, source_type, issn_l, issns (list), cited_by_count, n_authors, truncated_fixed (bool), topic_id, topic, subfield, field, domain, referenced_works (list), in_faculty_corpus (bool), in_lab_corpus (bool) |
| `authorships.parquet` | (work_id, position_idx) | author_id, author_name, raw_author_name, inst_ids (list), country_codes (list), raw_affiliations (list), is_corresponding, faculty_id (nullable), our_lab (nullable) |
| `faculty_papers.parquet` | (work_id, faculty_id, institution) | affil_method {lineage, raw_string} |
| `sources.parquet` | `source_id` | display_name, type, issn_l, issns, host_org |
| `quartiles.parquet` | `work_id` | quartile, quartile_source {sjr, core, none}, sjr_year_used |
| `outflow_works.parquet` | `work_id` | doi, year, cited_by_count, title, inst_ids (list, Indian non-umbrella) |
| `inflow_works.parquet` | `work_id` | doi, year, cited_by_count, title, source_name, inst_ids (list), referenced_works (list) |
| `institutions.parquet` | `inst_id` | display_name, country_code, type, ror, lineage (list), cluster, is_umbrella, is_academy, our_lab, label |
| `cit_edges.parquet` | (src, tgt) | scope {internal, outflow, inflow}, year, cross_institute |
| `coauthor_pairs.parquet` | (a_key, b_key, work_id) | a_name, b_name, inst_a, inst_b, year, a_fac, b_fac, a_internal, b_internal |

---

## 7. Pipeline steps S00–S15

Each step has the signature `def run(cfg, oa, argv=()) -> None` (`argv` = extra CLI arguments such as `--scrape`) in `src/dpcn/steps/sXX_*.py`, logs what it did, and finishes with **acceptance checks** that raise on failure.

### S00: verify institutions and budget
- **Do:** for each lab, call `institutions/<id>` (free) and compare `ror` and `display_name` against the config. Run `count("works", f"authorships.institutions.lineage:{id},publication_year:2016-2026")`. Print a table and `oa.report()`.
- **Accept:** every ROR matches; counts are within ±15% of the plan's §5.1 numbers. A larger drift is fine but must be noted in `qa_log.md`.
- **Cost:** 4 list calls.

### S01: faculty roster (semi-manual; R2)
- **Goal:** `data/manual/faculty_roster.csv`

  ```
  faculty_id,name,designation,department,institution,profile_url,orcid,status,source,notes
  CCMB-001,Rakesh K Mishra,Chief Scientist,Genomics,CSIR-CCMB,https://www.ccmb.res.in/people-details/?id=..,,current,website,
  ```

- **Scrapers** (`s01_roster.py --scrape <lab>` writes `data/review/roster_<lab>_scraped.csv`, which a human cleans and appends to the master roster):
  - **CCMB:** fetch the homepage and collect `href="/people-details/?id=N"` and `/dept_people/?sub_id=N`. Fetch each people-details page and extract name, designation, and group/department with BeautifulSoup. Keep scientists only (designation contains *Scientist*, *Director*, *Fellow*, *Emeritus*).
  - **CDRI:** the homepage links `ScientistDivisionWise?division=<code>`. Collect all division codes from the navigation and fetch each. The division name becomes `department`.
  - **IMTECH:** start from the "Departments at IMTECH" page under *About*, then follow each department's faculty links.
  - **IGIB:** `ScientistDirectory.html` embeds a `PEOPLE = [...]` array in a script block (name, profile URL, research areas); each profile page then gives designation, decision unit (department), ORCID and PubMed links. 42 people.
  - **IMTECH:** the default site is Hindi; use the `/en/.../scientists` path. Cards give name and expertise, profile pages give designation. The site's department filter does not work, so `department` stays blank (D20 fallback).
- **Rules:**
  - Keep the website's spelling.
  - One person, one `faculty_id`, even if they changed designation.
  - Mark `status=former` for leavers found via annual reports or the Wayback Machine (optional, D3).
- **Accept:** about 300 rows. No duplicate names within a lab (`norm(name)` unique). Every row has an institution in the config. A second team member has reviewed it.
- **Cost:** 0 API calls. Be polite to lab websites (1 request/second, cache the HTML in `data/cache/web/`).

### S02: author candidates
- **Do:** for each lab, paginate

  ```
  authors?filter=affiliations.institution.id:<lab_id>
          &select=id,display_name,display_name_alternatives,orcid,works_count,summary_stats,affiliations,last_known_institutions
  ```

  For each author, compute `years_at_lab` from `affiliations[*]` where `institution.id == lab`, keeping years within the window. Store in `author_candidates.parquet`.
- **Accept:** row counts are close to the plan's "ever affiliated" numbers (≈ 3.1k / 2.4k / 1.6k / 5.0k).
- **Cost:** about 65 list calls.

### S03: match faculty to author IDs (+ human review)
- **Algorithm per roster row (lab L):**
  1. If the roster has an `orcid`, select the candidates with the same ORCID: `method=orcid`, score 100.
  2. Otherwise compute `score(name, [display_name] + alternatives)` for every candidate at L. Keep candidates with score ≥ `review_min_score` (70) **and** at least `min_years_at_lab_in_window` year at L in the window.
  3. Rank by (score, years at L in window, works_count).
  4. **Auto-accept** every candidate with score ≥ 92 whose name is initials-compatible. Several IDs may be accepted, because OpenAlex splits profiles. If two *different* plausible people share the surname and initials (e.g., two "S. Kumar"), **do not auto-accept**; send them to review.
  5. Write the rest to `data/review/faculty_match_review.csv` with the top-5 candidates per faculty: `faculty_id, name, cand_author_id, cand_name, score, years_at_lab, works_count, orcid, sample_titles, decision`. `sample_titles` = 3 recent titles from `works?filter=author.id:<A>&per_page=3&select=title` (1 cheap call each, only for review rows).
- **Human review:** fill `decision` with `accept` or `reject`. Overrides go in `data/manual/faculty_match_overrides.csv` (`faculty_id,author_id,decision`), which is applied last.
- **Gap check (D2):** list candidates with ≥ 5 years at L in 2018–2026 and `works_count` ≥ 20 that are unmatched to any faculty member, in `data/review/roster_gaps.csv`. Review them and add genuine faculty to the roster.
- **Accept:** ≥ 95% of roster faculty have at least one author ID. Print the unmatched list (it goes into the report's limitations).
- **Cost:** about 100 small calls (sample titles).

### S04: fetch works
- **Faculty corpus:** collect all accepted author IDs (~300–450). For each batch of 100:

  ```
  works?filter=authorships.author.id:A1|…|A100,publication_year:2016-2026
       &select=WORK_SELECT&per_page=200&cursor=*
  ```

  Append to `works_raw/faculty.jsonl.gz`.
- **Lab corpus (coverage and Jaccard base):** for each lab, `filter=authorships.institutions.lineage:<lab>,publication_year:2016-2026`, written to `works_raw/lab_<short>.jsonl.gz`.
- **Truncation fix:** for any work with `len(authorships) == 100`, call `works/<W>` (free) and replace the authorships.
- **Accept:** the number of unique work IDs is reported, and the per-lab corpus counts equal the S00 counts.
- **Cost:** faculty ≈ 5 batches × ~15 pages ≈ 75 calls; corpus ≈ 55 calls.

### S05: normalise, filter, deduplicate
1. Flatten the raw JSON into `works.parquet` and `authorships.parquet` (§6). Feed every institution object into the registry. Save `institutions.parquet` with clusters (D12).
2. **Type filter (D7):** keep the work if `work_type ∈ include_work_types`, `source_type ∈ {journal, conference}` (or `work_type == conference-paper`), and it is not retracted. Log the counts dropped per reason.
3. **Faculty-paper link with affiliation check (D4).** For each authorship whose `author_id` maps to faculty F at lab L, there is a link when:
   - any `inst_id` has L's ID in its lineage (`affil_method=lineage`), **or**
   - `raw_affiliations` contains any alias of L, case-insensitive (`affil_method=raw_string`).

   Otherwise the authorship is **not** a lab paper for F, so drop that link.
4. **Deduplicate:**
   - Group by DOI (lowercase); keep the record with the highest `cited_by_count`, then the earliest `publication_date`.
   - For records without a DOI, group by (`norm(title)`, year) and do the same.
   - Keep a mapping `dupe_of` for traceability.
5. **IMTECH 2026 anomaly:** print the distribution of `publication_date`, the top journals and the top authors for IMTECH 2026 works, then decide and record in `qa_log.md`:
   - if they are genuine, keep them;
   - if it is a date artefact (e.g., an online-first 2025 paper recorded as 2026), keep OpenAlex's year but document it;
   - if they are wrong-institution records, exclude them via an override list.
- **Accept:** each faculty-paper link has a lab; no duplicate DOIs; the coverage ratio (faculty-corpus papers ÷ lab-corpus papers after the same type filter) is printed per lab.

### S06: enrich (quartile, CORE, research area, department)
- **Sources:** for unique `source_id`s, call `sources?filter=openalex:S1|…|S100&select=id,display_name,type,issn_l,issn,host_organization_name` (about 20 calls).
- **SJR manual download (R2):**
  1. Open scimagojr.com → *Journal Rankings*.
  2. For each year 2016 → latest, choose *All subject areas*, *All types*, *Download data*.
  3. Save the file as `data/manual/sjr/scimagojr_<YEAR>.csv`.

  Files are `;`-separated with decimal commas. Useful columns: `Title`, `Issn` (e.g. `"15548627, 15548635"`), `SJR Best Quartile`, `Type`, `Categories`.
- **Quartile join (D8):**
  ```python
  def issn_norm(x): return x.replace("-", "").strip().upper()
  # build dict per SJR year: issn -> best_quartile, title_norm -> best_quartile
  y_used = min(paper_year, max(sjr_years))   # year_matched; also fall back to y_used-1 if missing
  # try: issn_l, then each issn; then norm(title) == norm(SJR Title)
  # "-" in SJR Best Quartile means unranked -> NA
  ```
- **CORE:** the export has no header. Columns are `id,title,acronym,source,rank,dblp,for1,for2,for3`. For conference rows, match by normalised title (token-set ≥ 90) or by acronym found in the source name. `rank ∈ {A*, A, B, C}`; anything else is NA.
- **Research area:** `primary_topic` → topic, subfield, field, domain (already in works).
- **Department:** taken from the roster (D20). If it is blank, use the faculty member's modal `subfield` and set `dept_source=openalex`.
- **Accept:** print quartile coverage per lab (target ≥ 85% of journal papers) and the top-20 unmatched journals by paper count for a manual look. Fix obvious ones by adding rows to `data/manual/quartile_overrides.csv` (`issn,quartile`).

### S07: Indian in-flow and out-flow
Let `OUR` = the set of work IDs in the **final dataset** (after S05).

- **Out-flow** (works we cite that have an Indian author). For each batch of 100 IDs from `OUR`:

  ```
  works?filter=cited_by:W1|…|W100,institutions.country_code:IN
       &select=id,doi,title,publication_year,cited_by_count,authorships
  ```

  Store in `outflow_works.parquet` and add their institutions to the registry. The edges themselves are built in S09 by intersecting each of our works' `referenced_works` with this set.
- **In-flow** (Indian works citing us). For each batch of 100:

  ```
  works?filter=cites:W1|…|W100,institutions.country_code:IN,publication_year:2016-2026
       &select=id,doi,title,publication_year,cited_by_count,primary_location,authorships,referenced_works
  ```

  Deduplicate by ID across batches. Store in `inflow_works.parquet`.
- Save `inst_ids` per work as the **Indian non-umbrella** set (§5.4).
- **Accept:** print the totals. Sanity check: the sum over our works of `|referenced_works ∩ outflow|` is > 0 for every lab, and the in-flow count is less than the sum of `cited_by_count`.
- **Cost:** about 70 batches × (1–5 pages) ≈ 150–300 calls each way.

### S08: build `group29_data.csv`
Rows = `faculty_papers` (one per paper × faculty × lab, D5), joined with works, quartiles and the roster.

**Exact column order:**
```python
REQUIRED = ["group","institution","author","title","year","type","journal_name","issn","doi",
            "citations","quartile","coauthor_institutes","cites_indian_inst","cited_by_indian_inst"]
EXTRA = ["openalex_id","author_openalex_ids","faculty_id","department","designation","field","subfield",
         "primary_topic","n_authors","is_corresponding","coauthor_institutes_all","sjr_year_used"]
```

**Field rules:**

| Column | Rule |
|---|---|
| `group` | `29` |
| `institution` | Lab short name |
| `author` | Roster name |
| `title` | Collapse whitespace; drop HTML tags (`<i>`, `<sub>`) |
| `type` | `journal` / `conference` (D7) |
| `issn` | `issn_l`, else the first ISSN; blank for conferences |
| `doi` | OpenAlex's DOI URL. If it is missing, write the OpenAlex work URL (D6). |
| `citations` | Integer |
| `quartile` | `Q1`–`Q4`, `A*`/`A`/`B`/`C`, or `NA` |
| `coauthor_institutes` | `"; ".join(sorted(label(i) for i in indian_insts(work) if partner_ok(i, own_lab=L)))`. Empty string if there are none. |
| `coauthor_institutes_all` | The same, including foreign institutions and our other labs, in `Name (CC)` format |
| `cites_indian_inst` | `"TRUE"` if ∃ r ∈ referenced_works with `r ∈ outflow ∪ OUR` and `{i ∈ inst_ids(r) : partner_ok(i, L)} ≠ ∅`; else `"FALSE"` |
| `cited_by_indian_inst` | `"TRUE"` if ∃ c ∈ inflow with `w ∈ c.referenced_works` and `{i ∈ inst_ids(c) : partner_ok(i, L)} ≠ ∅`, or ∃ c ∈ OUR citing w with such an institution; else `"FALSE"` |

**Writing the file:**
- `df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")`.
- Sort by institution, author, year, title.
- Also write `metadata.json` with: collection date, OpenAlex snapshot note, row and paper counts per lab, and the git commit hash.

**Accept:** run `s15_validate --only main` and pass.

### S09: citation network
```python
OUR = set(works_final.work_id)
inst = {w: indian_insts(...) for w in OUR | outflow | inflow}       # sets, our labs as short names
edges = []
for w in OUR:                                   # internal + out-flow
    for r in referenced_works[w]:
        if r in OUR:
            edges.append((w, r, "internal"))
        elif r in outflow_ids:
            edges.append((w, r, "outflow"))
for c in inflow_ids - OUR:                      # in-flow
    for r in set(inflow_refs[c]) & OUR:
        edges.append((c, r, "inflow"))
def cross(s, t):  # D14
    return any(x != y for x in inst[s] for y in inst[t])
# keep: all internal edges; outflow/inflow edges only if cross(s, t) is True (others counted, not exported)
```

**`citation_network.csv` columns:**
```
source_doi,target_doi,source_inst,target_inst,year,
source_openalex_id,target_openalex_id,edge_scope,cross_institute,target_year
```
`source_inst` / `target_inst` = `"; ".join(our labs first, then other labels)`. `year` = source year.

**Analysis (G_int):**
```python
G = nx.DiGraph()
G.add_nodes_from(OUR)                    # include isolates
G.add_edges_from((s, t) for s, t, sc in edges if sc == "internal")
pr = nx.pagerank(G, alpha=0.85)
indeg = dict(G.in_degree())
wcc = max(nx.weakly_connected_components(G), key=len)
```
- **Lab-to-lab matrix:** for internal edges, count (lab_s, lab_t) over the products of our-lab memberships.
- **Outputs:**
  - `networks/citation_internal.gexf` (node attrs: label = short title, lab, year, field, citations, pagerank, indeg);
  - `networks/citation_nodes.csv`;
  - `stats/citation_pagerank_top.csv` (top 10 overall and per lab);
  - `stats/citation_indegree_dist.csv`;
  - `stats/lab_citation_matrix.csv`;
  - `stats/network_summary.json` (nodes, edges, density, WCC size, share with in-degree 0, edges dropped as non-cross).
- **Dashboard subgraph:** the top `dashboard_citation_nodes` nodes by PageRank, plus internal edges among them. Precompute positions with `nx.spring_layout(sub, seed=42, k=…)` so the browser uses a `preset` layout (fast and stable). Write `networks/citation_dash.json`.

### S10: authorship network
```python
key = lambda a: f"F:{fac_of[a.author_id]}" if a.author_id in fac_of else f"A:{a.author_id}"
for w in works_final:
    auths = authorships[w]               # full list (truncation fixed)
    if len(auths) > max_authors_for_pairs:
        skipped += 1; continue
    people = {}                          # key -> (name, inst_label, internal?)
    for a in auths:
        k = key(a)
        lab = first our_lab among a.inst_ids
        inst_label = lab or label(first Indian non-umbrella inst) or label(first inst) or "Unknown"
        people[k] = (display_name, inst_label, lab is not None)
    for (ka, pa), (kb, pb) in combinations(sorted(people.items()), 2):
        if pa[2] or pb[2]:                         # at least one endpoint internal (D15)
            rows.append(...)
```

**`authorship_network.csv` columns:**
```
author_a,author_b,paper_doi,inst_a,inst_b,year,
author_a_id,author_b_id,a_is_faculty,b_is_faculty,cross_institution,indian_link
```
- `cross_institution` = `inst_a != inst_b`.
- `indian_link` = both endpoints are Indian and their institutions differ.
- Keys are sorted so that `author_a_id < author_b_id`.

**Graphs:**
```python
Gf = nx.Graph()                    # faculty-only (primary)
Gf.add_nodes_from(all faculty with ≥1 dataset paper, attrs: name, lab, department)
for each pair where both are faculty: Gf[a][b]["weight"] += 1  (count unique papers)
Gi = nx.Graph()                    # internal: both endpoints internal
deg  = nx.degree_centrality(Gf)
stre = dict(Gf.degree(weight="weight"))
btw  = nx.betweenness_centrality(Gf, normalized=True)                     # exact
btwi = nx.betweenness_centrality(Gi, k=min(1000, len(Gi)), seed=42, normalized=True)
comms = nx.community.louvain_communities(Gf, weight="weight", resolution=1.0, seed=42)
Q = nx.community.modularity(Gf, comms, weight="weight")
```
(Optional: run Leiden via `igraph` + `leidenalg` on Gi and report Q for both.)

**Hub authors (slide 12):** for each faculty member, `n_partner_insts` = distinct `partner_ok` Indian institutions among co-authors across their papers. Rank them. Also list the top betweenness nodes in Gi.

**Outputs:**
- `networks/authorship_faculty.gexf`, `authorship_internal.gexf`;
- `stats/authorship_centrality.csv` (faculty_id, name, lab, dept, degree, strength, betweenness, betweenness_internal, community);
- `stats/communities.csv` (community, size, top labs and departments, top 3 members);
- `stats/hub_authors.csv`;
- `networks/authorship_dash.json` (Gf full plus a trimmed Gi, with precomputed positions).

### S11: `indian_connections.csv` and Jaccard
- **Shared papers:** for each final work w and each of our labs L on w (from faculty_papers), for each partner P in `indian_insts(w)` with `partner_ok(P, L)`: increment `shared[L, P]` and add `cited_by_count(w)` to `shared_cit[L, P]`.
- **Citation exchange** (from exported cross edges plus internal edges):
  - for s→t, for every L ∈ inst[t] ∩ OUR_LABS and P ∈ inst[s] with `partner_ok(P, L)`: `cites_in[L, P] += 1`;
  - for every L ∈ inst[s] ∩ OUR_LABS and P ∈ inst[t] with `partner_ok(P, L)`: `cites_out[L, P] += 1`.
- **Columns:**
  ```
  your_inst,partner_inst,shared_papers,total_citations,
  cites_in,cites_out,shared_papers_citations,partner_openalex_id,partner_cluster,
  cross_cluster,pair_label,partner_in_group,partner_is_csir_academy,jaccard_topics,jaccard_subfields
  ```
  - `total_citations = cites_in + cites_out` (A8).
  - `partner_in_group` = the partner is one of the other three labs.
  - `pair_label` = e.g. `CSIR↔IIT`.
- **Jaccard (D19):**
  - For each lab: `group_by("works", f"authorships.institutions.lineage:{L},publication_year:2016-2026", "primary_topic.id")`, then take the top-100 keys.
  - For each of the lab's top-30 partners by `shared_papers`: the same call on the partner ID.
  - `J = |A∩B| / |A∪B|`. Subfields work the same way with `primary_topic.subfield.id`.
- **Also write:**
  - `stats/partner_ranking.csv` (per lab, sorted by shared papers);
  - `stats/cross_cluster_summary.csv` (pair_label → partners, shared papers, citations);
  - `stats/citation_flow_summary.csv` (per lab: in, out, ratio = in/out);
  - `stats/citation_flow_year.csv` (lab × year × {in, out}, by citing year);
  - `stats/top_citing_institutes.csv` (top 10 per lab by `cites_in`);
  - `stats/top_citing_papers.csv` (top 10 in-flow works per lab by `cited_by_count`).
- **Cost:** about 4 + ~100 group-by calls.

### S12: statistics and figures
**Tables** in `outputs/stats/` (all derived from the final dataset):

| File | Content |
|---|---|
| `inst_summary.csv` | Per lab: faculty, papers, citations, mean and median citations, % uncited, Q1 fraction (+ coverage), institutional h, CAGR 2016–2025, mean authors per paper, % foreign collab, % Indian partner collab, papers per faculty |
| `inst_year_counts.csv` | Lab × year papers and citations (2026 flagged partial) |
| `inst_quartile.csv` | Lab × {Q1..Q4, NA} counts and shares |
| `inst_top_journals.csv` | Top 5 per lab: journal, papers, citations, quartile |
| `inst_fields.csv`, `inst_subfields.csv` | Shares, top 10 + other |
| `top_cited_papers.csv` | Top 10 overall and per lab |
| `faculty_metrics.csv` | Per faculty: papers, citations, cites/paper, h_window, h_lifetime, top_journal, q1_fraction, first_year, last_year, department + network metrics merged from S10 |
| `dept_metrics.csv` | Per lab × department |
| `hindex_hist.csv` | Lab × bin (0–4, 5–9, …) |
| `core_ranks.csv` | Lab × rank counts, plus N matched of M conference papers |

**Window h-index:**
```python
def h_index(cits):
    c = sorted(cits, reverse=True)
    return sum(1 for i, x in enumerate(c, 1) if x >= i)
```

**Figures** (matplotlib, 200 dpi, consistent lab colours from one palette in `config/settings.yaml`):
- `trend.png`, `quartiles.png`, `top_journals.png`, `hindex_hist.png`, `fields.png`
- `pagerank_top10.png`, `indegree_dist.png` (log-log), `flow_year.png`, `top_citing_insts.png`
- `authorship_faculty.png` (spring layout, community colours), `partners.png`, `cross_cluster.png`

### S13: dashboard (details in §8)

### S14: report (details in §9)

### S15: validate and package
`python -m dpcn run s15` performs every check in plan §11 and prints a pass/fail table. Core checks:

```python
REQ = {
 "group29_data.csv": REQUIRED,
 "citation_network.csv": ["source_doi","target_doi","source_inst","target_inst","year"],
 "authorship_network.csv": ["author_a","author_b","paper_doi","inst_a","inst_b","year"],
 "indian_connections.csv": ["your_inst","partner_inst","shared_papers","total_citations"],
}
for f, cols in REQ.items():
    df = pd.read_csv(sub / f, dtype=str, keep_default_na=False)
    assert list(df.columns[:len(cols)]) == cols, f"{f}: column order"
main = pd.read_csv(sub / "group29_data.csv", dtype=str, keep_default_na=False)
assert (main.group == "29").all()
assert main.institution.isin(LAB_SHORTS).all() and set(main.institution) == set(LAB_SHORTS)
assert main.year.astype(int).between(2016, 2026).all()
assert main.type.isin(["journal", "conference"]).all()
assert main.quartile.isin(["Q1","Q2","Q3","Q4","A*","A","B","C","NA"]).all()
for b in ["cites_indian_inst", "cited_by_indian_inst"]:
    assert main[b].isin(["TRUE", "FALSE"]).all()
assert main.doi.str.match(r"^https://(doi\.org/10\.|openalex\.org/W)").all()
assert not main.duplicated(["openalex_id", "faculty_id", "institution"]).any()
# + every lab has every year; consistency of flags vs edges; scope checks; no self-loops
```

**Package:**
- Copy the deliverables to `outputs/submission/`.
- Write `README.txt` containing:
  - file list, row counts and collection date;
  - the decisions summary (D2, D4, D5, D8, D10, D11, D13–D16);
  - the column dictionary, including the extra columns;
  - a contact line.
- Zip to `group29_week2.zip` (the four CSVs + README + metadata) and `group29_week3.zip` (report + dashboard).

---

## 8. Dashboard implementation (S13)

**Architecture (D21):** Python (Jinja2) renders `dashboard_src/template.html.j2` into `outputs/submission/group29_dashboard.html`.

- All data is embedded as one JSON blob: `<script id="data" type="application/json">…</script>`.
- `app.js` and `styles.css` are inlined.
- Libraries are loaded from CDN by default. `--offline` inlines copies from `dashboard_src/vendor/`, giving a truly single-file offline dashboard.

**Libraries (pinned):**
- Plotly.js `2.35.2` (charts)
- Tabulator `6.3.0` (sortable, searchable tables)
- Cytoscape.js `3.30.2` (network graphs)

All three are available on cdnjs or jsDelivr.

**Data bundle** (built from `outputs/stats` and `outputs/networks`):
```json
{
  "meta": {"group": 29, "collected": "2026-10-xx", "labs": ["CSIR-CCMB","CSIR-IGIB","CSIR-IMTECH","CSIR-CDRI"], "colors": {...}},
  "kpis": {"CSIR-CCMB": {...}, "ALL": {...}},
  "trend": [{"lab":"CSIR-CCMB","year":2016,"papers":..,"citations":..,"partial":false}, ...],
  "quartiles": [...], "top_journals": [...], "faculty": [...], "hindex_hist": [...],
  "fields": [...], "subfields": [...], "top_cited": [...], "core": [...],
  "citation_graph": {"nodes":[{"id","label","lab","year","pr","indeg","doi","x","y"}], "edges":[{"s","t"}]},
  "pagerank_top": [...], "indegree_dist": [...], "flow_year": [...], "flow_summary": [...],
  "top_citing_insts": [...], "top_citing_papers": [...],
  "authorship_faculty": {"nodes":[{"id","name","lab","dept","deg","btw","comm","x","y"}], "edges":[{"s","t","w","cross"}]},
  "authorship_internal": {...}, "centrality": [...], "communities": [...], "hubs": [...],
  "partners": [...], "cross_cluster": [...]
}
```

**Layout:** header with title and a **lab selector** (All, CCMB, IGIB, IMTECH, CDRI), then six tabs. Every render function reads `state.lab` and filters the data.

| Tab | Panels (spec #) | Implementation |
|---|---|---|
| Overview | KPI tiles; **(1) trend** | Plotly grouped bars or lines per lab; 2026 bar hatched or labelled "partial" |
| Journals | **(3) quartile**, **(5) top-5 journals**, **(9) CORE** | Stacked 100% bars per lab; horizontal bars; CORE bars, or a note card "N of M conference papers are CORE-ranked" |
| Faculty | **(2) faculty list**, **(4) performance table**, **(6) h-index histogram** | One Tabulator table (columns: name, dept, h-window, papers, citations, top journal, Q1 %, degree) with header filters and sorting; a "compact" toggle shows the panel-2 subset; Plotly histogram |
| Research | **(7) research areas**, **(8) most-cited top 10** | Plotly sunburst (field → subfield); Tabulator with DOI links |
| Citation network | **(10)** | Cytoscape `preset` layout; node size ∝ PageRank, colour = lab, arrows; tooltip/side panel on tap; PageRank top-10 table; in-degree log-log; flow year lines; top-10 citing institutes bars; impact-ratio tiles |
| Collaboration | **(11)** | Cytoscape graph with toggles (faculty / internal; colour by community / lab); cross-lab edges dashed; centrality table; partner ranking with cluster badges and Jaccard; cross-cluster summary bars; hub authors |

**Performance rules:** at most ~600 nodes and ~3,000 edges per Cytoscape view. Use precomputed positions. Disable animation on large graphs. Lazy-render a tab only the first time it opens.

**Accept:** open the HTML file directly in a browser. All 11 panels render for each lab and for "All". There are no console errors. The file size is below 15 MB.

---

## 9. Report implementation (S14)

- `python-pptx` builds `outputs/report/group29_report.pptx` (16:9) following the 10-slide outline in plan §7.8.
- Each slide has a title, 1–2 figures from `outputs/figures`, and up to 4 bullets.
- **Bullets come from `report_src/findings.yaml`.** The team writes the text after looking at the stats. Numbers are placeholders filled from the stats tables, so every number is traceable:
  ```yaml
  slide3:
    - "CDRI is the most productive lab ({inst_summary[CSIR-CDRI].papers} papers, CAGR {inst_summary[CSIR-CDRI].cagr:.1%})."
  ```
- Slide 2 automatically lists the coverage numbers (roster match %, quartile coverage, coverage ratio) and limitations.
- Export to PDF by hand (PowerPoint: *Save As → PDF*) or with LibreOffice:
  ```bash
  soffice --headless --convert-to pdf outputs/report/group29_report.pptx --outdir outputs/report
  ```
- **Accept:** ≤ 10 slides, every required metric present (check against plan §2.6), and peer-reviewed by two members.

---

## 10. Runbook, API budget and timing

**First run (in order):**
```bash
python -m dpcn run s00
```
```bash
python -m dpcn run s01 --scrape all
```
*(Manual: clean the roster, download SJR files, review matches.)*
```bash
python -m dpcn run s02
```
```bash
python -m dpcn run s03
```
*(Manual: fill `data/review/faculty_match_review.csv`, then re-run s03 to apply decisions.)*
```bash
python -m dpcn run all --from s04
```

**Re-run after any manual change:** `python -m dpcn run all --from <step>`. Cached calls are free.

**Estimated OpenAlex usage** (list calls at $0.0001 each; single lookups free):

| Step | Calls | Cost |
|---|---:|---:|
| S00 verify | 4 | — |
| S02 author candidates | ~65 | $0.007 |
| S03 review samples | ~100 | $0.010 |
| S04 faculty works + lab corpus | ~130 | $0.013 |
| S06 sources | ~20 | $0.002 |
| S07 out-flow + in-flow | ~300–600 | $0.03–0.06 |
| S11 Jaccard group-bys | ~110 | $0.011 |
| **Total** | **~750–1,050** | **≈ $0.10** |

This fits easily in one free key's $1/day. Without a key it would hit the $0.10/day cap, so **use keys**.

**Wall-clock:** a full uncached run takes about 15–30 minutes. A cached re-run takes about 1–2 minutes.

---

## 11. Testing

`pytest -q` runs these tests:

- `tests/test_names.py`:
  - `initials_compatible("R. K. Mishra", "Rakesh Kumar Mishra")` is True;
  - `("S. Kumar", "Sanjay Gupta")` is False;
  - surname-first ordering works;
  - title stripping works.
- `tests/test_institutions.py`:
  - classify representative names: "Indian Institute of Technology Delhi" → IIT; "IISER Pune" → IISc/TIFR/IISER; "CSIR-IICT" (lineage) → CSIR; "BARC" → DAE; "AIIMS New Delhi" → Medical;
  - umbrella IDs are never `partner_ok`;
  - AcSIR is excluded when the config says so.
- `tests/test_flags.py`: toy works with known references and citers check D14 / `cites_indian_inst` / `cited_by_indian_inst` and the `cites_in` / `cites_out` counts.
- `tests/test_networks.py`: a 5-node toy citation graph has known PageRank ordering and in-degree; a toy co-authorship graph checks the > 50-author skip and canonical pair ordering.
- `tests/test_schema.py`: S15 checks run on a tiny fixture.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 400 on a works query | More than 100 OR values, a typo in the filter field, or `select` used with `group_by` | Check the batch size; print `r.url`; remove `select` from group-by calls |
| `BudgetExceeded` | Daily $ nearly used up | Wait for midnight UTC reset, or use another member's key; the cache keeps progress |
| HTTP 429 | Too many calls too fast | The client backs off automatically; raise `sleep_s` |
| Faculty with 0 papers | Wrong or missing author ID, or the D4 affiliation check failed | Inspect `author_candidates` for that name; check `raw_affiliations`; add an override |
| A faculty member's paper count looks far too high | A merged OpenAlex profile (another person with the same name) | D4 usually fixes this; otherwise reject that author ID in overrides |
| Many `NA` quartiles | Missing SJR year file, or ISSN formats differ | Confirm all yearly files exist; check the hyphen-stripping and the `Issn` split on `", "` |
| Dashboard blank | JSON too large, or a JS error | Open the browser console; reduce graph sizes in settings |
| Excel mangles DOIs or names | Excel auto-formatting and encoding | Open via *Data → From Text/CSV*, UTF-8. The CSVs themselves are fine. |
| Paths with spaces fail in shell commands | The repo path contains spaces | Always quote paths; the code uses `pathlib` relative to the repo root |

---

## 13. Conventions and git workflow

- **Code:**
  - Python 3.12 with type hints.
  - Format with `black`; lint with `ruff` (optional).
  - One module per step; shared logic only in `openalex.py`, `names.py`, `institutions.py` and `io.py`.
  - No hard-coded IDs or paths in step code; everything comes from `config/`.
- **Data hygiene:**
  - Commit `data/manual/*`, `data/review/*` (decisions) and `outputs/submission/*` at milestones.
  - Never commit `data/cache` or `data/interim`; they can be regenerated.
- **Branches:** `main` (protected) ← `feat/sXX-...` via pull request with one reviewer. Tag the milestones `v-week2` and `v-week3`.
- **Notebooks:** allowed for exploration in `notebooks/`. Anything that produces a submitted number must live in `src/dpcn/steps`.
- **QA log:** `docs/qa_log.md` records every manual decision: the IMTECH anomaly, roster gaps, match overrides, quartile overrides and spot-check results.

**Build order for coding sessions:**
1. Scaffold the repo, config, `openalex.py`, CLI and S00.
2. S01 scrapers.
3. S02–S03 matching and review sheet.
4. S04–S05.
5. S06.
6. S07–S08, then S15 checks for the main CSV (**Week-2 draft**).
7. S09–S11 (**Week-2 submission**).
8. S12.
9. S13 dashboard.
10. S14 report and final S15.
