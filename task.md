# Team task board · Group 29

What is left before submission, split so the three of us can work in parallel. Each task says what to do, which file to change, how to check it and what to commit. **Owners are only suggestions**: swap freely, and put your name in the `Owner` column when you start a task. Tick the box when it is done and pushed.

Most of these tasks need **human judgement and manual checking**: this is the work the About tab credits to the team. Please do them by hand, not by script.

## Before you start

```bash
git pull
```
```bash
source .venv/bin/activate
```
```bash
python -m dpcn run s26
```
```bash
python -m dpcn run s13
```

- Open `outputs/submission/group29_dashboard.html` in a browser.
- `pytest -q` must pass (150 tests) and `python -m dpcn run s15` must pass before you push.
- **Never commit:**
  - `.env` (the OpenAlex key);
  - `data/manual/jcr/` (licensed);
  - `data/manual/sjr_full/`.
  These are git-ignored, so they stay that way unless forced.
- **Re-running steps:** after changing a file in `data/manual/`, re-run the step that reads it, then `s13` to rebuild the dashboard. The table below says which step reads which file.

| File you edit | Re-run |
|---|---|
| `data/manual/precision_audit.csv` | `s26`, `s13` |
| `data/manual/phase2_notes.yaml` | `s13` |
| `data/manual/science_context.yaml` | `s13` |
| `data/manual/peer_institutes.csv` | `s25`, `s13` |
| `data/manual/institution_ownership.csv` | `s16`, `s17`, `s26`, `s13` |
| `data/manual/faculty_roster.csv`, `faculty_match_overrides.csv` | `all --from s01` (slow; the cache makes it free of API cost) |

## What is already done (for reference)

| Area | Where | Step |
|---|---|---|
| Phase II directions (overview, faculty and department comparison, top papers, journals, networks, flags) | Overview, Publications, Explore, Networks, Flags | s16 |
| 14 tested findings (self-citation, lab walls, distance decay, persistence, credit, flow window…) | Findings | s17 |
| Epidemics (SIS/SIR, many seeds, thresholds, super-spreaders, lab walls, interventions, live simulator), random walks | Dynamics | s23 |
| Null-model table with bipartite null, communities vs labels, students as glue, growth laws, link prediction, twins, contagion, main path | Networks → Structure | s24 |
| 13 Indian biology peer institutes, RCA vs India, gravity model | Benchmark | s25 |
| Journal re-grading, Q1/IF signal, partner payoff, citers vs collaborators, laws, fragility, jumps, productivity random walk, filtered h-index, explorer data | Findings → More results, Explore | s26 |
| Verdict for every research question; "not done" and "blind spots" lists | Findings → Verdicts | – |
| Filter & find, Person profile, Compare, Ask-the-data chatbot | Explore, bottom-right button | – |

## Tasks

### A. Manual checks (most important: these are our human contribution)

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-01 | Precision audit of the faculty–paper matching | Deepraj | ☐ |
| T-02 | Check the "glue people" (top non-faculty bridges) | Aman | ☐ |
| T-03 | Verify the peer-institute list | Devansh | ☐ |
| T-04 | Verify every source in the Science context page | Aman | ☐ |
| T-05 | Classify the remaining citing institutions by ownership | Devansh | ☐ |
| T-06 | Collect joining years for faculty (enables career-stage analysis) | Deepraj | ☐ |
| T-07 | Fill the 6 unknown departments and check merged-profile flags | Devansh | ☐ |

**T-01 · Precision audit (about 2–3 hours).**
- **File:** `data/manual/precision_audit.csv` holds 55 randomly chosen (paper, faculty) links, stratified by how the affiliation was matched.
- **What to check for each row:**
  - open the DOI;
  - confirm that this faculty member is an author;
  - confirm that the paper lists their lab (the `raw_affiliation` column shows what OpenAlex has).
