# Group 29 Handoff: status, plan and what to do next

Written 2026-10-13. Read this first. It tells you what exists, what state the data is in, how to run everything, and exactly what to do next. The other documents go deeper:

| Document | Use it for |
|---|---|
| [01_PROJECT_PLAN.md](01_PROJECT_PLAN.md) | What the assignment requires, ambiguities and how we resolved them, scope, all method decisions (D1–D22), timeline, risks, requirement-to-deliverable checklist |
| [02_IMPLEMENTATION_GUIDE.md](02_IMPLEMENTATION_GUIDE.md) | How each pipeline step S00–S15 works: inputs, outputs, logic, API cost, acceptance checks; dashboard and report design |
| [qa_log.md](qa_log.md) | Dated log of every finding, anomaly and manual decision so far, including open items |
| This file | Current status, setup, day-to-day workflow, next steps in order, pitfalls |

---

## 1. The project in one paragraph

DPCN Research Mapping Project (instructor: Chittaranjan Hens), **Group 29**. We map 2016–2026 research output of four CSIR biology labs: **CCMB** (Hyderabad), **IGIB** (Delhi), **IMTECH** (Chandigarh) and **CDRI** (Lucknow). Deliverables: **Week 1–2** `group29_data.csv`, `citation_network.csv`, `authorship_network.csv`, `indian_connections.csv`; **Week 3** a statistics report (at most 10 slides) and an interactive dashboard with 11 panels including a citation network and a co-authorship network. All analysis stays within our four labs; links to other Indian institutions appear only in the raw files. Data source is OpenAlex, with Scimago (journal quartiles) and CORE (conference ranks) for enrichment.

## 2. Status at a glance

Updated 2026-10-14. Every step is built and has run; `python -m dpcn run s15` passes all checks.

| Step | What it does | State |
|---|---|---|
| S00 | Verify the four labs in OpenAlex | **Done** |
| S01 | Faculty roster | **Done**: 294 faculty = 232 from the websites + 62 added from authorship evidence (D25, qa_log 2026-10-14) |
| S02 | Author candidate pool | **Done**: 11,892 rows |
| S03 | Match faculty to OpenAlex IDs | **Done**: 278 of 294 matched (94.6%); review decisions recorded in the sheet and in qa_log |
| S04 / S05 | Raw works; inclusion rules | **Done**: 6,063 papers, 8,107 faculty-paper rows; coverage of each lab's output 71–81% |
| S06 | Quartiles, CORE, departments | **Done**: SJR quartile known for 93–98% of journal papers |
| S07 | Indian in/out-flow | **Done**: 33,936 Indian works cited, 31,482 Indian works citing (about 600 calls, $0.12) |
| S08 | `group29_data.csv` | **Done**: 14 required columns + 18 extras |
| S09 | Citation network | **Done**: 64,240 exported edges (9,634 internal); PageRank, in-degree, lab matrix |
| S10 | Authorship network | **Done**: 127,062 pair rows; faculty graph 274 nodes / 1,311 links, 31 Louvain communities (Q 0.54) |
| S11 | `indian_connections.csv` + Jaccard | **Done**: 6,182 lab–partner rows, Jaccard for each lab's top 30 partners |
| S12 | Statistics tables and figures | **Done**: `outputs/stats/`, `outputs/figures/` |
| S13 | Dashboard | **Done**: `outputs/submission/group29_dashboard.html`, 6.7 MB, opens offline (libraries inlined; `--cdn` for a small file) |
| S14 | Report | **Done**: `outputs/report/group29_report.pptx` + `.pdf`, 10 slides, every number read from `outputs/stats` |
| S15 | Validate and package | **Done**: all checks pass; `group29_week2.zip`, `group29_week3.zip` |

Nothing has been submitted yet. Open decisions that affect the work (see also section 8):

1. **CDRI scope.** The slide deck lists CDRI under Group 29; the instruction note's table puts CDRI under Groups 27–28. We included it. Confirm with the instructor; removing it is deleting one block in `config/institutions.yaml` and re-running from S02.
2. Five more questions for the instructor are in plan section 14 (definition of faculty, `total_citations` meaning, h-index window, extra columns, dashboard format).

## 3. Setup on a new machine

