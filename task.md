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
| Course network models (heavy tails, small world, robustness, SI/SIS, link prediction, tie formation) | Networks → Network models | s18 |
| Specification curve, test-wide BH, method diffusion, simplicial closure, generative model | Findings → Robustness & dynamics | s19 |
| Extra OpenAlex data, team assembly, tie survival, brokerage, RSiena | Dynamics → Teams, ties & careers | s20–s22 |
| Verdict for every research question; "not done" and "blind spots" lists | Findings → Verdicts | – |
| Filter & find, Person profile, Compare, Ask-the-data chatbot | Explore, bottom-right button | – |

## Tasks

### A. Manual checks (most important: these are our human contribution)

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-01 | Precision audit of the faculty–paper matching | Deepraj | ◐ evidence pre-filled; 55 verdicts to confirm |
| T-02 | Check the "glue people" (top non-faculty bridges) | Aman | ☐ |
| T-03 | Verify the peer-institute list | Devansh | ☑ done by Deepraj |
| T-04 | Verify every source in the Science context page | Aman | ☐ |
| T-05 | Classify the remaining citing institutions by ownership | Devansh | ☑ done by Deepraj |
| T-06 | Collect joining years for faculty (enables career-stage analysis) | Deepraj | ◐ worksheet built; years to decide |
| T-07 | Fill the 6 unknown departments and check merged-profile flags | Devansh | ◐ evidence and merged profiles done (Deepraj); roster decision open |
| T-17 | Check the "Only here" coverage map against our reviews of the other groups | everyone | ◐ firsts checked (Deepraj); rest open |

**T-01 · Precision audit (about 2–3 hours).**
- **Status (Deepraj):** the sample was regenerated with raw affiliations (the first version had none). `python -m dpcn.audit_precheck` added evidence columns. `precheck_byline` checks Crossref's author list, a second source. `precheck_affiliation` checks the OpenAlex raw affiliation text. `precheck_name` compares names.
  - 53 of 55 rows are consistent on all three. The 2 flagged rows are spelling variants, explained in `precheck_note`.
  - **Still to do by hand:** open each DOI, then fill `verdict` and `checked_by`. The evidence makes this about 1 minute a row.
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
- **Status (done by Deepraj):** all 13 OpenAlex IDs resolve to the intended Indian institute, and every city matches except one.
  - **THSTI:** OpenAlex places it in Gurugram, but it is in the NCR Biotech Science Cluster, Faridabad. The CSV is right; the gravity distance changes by about 30 km.
  - **inStem:** OpenAlex uses the older name.
  - The result is recorded in the `checked` column. No peers were added (NBRI, CFTRI and NIPER Mohali remain optional).
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
- **Status (done by Deepraj):** the last 9 institutions with 30+ citations were classified from their legal status: 6 private universities or colleges, plus 3 government (a state agricultural university, a state medical university and a central institution of national importance).
  - All 349 heavy citers now have an ownership class.
  - Re-running s16, s17, s26 and s13 changed no flags.
  - The new rows say `verified = no` until someone confirms them on the UGC list.
- **Where:** Flags → "Institutions citing the labs" still has unclassified institutions.
- **What to record:** for those with 30 or more citations, add rows to `data/manual/institution_ownership.csv` with ownership (`government`, `government-aided`, `private`, `international`), source and date checked.
- **Re-run:** `s16`, `s17`, `s26` and `s13`.
- **Commit:** `Ownership for N more institutions`.

**T-06 · Joining years (3 hours, can be shared).**
- **Status (Deepraj):** `python -m dpcn.joining_worksheet` built `data/manual/joining_years.csv` (294 rows). It holds the OpenAlex first year at the lab (274 faculty) and the first paper year (272). For 29 CCMB faculty it also has PhD year, last postdoc year and experience, read from the CCMB website.
  - IGIB, IMTECH and CDRI pages do not give these.
  - Fill `joined_year`, `source_url` and `checked_by` there instead of in the roster. Re-running the script keeps what you typed.
  - A first-paper year far before the PhD (e.g. 1969) means a merged OpenAlex profile: note it.
- **Why:** course paper P1 studies how output changes with career stage. We could not do this because the roster has no joining years.
- **Where to look:** lab websites, CVs and annual reports.
- **What to record:** add a column `joined_year` to `data/manual/faculty_roster.csv` for as many current faculty as possible (leave blank when unknown). Add a source URL in `notes`.
- **Then:** tell the team, and the career-stage analysis can be added to `s26`.
- **Commit:** `Joining years for N faculty`.