- **What to record:** set `verdict` to `correct`, `wrong` or `unsure`, put your name in `checked_by`, and give a reason in `notes` when it is not `correct`.
- **Ideally two people:** split the rows, then each re-checks five of the other person's rows.
- **Check:** re-run `s26` and `s13`. About → "Hand-checked precision" then shows the precision with a 95% interval.
- **Commit:** `Precision audit of 55 links`.

**T-02 · Glue people (about 1 hour).**
- **Source:** `outputs/stats/research_glue_people.csv` lists the 15 non-roster lab authors who link the most faculty pairs.
- **What to look up:** for each person, use the lab website or Google Scholar to find whether they are a student, postdoc, technical staff or a scientist missing from our roster.
- **What to record:** write the result in a new file `data/manual/glue_people_roles.csv` with columns `name, lab, role, source_url, checked_by`.
- **If you find a missing scientist:** tell the team, because they may belong on the roster.
- **Commit:** `Roles of glue authors`.

**T-03 · Peer institutes (1 hour).**
- **File:** `data/manual/peer_institutes.csv` lists the 13 peers and why each was chosen.
- **What to check:**
  - each city (OpenAlex places THSTI in Gurugram; it is in Faridabad);
  - each choice.
- **Possible additions:** CSIR-NBRI, CSIR-CFTRI and NIPER Mohali, if the team wants more CSIR sister labs.
- **Re-run:** `s25` and `s13`. The step fetches from OpenAlex; with the key in `.env` it costs a few cents.
- **Commit:** `Peer list checked`.

**T-04 · Science context sources (1 hour).**
- **File:** for every item in `data/manual/science_context.yaml`, open the source.
- **What to check:** the claim matches what the paper says, and the citation (authors, year, journal, volume, pages) is right.
- **What to edit:** fix anything wrong. Add one or two results you know from the course papers (P1–P10, see `papers_summary.md` in the shared folder).
- **Commit:** `Science context sources checked`.

**T-05 · Ownership of citing institutions (2 hours).**
- **Where:** Flags → "Institutions citing the labs" still has unclassified institutions.
- **What to record:** for those with 30 or more citations, add rows to `data/manual/institution_ownership.csv` with ownership (`government`, `government-aided`, `private`, `international`), source and date checked.
- **Re-run:** `s16`, `s17`, `s26` and `s13`.
- **Commit:** `Ownership for N more institutions`.

**T-06 · Joining years (3 hours, can be shared).**
- **Why:** course paper P1 studies how output changes with career stage. We could not do this because the roster has no joining years.
- **Where to look:** lab websites, CVs and annual reports.
- **What to record:** add a column `joined_year` to `data/manual/faculty_roster.csv` for as many current faculty as possible (leave blank when unknown). Add a source URL in `notes`.
- **Then:** tell the team, and the career-stage analysis can be added to `s26`.
- **Commit:** `Joining years for N faculty`.

**T-07 · Departments and merged profiles (1 hour).**
- **Departments:** the 6 faculty with an unknown department (Explore → Faculty list, filter "Department") need one from the lab websites. Put it in `faculty_roster.csv`.
- **Merged profiles:** Flags → "Lifetime citations" flags OpenAlex profiles that may merge several people. For each flagged person, look at the OpenAlex profile and record in `faculty_match_overrides.csv` whether it is merged. There is already a decision column.

### B. Writing (our own words)

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-08 | Team interpretation for the new pages | everyone, one section each | ☐ |
| T-09 | Read and rewrite `RESEARCH_FINDINGS.md` in our own words | Devansh | ☐ |
| T-10 | Update the report slides with the new results | Aman | ☐ |
| T-11 | Check each verdict's wording on Findings → Verdicts | Deepraj | ☐ |

**T-08 · Team interpretation.**
- Each new page has an empty "Team interpretation" box. Fill it in `data/manual/phase2_notes.yaml` under these keys:
  - `extras` (More results);
  - `verdicts`;
  - `structure`;
  - `dynamics` (Epidemics);
  - `walks`;
  - `benchmark`.
