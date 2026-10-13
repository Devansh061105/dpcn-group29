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
