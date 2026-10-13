# DPCN Research Mapping Project — Group 29 Project Plan

| | |
|---|---|
| **Course** | DPCN (Instructor: Chittaranjan Hens), Academic Year 2026 |
| **Team** | Group 29 — CSIR Biology / Life Sciences cluster |
| **Document** | Project plan (the *what* and *why*). The *how* is in [02_IMPLEMENTATION_GUIDE.md](02_IMPLEMENTATION_GUIDE.md). |
| **Version / date** | v1.1 — 2026-10-13 (v1.0 plus the results of steps S00–S05; see the next section) |
| **Sources** | `DPCN Research Mapping Project_n4.pptx` (12 slides) and `DPCN_Instruction_Note.docx` (11 sections) |

---

## Status and changes since v1.0

**Where we are:** steps S00–S05 are built, run and tested (102 unit tests). That covers the faculty roster, the OpenAlex author matching and the first dataset tables. No deliverable file has been produced yet. The step-by-step status, setup and next actions for a new team member are in [03_HANDOFF.md](03_HANDOFF.md); dated findings are in [qa_log.md](qa_log.md).

| Phase (section 9) | State |
|---|---|
| P0 Setup | **Done** |
| P1 Roster | **Done, with caveats**: 232 scientists scraped from the four lab websites; the manual Scimago and CORE downloads and a second-person review are still to do |
| P2 Matching | **Run**: 213 of 232 matched (91.8%); 19 need a manual decision |
| P3 Collection | **Done**: 4,584 papers in the intermediate tables; coverage is limited by the roster (below) |
| P4 Enrichment and flows | Not started (S06, S07) |
| M1 draft dataset | Not started (S08) |
| P5 Networks, M2 | Not started (S09 to S11) |
| P6 Stats, P7 Dashboard, P8 Report, M3 | Not started (S12 to S15) |

**What changed in the method, and why** (new decisions D23 to D26 in section 6):

1. **The author pool comes from lab papers, not profile affiliations (D23).** Matching only against OpenAlex profiles that list the lab missed people whose main profile carries no lab affiliation. We now match against authors who appear on lab-affiliated papers, and use ORCID and the papers listed on each person's own web page as stronger evidence.
2. **Precision safeguards (D26).** Auditing the first matching runs found wrong matches (alternate names of merged profiles, surname-first misreads). Fixed and covered by tests.
3. **The faculty definition is extended in practice (D25).** The scraped rosters cover only 46 to 68% of each lab's papers; well-known scientists are missing from the websites. S05 produces a ranked list of lab-affiliated authors who are not on the roster so that real scientists, current or former, can be added after a person confirms them. This uses the option left open in D3.
4. **Link methods are recorded and one is optional (D24).** A paper is linked through OpenAlex institution data or the raw affiliation text (as planned); a third, weaker method (author profile says they were at the lab that year) exists but is switched off by default.

**Items from v1.0 now closed:** A1/A2 still stand (we include CDRI; instructor confirmation pending). The IMTECH 2026 anomaly was 169 fungal taxon-name records with no journal and is excluded correctly. IGIB's scientist list turned out to be scrapeable, so no manual entry was needed. Roster size is 232, not about 300.

**New risks found:** the roster limits coverage (now rated High, section 12); the IGIB website itself carries a wrong ORCID on one profile; IMTECH publishes no departments.

---

## Contents