**T-07 · Departments and merged profiles (1 hour).**
- **Status (Deepraj):**
  - **Departments:** the 6 profile pages were read; the evidence is in `data/manual/department_review.csv`. Only Imtiyaz Yaseen heads a research group (host epigenetics in infection). Four IMTECH "faculty" are support scientists: patents, science communication, website, and one blank profile. IGIB-035's page is a 404.
  - **Team decision needed:** keep these four in the faculty roster, or drop them (this changes faculty counts). Then copy the departments into `faculty_roster.csv` and re-run `all --from s06`.
  - **Merged profiles:** one lifetime flag (Ashish Awasthi, CDRI-097). His profile is coherent: a biostatistician whose lifetime citations come from Global Burden of Disease consortium papers before CDRI. It is not a merge; keep the flag as "long career outside the window".
  - Two suspect-merged profiles were checked by hand and recorded in `data/manual/merged_profiles.csv`. Their papers stay but their lifetime metrics are excluded (wired into s12 and s16):
    - **Vivek Rao (IGIB-041):** linked to a Toronto cardiac surgeon; lifetime h was 72, now 13.
    - **Manoj Kumar (IMTECH-013):** a namesake merge; lifetime citations now shown as unknown.
  - Chattopadhyay and A. B. Patel are coherent profiles with a stray early paper.
- **Departments:** the 6 faculty with an unknown department (Explore → Faculty list, filter "Department") need one from the lab websites. Put it in `faculty_roster.csv`.
- **Merged profiles:** Flags → "Lifetime citations" flags OpenAlex profiles that may merge several people. For each flagged person, look at the OpenAlex profile and record in `faculty_match_overrides.csv` whether it is merged. There is already a decision column.

**T-17 · "Only here" map (1–2 hours, split by theme).**
- **Status (Deepraj):** every "first" was searched for in all 30 review files. Three turned out to be done by one other group each and are now "rare":
  - k-shell spreading test (Group 3);
  - pair survival (Group 31);
  - h-index leaderboard with filters (Group 21).
  The other 14 firsts hold. The `yes`/`partial` rows by theme are still open for everyone.
- **File:** `data/manual/novelty_map.csv` matches each of the 154 items in our catalogue of the other groups' projects to what we did (`ours` = yes / partial / no, `page`, `what_we_did`), plus 14 "firsts" (`other_groups` = 0) and 23 baseline rows (`other_groups` = −1).
- **What to check:** open your own reviews (`reviews/groupNN.md` in the shared folder). Is any "first" actually done by a group? Is any item marked `yes` not really on our dashboard? Fix the row; the page and the chatbot update after `s13`.
- **Why it matters:** the examiner will ask "what did you do that others did not?". These numbers must be ones we can defend.

### B. Writing (our own words)

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-08 | Team interpretation for the new pages | everyone, one section each | ☐ |
| T-09 | Read and rewrite `RESEARCH_FINDINGS.md` in our own words | Devansh | ☑ numbers verified (Deepraj); rewording optional |
| T-10 | Update the report slides with the new results | Aman | ☐ |
| T-11 | Check each verdict's wording on Findings → Verdicts | Deepraj | ☑ |

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
- **Status (Deepraj):** 21 headline numbers were re-checked against the current output files after today's re-runs, and all match.
  - The identity note now records the two merged profiles that were fixed.
  - Rewording the explanations in your own voice is still worth doing before the viva.
- It lists 60 tested results, from both sets of Phase III work and the methods no other group used.
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
- **Status (Deepraj, done):** two verdicts that stated their evidence without numbers (middle-author papers; "most cited labs") now compute it from the data. Six verdicts were added for the methods no other group used (P1, P8, P6, P3, P9, P10).
- Every verdict on Findings → Verdicts is computed, but the question text and the "why" lines are ours: check them.
- If you disagree with a verdict, change the logic in `src/dpcn/dashboard/phase3.js` (`verdictItems`) or note it in the team interpretation.

### C. Testing the dashboard

| # | Task | Owner (suggested) | Done |
|---|---|---|---|
| T-12 | Chatbot test: 30 questions | Aman | ☐ |
| T-13 | Device and browser check | everyone | ☐ |
| T-14 | Live simulator sanity check | Devansh | ☑ done by Deepraj |

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
- **Status (done by Deepraj):** SIS, seeded at the best-connected person, μ = 0.2, 10 random seeds each:
  - λ = 0.025 (below the 0.054 threshold): 8 of 10 died out within 80 steps;
  - λ = 0.25: none died out, and about 230 of 253 faculty were infected;
  - the same seed gives an identical run.
  - SIR seeded once per lab reaches every lab; "Run 100 seeds" draws its histogram.
- **Caution:** the task's example (β = 0.02, μ = 0.2) is λ = 0.1, which is above this network's threshold, so it should spread, and it does.
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
- **What did you do that other groups did not?** Overview → Only here: 14 firsts, the rare items, and the baseline we kept.
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
