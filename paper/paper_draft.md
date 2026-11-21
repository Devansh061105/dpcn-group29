# Walls between labs: how collaboration forms, lasts and spreads in four Indian national laboratories

*Draft for the DPCN course project, Group 29 (Devansh Magotra, Deepraj Choudhary, Aman Uniyal). Every number is produced by the pipeline in this repository (steps s16–s22) and can be traced to a file in `outputs/stats/`; see `RESEARCH_FINDINGS.md` for the full list of results with their tests. Items marked **[TODO]** need work by the team.*

## Abstract

National laboratories are meant to be shared scientific infrastructure, yet little is known about how researchers in sister laboratories actually work together. We reconstruct the 2016–2026 publication record of 274 faculty in four CSIR biology laboratories in India (CCMB, IGIB, IMTECH, CDRI; 6,027 papers) from OpenAlex and model their co-authorship and citation networks. Collaboration is almost entirely confined within laboratories: 4.8% of faculty co-authorship links cross laboratories against 71% if laboratory labels were shuffled. In a discrete-time model of tie formation with topic similarity, network position, output, seniority and year held fixed, a same-laboratory pair is 30 times more likely to start collaborating (95% CI 17–51); the effect lies between 22× and 46× across 48 alternative specifications, survives plausible author-matching errors, and is confirmed by a stochastic actor-oriented model (RSiena; same laboratory +1.91 log-odds, s.e. 0.11, while same department is null). Departments add little once the laboratory is known, and a degree-corrected block model describes the network best when its blocks are the four laboratories. New ties form by triadic and simplicial closure, mostly through shared colleagues; cross-laboratory ties start weak, are renewed half as often, and bring no measurable citation gain to the people who form them. A pandemic-driven burst of collaboration did not create lasting bridges. Spreading processes on the network take two to three times longer to reach all laboratories than on a degree-matched random network, and the adoption of research methods follows co-authorship but is explained by shared research groups rather than measurable influence. The laboratories co-author abroad (19% of papers) far more often than with each other (1.1%). We discuss what these walls mean for policies that aim to make national laboratories function as one system.

## 1. Introduction

- Motivation: CSIR's 37 laboratories share a mandate, funding and an academy (AcSIR); policy repeatedly calls for inter-laboratory programmes. Whether researchers in sister laboratories collaborate is an empirical question with direct policy relevance.
- Literature: co-authorship networks as maps of science (Newman 2001, 2004; Barabási et al. 2002); team assembly (Guimerà et al. 2005; Wuchty et al. 2007); homophily and organisational boundaries in collaboration (e.g. Kabo et al.; Dahlander & McFarland 2013) **[TODO: add 3–5 references on institutional boundaries]**; triadic and simplicial closure (Kossinets & Watts 2006; Benson et al. 2018); knowledge flow and distance in citation networks (Singh et al. 2020); scale-free claims (Broido & Clauset 2019); social contagion vs homophily (Anagnostopoulos et al. 2008; Aral et al. 2009; Centola 2010); Indian scientometrics **[TODO]**.
- Contribution: (1) a fully reproducible, hand-checked dataset of four national laboratories; (2) evidence, robust to specification and data error, that the laboratory and not the department is the unit of collaboration; (3) a dynamic account of why the walls persist: tie formation, survival, group formation and returns to brokerage; (4) course models (heavy tails, small worlds, percolation, SI/SIS, link prediction) applied with proper null models.

## 2. Data

- Sources: OpenAlex (works, authors, institutions, citations; collected 2026-10-13, citing works refreshed 2026-11-20), Scimago SJR quartiles, CORE ranks, JCR 2024 impact factors (licensed, team copy).
- Faculty rosters: 294 faculty from laboratory websites and authorship evidence, with current or former status checked against laboratory pages (data/manual/faculty_roster.csv).
- Identity: ORCID first, then papers listed on profile pages, then unambiguous names; manual decisions recorded; zero IDs shared between faculty.
- Affiliation rule: a paper counts for a faculty member only if that person's own authorship carries the laboratory.
- Cleaning: 87 records removed or merged (meeting abstracts, ChemInform digests, news, commentaries, duplicate versions; cleaning_log.csv).
- Networks: faculty co-authorship (274 nodes, 1,250 links; papers with ≤ 50 authors), all-author network (17,136 nodes), internal citation network (9,660 citations).
- Extra data (s20): funders (4,444 papers), author countries (6,026), career start years (273 faculty), ties before 2016 (633 pairs), world citing works by country and field.
- **[TODO]** Validation: hand-checked sample of faculty–paper links (precision and recall); citation counts against Scopus / Google Scholar; year-by-year roster from CSIR annual reports.

## 3. Methods (summary; details in the dashboard Methods sections)

- Null models: lab-label permutation; degree-preserving rewiring; Erdős–Rényi; citation reshuffles within year × field strata.
- Tie formation: discrete-time logistic hazard over unlinked active pairs (190,222 pair-years, 894 new links) with year effects and dyadic-robust standard errors (Aronow, Samii & Assenova 2015); node-label permutation test; specification curve over 48 choices; stochastic actor-oriented model (RSiena, three waves).
- Tie survival: life tables and a discrete-time repeat hazard.
- Groups: simplicial closure of faculty triples (train 2016–20, test 2021–25); team-assembly growth model with papers as hyperedges.
- Course models: CSN power-law fits with bootstrap and likelihood-ratio tests; small-world σ; targeted and random node removal, Molloy–Reed threshold, lab edge cuts; SI and SIS with mean-field thresholds; link prediction with out-of-sample AUC; time-respecting paths.
- Diffusion: adoption hazard of eight research methods with exposure counts, a simple-contagion benchmark and the shuffle test.
- Impact: faculty-year panel with faculty and year fixed effects; field-and-year normalised citations; fractional counting.
- Multiple testing: Benjamini–Hochberg across all 210 reported tests (125 keep q < 0.05; the nine lost are secondary terms).