- Write 4–8 sentences in your own words: what surprised you, what you believe, what you doubt.
- The dashboard never writes these; that is the point.
- **Re-run:** `s13`.

**T-09 · `RESEARCH_FINDINGS.md`.**
- It lists 28 tested results.
- Read each one, open the matching dashboard chart, and check that the number and the sentence agree.
- Rewrite the explanations in your voice.
- Mark anything you would not defend in a viva.

**T-10 · Report slides.**
- `python -m dpcn run s14` builds `outputs/report/`. It covers Phase II and s17, but not s23–s26 yet.
- Add three slides:
  - **Dynamics:** lab walls cut cross-lab outbreak reach from 23% to 5%; a random walker needs 147 steps to leave its lab, against 10 by chance.
  - **Structure:** students and staff more than double cross-lab links (4.8% → 11.1%); topic contagion is homophily.
  - **Benchmark:** mean FWCI ranks 4, 9, 11 and 14 of 17; collaboration decays with distance twice as fast as citation.
- Use screenshots from the dashboard (`#tab=epidemics&shot=1` hides the toolbars).

**T-11 · Verdict wording.**
- Every verdict on Findings → Verdicts is computed, but the question text and the "why" lines are ours: check them.
- If you disagree with a verdict, change the logic in `src/dpcn/dashboard/phase3.js` (`verdictItems`) or note it in the team interpretation.

### C. Testing the dashboard

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-12 | Chatbot test: 30 questions | Aman | ☐ |
| T-13 | Device and browser check | everyone | ☐ |
| T-14 | Live simulator sanity check | Devansh | ☐ |

**T-12 · Chatbot test.**
- Open "Ask the data" and ask 30 questions a viva examiner might ask. Mix in:
  - names;
  - labs;
  - "compare X and Y";
  - thresholds;
  - "what is …";
  - findings.
- Log every wrong or useless answer in `data/manual/chatbot_tests.md` (question, answer, what it should say).
- Missing definitions can be added to `GLOSS` in `src/dpcn/dashboard/chat.js`. Bigger problems go to the team.

**T-13 · Devices.**
- Open the file on:
  - a laptop (1366 and 1920 wide);
  - a phone;
  - Chrome and Firefox;
  - light and dark theme.
- Note anything cut off or unreadable, with a screenshot.

**T-14 · Simulator.**
- On Dynamics → Epidemics → "Run it yourself", check that:
  - β = 0.02, μ = 0.2 (below the threshold) dies out quickly;
  - β = 0.3 spreads;
  - seeding in different labs shows the walls;
  - "Run 100 seeds" gives a histogram.
- Write two sentences on what you saw for the team interpretation.

### D. Viva preparation

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-15 | Each member explains every page in two minutes | everyone | ☐ |
| T-16 | Prepare answers for the likely questions below | everyone | ☐ |

Likely questions:
- **Why compare with null models?** To know what "a lot" means.
- **Which null for co-authorship, and why bipartite?**
- **Is anything causal?** No: these are associations.
- **How was the faculty matched, and how accurate is it?** See T-01.
- **What is FWCI, and why is it fairer than citations?**
- **Why does fractional counting change the leaders?**
- **What would you need to study career stages or gender?** Joining years (T-06). Gender is not collected, and inferring it from names would be wrong.
- **What did the team do by hand?** See the About tab: the roster, identity decisions, exclusions, ownership, the precision audit, these notes.
- **How was AI used?** As assistance only. Every number comes from the pipeline, and the team checked the data and wrote the interpretations.

## How to commit

```bash
git add -A -- . ':!.claude'
```
```bash
git commit -m "Short message"
```
```bash
git push
```

Keep messages short and pull before you push. If two people edit the same YAML file, the merge is easy, but tell each other first.
