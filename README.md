# DPCN Research Mapping Project · Group 29

This is our project for the DPCN course (Instructor: Chittaranjan Hens). We mapped the 2016–2026 research output of four CSIR biology labs: **CCMB** (Hyderabad), **IGIB** (New Delhi), **IMTECH** (Chandigarh) and **CDRI** (Lucknow). From that data we built citation and co-authorship networks and traced how the labs connect with other Indian institutions.

Our data comes from OpenAlex, with journal quartiles from Scimago and conference ranks from CORE. Papers were collected on 2026-10-13; the citing works were refreshed and the data re-cleaned on 2026-11-20.

## What we built

All our submission files are in `outputs/submission/` and `outputs/report/`:

- `group29_data.csv`: 6,027 papers by 274 of 294 roster faculty (8,064 rows, one per paper and faculty member)
- `citation_network.csv`: the citation edges among our papers and to and from other Indian institutions
- `authorship_network.csv`: the co-author pairs
- `indian_connections.csv`: our partner institutions across India, with shared papers and citations
- `group29_dashboard.html`: our interactive dashboard, a single file that opens in any browser
- `group29_report.pptx` / `.pdf`: our 10-slide statistics report

## Phase II: the instructor's additional directions

Step `s16` adds the analyses the instructor asked for and step `s17` tests the main patterns against randomised baselines. Both are computed from the submitted files above, and the dashboard gains five tabs for them:

- **Overview** opens with six research questions and the answers computed from the data below.
- **Impact & authors** (with lab-level totals that include papers by students and staff, shown separately from the faculty counts): Q1 papers with impact factor above 5 and above 10, papers by author count (under 10, 10 or more, 100 or more), yearly trend with the number of collaborating institutions (with and without consortium papers), top 30 papers by journal impact factor, most frequently published journals, and a table showing how the Q1 counts above IF 5 and IF 10 change with the impact-factor source. Conference abstracts printed in journal supplements (8 papers) stay in the publication counts but are left out of the top-30 and top-10 lists.
- **Faculty compare**: faculty compared on papers, Q1 papers, citations, collaborating institutions and co-author links; most productive and most connected; each faculty member's top 10 papers by impact factor; departments compared on output, Q1, citations and collaboration.
- **Institutions & time**: an institutional network with a year range, the faculty co-authorship network year by year (students excluded), and citation activity over time.
- **Flags**: papers with 100 or more authors and the faculty whose citations depend on them; faculty whose OpenAlex lifetime totals look like a merged namesake profile; institutions that cite the labs heavily, split by government and private ownership, with evidence on why (concentration in one author or journal, shared authors, review articles). Citation counts are also divided by each institution's own output (papers in the labs' fields, 2016-2026, from OpenAlex) to show which institutions cite the labs more than their size explains. Citations a lab paper makes to its own or another lab's paper are not counted as an institution citing the labs.
- **Findings**: results tested against null models: who cites whom (self, co-author, same lab, other lab), lab-to-lab citation exchange against a permutation null, lab versus department as the unit of collaboration (label permutation, degree-preserving rewiring, logistic model), citation lift by co-authorship distance, tie persistence and triadic closure, lab-led versus middle-author papers, lab citation impact with controls, the COVID-19 peak, Indian citation flow in and out over the same two-year window (so recent years are not biased by citation lag), fractional counting with rank shifts, field-and-year normalised citations (MNCS, top-10% share) and how concentrated each lab's citations are. `outputs/stats/research_*.csv` hold every number, and `RESEARCH_FINDINGS.md` explains them.

**Network models (step `s18`)** apply the course's models to the faculty co-authorship network and add a second Findings page: power-law fits of the degree and citation distributions with the Clauset–Shalizi–Newman method (bootstrap goodness of fit and likelihood-ratio tests against log-normal, exponential and cut-off power laws), small-world tests against Erdős–Rényi and degree-preserving random graphs, robustness when faculty leave at random or by attack (and how many links separate the labs), SI and SIS spreading with the epidemic threshold compared to theory, link prediction scored on later years, and a discrete-time model of how new collaborations form (lab, department, topic, shared co-authors, output, seniority) with dyadic-robust errors and a permutation test. `outputs/stats/netmodel_*.csv` hold every number; `python -m dpcn run s18 --quick` is a fast smoke test.