## 4. Results

### 4.1 The laboratory is the unit of collaboration
- 4.8% of faculty links cross laboratories vs 71.1% under label permutation (z = −34) and 52% under degree-preserving rewiring; lab assortativity 0.91.
- Tie formation: same lab OR 29.6 (17.4–50.6), permutation p = 0.005; same department 1.43 (0.99–2.08); topic similarity 1.55 (0.99–2.40); shared co-authors 1.74 per e-fold; seniority n.s.
- Specification curve: OR 21.7–46.4 across 48 specifications; lowest lower bound 13.2 (Figure: spec curve).
- Data errors: unchanged under random drops or within-lab mix-ups; 4.4× even if 20% of links were reassigned to faculty in other laboratories.
- Communities: the four-laboratory partition has the shortest DC-SBM description length (9,152 nats vs 9,184 Louvain consensus, 12,032 departments).
- RSiena (185 faculty, three waves, ties form and dissolve; all models converged, max ratio 0.13–0.20): same lab +1.91 (s.e. 0.11; 6.8× odds), same department +0.04 (0.09), transitive triads +0.27 (0.02), topic similarity +1.21 (0.11), output +0.15 (0.03), seniority n.s.
- Extra controls: ties before 2016 (OR 3.2) and career age (0.80 per decade) matter; the lab effect stays 28×.

### 4.2 How ties form and how long they last
- Triadic closure: a shared co-author makes a new link ~16× more likely; closure predicts within-lab links (AUC ~0.66) but cross-lab links barely (0.57).
- Simplicial closure: triples with three repeated pairwise ties close at 21.7% vs 3.9% for open wedges (OR 6.8); wedges spanning laboratories close at 0.5% vs 4.1%.
- Team assembly: papers as groups reproduce the clustering (0.30 vs 0.32) and modularity, which pairwise models cannot (0.15); real cross-laboratory links exceed the team model's (4.8% vs 1.5%), pointing to specific brokers.
- Survival: after five years 44% of same-lab vs 26% of cross-lab pairs have written again; first-year strength is the main predictor (OR 8.2).
- Cross-lab ties form through shared colleagues (13× per e-fold of shared co-authors vs 1.7× within a lab) and follow prior citation (17% of new cross-lab links vs 8% overall).

### 4.3 Structure: small world, heavy tails, fragility
- Small world: L = 3.55 vs 2.61 (ER), C = 0.36 vs 0.04; σ = 6.4.
- Heavy tails but not scale-free: power law plausible only above 21 links for faculty; log-normal or cut-off power law preferred for the all-author network; rejected for paper citations.
- Fragility: 24 faculty with the most cross-lab ties disconnect every pair of laboratories; random removal halves the network only after 44% (Molloy–Reed: 95%).

### 4.4 Spreading and diffusion
- SI: median 10 steps to reach all laboratories vs 4 in a degree-preserving null; 14 without the five main brokers. SIS threshold λ ≈ 0.063 vs QMF 0.039, HMF 0.049.
- Method adoption: OR 2.3 / 3.9 / 4.8 for 1 / 2 / 3+ adopting co-authors, through same-lab ties; shuffle test p = 0.53 (no influence beyond homophily); below the simple-contagion benchmark for 3+.
- Time-respecting paths: 88% of (early faculty, other lab) pairs reachable by 2025 vs 96% in the static network; timing no different from random.

### 4.5 Consequences: impact, credit and the outside world
- Brokerage: no within-person citation gain from cross-lab ties or brokerage.
- Citation: 92% of citations between our papers share an author; removing them reorders PageRank; independent citations still stay within laboratories (1.26–1.69× chance).
- Credit: field-normalised impact is similar across laboratories (MNCS 0.96–1.15); CCMB's totals rest on ~29 effective papers; full counting rewards consortium membership.
- COVID-19: pairs formed on pandemic work rarely continued on other topics (10% vs 36%).
- Outside: 19% of papers have a foreign co-author vs 1.1% with a sister laboratory; India accounts for 10–22% of citing country mentions.

## 5. Discussion
- Why walls persist: lab-specific resources and supervision, weak first ties, no citation return to brokerage, and group-based assembly that reinforces existing teams.
- Policy: target brokers and strong first collaborations (multi-paper joint projects) rather than one-off consortia; the COVID example shows mission-driven ties do not persist on their own.
- Generality: **[TODO: compare with other groups' institutions from the course if data can be pooled]**.

## 6. Limitations
- OpenAlex coverage and disambiguation (hand-checked identities for faculty only; students in the all-author network unverified); roster built from current websites (**[TODO: CSIR annual reports]**); seniority from current grade; method detection from titles and topics; associations, not causal effects; four laboratories in one field.

## 7. Data and code availability
- Repository with pipeline (s00–s22), tests (pytest) and outputs; **[TODO: Zenodo DOI for the frozen snapshot]**. JCR values are licensed and not redistributed.

## Figures (from outputs/figures and the dashboard)
1. Faculty co-authorship network coloured by laboratory.
2. Specification curve of the same-lab effect (Findings → Robustness & dynamics).
3. Tie formation odds ratios and RSiena estimates.
4. Simplicial closure and tie survival.
5. Robustness to node removal and SI spreading (netmodel_robustness.png).
6. Degree and citation distributions with fits (netmodel_tails.png).
