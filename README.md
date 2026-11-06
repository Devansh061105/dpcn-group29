# DPCN Research Mapping Project · Group 29

This is our project for the DPCN course (Instructor: Chittaranjan Hens). We mapped the 2016–2026 research output of four CSIR biology labs: **CCMB** (Hyderabad), **IGIB** (New Delhi), **IMTECH** (Chandigarh) and **CDRI** (Lucknow). From that data we built citation and co-authorship networks and traced how the labs connect with other Indian institutions.

Our data comes from OpenAlex, with journal quartiles from Scimago and conference ranks from CORE. The snapshot was taken on 2026-10-13.

## What we built

All our submission files are in `outputs/submission/` and `outputs/report/`:

- `group29_data.csv`: 6,063 papers by 294 faculty (8,107 rows, one per paper and faculty member)
- `citation_network.csv`: the citation edges among our papers and to and from other Indian institutions
- `authorship_network.csv`: the co-author pairs
- `indian_connections.csv`: our partner institutions across India, with shared papers and citations
- `group29_dashboard.html`: our interactive dashboard, a single file that opens in any browser
- `group29_report.pptx` / `.pdf`: our 10-slide statistics report

## Phase II: the instructor's additional directions

Step `s16` adds the analyses the instructor asked for, computed from the submitted files above (same 2026-10-13 snapshot), and the dashboard gains four tabs for them:

- **Overview** opens with six research questions and the answers computed from the data below.
- **Impact & authors**: Q1 papers with impact factor above 5 and above 10, papers by author count (under 10, 10 or more, 100 or more), yearly trend with the number of collaborating institutions (with and without consortium papers), top 30 papers by journal impact factor, most frequently published journals, and a table showing how the Q1 counts above IF 5 and IF 10 change with the impact-factor source. Conference abstracts printed in journal supplements (8 papers) stay in the publication counts but are left out of the top-30 and top-10 lists.
- **Faculty compare**: faculty compared on papers, Q1 papers, citations, collaborating institutions and co-author links; most productive and most connected; each faculty member's top 10 papers by impact factor; departments compared on output, Q1, citations and collaboration.
- **Institutions & time**: an institutional network with a year range, the faculty co-authorship network year by year (students excluded), and citation activity over time.
- **Flags**: papers with 100 or more authors and the faculty whose citations depend on them; institutions that cite the labs heavily, split by government and private ownership, with evidence on why (concentration in one author or journal, shared authors, review articles). Citation counts are also divided by each institution's own output (papers in the labs' fields, 2016-2026, from OpenAlex) to show which institutions cite the labs more than their size explains.

```bash
python -m dpcn run s16
```
```bash
python -m dpcn run s13
```

**Author and affiliation checks** (faculty lists, identity matching, affiliation rule, departments, quartiles) are summarised on the About tab with the counts behind them.

**Impact factor.** Clarivate's JCR is licensed, so the raw lists are not in the repo. The team supplied a JCR 2024 export (matched by ISSN, 1,327 of our 1,568 journals) plus a JCR 2025 list that has titles only (used to fill 27 more journals). The 72 journals not in either use Scimago's 2-year citations per document (`data/manual/sjr_full/`, Scopus data), and 142 more use OpenAlex's 2-year mean citedness. The raw JCR and Scimago files are git-ignored (licensed or large), so each team member keeps their own copy in those folders; without them step s16 falls back to the OpenAlex proxy and its outputs will differ from the committed ones. The source is labelled for every journal. The substitutes are not Clarivate's number: Scimago counts every document type, so it reads far below the JCR value for Nature and Science (about 19 and 17 against 48.5 and 45.8). Using JCR rather than the substitutes lowers the count of Q1 papers above IF 5 from about 1,930 to 1,221, so the choice of source matters for that headline number.

**Ownership of citing institutions** is a hand-made classification in `data/manual/institution_ownership.csv`. The 21 institutions that the flags rely on were checked on 2026-11-05 against UGC lists, state Acts and the institutions' own documents (the `evidence` column says what each check used; `verified` is yes, partial or no). The other 184 rows are still unverified. Jamia Hamdard is recorded as government-aided, because its own prospectus says so, and is therefore not flagged as non-government.

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

The pipeline runs in steps `s00` to `s15`, from building the faculty roster through to validating the final files. `python -m dpcn list` shows every step, and `pytest -q` runs our tests. API responses are cached in `data/cache/`, so re-runs are free.

## Repository

- `config/`: our labs, settings and partner-institution rules
- `data/manual/`: the faculty roster and other inputs we maintain by hand
- `src/dpcn/`: the pipeline code
- `outputs/`: the deliverables, statistics tables, network files and figures
- `tests/`: our unit tests

## Notes

- A paper counts for a faculty member only if their own byline carries the lab's affiliation.
- 2026 is a partial year.
- Our analysis stays within our four labs; links to other institutions appear only in the raw files.
