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

```bash
python -m dpcn run s16
```
```bash
python -m dpcn run s17
```
```bash
python -m dpcn run s13
```

**Author and affiliation checks** (faculty lists, identity matching, affiliation rule, departments, quartiles) are summarised on the About tab with the counts behind them.

**Impact factor.** Clarivate's JCR is licensed, so the raw lists are not in the repo. The team supplied a JCR 2024 export (matched by ISSN, 1,355 of our 1,573 journals, 4 of them through the title that succeeded a renamed journal) plus a JCR 2025 list that has titles only (34 more journals). `data/manual/issn_aliases.csv` maps ISSNs that OpenAlex and JCR list differently (for example The Lancet's print ISSN). The 62 journals not in either use Scimago's 2-year citations per document (`data/manual/sjr_full/`, Scopus data), and 122 more use OpenAlex's 2-year mean citedness. The raw JCR and Scimago files are git-ignored (licensed or large), so each team member keeps their own copy in those folders. Step s16 stops if the JCR file is missing or matches under 80% of journals, and the Scimago and OpenAlex values of the previous run are kept unless `--refresh-fallbacks` is given (`outputs/stats/if_fallback_review.csv` lists them). The source is labelled for every journal. The substitutes are not Clarivate's number: Scimago counts every document type, so it reads far below the JCR value for Nature and Science (about 19 and 17 against 48.5 and 45.8). Using JCR rather than the substitutes lowers the count of Q1 papers above IF 5 from 1,979 to 1,236, so the choice of source matters for that headline number.

**Ownership of citing institutions** is a hand-made classification in `data/manual/institution_ownership.csv`. It has 379 institutions. The 21 that the flags rely on were checked on 2026-11-05, and 174 more on 2026-11-20, against UGC lists, state Acts and the institutions' own pages (the `evidence` column says what each check used; `verified` is yes for 152, partial for 43). The other 184 rows are still unverified. Jamia Hamdard is recorded as government-aided, because its own prospectus says so, and is therefore not flagged as non-government.

**Every table on the dashboard has a Download CSV button**, and the About tab lists the manual work behind the data (roster, identity decisions, exclusions, ownership checks) with counts read from `data/manual/`. The Flags tab states that a flag is a prompt to look closer, not a judgement, and individual citing authors are not named.

**Our interpretation** of each result is written in `data/manual/phase2_notes.yaml` and shown on the dashboard; the dashboard itself only reports numbers.

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

The pipeline runs in steps `s00` to `s17`, from building the faculty roster through to validating the final files. `python -m dpcn list` shows every step, and `pytest -q` runs our tests. API responses are cached in `data/cache/`, so re-runs are free.

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