**Robustness and dynamics (step `s19`)** add a third Findings page: a specification curve (the same-lab effect on new collaborations under 48 combinations of author cap, risk set, years, hub removal and controls), Benjamini–Hochberg correction across every p-value on the Findings pages, technique diffusion (do faculty take up CRISPR, sequencing, docking, machine learning and other methods after their co-authors, with a shuffle test for influence vs homophily), simplicial closure of faculty triples, a generative model that grows the network from the fitted tie model, the persistence of COVID-19 collaborations, and whether citing a colleague predicts collaborating. `outputs/stats/ext_*.csv` hold every number.

**Teams, ties and careers (steps `s20`–`s22`)** add a fourth Findings page. `s20` fetches extra OpenAlex data (funders, author countries, careers, faculty ties before 2016, citing works by country and field; about 700 cached calls) into `outputs/stats/enrich_*.csv`. `s21` fits a Guimerà-style team-assembly model with papers as groups, tie survival, a brokerage-and-impact panel with faculty fixed effects, sensitivity to author-data errors, time-respecting paths, community inference with a degree-corrected block model, and the OpenAlex extras (`outputs/stats/dyn_*.csv`). `s22` fits a stochastic actor-oriented model of the faculty network in R with RSiena (`outputs/stats/siena_*`).

R for `s22`: no admin rights needed; with Miniconda,

```bash
conda create -n dpcn-r -c conda-forge r-base=4.4
```
```bash
conda run -n dpcn-r Rscript -e "install.packages(c('RSiena','jsonlite'), repos='https://cloud.r-project.org', type='binary')"
```

The step finds `Rscript` in that environment (or set `DPCN_RSCRIPT` to another `Rscript`).

### Phase III: dynamics, structure, peers and an interactive explorer

Steps `s23`–`s26` add network dynamics, structural tests, a peer benchmark and the remaining checks from our improvement plan. The dashboard now has nine sections, and the teammate pages above sit inside them (Network models under Networks, Robustness & dynamics under Findings, Teams, ties & careers under Dynamics).

- **Explore**: *Filter & find* recomputes everything in the browser for any thresholds (years, author count, impact factor, citations, quartile, field, role, COVID-19, title words), including each person's h-index on the matching papers; presets include "h-index above 10 on papers with fewer than 100 authors" and "impact factor above 10 with fewer than 100 authors". *Person profile* shows every number for one scientist (output by role, standing in their lab, papers, co-author network, credit counted three ways, people they might connect with). *Compare* puts up to six people, or the four labs, side by side.
- **Dynamics** (`s23`): SIS and SIR epidemic models on the faculty network with many random seeds (threshold against rewired and random networks, super-spreaders, seeding strategies, whether lab walls slow spreading, simulated new cross-lab links) and a live simulator where you seed an outbreak yourself; random walks (first-passage times between labs, how long a walker stays home) and productivity as a random walk (course paper P1).
- **Networks → Structure** (`s24`): null-model table including the bipartite null, communities against labs and departments, students and staff as glue, densification and preferential attachment, early position against later output, fragility of cross-lab links, link prediction, cross-lab "twins" who never wrote together, topic contagion with a placebo, the citation main path and research breadth.
- **Benchmark** (`s25`): our labs against 13 Indian biology institutes from identical OpenAlex queries (FWCI, top-10% share, growth, openness, specialisation against India, a gravity model of distance), and a *Science context* page setting classic results (Lotka, Price, Bradford, Seglen, Newman, Kitsak…) beside our data (`data/manual/science_context.yaml`). Peers are listed in `data/manual/peer_institutes.csv`.
- **Findings → More results and Verdicts** (`s26`): journal re-grading, the Q1 and impact-factor signal, which partners pay off, citers against collaborators, rising citers, heavy-citer mechanisms, local against global impact, the partner backbone, bibliometric laws, fragility of the headlines and automatic "why did it jump" notes; every research question with a verdict, plus what we did not do and what the numbers cannot show.
- **Ask the data**: a chatbot (bottom right) that answers from the dashboard's own numbers in the browser, with no external service: people, labs, peer institutes, thresholds, top lists, definitions and every finding, each answer linking to its evidence.
- **Overview → Only here**: every method and feature of the 29 other groups' projects (catalogued from the team's reviews of each project, `data/manual/novelty_map.csv`), matched to ours: 14 firsts no other group did (with their results), the rare items we did, and the common baseline we kept. Step `s27` adds the six instructor-paper methods no group used: P1 by career age, P3 event study, P6, P8 (Gibrat), P9 and P10.
- **About** adds data completeness and the hand-checked precision audit (`data/manual/precision_audit.csv`, a seeded sample the team fills in).