1. [Executive summary](#1-executive-summary)
2. [Assignment requirements: full breakdown](#2-assignment-requirements-full-breakdown)
3. [Ambiguities and discrepancies, and how we resolve them](#3-ambiguities-and-discrepancies-and-how-we-resolve-them)
4. [Scope](#4-scope)
5. [Data landscape: reconnaissance findings](#5-data-landscape-reconnaissance-findings)
6. [Definitions and methodological decisions](#6-definitions-and-methodological-decisions)
7. [Methodology by task](#7-methodology-by-task)
8. [Deliverables map](#8-deliverables-map)
9. [Timeline and milestones](#9-timeline-and-milestones)
10. [Team roles](#10-team-roles)
11. [Quality assurance plan](#11-quality-assurance-plan)
12. [Risks and mitigations](#12-risks-and-mitigations)
13. [Requirements traceability matrix](#13-requirements-traceability-matrix)
14. [Questions to send the instructor](#14-questions-to-send-the-instructor)

---

## 1. Executive summary

Group 29 maps the research output of the **four CSIR biology labs** assigned on slide 9 of the deck:

| Short name | Full name | City |
|---|---|---|
| **CSIR-CCMB** | Centre for Cellular & Molecular Biology | Hyderabad, Telangana |
| **CSIR-IGIB** | Institute of Genomics & Integrative Biology | New Delhi |
| **CSIR-IMTECH** | Institute of Microbial Technology | Chandigarh |
| **CSIR-CDRI** | Central Drug Research Institute | Lucknow, Uttar Pradesh |

The window is **2016–2026**. We deliver:

- **Week 1–2:** `group29_data.csv`, `citation_network.csv`, `authorship_network.csv`, `indian_connections.csv`
- **Week 3:** a statistics report (≤ 10 slides) and an interactive dashboard (11 panels, including two network visualisations)

**Approach in one paragraph.** We use **OpenAlex** as the single primary source because it is free, has an API, has clean IDs for all four labs, and exposes everything the networks need: `referenced_works`, `cites:` / `cited_by:` filters, institution lineage, and topics.

- **Faculty.** A scientist roster is compiled from each lab's website and matched to OpenAlex author IDs, with human review.
- **Journal quality.** Quartiles come from **Scimago (SJR)** files, downloaded manually and joined on ISSN.
- **Conference ranks.** These come from the **CORE** export.
- **Indian connectivity.** It is derived from the country and institution of every co-author, citing work and cited work.
- **Code.** A reproducible, cached Python pipeline produces every file. The dashboard is one self-contained HTML file, so the professor can open it without installing anything.

**Headline numbers from reconnaissance (OpenAlex, all work types, 2016–2026):**

| | CCMB | IGIB | IMTECH | CDRI | **Total** |
|---|---:|---:|---:|---:|---:|
| Works (all types) | 2,333 | 2,643 | 1,636 | 3,952 | **10,564** |
| of which `article` | 1,708 | 1,907 | 1,318 | 3,339 | 8,272 |
| Authors ever affiliated (OpenAlex) | 3,072 | 2,443 | 1,620 | 4,962 | — |

These numbers mean the project is small enough to collect fully in a day once the faculty roster is ready. The real work is the **faculty roster and matching** and **correctly defining the Indian-connectivity flags**.

---

## 2. Assignment requirements: full breakdown

### 2.1 The four core tasks

| # | Task | What it means for us |
|---|---|---|
| T1 | **Data collection** | All faculty publications 2016–2026 for our institutions, exported to the specified CSV columns |
| T2 | **Statistics report** | Metrics at **faculty**, **department** and **institution** level; ≤ 10 slides or ≤ 5 pages |
| T3 | **Interactive dashboard** | 11 required panels for each institution |
| T4 | **Network analysis** | Citation network (directed) plus authorship network (undirected), as edge-list CSVs and visualisations |

### 2.2 Deliverables and deadlines

| Deadline | File | Required content |
|---|---|---|
| Week 1–2 | `group29_data.csv` | 14 columns (§2.3) |
| Week 1–2 | `citation_network.csv` | `source_doi, target_doi, source_inst, target_inst, year` |
| Week 1–2 | `authorship_network.csv` | `author_a, author_b, paper_doi, inst_a, inst_b, year` |
| Week 1–2 | `indian_connections.csv` | `your_inst, partner_inst, shared_papers, total_citations` |
| Week 3 | Statistics report | ≤ 10 slides / ≤ 5 pages, all metrics in §2.6 |
| Week 3 | Interactive dashboard | All panels in §2.5, including both network graphs |

### 2.3 Main dataset columns (`group29_data.csv`)

| Column | Spec | Our rule (detail in §6) |
|---|---|---|
| `group` | Group number | Always `29` |
| `institution` | Assigned institution | One of `CSIR-CCMB`, `CSIR-IGIB`, `CSIR-IMTECH`, `CSIR-CDRI` |
| `author` | Faculty full name | Name as on the roster (the website), not the OpenAlex spelling |
| `title` | Paper title | OpenAlex `title`, whitespace-normalised |
| `year` | 2016–2026 | OpenAlex `publication_year` |
| `type` | `journal` or `conference` | From the source type (D7) |
| `journal_name` | Journal / conference | OpenAlex `primary_location.source.display_name` |
| `issn` | Journals only | `issn_l`, else the first ISSN; blank for conferences |
| `doi` | DOI URL | `https://doi.org/...` form |
| `citations` | Count at collection date | OpenAlex `cited_by_count`; the collection date is recorded in `metadata.json` |
| `quartile` | Q1–Q4 or CORE A*/A/B/C | SJR best quartile for the matching year, or CORE rank; `NA` if unknown |
| `coauthor_institutes` | `;`-separated co-author institutions (Indian connections) | Indian institutions on the paper other than this row's institution |
| `cites_indian_inst` | TRUE/FALSE | TRUE if any reference has an Indian institution other than this row's institution |
| `cited_by_indian_inst` | TRUE/FALSE | TRUE if any citing work has an Indian institution other than this row's institution |

We append extra columns **after** the 14 required ones: `openalex_id`, `author_openalex_ids`, `department`, `designation`, `field`, `subfield`, `primary_topic`, `n_authors`, `is_corresponding`, `coauthor_institutes_all`, `sjr_year_used`. The spec says the file "must include" the required columns, so extra columns are allowed. They let every statistic be reproduced from the submitted file alone.

### 2.4 Network requirements

**Citation network (6a):** directed graph, papers → papers.

- Extract pairs from `referenced_works`.
- Compute in-degree within the corpus and PageRank.
- Map citation flow into and out of our institutions from and to other Indian institutes.
- Flag cross-institute edges in the main CSV.
- Export the edge list and visualise it.

**Authorship network (6b):** undirected graph, authors – authors.

- Extract co-author pairs from every paper.
- Compute degree and betweenness centrality.
- Run Louvain/Leiden community detection.
- Flag cross-institution edges.
- Export the edge list and visualise it.

**Indian connectivity (7a/7b):**

- **Citation flow:** in-flow and out-flow counts, top-10 Indian institutes citing us, In/Out impact ratio, a year-wise flow chart, and (slide 12 only) the top-10 most-cited papers citing our institutes.
- **Connectivity map:** list and rank of Indian partner institutions by joint papers, cross-cluster flags (IIT ↔ CSIR, …), Jaccard similarity of topics, and (slide 12 only) hub authors who bridge institutes.

### 2.5 Dashboard panels (11, per institution)

1. Publication trend (papers per year)
2. Faculty list (name, department, h-index, total papers)
3. Journal quartile distribution (Q1–Q4)
4. Faculty performance table, sortable (papers, citations, top journal, h-index)
5. Top-5 journals per institution
6. h-index histogram
7. Research-area breakdown
8. Top-10 most-cited papers (title, journal, year, citations, DOI)
9. Conference rank (CORE A*/A/B/C) "where applicable"
10. Citation network: interactive directed graph *(new)*
11. Authorship network: interactive undirected graph *(new)*

### 2.6 Report contents

The report must cover:

1. Publication trend
2. Q1 fraction per institution
3. Faculty h-index distribution
4. Top-5 journals per institution
5. Top-10 most-cited papers
6. Research areas
7. Citation network summary: PageRank top-10, in-degree distribution, cross-institute flow
8. Authorship network summary: degree and betweenness, communities

It must do this at faculty, department and institution level, in ≤ 10 slides / ≤ 5 pages.

### 2.7 Rules

- Groups work independently, with no data sharing. Collaboration is allowed only if the instructor is told in advance.
- **Analysis stays within our assigned institutions.** Cross-institute edges appear **only in the raw files**.
- Do not merge with another group's data.

---

## 3. Ambiguities and discrepancies, and how we resolve them

| # | Issue | Where | Our resolution |
|---|---|---|---|
| A1 | **Which institutions does Group 29 have?** The deck (slide 9) lists **CCMB, IGIB, IMTECH, CDRI**. The note's summary table lumps Groups 29–30 as "CCMB, IGIB, IMTECH, BARC, IGCAR, RRCAT, NISER" and places CDRI under Groups 27–28. | Deck slide 9 vs note §3 | **Follow the deck: four labs.** The note itself says "see the PPT" for per-group detail, and slide 9 is explicit (CDRI sits under the Group 29 heading). The pipeline is parameterised, so adding or dropping CDRI is a one-line config change. **Confirm with the instructor (Q1).** |
| A2 | "2–3 institutions" per group, but slide 9 gives Group 29 four | Note §2, §3 | Same as A1: do all four. |
| A3 | Dataset deadline "Week 2" (deck) vs "Week 1–2" (note) | Slide 10 vs note §10 | Plan for the end of Week 2, with a draft at the end of Week 1. |
| A4 | Slide 1 says "3 tasks per group"; elsewhere it is 4 | Slide 1 | Do 4 (networks are now required). |
| A5 | Quartile range: deck mentions Q1/Q2/Q3, note says Q1–Q4 | Slide 2 vs note §5 | Use Q1–Q4. |
| A6 | **"Faculty" is never defined** | Everywhere | **Faculty = scientific staff (PIs) listed on the lab's website** (Scientist, Senior/Principal/Chief Scientist, Director, Emeritus and DST/DBT/Ramalingaswami fellows who run groups). Students, postdocs and technical staff are excluded as roster entries, though they still appear as co-authors (D2). |
| A7 | **"Another Indian institution"** is never defined | §5, §6a | Any institution with country `IN` **other than the row's own institution**. This includes the other three Group 29 labs and other CSIR labs. Umbrella bodies (CSIR HQ, Govt. of India, Ministry of S&T, DAE, DBT HQ) are not counted as partners (D11). |
| A8 | `total_citations` in `indian_connections.csv` is ambiguous: citations exchanged between the two institutes, or total citations of the shared papers? | Note §7c | **`total_citations` = citations exchanged (in + out) between `your_inst` and `partner_inst`.** We also add `shared_papers_citations`, `cites_in` and `cites_out` columns, so whichever reading the professor intended is present. |
| A9 | Citation-network columns: slide 11 says `source_doi, target_doi, year`; the note adds `source_inst, target_inst` | Slide 11 vs note §6a | Use the superset (the note's 5 columns) plus extras. |
| A10 | Authorship columns: slide 12 says `doi`; the note says `paper_doi` and adds `inst_a, inst_b` | Slide 12 vs note §6b | Use the note: `author_a, author_b, paper_doi, inst_a, inst_b, year`. |
| A11 | `indian_connections` columns: slide 12 says `your_inst, partner_inst, papers` | Slide 12 vs note §7c | Use the note: `your_inst, partner_inst, shared_papers, total_citations` (+ extras). |
| A12 | Authorship nodes: the note says "each node is a faculty member" but also "extract co-author pairs from **every** paper" | Note §6b | Two layers. The **analysis graph** has faculty only (as worded). The **raw edge file** has every pair involving at least one author from our labs. A secondary "internal" graph (all authors from our labs) adds robustness (D15). |
| A13 | h-index: lifetime or within 2016–2026? | Note §4, §8 | Primary: **window h-index**, computed from our dataset, so it is reproducible from the CSV. We also show OpenAlex's lifetime h-index for context, labelled clearly (D10). |
| A14 | Conference rank for a biology cluster | Note §4 | CORE ranks are a CS venue list, so almost all our venues will be unranked. We still implement the matcher and show the panel with an explicit "not applicable: N of M conference papers matched" note. |
| A15 | Slide-12-only items: "top-10 most-cited papers citing your institute" and "hub authors bridging institutes" | Slide 12 | Include both (cheap, and it covers the union of both documents). |
| A16 | Checklist says report ≤ 10 slides "(use dahborad)", probably meaning the dashboard is the main vehicle | Note §11 | Keep the report to ≤ 10 slides, built from the same figures as the dashboard. |

> **Rule of thumb we follow:** when the two documents differ, **satisfy the union** (more columns or panels never hurt) and **document the choice** in the report's method slide and in `outputs/submission/README.txt`.

---

## 4. Scope

### 4.1 Institutions (verified 2026-10-13)

| Short | OpenAlex ID | ROR | Website | Faculty page (found) |
|---|---|---|---|---|
| CSIR-CCMB | `I185638415` | `05shq4n12` | ccmb.res.in | `/people-details/?id=N` and `/dept_people/?sub_id=N` |
| CSIR-IGIB | `I177828482` | `05ef28661` | igib.res.in | `/ScientistDirectory.html` (names embedded in the page's script; scraped) |
| CSIR-IMTECH | `I4210147764` | `055rjs771` | imtech.res.in | "Departments" page under *About* |
| CSIR-CDRI | `I185249246` | `04t8qjg16` | cdri.res.in | `ScientistDivisionWise?division=<code>` |

All four are `type: facility` with lineage → CSIR (`I66760702`) → Ministry of S&T (`I4210134808`) → Government of India (`I2799351866`). A search for duplicate or alias records (e.g., "IMTECH Chandigarh", "CDRI Lucknow") returned **no duplicates**, so one ID per lab is enough. We still filter on `authorships.institutions.lineage:` (not `.id:`) so that any child records are included.

### 4.2 Time window
`publication_year` 2016–2026 inclusive. **2026 is a partial year** (collection date ~October 2026). Trend charts mark 2026 as partial, and growth rates (CAGR) use 2016–2025.

### 4.3 In scope / out of scope

| In scope | Out of scope |
|---|---|
| Journal articles, reviews, letters; conference papers | Preprints (to avoid double counting with the published version), book chapters, datasets, peer reviews, errata, editorials, paratext, retraction notices |
| Faculty on the current website roster, plus faculty who left during 2016–2026 if we can identify them (optional, D3) | Students and postdocs as "faculty" rows |
| Indian cross-institute edges in raw files | Analysis that merges in other groups' institutions |
| Citations to and from any year (targets of references can be pre-2016) | Citing works outside 2016–2026 |

---

## 5. Data landscape: reconnaissance findings

### 5.1 Works per year (OpenAlex, all types, `authorships.institutions.lineage`)

| Year | CCMB | IGIB | IMTECH | CDRI |
|---|---:|---:|---:|---:|
| 2016 | 201 | 236 | 150 | 433 |
| 2017 | 192 | 244 | 121 | 372 |
| 2018 | 155 | 218 | 139 | 339 |
| 2019 | 167 | 198 | 113 | 299 |
| 2020 | 177 | 218 | 142 | 301 |
| 2021 | 261 | 322 | 144 | 332 |
| 2022 | 255 | 288 | 132 | 410 |
| 2023 | 257 | 254 | 139 | 399 |
| 2024 | 203 | 269 | 154 | 396 |
| 2025 | 241 | 241 | 141 | 392 |
| 2026* | 224 | 155 | **261** | 279 |

\* Partial year. **The IMTECH 2026 spike (261, of which 242 are articles, versus a typical ~140)** is suspicious. It may be a publication-date artefact or a batch of journal records. **Resolved in S05:** 169 of the 2026 records have a DOI but no journal, and every title sampled is a fungal taxon name (for example "Paraaniptodera longispora K. L. Pang ..."), not a paper. The "no journal source" rule excludes them; IMTECH has 72 real papers in 2026, in line with about 100 a year before.

### 5.2 Type mix
Overall about 78% of works are `article`. Preprints are 5–12% depending on the lab (IGIB and CCMB are highest). Book chapters are 4–6%. Pure conference papers are fewer than 15 per lab, which confirms A14.

### 5.3 Paper shape (sample of CCMB's 200 most-cited articles)
- Median **60** references per paper.
- Median **7** authors per paper. Some papers hit the **100-author cap** that OpenAlex list endpoints apply (e.g., the autophagy guidelines paper). For those, the full author list must be fetched by single-work lookup (free), and papers with more than 50 authors are excluded from co-authorship pair generation (D16).
- The 100 most-cited CCMB articles are cited by 24,287 works, **2,386 of them with an Indian author**. The Indian in-flow set for the whole corpus will therefore be in the tens of thousands, still cheap to collect with 100-ID batched `cites:` filters.

### 5.4 Source access

| Source | Status | Implication |
|---|---|---|
| **OpenAlex** | Usage-based pricing since 2026. **No key: $0.10/day (~1,000 list calls). Free key: $1/day (~10,000 list calls, ~1,000 searches).** Single-entity lookups by ID/DOI are free. Usage is visible in the `X-RateLimit-*` response headers. | **Every team member creates a free key.** Our full pipeline needs roughly 1,000–1,500 list calls (§10 of the guide), which is well inside one key's daily budget, provided all responses are **cached on disk** so re-runs cost nothing. |
| **Scimago (SJR)** | The scripted download is blocked by a Cloudflare challenge (HTTP 403) | **Manual step:** download yearly CSVs from scimagojr.com in a browser (2016 → latest) and place them in `data/manual/sjr/`. |
| **CORE portal** | CSV export works (`CORE2023`, no header row) | Scripted download is fine. |
| **Lab websites** | All four sites can be scraped (IGIB's directory embeds its names in a script block; IMTECH serves Hindi unless the `/en/` path is used). | Automated roster scraping for all 4 labs (S01). |
| Scopus / IRINS | Optional | Use only for spot-checks (e.g., citation counts for the top 10 papers, missing faculty). Not part of the pipeline. |

### 5.5 Useful OpenAlex institution IDs for classification

| Entity | ID | Use |
|---|---|---|
| CSIR (HQ / parent) | `I66760702` | Lineage → cluster "CSIR"; as a stand-alone affiliation it is an *umbrella*, not a partner |
| AcSIR (Academy of Scientific & Innovative Research) | `I99364266` | CSIR's degree-granting academy. PhD students list it, so it is very frequent. Flagged `is_csir_academy`. |
| Dept. of Atomic Energy | `I3149292468` | Lineage → cluster "DAE" (e.g., BARC `I1329621470`) |
| ICMR | `I37048141` | Cluster "ICMR" |
| Dept. of Biotechnology | `I3141573830` | Lineage → cluster "DBT institutes" |
| Ministry of S&T / Govt. of India | `I4210134808` / `I2799351866` | Umbrella: never a partner |

---

## 6. Definitions and methodological decisions

Each decision has an ID that the guide and the code refer to.

| ID | Decision | Rationale | Alternative considered |
|---|---|---|---|
| **D1** | Institutions = CCMB, IGIB, IMTECH, CDRI (config-driven) | Deck slide 9; see A1 | 3 labs (drop CDRI) if the instructor says so |
| **D2** | **Faculty** = PIs and scientists on the lab website roster, matched to one or more OpenAlex author IDs | Matches "faculty" intent, keeps h-index and faculty tables meaningful. OpenAlex "ever affiliated" (1.6k–5k per lab) is dominated by students and postdocs. | Data-driven roster: authors with ≥ N works at the lab. Used **only as a cross-check** to find roster gaps. |
| **D3** | Faculty who left before 2026: optional. Include them if found (e.g., via the Wayback Machine or annual reports) and flag them `status=former`. | Current websites under-represent 2016–2019 output | Ignore leavers. Documented as a limitation. |
| **D4** | A paper is in the dataset if (a) a matched faculty author is on it, (b) **that faculty authorship carries the lab's affiliation** (OpenAlex lineage, or a regex on `raw_affiliation_strings` as fallback), (c) 2016 ≤ year ≤ 2026, (d) it passes the type filter (D7) | This is institutional output: a faculty's pre-joining papers from elsewhere do not count | Count all of a faculty member's papers. Rejected because it inflates the lab's output. |
| **D5** | **Row granularity: one row per (paper × faculty author × institution).** A paper co-authored by 2 faculty yields 2 rows. Paper-level stats deduplicate on `openalex_id`. | The `author` column is singular. Faculty-level stats need this shape. | One row per paper with authors joined by `;`. Rejected: it breaks faculty stats. |
| **D6** | Node key = DOI. When a DOI is missing, use the OpenAlex work URL (`https://openalex.org/W…`). The OpenAlex ID is always kept in extra columns. | Spec uses DOIs. About 2–5% of works lack one. | Drop DOI-less works. Rejected: it loses data. |
| **D7** | `type` = `journal` when the source type is `journal` and the work type is in {article, review, letter}. `type` = `conference` when the source type is `conference`, or the work type is `conference-paper` / proceedings. Everything else is excluded. Retracted and paratext works are excluded. | Spec allows only these two values | — |
| **D8** | **Quartile** = SJR "Best Quartile" of the **publication year** (fallback to the latest SJR year for years not yet published). Matched on ISSN (issn_l → any ISSN), then on exact normalised title. Conferences use the CORE rank. Unknown values are `NA`. | Year-matched quartile is the fairer measure. SJR is free. | One SJR year for all papers. Simpler, and kept as a config switch. |
| **D9** | **Q1 fraction** = Q1 papers ÷ journal papers *with a known quartile*. Coverage (% with a known quartile) is always reported next to it. | Avoids penalising unmatched journals while staying transparent | Q1 ÷ all journal papers. Reported as a secondary figure. |
| **D10** | **h-index (primary)** = window h-index from the faculty's papers in our dataset (citations as of the collection date). **Secondary** = OpenAlex `summary_stats.h_index` (lifetime); with multiple author IDs we take the maximum and flag it. | Reproducible from the submitted CSV | Lifetime only. Not reproducible, and it mixes in non-lab output. |
| **D11** | **Indian institution** = an OpenAlex institution with `country_code == "IN"`. **Partner** = an Indian institution that is not the row's own lab and not an umbrella body (CSIR HQ, GoI, MoST, DAE HQ, DBT HQ). AcSIR is kept but flagged, and is excluded from "cross-institute" headline numbers by default (switchable). | AcSIR affiliations are internal student registrations, not real external collaboration. Umbrella records are parsing artefacts. | Count AcSIR as an external partner. It would dominate every ranking. |
| **D12** | **Our cluster** = CSIR (biology). **Partner clusters** come from rules: lineage first (CSIR / DAE / ICMR / DBT), then name regex (IIT, NIT, IIIT, IISER, IISc, TIFR, AIIMS/medical, central universities from a list, other universities), then OpenAlex `type` (company → Industry, healthcare → Hospital), then a manual override file. `cross_cluster = partner_cluster != "CSIR"`. Pair label e.g. `CSIR↔IIT`. | Spec asks for IIT ↔ CSIR style flags | — |
| **D13** | **Citation network layers**: <br>• **G_int** (analysis): nodes = all our corpus papers, edges = our paper → our paper. In-degree and PageRank are computed here, matching "within your institution's corpus". <br>• **Raw edges** (`citation_network.csv`): G_int edges **plus** Indian out-flow (our paper → work with an Indian institution not on the source paper) **plus** Indian in-flow (work with an Indian institution not on the target paper → our paper). Foreign-only edges are **not exported**, only counted in the summary. | Matches "within institutions" for analysis and "cross-institute edges in raw files only" | Export all references (~600k edges, mostly foreign). Rejected: large, and not requested. |
| **D14** | `year` in the citation file = **citing (source) paper year**. `source_inst` / `target_inst` = `;`-joined Indian institutions on each paper (our lab first). Edge is `cross_institute = TRUE` when the source paper has an Indian institution absent from the target paper (or vice versa). | Gives a well-defined flow direction and time | — |
| **D15** | **Authorship network layers**: <br>• **G_fac** (primary analysis, per spec wording): nodes = roster faculty (all their OpenAlex IDs merged into one node), edge = co-authored ≥ 1 dataset paper, weight = number of joint papers. <br>• **G_internal** (secondary): nodes = every author affiliated with one of our 4 labs on a dataset paper (faculty + students + postdocs). Used for community robustness and bridge detection. <br>• **Raw edges** (`authorship_network.csv`): every author pair on every dataset paper where **at least one endpoint is affiliated with one of our labs on that paper**. One row per (pair, paper). | Faculty-only graphs are sparse but literal. The internal graph shows real lab structure. The raw file satisfies "every paper". | All pairs on every paper (external–external too). Rejected: noisy and irrelevant to our analysis. |
| **D16** | Papers with **> 50 authors** are excluded from pair generation (they are still in the dataset). Threshold is configurable; report how many papers were excluded. | Consortium papers create huge cliques that distort centrality | Newman 1/(n−1) weighting. Offered as an optional variant. |
| **D17** | Community detection = **Louvain** (`networkx.community.louvain_communities`, weighted, `seed=42`, resolution 1.0). Report modularity Q. Leiden (`leidenalg`) optional for comparison. | Deterministic, no extra native dependency | Leiden as primary if installation is easy |
| **D18** | Betweenness: exact on G_fac. On G_internal, sampled with `k=min(1000, n)` and `seed=42`. Normalised. | G_internal may have several thousand nodes | — |
| **D19** | **Jaccard topic similarity** between lab L and partner P = \|T_L ∩ T_P\| / \|T_L ∪ T_P\|, where T_X = **top-100 OpenAlex topics** by count for X's 2016–2026 works (via `group_by=primary_topic.id`). Computed for each lab's **top-30 partners** by shared papers. Subfield-level Jaccard is a secondary measure. | A consistent top-K avoids size bias. One API call per institution. | All topics with ≥ 3 papers. Size-biased toward large partners. |
| **D20** | **Research area** = OpenAlex `primary_topic` → field / subfield / domain. **Department** = division or research area from the lab website. If none is available, the faculty member's modal OpenAlex subfield is used, marked `dept_source=openalex`. | CCMB and IGIB do not publish formal departments | — |
| **D21** | **Dashboard** = a single self-contained static HTML file (Plotly.js + Tabulator + Cytoscape.js, data embedded as JSON), generated by Python | One file to submit, opens offline-ish, can also go on GitHub Pages, needs no server | Streamlit or Dash. Easier to build, but needs a running server or deployment. |
| **D22** | All API responses are cached on disk, keyed by request URL. Collection date and code version are written to `outputs/submission/metadata.json`. | Re-runs are free and reproducible | — |
| **D23** | **Candidate pool for matching = authors who appear on lab-affiliated papers in 2016–2026** (plus S02 profile data: years at the lab, works count, merged-profile flag). Evidence order: ORCID, then papers listed on the person's own web page, then an unambiguous name match, then a manual decision. | Affiliation is stored per paper in OpenAlex; a person's main profile may carry no lab affiliation (IMTECH's Pawan Gupta has 6 works under an IMTECH-affiliated profile). The same corpus is needed by S04, so it costs nothing extra. | Profiles with a lab affiliation record only (the v1.0 design). |
| **D24** | **Faculty–paper links are recorded with their method**: `lineage` (OpenAlex resolved an institution under the lab), `raw_string` (the raw affiliation text names the lab), and `profile_years` (the authorship has no institution at all but the author's own profile places them at the lab that year). `profile_years` is **off by default** (`work_filter.link_by_profile_years`); S05 reports what it would add (about 262 papers). | Keeps D4 exactly while making the borderline cases visible and switchable. The lineage links are precise: in 99.3% a raw affiliation string names the lab. | Always on (more recall, a judgement call), or never offered. |
| **D25** | **Roster growth from authorship evidence.** Scientists who are missing from the website lists but are frequent last/corresponding authors on lab papers can be added, as `current` or `former`, after a team member confirms them. Extends D2 and uses the option in D3. The report states the resulting definition. | The scraped rosters give only 46 to 68% paper coverage; the missing people are well-known lab scientists. | Keep the website lists only and report the low coverage as a limitation. |
| **D26** | **Name-matching safeguards.** Only a candidate's display name may auto-accept (alternate names of merged profiles led to wrong matches); a family name must agree (fuzzy >= 92); first given names must line up; a name is read surname-first on both sides only when initials follow; ORCIDs taken from web pages must agree with the name; an author claimed by two faculty is held back; when different people match, a leader is accepted only with >= 10 lab papers and >= 5x the next person. | The first matching runs, audited by hand, accepted Sachin Kumar as eleven other Kumars and Prem P Yadav as Pooja Yadav. | Looser fuzzy matching with more manual review. |

---

## 7. Methodology by task

### 7.1 Pipeline overview

```
 (manual)                 (OpenAlex API, cached)                 (local processing)
┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌───────────────────┐   ┌──────────────┐
│ S01 Roster │──▶│ S02 Author   │──▶│ S03 Match +   │──▶│ S04 Fetch faculty │──▶│ S05 Normalise│
│ (websites) │   │  candidates  │   │ human review  │   │  works (+ corpus) │   │  filter/dedup│
└────────────┘   └──────────────┘   └───────────────┘   └───────────────────┘   └──────┬───────┘
 ┌──────────────┐                                                                      │
 │ SJR / CORE   │──────────────────────────────▶ S06 Enrich (quartile, CORE, area) ◀──┤
 │ (manual dl)  │                                                                      │
 └──────────────┘          S07 Indian in-flow (cites:) / out-flow (cited_by:)  ◀───────┤
                                         │                                             │
              ┌──────────────────────────┴──────────────┬──────────────────┬───────────┘
              ▼                                         ▼                  ▼
     S08 group29_data.csv                    S09 citation network   S10 authorship network
              │                                         │                  │
              └──────────────┬──────────────────────────┴──────────────────┘
                             ▼
                S11 indian_connections (+ Jaccard)  ─▶  S12 statistics + figures
                                                              │
                                     S13 dashboard (HTML) ◀───┴──▶ S14 report (≤10 slides)
                                                              │
                                                   S15 validate + package
```

### 7.2 Task 1: data collection

**Step A. Faculty roster (S01; the largest manual effort).**

1. Scrape the faculty listings for CCMB (people-details pages), CDRI (division-wise scientist pages) and IMTECH (departments page). For IGIB, use the browser or copy manually.
2. Record per person: `faculty_id` (e.g. `CCMB-001`), `name`, `designation`, `department`, `institution`, `profile_url`, `orcid` (if listed), `email_domain`, `status` (current/former), `source`.
3. Keep scientists and PIs only (A6).
4. *Gap check:* list OpenAlex authors with ≥ 10 lab-affiliated works in 2020–2026 and `last_known_institutions` = the lab. Anyone not on the roster is reviewed. Typical cases are a recently joined or departed scientist, or a long-time senior technical officer.
5. *Actual size (scraped 2026-10-13):* CCMB 41, IGIB 42, IMTECH 48, CDRI 101, so **232 faculty**. IMTECH lists no departments, so the D20 fallback applies there.

**Step B. Author matching (S02–S03).**

1. Pull **all** OpenAlex authors ever affiliated with each lab (`affiliations.institution.id:<lab>`): ~12k authors in total, ~65 list calls.
2. For each roster name, generate candidates by fuzzy matching on a normalised name:
   - lowercase, strip titles (Dr., Prof.), strip punctuation;
   - handle initials ("R. K. Mishra" ↔ "Rakesh Kumar Mishra");
   - handle reordered tokens and Indian name variants (e.g., *Kumar* as middle name).
3. Score each candidate: token-set similarity, plus initials compatibility, plus works count at the lab 2016–2026, plus ORCID equality (decisive when present), plus topic plausibility.
4. Auto-accept when the score is high and there is a single strong candidate. Otherwise write to `faculty_match_review.csv` for a human to confirm.
5. **Multiple author IDs per faculty are expected**, because OpenAlex splits profiles. Accept all IDs that clearly belong to the same person.
6. Output `faculty_author_map.csv`. **Target: ≥ 95% of the roster matched**. Unmatched faculty are listed in the report's limitations.

**Step C. Works (S04–S05).**

1. Fetch works by `authorships.author.id:<id1|…|id100>,publication_year:2016-2026` (cursor pagination, 200 per page).
2. Separately fetch the **institution corpus** (`authorships.institutions.lineage:<lab>`) for the coverage ratio: faculty-corpus papers ÷ institution-corpus papers (expected 50–80%; the rest are students' or staff's papers without a faculty co-author, or roster gaps).
3. Apply D4 (the affiliation check on the faculty's own authorship) and D7 (type filter).
4. Deduplicate: same OpenAlex ID → same DOI → normalised title + year.
5. Re-fetch works with exactly 100 authorships by single lookup (free) to get full author lists.
6. Investigate the IMTECH 2026 anomaly.

**Step D. Enrichment (S06).**

1. Fetch source metadata (ISSNs, type) for all unique sources.
2. Join SJR by year and ISSN (D8), and join CORE for conferences.
3. Attach field, subfield and topic, plus department from the roster (D20).

**Step E. Indian connectivity flags (S07).**

1. **Out-flow:** batched `cited_by:<100 of our IDs>,institutions.country_code:IN` returns the Indian works that our papers cite. Intersect each of our papers' `referenced_works` with this set to get edges.
2. **In-flow:** batched `cites:<100 of our IDs>,institutions.country_code:IN,publication_year:2016-2026` returns Indian citing works, with their `referenced_works` and authorships. Intersect to get edges.
3. Per edge, compare the Indian institution sets on both papers (D14) to decide `cross_institute`.
4. Per main-CSV row, `cites_indian_inst` / `cited_by_indian_inst` = TRUE if at least one cross-institute out/in edge exists **relative to that row's institution** (A7).
5. `coauthor_institutes` = Indian institutions on the paper other than the row's institution, with umbrella bodies removed (D11).

### 7.3 Task 2: statistics (metric catalogue)

| Level | Metric | Definition |
|---|---|---|
| Institution | Papers per year, total | Unique papers by year; 2026 marked partial |
| Institution | CAGR | (P₂₀₂₅ / P₂₀₁₆)^(1/9) − 1 |
| Institution | Citations | Total, mean, median per paper; share uncited |
| Institution | Q1 fraction (D9) + Q1–Q4 shares | Over journal papers with a known quartile, plus coverage % |
| Institution | Top-5 journals | By paper count (ties broken by citations), with each journal's quartile |
| Institution | Research areas | Share by field and subfield (top 10 + "other") |
| Institution | Institutional h-index | h over the lab's unique papers |
| Institution | Collaboration | % papers with ≥ 1 foreign co-author; % with ≥ 1 Indian partner co-author; mean authors per paper |
| Institution | Productivity | Papers per faculty, citations per faculty |
| Department | Papers, citations, Q1 fraction, #faculty, mean and median window-h | Grouped by `department` |
| Faculty | Papers, citations, citations/paper, window-h, lifetime-h, top journal (most frequent), Q1 fraction, first/last active year, degree, betweenness, community | One row per faculty |
| Cross-cutting | Top-10 most-cited papers (overall and per lab) | Title, journal, year, citations, DOI |
| Cross-cutting | h-index distribution | Histogram per lab (bins of 5), with summary statistics |

### 7.4 Task 4a: citation network

- **Build:**
  - G_int (D13): directed, nodes = corpus papers (one node per unique paper, attributes: lab(s), year, field, citations, quartile).
  - Extended graph G_ext = G_int + Indian in/out edges, used for flow analysis.
- **Metrics on G_int:**
  - in-degree and out-degree (internal);
  - PageRank (α = 0.85, weighted = no);
  - number of weakly connected components and size of the largest one;
  - density;
  - in-degree distribution (log-log plot plus the share of papers with in-degree 0);
  - reciprocity (expected ~0);
  - **lab-to-lab citation matrix** (4 × 4: CCMB → IGIB …);
  - PageRank top-10 table.
- **Flow (7a, on raw edges):**
  - in-flow and out-flow counts per lab;
  - In/Out impact ratio;
  - year-wise in/out lines 2016–2026;
  - top-10 Indian institutes citing each lab;
  - top-10 most-cited Indian works citing each lab.
- **Exports:**
  - `citation_network.csv`;
  - `networks/citation_internal.gexf` (for Gephi);
  - a node table `networks/citation_nodes.csv`;
  - dashboard JSON (top ~300 nodes by PageRank + their internal neighbours, so the browser graph stays responsive).

### 7.5 Task 4b: authorship network

- **Build:** G_fac and G_internal (D15), plus raw pairs (D16 threshold).
- **Metrics:**
  - degree centrality (normalised) and strength (weighted degree);
  - betweenness (D18);
  - closeness (optional);
  - Louvain communities plus modularity (D17);
  - community size distribution;
  - community × lab and community × department crosstabs (do communities follow departments?);
  - cross-institution edge share;
  - **hub authors**: faculty whose co-authors span the most distinct Indian partner institutions, and faculty with the highest betweenness in G_internal.
- **Exports:**
  - `authorship_network.csv`;
  - `networks/authorship_faculty.gexf` and `authorship_internal.gexf`;
  - node tables;
  - dashboard JSON (full G_fac, ~300 nodes; G_internal trimmed to nodes with degree ≥ 2 or the top 600 by degree).

### 7.6 Indian connectivity (Section 7)

- **Connectivity map:** for each lab × partner, compute:
  - `shared_papers` (unique papers with both);
  - `cites_in`, `cites_out`, `total_citations` (= in + out, A8);
  - `shared_papers_citations`;
  - `partner_cluster`, `cross_cluster`, `pair_label`;
  - `jaccard_topics` (D19; top-30 partners per lab, blank otherwise);
  - `partner_is_in_group` (one of the other three Group 29 labs);
  - `partner_is_csir_academy`.
- **Partner set** = union of co-authorship partners and citation partners.
- Rankings and a cross-cluster summary (e.g., CSIR ↔ IIT: papers, citations) go into the stats folder and the dashboard.

### 7.7 Task 3: dashboard

A single HTML file with a **lab selector** (CCMB / IGIB / IMTECH / CDRI / All) that drives every panel. It has six tabs:

1. **Overview:** KPI tiles (papers, citations, faculty, Q1 %, institutional h) and the trend chart.
2. **Journals:** quartile distribution, top-5 journals, CORE panel.
3. **Faculty:** faculty list and sortable performance table (one Tabulator table with search; a "faculty list" column subset view satisfies panel 2), plus the h-index histogram.
4. **Research:** area breakdown (treemap or sunburst field → subfield) and the most-cited top 10.
5. **Citation network:** Cytoscape graph (node size = PageRank, colour = lab, arrows on, click a node for title, DOI and year), the PageRank top-10 table, the in-degree distribution, and Indian flow charts (year-wise lines, top-10 citing institutes bar).
6. **Collaboration:** authorship graph (G_fac by default, toggle to G_internal; colour = community or lab; node size = degree; cross-institution edges highlighted), centrality tables, and partner ranking with cross-cluster badges and Jaccard.

The dashboard is built by `S13`, which reads `outputs/stats/*.csv` and `networks/*.json`, so it always matches the submitted data.

### 7.8 Task 2: report (≤ 10 slides)

| # | Slide | Content |
|---|---|---|
| 1 | Title and scope | Group 29, 4 labs, window, data snapshot date, headline KPIs |
| 2 | Data and method | Sources, roster → matching → filters, decisions D2/D4/D8/D10/D11, coverage, limitations |
| 3 | Publication trend | Papers per year per lab (2026 partial), CAGR, paper and citation totals |
| 4 | Journal quality | Q1 fraction per lab (+ coverage), Q1–Q4 stacked bars, top-5 journals table |
| 5 | Faculty | h-index histograms, top-10 faculty table, department-level summary |
| 6 | Research areas and impact | Field and subfield shares, most-cited top-10 |
| 7 | Citation network | G_int stats, PageRank top-10, in-degree distribution, 4×4 lab-citation matrix |
| 8 | Indian citation flow | In/out per lab, impact ratio, year-wise flow, top-10 citing institutes |
| 9 | Authorship network | Degree and betweenness leaders, communities (Q, sizes), cross-lab edges, hub authors |
| 10 | Connectivity map and takeaways | Partner ranking, cross-cluster links, Jaccard, 3–5 key findings |

---

## 8. Deliverables map

| File (in `outputs/submission/`) | Produced by | Requirement refs |
|---|---|---|
| `group29_data.csv` | S08 | Note §2.1, §5; slides 10, 12 |
| `citation_network.csv` | S09 | Note §6a, §7c; slides 11, 12 |
| `authorship_network.csv` | S10 | Note §6b, §7c; slides 11, 12 |
| `indian_connections.csv` | S11 | Note §7b, §7c; slide 12 |
| `group29_dashboard.html` | S13 | Note §4; slides 2, 10 |
| `group29_report.pptx` (+ `.pdf`) | S14 | Note §8; slide 10 |
| `README.txt` + `metadata.json` | S15 | Documents decisions, collection date, row counts |
| *(supporting)* `networks/*.gexf`, `stats/*.csv` | S09–S12 | "Visualise using Gephi / NetworkX" |

---

## 9. Timeline and milestones

The start date is not stated in the brief. **Day 1 = the day we start coding.**

| Phase | Days | Work | Exit criterion |
|---|---|---|---|
| **P0 Setup** | 1 | Repo, environment, OpenAlex keys, config, client + cache, S00 verification | `python -m dpcn run s00` prints 4 verified labs and remaining budget |
| **P1 Roster** | 1–3 | S01 scrape and enter rosters; manual SJR + CORE downloads (in parallel) | `faculty_roster.csv` ~300 rows, reviewed by a second member |
| **P2 Matching** | 3–4 | S02 candidates, S03 auto-match + human review | ≥ 95% matched; review sheet signed off |
| **P3 Collection** | 4–5 | S04 works + corpus, S05 normalise, investigate the IMTECH anomaly | Interim tables built; coverage ratio reported |
| **P4 Enrichment + flows** | 5–6 | S06 quartiles and areas; S07 in/out-flow | Quartile coverage ≥ 85% of journal papers |
| **M1: Draft dataset** | **end of Week 1** | S08 draft `group29_data.csv` + validator passes | Draft shared within the team |
| **P5 Networks** | 7–9 | S09, S10, S11 (+ Jaccard) | Three network CSVs validated; GEXF opens in Gephi |
| **M2: Week-2 submission** | **end of Week 2** | S15 package the four CSVs + README | **Submit** |
| **P6 Stats** | 10–12 | S12 tables + figures | All metrics in §7.3 present |
| **P7 Dashboard** | 11–15 | S13 template, panels, network views, polish | All 11 panels working for each lab and "All" |
| **P8 Report** | 14–16 | S14 build ≤ 10 slides, write findings | Peer review by 2 members |
| **M3: Week-3 submission** | **end of Week 3** | Report + dashboard + final package | **Submit** |

Buffer: Days 17–18 (or the weekend) for fixes.

**Status against this timeline (2026-10-13):** P0 done; P1 and P2 built (manual review and downloads outstanding, see 03_HANDOFF.md); P3 done; everything from P4 on is not started. The calendar start date is not known to this document, so the day numbers above are relative.

---

## 10. Team roles

The team size is not stated. Adapt as needed: with 3 people merge R4 + R5; with 2, split data/network vs dashboard/report.

| Role | Owns | Main steps |
|---|---|---|
| **R1 Data lead** | OpenAlex client, cache, works pipeline, main CSV | S00, S02, S04, S05, S08 |
| **R2 Roster and quality lead** | Faculty rosters, matching review, SJR/CORE downloads, validation | S01, S03, S06, S15 |
| **R3 Network lead** | Citation and authorship networks, Indian connectivity, Jaccard | S07, S09, S10, S11 |
| **R4 Dashboard lead** | HTML template, charts, Cytoscape views | S13 |
| **R5 Analysis and report lead** | Statistics, figures, report slides, findings | S12, S14 |

**Working agreements:**

- Use git with one branch per step and pull requests reviewed by one other member.
- Data files are never committed except `data/manual/*` and the final submission.
- Every number in the report must come from `outputs/stats/`, never typed by hand.

---

## 11. Quality assurance plan

**Automated checks (`S15 validate`) must all pass before submission:**

1. **Schema:** exact required column names, in the required order, in all 4 CSVs. No required column entirely empty (except `issn` for conference rows).
2. **Values:**
   - `group == 29`;
   - `institution` within the 4 names;
   - `year` within 2016–2026;
   - `type` in {journal, conference};
   - `quartile` in {Q1, Q2, Q3, Q4, A*, A, B, C, NA};
   - booleans exactly `TRUE` / `FALSE`;
   - DOIs match `^https://doi.org/10\.` or are OpenAlex URLs;
   - `citations` ≥ 0 and integer.
3. **Coverage:** all 4 institutions present. Every year present for every lab. Roster match rate ≥ 95%. Quartile coverage reported.
4. **Integrity:**
   - no duplicate (openalex_id, author, institution) rows;
   - every DOI in the network files exists in the main CSV (for internal endpoints);
   - `authorship_network` has `author_a < author_b` (canonical order) and no self-loops;
   - `indian_connections.your_inst` is within our 4 labs and `partner_inst` is not equal to `your_inst`.
5. **Consistency:** the count of `cites_indian_inst == TRUE` rows equals the count derived from `citation_network.csv` out-flow edges. The same holds for `cited_by_indian_inst` with in-flow.
6. **Scope:** statistics tables contain only the 4 labs. Partner institutions appear only in connectivity tables and raw files.

**Manual spot-checks (logged in `docs/qa_log.md`):**

- 20 random rows: title, year, journal and DOI checked against the publisher page.
- 10 random faculty: paper count compared with their website or Google Scholar list (order of magnitude).
- Top-10 most-cited: citations compared with Scopus/Google Scholar (expect OpenAlex within ±20%).
- 10 random `coauthor_institutes` values: affiliation strings read manually.
- The 5 highest-PageRank papers make sense for the lab.

---

## 12. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenAlex author disambiguation errors (split or merged profiles) | High | Wrong faculty counts and h-index | Multiple IDs per faculty; D4 affiliation check removes merged-in strangers; human review; spot-checks |
| Name variants and initials in Indian names | High | Missed matches | Initials-aware fuzzy matching, ORCID, manual review sheet |
| Roster incomplete (leavers, retirees, scientists missing from the websites) | **High — occurred** | Only 46–68% of each lab's papers have a roster member on them; lower in early years | D25: ranked uncovered-author list, confirm and add; report the coverage ratio and the faculty definition |
| IMTECH publishes no departments | Certain | Department-level stats weaker for IMTECH | D20 fallback: OpenAlex modal subfield |
| OpenAlex budget exhausted | Low (with key) | Pipeline stalls | Free keys for everyone, disk cache, budget guard in the client that stops before 90% use |
| SJR coverage gaps (new or regional journals) | Medium | Lower quartile coverage | Title fallback; report coverage; `NA` rather than guessing |
| Hyperauthorship papers distort the authorship network | Medium | Misleading centrality | D16 threshold, reported |
| AcSIR and umbrella affiliations inflate "partners" | High | Misleading rankings | D11 exclusions and flags |
| 2026 partial year misread as a decline | High | Wrong trend claims | Marked partial; CAGR to 2025 |
| IMTECH 2026 anomaly | Closed | — | Resolved in S05: 169 fungal taxon-name records with no journal, excluded by the source rule |
| Wrong data on a lab website (IGIB lists one person's ORCID on another's profile) | Occurred | A wrong author match | D26: an ORCID must agree with the name; roster ORCID IGIB-014 to be blanked by hand |
| Papers with no institution data on the faculty member's authorship | Medium | About 262 probable lab papers missed | D24: optional `profile_years` rule, decision recorded in the report |
| Citation counts differ from Scopus / Google Scholar | Certain | Questions in viva | State the source and snapshot date; show the comparison for the top 10 |
| Dashboard performance with large graphs | Medium | Laggy UI | Show top-N subgraphs in the browser; full graphs in GEXF |
| Group 29 scope changed by the instructor | Low–medium | Rework | Config-driven institution list; ask early (Q1) |

---

## 13. Requirements traceability matrix

| Requirement (source) | Where satisfied |
|---|---|
| Fetch 2016–2026 faculty publications (note §2.1, slide 2) | S01–S05, D2/D4 |
| CSV with 14 columns, named `group29_data.csv` (note §5, slide 10) | S08, §2.3 |
| `coauthor_institutes`, `cites_indian_inst`, `cited_by_indian_inst` (note §5, slide 12) | S07/S08, D11/D14 |
| Metrics at faculty/department/institution level (note §2.2) | S12, §7.3 |
| Publication trend (note §4, §8) | S12 → dashboard Overview, report slide 3 |
| Faculty list with department, h, papers (note §4) | Dashboard Faculty tab |
| Quartile distribution and Q1 fraction (note §4, §8) | S06/S12 → Journals tab, slide 4 |
| Sortable faculty performance table (note §4) | Tabulator table |
| Top-5 journals per institution (note §4, §8) | S12 → Journals tab, slide 4 |
| h-index histogram/distribution (note §4, §8) | S12 → Faculty tab, slide 5 |
| Research-area breakdown (note §4, §8) | S06/S12 → Research tab, slide 6 |
| Top-10 most-cited (note §4, §8) | S12 → Research tab, slide 6 |
| CORE rank breakdown (note §4) | S06 → Journals tab (with N/A note) |
| Citation network: pairs, in-degree, PageRank, flow, flags, export, visual (note §6a, slide 11) | S07/S09, §7.4 |
| Authorship network: pairs, degree, betweenness, Louvain/Leiden, cross-inst flags, export, visual (note §6b, slide 11) | S10, §7.5 |
| Citation flow: in, out, top-10 citing institutes, ratio, year-wise (note §7a, slide 12) | S09/S11/S12 → Citation tab, slide 8 |
| Top-10 most-cited papers citing our institutes (slide 12) | S12 → Citation tab |
| Connectivity: partner list, rank, strength, cross-cluster, Jaccard (note §7b, slide 12) | S11 → Collaboration tab, slide 10 |
| Hub authors bridging institutes (slide 12) | S10/S12 → Collaboration tab, slide 9 |
| `indian_connections.csv` (note §7c) | S11 |
| Analysis within assigned institutions; cross edges in raw only (note §7c, slide 12) | D13/D15, validator check 6 |
| Report ≤ 10 slides incl. network summaries (note §8, §11) | S14, §7.8 |
| Dashboard with both network panels (note §4, §11) | S13, §7.7 |
| No inter-group sharing; notify if collaborating (note §1, §11) | Team agreement |

---

## 14. Questions to send the instructor

Send these early, in Week 1.

1. **Group 29 scope:** the deck lists CCMB, IGIB, IMTECH **and CDRI** for Group 29, but the note's table places CDRI with Groups 27–28. Should we include CDRI? *(We are proceeding with all four.)*
2. **Faculty definition:** is it acceptable to define faculty as scientists/PIs on the institute website, excluding students, postdocs and technical staff?
3. **`total_citations` in `indian_connections.csv`:** citations exchanged between the two institutes, or total citations of the shared papers? *(We provide both.)*
4. **h-index:** window (2016–2026, from our data) or lifetime? *(We show both; window is primary.)*
5. **Extra columns:** are additional columns after the required 14 acceptable in the CSVs?
6. **Dashboard format:** is a self-contained HTML file acceptable, or must it be hosted?