Requirements: Git, Miniconda (or any Python 3.11+), a free OpenAlex account.

```bash
git clone https://github.com/Devansh061105/dpcn-group29.git
```
```bash
cd dpcn-group29
```
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

**API key.** Sign up at openalex.org, open Settings, copy the API key. Copy `.env.example` to `.env` and fill in `OPENALEX_API_KEY=` (and optionally `OPENALEX_EMAIL=`). `.env` is git-ignored: never commit or paste a key. A free key gives a $1/day budget (about 10,000 list calls); without one the budget is $0.10/day. Every team member should use their own key.

**Check the setup:**

```bash
python -m dpcn list
```
```bash
python -m dpcn run s00
```
```bash
pytest -q
```

`s00` should print four labs with status OK; `pytest` should report 102 passed.

**What is and is not in the repository.** Committed: code, config, docs, the faculty roster (`data/manual/faculty_roster.csv`), the scraped roster drafts and the S03 review sheets (`data/review/`). **Not committed** (regenerable, listed in `.gitignore`): the API response cache `data/cache/`, intermediate tables `data/interim/`, and `.env`. So on a fresh clone you re-run S02 to S05 once to rebuild `data/interim/` (about 600 API calls, roughly 30 minutes, well within one day's $1 budget). After that every step is cached and free to repeat.

## 4. How the code is organised

```
config/            institutions.yaml (the 4 labs and their OpenAlex IDs), settings.yaml (thresholds, paths),
                   cluster_rules.yaml (how partner institutions are classified)
src/dpcn/
  cli.py           python -m dpcn list | run <step> | run all [--from sXX]
  config.py        loads the YAML files and .env
  openalex.py      cached, budget-aware API client (every response cached on disk)
  web.py           polite cached fetcher for lab websites
  names.py         name cleaning and the name-matching rules
  corpus.py        fetches each lab's papers and builds the "authors with lab papers" pool (shared by S03 and S04)
  institutions.py  registry of every institution seen: ours, Indian, umbrella, partner cluster (rules in config/cluster_rules.yaml)
  steps/s00..s05   the implemented steps; each exposes run(cfg, oa, argv)
data/manual/       human-maintained inputs (faculty_roster.csv; sjr/ and core/ are empty, to be filled)
data/review/       files a person reads and edits (match review sheet, roster drafts, roster gap list)
outputs/           submission/, stats/, networks/, figures/, report/ (all empty so far)
tests/             102 offline unit tests (no network needed)
```

Design rules the code follows:

- **Cache everything.** `OpenAlex.get` stores each response as gzip JSON under `data/cache/openalex/`, keyed by URL without the API key. Re-running a step is free. It stops making live calls once 90% of the daily budget is used.
- **Steps are idempotent** and read only from `data/manual`, `data/review`, `data/interim` or earlier outputs.
- **No hard-coded IDs or paths in step code**; everything comes from `config/`.
- **Human decisions are never overwritten.** S01's merge only adds; S03 reads back every `accept`/`reject` from the review sheet.
- **Every number in the final report must come from `outputs/stats/`**, never typed by hand.

## 5. What has been done, with the numbers

### S00: verification
All four ROR IDs and OpenAlex IDs in `config/institutions.yaml` match OpenAlex. Works in 2016–2026 (all types): CCMB 2,333, IGIB 2,643, IMTECH 1,636, CDRI 3,952.

### S01: faculty roster
Scraped from each lab's website (the sites list scientists only, which fits our definition of faculty: scientists and principal investigators, not students or technical staff).

| Lab | Faculty | Source page | Notes |
|---|---:|---|---|
| CCMB | 41 | `/dept_people/all-faculty` plus each profile | has departments |
| IGIB | 42 | `/ScientistDirectory.html` (names embedded in a script block) | has departments (decision units); 28 ORCIDs scraped |
| IMTECH | 48 | `/en/.../scientists` (the default page is Hindi) | **no departments published**; the site's filter does not work |
| CDRI | 101 | 12 division pages | division name used as department |

Result: `data/manual/faculty_roster.csv` (232 rows). Columns include `faculty_id` (e.g. `CCMB-001`), name, designation, department, institution, profile URL, ORCID, status (`current`/`former`), plus matching evidence scraped from profile pages: `profile_dois`, `profile_pmids`.

### S02: author candidate pool
Every OpenAlex author with an affiliation record at one of the labs: 11,892 rows (CCMB 2,989; IGIB 2,412; IMTECH 1,604; CDRI 4,887), each with years at the lab, works count, ORCID and a `suspect_merged` flag (40 or more affiliations, or 1,500 or more works, which usually means several people merged into one profile).

### S03: matching faculty to OpenAlex authors
Candidate pool: authors who appear on lab-affiliated papers in the window (more reliable than profile affiliation records), combined with S02's profile data. Evidence, strongest first:

1. **ORCID** (28 faculty). The author's name must still fit; the IGIB website lists one person's ORCID on another person's page, and such a mismatch is sent to review.
2. **Papers listed on the person's own web page** (830 DOIs and 87 PubMed IDs were looked up): the author on that paper whose name fits is the person.
3. **Name match**, accepted automatically only when unambiguous: display name only (never an alternate name), not a merged profile, not initials-only, has lab papers, and no different person with a comparable record.
4. **Manual** decisions from the review sheet.

Outputs (in `data/interim/`, regenerated by running S03): `faculty_author_map.parquet` (faculty to author IDs, with the method used), `lab_author_pool.parquet`. In `data/review/`: `faculty_match_review.csv` and `roster_gaps.csv`.

| Lab | Faculty | Matched | Unmatched |
|---|---:|---:|---:|
| CCMB | 41 | 40 | 1 |
| IGIB | 42 | 39 | 3 |
| IMTECH | 48 | 42 | 6 |
| CDRI | 101 | 92 | 9 |
| **Total** | **232** | **213 (91.8%)** | **19** |

74 faculty have more than one author ID, because OpenAlex splits people across profiles. Several bugs found by auditing the first runs are fixed and covered by tests (see qa_log, S03 entries): alternate names of merged profiles matching the wrong person, a surname-first reading matching different people, and a full first name matching a middle initial.

### S04: raw works
`data/interim/works_raw/`: `faculty.jsonl.gz` (7,838 papers by the 332 accepted author IDs, at any affiliation, article/review/letter/conference-paper only) and one `lab_<name>.jsonl.gz` per lab (CCMB 2,333; IGIB 2,644; IMTECH 1,635; CDRI 3,952 works, all types). Papers that list exactly 100 authors were re-fetched individually (131 in the faculty collection, 134 across the lab corpora), because list queries cut the author list at 100. About 226 API calls.

### S05: dataset tables (the inclusion rules)
Rules applied: (1) type and source (plan D7): journal articles, reviews, letters and conference papers with a journal or conference source; no preprints, book chapters, errata, datasets, peer reviews, retractions, or records without a source; (2) a paper counts for a faculty member only if **their own authorship** carries the lab, through OpenAlex institution data (lineage) or, failing that, the raw affiliation text (plan D4); (3) duplicates collapse by DOI, or by long title plus year.

Tables in `data/interim/`: `works.parquet` (4,584 papers: 4,574 journal, 10 conference), `faculty_papers.parquet` (5,830 faculty-paper rows with the link method), `authorships.parquet` (47,644 rows, with institutions and countries), `institutions.parquet` (3,852 institutions with cluster, umbrella and academy flags), `lab_corpus_kept.parquet` (every kept lab paper, with whether it is in the dataset), plus `s05_summary.json`.

| Lab | Faculty with at least one dataset paper | Dataset papers per year (2016 to 2025) |
|---|---|---|
| CCMB | 39 of 41 | 56 to 116 |
| IGIB | 37 of 42 | 54 to 109 |
| IMTECH | 42 of 48 | 50 to 71 |
| CDRI | 92 of 101 | 161 to 255 |

Checks done: no duplicate DOIs; the integrity checks in code pass; in 99.3% of lineage-linked authorships a raw affiliation string names the lab (the rest are spelling variants), so the link rule is precise. The IMTECH 2026 spike from S00 was 169 fungal taxon-name records with no journal; correctly excluded (see qa_log).

**The main limitation is coverage, not precision.** Only 46 to 68% of each lab's papers have a roster member on them (IGIB 46%, CCMB 52%, IMTECH 55%, CDRI 68%), and coverage is lower in earlier years. Well-known lab scientists are simply missing from the roster (for example Vinod Scaria, Sridhar Sivasubbu and Ritushree Kukreti at IGIB). Task 1b below fixes this.

## 6. What to do next, in order

The pipeline is complete; what is left is review and judgement.

1. **Second-person review of the roster growth** (qa_log 2026-10-14): check the 62 people added from `uncovered_lab_authors.csv` (`source = uncovered-author list (S05)` in `data/manual/faculty_roster.csv`). Remove anyone who is not a scientist/PI, fill `designation`/`department` where known. Six merged OpenAlex profiles were skipped (Anurag Agrawal, Ajay Kumar Srivastava, Divya Ramesh Singh, Shailendra Kumar Saxena, Brijesh N. Kumar, Vijay Pal Singh); add them by hand if wanted. After any change:

```bash
python -m dpcn run all --from s03
```

2. **Read the report and the dashboard as a reader would.** The "key findings" sentences on slide 10 are generated from the statistics; rewrite them in your own words if you prefer (edit `src/dpcn/steps/s14_report.py`, function `build`).
3. **Manual spot checks** (plan §11): 20 random rows against publisher pages; top-10 citations against Google Scholar; log results in `docs/qa_log.md`.
4. **Send the instructor questions** (plan §14), especially CDRI.
5. Correct the wrong ORCID on `IGIB-014` in `faculty_roster.csv` (Arpan Parichha's ORCID copied from the IGIB site).
6. **Submit**: week 2 = `outputs/submission/group29_week2.zip`; week 3 = `outputs/submission/group29_week3.zip`.

**If new journals enter the dataset** (roster changes), re-fetch the SJR files: see `data/manual/sjr/README.md`.

## 7. Working conventions

- **Git:** work on a branch per step (`feat/s04-works`), open a pull request, have one other person review, merge to `main`. Commit the manual inputs and review decisions; never commit `.env`, `data/cache/` or `data/interim/`.
- **Tests:** logic that decides which papers or people are included must have unit tests (see `tests/test_match.py` for the style: small hand-built examples, no network). Run `pytest -q` before every push.
- **Audit before trusting.** The S03 audit found bugs that a good-looking match rate hid. After any step that selects or links records, read a sample of the output against the source, and put the finding in `qa_log.md`.
- **Log every manual decision** in `docs/qa_log.md` (date, step, who, finding).
- **Do not share data with other groups**; do not merge datasets (assignment rule). If you want to collaborate with another group, the instructor must be told first.

## 8. Known issues and gotchas

- ~~IMTECH 2026 anomaly~~: resolved in S05. It was 169 fungal taxon-name records with no journal, excluded by the source rule (see qa_log).
- **IMTECH has no departments**; **IGIB-035 (Shivanshu Kukrety)** has a "coming soon" profile page (blank designation) and the directory spells the surname differently from its own URL.
- **Wrong ORCID on the IGIB site** for IGIB-014 (see Task 1, step 6).
- **OpenAlex quirks:** lists truncate authorships at 100; `select` cannot be combined with `group_by`; OR filters take at most 100 values; DOIs containing commas or pipes break filters (the code skips them); `authors?filter=openalex:` and `orcid:` filters work with `|` for OR.
- **2026 is a partial year.** Label it in every trend chart and compute growth to 2025.
- **Windows specifics:** the code reconfigures stdout to UTF-8, but if you see encoding errors set `PYTHONIOENCODING=utf-8`. `conda run` rejects multi-line `python -c` arguments; call the environment's `python.exe` directly or write a script file. Git prints "LF will be replaced by CRLF" warnings; they are harmless.
- **Scimago and CORE** cannot be fully scripted (see Task 2).
- **Budget:** OpenAlex usage is visible in the log line at the end of each step (`budget: $… left today`). Budget resets at midnight UTC.

## 9. Glossary of IDs used in the docs

- **D1 to D22**: method decisions, plan section 6. **A1 to A16**: ambiguities in the assignment documents and how we resolved them, plan section 3.
- **S00 to S15**: pipeline steps, guide section 7.
- **`faculty_id`**: roster key such as `IGIB-014`. **`author_id`**: an OpenAlex author ID such as `A5075246024`; one faculty member may have several.