```bash
python -m dpcn run s16
```
```bash
python -m dpcn run s17
```
```bash
python -m dpcn run s18
```
```bash
python -m dpcn run s19
```
```bash
python -m dpcn run s20
```
```bash
python -m dpcn run s21
```
```bash
python -m dpcn run s22
```
```bash
python -m dpcn run s23
```
```bash
python -m dpcn run s24
```
```bash
python -m dpcn run s25
```
```bash
python -m dpcn run s26
```
```bash
python -m dpcn run s27
```
```bash
python -m dpcn run s13
```

**Author and affiliation checks** (faculty lists, identity matching, affiliation rule, departments, quartiles) are summarised on the About tab with the counts behind them.

**Impact factor.** Clarivate's JCR is licensed, so the raw lists are not in the repo. The team supplied a JCR 2024 export (matched by ISSN, 1,355 of our 1,573 journals, 4 of them through the title that succeeded a renamed journal) plus a JCR 2025 list that has titles only (34 more journals). `data/manual/issn_aliases.csv` maps ISSNs that OpenAlex and JCR list differently (for example The Lancet's print ISSN). The 62 journals not in either use Scimago's 2-year citations per document (`data/manual/sjr_full/`, Scopus data), and 122 more use OpenAlex's 2-year mean citedness. The raw JCR and Scimago files are git-ignored (licensed or large), so each team member keeps their own copy in those folders. Step s16 stops if the JCR file is missing or matches under 80% of journals, and the Scimago and OpenAlex values of the previous run are kept unless `--refresh-fallbacks` is given (`outputs/stats/if_fallback_review.csv` lists them). The source is labelled for every journal. The substitutes are not Clarivate's number: Scimago counts every document type, so it reads far below the JCR value for Nature and Science (about 19 and 17 against 48.5 and 45.8). Using JCR rather than the substitutes lowers the count of Q1 papers above IF 5 from 1,979 to 1,236, so the choice of source matters for that headline number.

**Ownership of citing institutions** is a hand-made classification in `data/manual/institution_ownership.csv`. It has 379 institutions. The 21 that the flags rely on were checked on 2026-11-05, and 174 more on 2026-11-20, against UGC lists, state Acts and the institutions' own pages (the `evidence` column says what each check used; `verified` is yes for 152, partial for 43). The other 184 rows are still unverified. Jamia Hamdard is recorded as government-aided, because its own prospectus says so, and is therefore not flagged as non-government.

**Every table on the dashboard has a Download CSV button**, and the About tab lists the manual work behind the data (roster, identity decisions, exclusions, ownership checks) with counts read from `data/manual/`. The Flags tab states that a flag is a prompt to look closer, not a judgement, and individual citing authors are not named.

**Our interpretation** of each result is written in `data/manual/phase2_notes.yaml` and shown on the dashboard; the dashboard itself only reports numbers.

**Layout.** The dashboard has nine sections (Overview, Findings, Explore, Publications, Networks, Dynamics, Benchmark, Flags, About); sections with several pages show a pill switcher. Links such as `#tab=citation&lab=CSIR-IGIB` or `#tab=person&person=CCMB-016` open a page directly, the browser's back button works, and the lab selector at the top right filters every page. Long tables page 25 rows at a time, every chart has a "How to read this chart" note where it helps, and every table has a CSV download.

**Hosting.** The dashboard is one self-contained file and is served by GitHub Pages from `index.html`.

## Running it

```bash
pip install -r requirements.txt
```
```bash
pip install -e .
```

Copy `.env.example` to `.env` and add a free OpenAlex API key. Then run:

```bash
python -m dpcn run all
```


The pipeline runs in steps `s00` to `s27`, from building the faculty roster through to validating the final files. `python -m dpcn list` shows every step, and `pytest -q` runs our tests. API responses are cached in `data/cache/`, so re-runs are free.

## Repository

- `config/`: our labs, settings and partner-institution rules
- `data/manual/`: the faculty roster, identity overrides, ISSN aliases, excluded records and other inputs we maintain by hand
- `src/dpcn/`: the pipeline code
- `outputs/`: the deliverables, statistics tables, network files and figures
- `tests/`: our unit tests

## Notes

- A paper counts for a faculty member only if their own byline carries the lab's affiliation.
- 2026 is a partial year.
- **Cleaning.** Step s05 removes records that are not research papers (meeting abstracts, ChemInform digests, Nature news items, and the commentaries listed in `data/manual/work_exclusions.csv`) and merges duplicate versions (same DOI, eLife or F1000 versions, or the same title within two years). `outputs/stats/cleaning_log.csv` lists all 87 records removed or merged, with the reason.
- Our analysis stays within our four labs; links to other institutions appear only in the raw files.
