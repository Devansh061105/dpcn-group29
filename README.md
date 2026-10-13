# DPCN Research Mapping Project — Group 29

Mapping 2016–2026 research output, citation networks and authorship networks for the CSIR biology labs **CCMB, IGIB, IMTECH and CDRI**.

**New here? Start with [docs/03_HANDOFF.md](docs/03_HANDOFF.md)**: current status, setup, and the next steps in order.

| Doc | Purpose |
|---|---|
| [docs/03_HANDOFF.md](docs/03_HANDOFF.md) | Status, setup, how the code is organised, what to do next, known issues |
| [docs/01_PROJECT_PLAN.md](docs/01_PROJECT_PLAN.md) | Requirements, ambiguities, scope, decisions (D1–D22), methodology, timeline, roles, QA, risks, traceability |
| [docs/02_IMPLEMENTATION_GUIDE.md](docs/02_IMPLEMENTATION_GUIDE.md) | Environment, repo layout, config, OpenAlex client, step-by-step pipeline S00–S15, dashboard, report, runbook |
| [docs/qa_log.md](docs/qa_log.md) | Dated log of findings, anomalies and manual decisions |

**Status:** S00–S05 done (S03 awaits a manual review of 19 people; the roster should grow, see the handoff); S06–S15 not started.

## Quick start (Windows, Miniconda)

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

Copy `.env.example` to `.env` and paste your free OpenAlex API key (openalex.org → account settings). Then run:

```bash
python -m dpcn list
```
```bash
python -m dpcn run s00
```
```bash
pytest -q
```

All OpenAlex responses are cached in `data/cache/openalex/`, so re-running a step costs nothing.

**Deliverables:**
- **Week 1–2:** `group29_data.csv`, `citation_network.csv`, `authorship_network.csv`, `indian_connections.csv`
- **Week 3:** statistics report (≤ 10 slides) and interactive dashboard (single HTML file)

Source briefs: `DPCN Research Mapping Project_n4.pptx`, `DPCN_Instruction_Note.docx` (Instructor: Chittaranjan Hens).
