# Research findings · Group 29

What the data on four CSIR biology labs (CCMB, IGIB, IMTECH, CDRI; 2016–2026; 6,027 papers, 274 faculty) shows beyond descriptive counts. Each result below is tested against a randomised baseline or a model with controls. All numbers come from `outputs/stats/research_*.csv` and the `research_*.json` summaries (steps `s17`–`s26`), and the Findings, More results, Dynamics, Structure and Benchmark pages of the dashboard draw them. They are observational associations from OpenAlex data, not causal effects.

## Headline results

| # | Finding | Test | Result |
|---|---|---|---|
| 1 | The lab, not the department, is the unit of collaboration | lab-label permutation (2,000), degree-preserving rewiring (200), logistic model over 37,401 faculty pairs | 4.8% of links cross labs vs 71.1% under permutation (z = −34.4); same lab OR 55 (43–72) after topic similarity and output; same department OR 1.18 (0.93–1.48) |
| 2 | Internal citation is mostly self-citation | classify each of 9,660 citations among our papers | 92.4% share an author; 3.9% go through a co-author; only 3.7% are independent |
| 3 | Raw PageRank rewards self-citation | PageRank with and without shared-author citations | 5 of the raw top 10 fall to rank 350 or lower once self-citations go; the Simons Genome Diversity Project rises from 5 to 1 |
| 4 | Even independent citations stay home | permute cited papers within year × field strata (1,000) | 73.6% within lab vs 54.7% expected; observed/expected 1.69 CCMB, 1.55 IGIB, 1.48 IMTECH, 1.26 CDRI |
| 5 | Social proximity decays within two steps | citation lift by co-authorship distance (O·I/T null, Singh et al. 2020 style) | independent citations 2.0× between co-authors, 1.43× at distance 2, 0.54× at 3, 0.31× at 4+ |
| 6 | Cross-lab ties are fragile | repeat within 3 years of first joint paper, 2016–2022 | same lab 33.6% (30.4–36.9) vs cross-lab 11.8% (4.7–26.6), Fisher p = 0.008 |
| 7 | Triadic closure drives new links | P(new link · shared co-author) / P(new link · none), per year | lift 9.5–22.4, mean 15.9 |
| 8 | The network is clustered and has a rich club | vs degree-preserving rewiring | clustering 0.32 vs 0.13 (2.6×); rich club (degree ≥ 24) 0.70 vs 0.44 (1.6×); lab assortativity 0.91 |
| 9 | Lab citation impact differs after controls | OLS on log(1 + citations), year, field, team size, review, HC1 errors | vs CDRI: IMTECH +10.6% (1.8–20.0), CCMB −14.8%, IGIB −18.0%; doubling team size +29%; review +58% |
| 10 | The middle-author citation premium is team size | normalised citations, lab-led vs middle-author papers, within team-size bands | overall 1.41 vs 0.88 (p = 0.003), but medians are similar within the 5–14 author bands |
| 11 | COVID-19 work reshaped two labs' visibility | keyword classification of titles and topics | IGIB: 26% of 2021 papers, 33% of 2021 and 47% of 2022 citations; CCMB: 13% of 2021 papers, 33% of citations |
| 12 | The labs are net sources for Indian science; the 2022 "crossover" is citation lag | in vs out over the same two-year window per publication cohort | ratio 1.53 overall, above 1 every cohort from 2017; IMTECH 1.98, IGIB 1.87, CCMB 1.72, CDRI 1.27 |
| 13 | The citation leaders depend on full counting | fractional counting, rank shifts | 6 of the top 10 drop below rank 25; leader under fractional counting is rank 7 on full counts |
| 14 | CCMB's totals rest on a few papers | effective number of papers, MNCS with bootstrap CI | CCMB 29 effective papers vs CDRI 518; MNCS 0.96–1.15 with overlapping intervals |

## What each result means

**1. Labs are the walls, departments are not.** If lab labels were shuffled among the same 274 faculty, 71% of their 1,250 co-author links (papers with up to 50 authors) would cross labs; in reality 4.8% do. Even rewiring the network while keeping each person's number of co-authors yields 52% cross-lab. In the logistic model, two faculty in the same lab are 55 times more likely to have co-authored, a figure that barely changes when topic similarity (cosine over fields) and output are added. Topic similarity matters too (OR 8.9), but sharing a department adds nothing once lab and topic are known. *Implication:* collaboration policy aimed at inter-departmental work inside a lab would change little; the barrier sits between labs, even though all four are CSIR biology institutes.

**2–3. Most internal citations are a group citing itself.** Of 9,660 citations between our papers, 92% have an author in common, which is normal for building on one's own line of work, but it means a citation network of an institution is mostly a map of research programmes, not of influence. PageRank on that raw network ranks papers from heavily self-citing CDRI groups at the top (a 2016 neutrophil apoptosis paper with 120 citations is rank 1 raw and 512 without self-citations). Removing shared-author citations puts the Simons Genome Diversity Project (1,595 citations), a paper on population-specific disease genes in South Asia and IndiGenomes among the leaders. *Implication:* institutional citation rankings should drop author-overlap citations before computing centrality; this is a simple correction many dashboards (ours included, before this step) omit.

**4. Lab proximity beyond topic.** After removing citations with any shared author, 74% of the remaining citations still stay inside the lab. A null that permutes cited papers among those of the same year and the same fields expects 55%. A year-only null expects 38%, so about half of the within-lab excess (19 of 35 points) is not explained by topic. CCMB is the most inward-looking (1.69×) and CDRI the least (1.26×), plausibly because CDRI's chemistry and pharmacology span more subgroups that read each other's work anyway.

**5. Knowledge travels two steps.** Independent citations are twice as likely as chance between direct co-authors and still 43% more likely at distance two, then fall below chance. This matches the "distance decay" reported for physics by Singh et al. (2020) and gives a concrete radius for informal knowledge flow inside an institution. That distance 3–4 sits below the unconnected baseline suggests that pairs who are connected but far apart sit in different research programmes of the same lab.

**6–7. Cross-lab ties are short-lived; new ties come through friends.** Only 12% of new cross-lab pairs repeat within three years, against 34% of same-lab pairs. New links are about 16 times more likely between faculty who already share a co-author. Together these explain why the 60 cross-lab faculty links are scattered (78% rest on a single joint paper) and do not build into bridges: they are rarely renewed and rarely seed further links. The 2021 spike (23 cross-lab links, COVID genomics) did not carry over.

**9. Impact with controls.** Raw citations per paper favour CCMB and IGIB, but those labs also write larger, more consortium-heavy papers. With year, field, team size and review controls, IMTECH papers draw 11% more citations than CDRI's, while IGIB's draw 18% fewer and CCMB's 15% fewer. Team size is the strongest single predictor (each doubling about +29%).

**10. A caution on "borrowed" citations.** Papers where the lab only provides a middle author are 23% of papers but 34% of citations (54% at CCMB), and their field-normalised citations are higher (1.41 vs 0.88). Split by team size, the gap disappears: for 7–9 authors, medians 0.54 vs 0.59; 10–14 authors, 0.52 vs 0.65. The premium is a team-size effect, which is itself the policy-relevant point: a large share of the labs' visibility comes from being part of big collaborations rather than leading them.

**11. COVID-19.** IGIB's genomic surveillance and CCMB's sequencing made COVID-19 work a quarter of IGIB's 2021 output and almost half of its 2022 citations, and drove the 2021 jump in faculty links and partner institutions.

## Other results from the Phase II analysis

- **Who cites the labs.** Once citations are divided by the citing institution's own output in the labs' fields, none of the 18 heavy non-government citers is an outlier (largest robust z 1.1, against 2). Government and private institutions have the same median rate (50 per 1,000 papers). The real outliers are five government institutes that also co-author with the labs (IIIT Delhi, THSTI, NEERI, NIPER Hyderabad and Raebareli). Raw citation counts mostly measure size (Spearman 0.35 with the size-adjusted rate).
- **Students and staff.** 25% of lab papers (1,961; 22% of lab citations) have no roster scientist on them. Faculty-only counts therefore understate each lab's output by about a quarter, and more so at CCMB (29%) than at CDRI (19%).
- **Flow direction, corrected for citation lag.** Raw yearly counts make it look as if Indian citations into the labs overtook those going out only in 2022. Over the same two-year window (citations received within two years against references to Indian work of the previous two years), each year's papers receive 1.53× as many Indian citations as they give, and the ratio is above 1 for every cohort from 2017: IMTECH 1.98×, IGIB 1.87×, CCMB 1.72×, CDRI 1.27× (`research_flow_window.csv`).
- **Credit counting.** With fractional counting (citations ÷ authors), 6 of the 10 most cited faculty fall below rank 25 (G. Swarup 1 → 75, Puran Singh Sijwali 2 → 148) and Ritushree Kukreti rises from 7 to 1 (`research_faculty_credit.csv`).
- **Concentration.** CCMB's citations behave like 29 equally cited papers (top paper 16% of the total), IMTECH 58, IGIB 70, CDRI 518. Field-and-year normalised impact (MNCS) is close: CCMB 1.15 (0.95–1.40), IGIB 1.05, IMTECH 1.03, CDRI 0.96 (0.91–1.02); top-10% shares 11.9–13.8%. Gini of citations across faculty is highest at CCMB (0.68) and lowest at CDRI (0.55) (`research_lab_credit.csv`).
- **Author-identity risk.** One faculty profile carries 117,443 lifetime citations but 8 in our window, which indicates a merged namesake profile; lifetime metrics from OpenAlex need this check before use.

## Course network models (step `s18`)

The models taught in DPCN, applied to the faculty co-authorship network (274 faculty, 1,250 links, links from the first joint paper with at most 50 authors) and, where a larger sample is needed, to the network of all 17,136 authors on the labs' papers. Numbers come from `outputs/stats/netmodel_*.csv` and `netmodel_summary.json`; the dashboard shows them on Findings → Network models.

| # | Model | Test | Result |
|---|---|---|---|
| 15 | Heavy tails, not scale-free | Clauset–Shalizi–Newman fit, 300 bootstraps, Vuong tests | faculty degree: power law only above 21 links (38 faculty, p = 0.12), exponential and cut-off power law fit better; all authors: α = 2.56 above 36, p = 0.08, log-normal and cut-off power law favoured; paper citations: α = 2.64 above 40, p = 0.02 |
| 16 | Small world | vs 50 Erdős–Rényi and 50 degree-preserving graphs | faculty: L = 3.55 vs 2.61, C = 0.36 vs 0.04 (σ = 6.4; 1.9 vs degree-preserving); all authors: L = 4.31 vs 4.44, C = 0.66 vs 0.001 |
| 17 | Robust to chance, fragile to losing brokers | node removal: random (100 orders), degree, betweenness, cross-lab brokers | random removal halves the largest component after 44% of faculty (Molloy–Reed theory: 95%); betweenness after 13 people (5%); removing the 24 faculty with most cross-lab co-authors leaves no two labs connected (random: 270) |
| 18 | Lab walls slow spreading | SI (β = 0.05 per joint paper), one run per faculty; 10 rewired nulls | median 6 steps to reach another lab and 10 to reach all four, vs 2 and 4 with random mixing; 14 without the five main brokers |
| 19 | Epidemic threshold matches theory | SIS, recovery 0.2 | outbreaks persist from λ ≈ 0.063; quenched mean field 1/Λmax = 0.039, heterogeneous mean field ⟨k⟩/⟨k²⟩ = 0.049 |
| 20 | New links are predictable within labs, not across them | train on earlier years, test 2019–2025 | mean AUC: logistic model 0.88, same lab alone 0.83, Katz 0.80, Adamic–Adar 0.75, topic 0.60; cross-lab pairs only: model 0.64, topic 0.69, Katz 0.69 |
| 21 | Lab drives tie formation; shared colleagues matter most across labs | discrete-time logistic hazard, 190,222 pair-years, 894 new links, year effects, dyadic-robust errors, 200 label permutations | same lab OR 29.6 (17.4–50.6), permutation p = 0.005; same department 1.43 (0.99–2.08); shared co-authors 1.74 per e-fold; seniority n.s.; shared co-authors 13.0× per e-fold across labs vs 1.7× within; holdout AUC 0.89 (2023–2025) |

**15. Not scale-free.** The degree and citation distributions are heavy-tailed, but the power law is either rejected by the bootstrap or beaten by a log-normal or a power law with an exponential cutoff. A faculty member can only co-author with so many colleagues, which bends the tail down. This matches Broido & Clauset (2019): "scale-free" should be dropped from any write-up.

**16. A small world built from tight groups.** Paths are only about one step longer than in a random graph, while clustering is nine times higher. Part of the clustering comes from the degree sequence itself (degree-preserving graphs reach 0.14), but even against them σ ≈ 1.9.

**17. Fragility sits in a few people.** Configuration-model theory says random failure would need 95% of faculty to go before the network falls apart; in reality halving takes 44%, because the network is modular rather than random. Targeted removal is far worse: 13 high-betweenness faculty halve the largest component, and 24 cross-lab brokers disconnect every pair of labs. Isolating one lab needs cutting 23 (IMTECH) to 38 (CCMB) links.

**18–19. Spreading.** Anything passed along joint papers (methods, reagents, ideas) would take two to three times longer to reach all labs than in the same network without lab boundaries. SIS outbreaks start a little above the mean-field thresholds, as expected on a finite, clustered network.

**20–21. How ties form.** Within a lab, the network itself predicts new collaborations well; across labs, network scores barely beat chance and topic similarity does as well. The hazard model shows why: holding topic, network position, output, seniority and year fixed, a same-lab pair is about 30 times more likely to start collaborating, department adds little, and seniority nothing. The interaction term shows that a cross-lab collaboration almost always comes through a shared colleague (13× per e-fold of shared co-authors, against 1.7× within a lab). The policy lever is the brokers.

**Method notes.** The tie model is a dyadic logistic hazard, not a stochastic actor-oriented model (RSiena needs R, which is not part of this pipeline). It handles dependence between pairs that share a person with dyadic-robust errors (Aronow, Samii & Assenova 2015) and a lab-label permutation test. Seniority is the current CSIR grade on the roster, not the grade in each year. The risk set uses each person's last paper year, so it knows who is still active.

## Robustness and dynamics (step `s19`)

Checks on the main result and four dynamics on the faculty network. Numbers come from `outputs/stats/ext_*.csv` and `ext_summary.json`; the dashboard shows them on Findings → Robustness & dynamics.

| # | Question | Test | Result |
|---|---|---|---|
| 22 | Does the same-lab effect depend on analysis choices? | specification curve: 3 author caps × 2 risk sets (with / without look-ahead) × 2 year sets × hubs kept / dropped × 2 control sets = 48 models, dyadic-robust CIs | odds ratio 21.7–46.4 (median 31.3); lowest lower bound 13.2; same department 1.32–1.68, significant in 2 of 24 full models |
| 23 | Do the results survive a paper-wide multiple-testing correction? | Benjamini–Hochberg across all 210 p-values in s17–s22 | 134 with p < 0.05, 125 with q < 0.05; the nine lost are borderline control terms, two lab-exchange cells (CCMB ↔ IMTECH) and one power-law comparison; no headline result is affected |
| 24 | Do faculty adopt methods after their co-authors? | discrete-time adoption hazard, 8 methods pooled, 250 adoptions, year / method / lab effects, faculty-clustered errors | one adopting co-author OR 2.28, two 3.90, three or more 4.85; same-lab exposure OR 2.58 per e-fold, cross-lab 1.61 (n.s.); still 1.79–2.87 for adoptions not on a joint paper |
| 25 | Influence or homophily? | shuffle test (adoption years permuted among adopters, 200 times) | observed OR 2.73 vs shuffled 2.76, p = 0.53: the timing carries no influence signal |
| 26 | Simple or complex contagion? | observed rate vs independent-exposure prediction | k = 2: 4.2% vs 4.4% predicted; k ≥ 3: 4.7% vs 8.7%: no complex contagion, saturating exposure |
| 27 | Do triples close into joint papers? | closure 2021–25 of triples never on one 2016–20 paper, by ties (Benson et al. 2018) | 0 ties 0.03%, 1 tie 0.35%, 2 ties 3.9%, 3 ties 4.3%, 3 repeated ties 21.7% (vs wedge OR 6.8, p = 0.002); wedges spanning labs 0.5% vs 4.1% inside a lab (OR 0.12, p = 0.007) |
| 28 | Can the tie model grow the real network? | year-by-year simulation from 2016 with refitted variants, 40 runs each | full model: cross-lab 4.9% (real 5.2%), path 3.53 (3.44), lab modularity 0.38 (0.45); without lab: cross-lab 51%; clustering 0.15 vs 0.28 in every variant |
| 29 | Did COVID-19 collaborations last? | pairs first linked 2020–22 on COVID-19 vs other topics | later non-COVID joint paper 10% vs 36% (Fisher p < 0.001); 12 cross-lab COVID pairs, none continued on other topics |
| 30 | Does citing come before collaborating? | prior independent citation added to the tie model | 8.2% of new links vs 1.1% of unlinked pairs had a prior citation (17% of new cross-lab links); OR 1.67 (1.21–2.32) with all controls |

**22–23. The core claim is robust.** No choice we could make removes the lab effect: the smallest estimate (hubs dropped, full controls, no look-ahead) is still 22×. Department never matters much. Almost every reported result keeps q < 0.05 when all 210 tests from s17–s22 are corrected together.

**24–26. Methods travel with groups, not between them.** Faculty are two to five times more likely to start using a method once co-authors use it, mostly through same-lab co-authors. But when adoption years are shuffled among the adopters, the association does not weaken at all. In the language of Anagnostopoulos et al. (2008), the correlation is explained by who works with whom (shared groups and projects), not by one person's adoption causing the next. The dose-response follows simple contagion for two adopters and falls below it for more, the opposite of complex contagion.

**27. Groups need strong ties.** Three faculty who have each co-authored repeatedly in pairs are 6.8× more likely than an open wedge to write a paper together; a mere open triangle is not. Groups that span labs almost never close. Collaboration grows by strengthening ties inside groups before it adds people.

**28. Lab preference is enough for the lab structure; groups are needed for clustering.** Growing the network from the fitted model reproduces the cross-lab share, path length and most of the lab modularity; removing the lab term destroys them. No pairwise variant reaches the real clustering, because papers link several people at once. The next model should treat papers as hyperedges.

**29. A mission-driven shock did not build bridges.** COVID-19 work created new ties, but pairs formed on it rarely wrote together on anything else, and only 12 of them crossed labs.

**30. Citation is a precursor.** A prior citation raises the odds of a new collaboration by two-thirds beyond lab, topic and network position, and it is twice as common before cross-lab links.

**Limits.** Methods are detected from titles and OpenAlex topics, not full text. The shuffle test cannot detect influence that happens on the joint paper itself. The COVID-19 comparison has few cross-lab pairs. All are associations.

## Teams, ties and careers (steps `s20`–`s22`)

Step `s20` adds OpenAlex data (698 calls): funders on 4,444 papers, author countries on 6,026, every faculty member's publication years anywhere, 633 faculty pairs who wrote together before 2016, and the countries and fields of works citing each lab. Step `s21` runs the models below; `s22` fits a stochastic actor-oriented model in R (RSiena). Numbers come from `outputs/stats/dyn_*.csv`, `dyn_summary.json`, `siena_*`; the dashboard shows them on Findings → Teams, ties & careers.

| # | Question | Test | Result |
|---|---|---|---|
| 31 | Do papers-as-groups reproduce the network? | Guimerà et al. (2005) team assembly: real papers, sizes and newcomers; incumbent slots repeat past collaborators with q = 0.57 and stay in the lead lab with h = 0.99; 30 runs | clustering 0.30 (real 0.32; pair-by-pair model 0.15), lab modularity 0.45 (0.46); cross-lab share 1.5% (real 4.8%); without lab preference the cross-lab share is 72% |
| 32 | Do new ties last? | life table and discrete-time repeat hazard, 1,056 pairs, dyadic-robust | after 5 years 44% of same-lab and 26% of cross-lab pairs have written again; first-year strength OR 8.2 per e-fold (4.5–14.9); same lab 1.84 (0.95–3.59) |
| 33 | Do brokers gain? | faculty-year panel 2017–25 (1,874 faculty-years), faculty and year fixed effects | any cross-lab tie: −0.005 log points on next-year normalised citations (−0.09 to 0.08); brokerage −0.04 (−0.21 to 0.13); betweenness +0.025 on output (0.003–0.047) |
| 34 | Do data errors change the result? | drop or reassign 5–20% of faculty–paper links (20 runs each), 200 faculty bootstraps, leave one lab out | same-lab OR (all pairs, with topic and output) 56 observed; 56 with 20% dropped; 64 with 20% reassigned within lab; 14 / 7.8 / 4.4 with 5 / 10 / 20% reassigned to any lab; bootstrap 38–103; without one lab 27–93 |
| 35 | Can information reach other labs in time order? | earliest-arrival paths from 190 early faculty; 100 shuffles of contact years | 88% of (faculty, other lab) pairs reached by 2025 with one hop per year (shuffled 88%, 83–91%); static network 96% |
| 36 | Which partition describes the network? | 100 Louvain runs + consensus; degree-corrected SBM description length | labs 9,152 nats < Louvain consensus 9,184 < departments 12,032; consensus 6 communities, 95% lab purity; Louvain vs labs NMI 0.72 |
| 37 | Do funders, careers and old ties matter? | added to the tie model | joint paper before 2016 OR 3.2 (2.4–4.2); career age 0.80 per decade (0.70–0.92); shared funder 1.23 (0.73–2.05), uninformative because 86% of pairs share one; same lab stays 28 |
| 38 | Abroad, India or a sister lab? | author countries | foreign co-author on 19% of papers (CCMB 29%, CDRI 15%), another Indian institution on 56%, another of our labs on 1.1% |
| 40 | Does an actor-oriented model agree? | RSiena, 185 continuously active faculty, waves 2016–18 / 2019–21 / 2022–25 (ties 386, 407, 438; Jaccard 0.25, 0.23), modelType 2; all models converged (max ratio 0.13–0.20) | same lab +1.91 (s.e. 0.11; 6.8× odds per tie change), same department +0.04 (0.09, n.s.), transitive triads +0.27 (0.02), topic similarity +1.21 (0.11), output +0.15 (0.03), seniority n.s., degree n.s. |
| 39 | Who cites the labs worldwide? | citing works 2016–26 by author country | India is 10% (CCMB) to 22% (CDRI) of country mentions; the US and China lead for CCMB, IGIB and IMTECH |

**31. Groups explain the clustering.** Treating papers as groups, as in Guimerà et al. (2005), reproduces the clustering and lab modularity that no pair-by-pair model could. It produces too few cross-lab links, though: the real 4.8% are not random lapses in lab preference but are concentrated in particular brokers (see result 17).

**32–33. Cross-lab ties start weak and stay weak, and spanning labs does not pay.** Pairs whose first collaboration produced several papers are eight times more likely to continue. Within the same person over time, gaining a cross-lab tie or bridging groups brings no measurable gain in next-year citations, which offers one reason such ties are not renewed.

**34. The lab effect cannot be an artefact of matching errors.** Dropped links and mix-ups within a lab leave it unchanged. Only errors that move papers to people in other labs shrink it, and even 20% such errors (far above anything our checks found) leave it at 4×.

**35–36. Time and communities.** Respecting the order of joint papers, fewer faculty can reach another lab than the static network implies, but the real timing is no different from random timing. A block model compresses the network best when its blocks are the four labs: the official labs are the network's communities, and departments are too fine.

**40. The actor-oriented model agrees.** RSiena treats each faculty member as choosing to create or end ties, with ties allowed to dissolve between waves and dependence between ties built in. It finds the same structure as the dyadic models: a large same-lab effect, no department effect once the lab is known, transitive closure, topic similarity and an output effect, with seniority irrelevant.

**37–39. More data, same boundary.** Earlier collaboration triples the odds of a new one and older pairs collaborate less, but neither changes the lab effect. The labs co-author abroad (19% of papers) far more often than with each other (1.1%), and most of their citations come from outside India.

## More tested results (steps s23–s26)

These complement the course network models above. Rows 41–44 extend the SI/SIS results of rows 18–19 with SIR outbreak sizes over many random seeds, seeding strategies, super-spreaders, simulated interventions and random walks. The SIS thresholds differ slightly because they are defined differently: here the peak of the susceptibility, there the λ at which outbreaks persist.

| # | Finding | Test | Result |
|---|---|---|---|
| 41 | Lab walls slow spreading between labs | SIR outbreaks from each lab, 1,000 runs, real vs degree-preserving rewired networks (s23) | an outbreak reaches another lab in 5% of runs vs 23% rewired; IGIB → CDRI 4% vs 31% |
| 42 | Hubs lower the epidemic threshold | SIS with many random seeds, susceptibility peak, vs rewired and Erdős–Rényi | λc = 0.054 vs 0.063 rewired and 0.100 random; mean-field ⟨k⟩/⟨k²⟩ = 0.049 |
| 43 | Core members spread best | SIR from every faculty member as the first case | Spearman with outbreak size: eigenvector 0.95, k-shell 0.92, degree 0.87, betweenness 0.51 (k-shell beats degree, as in Kitsak et al. 2010) |
| 44 | A random walker is trapped in its lab | exact mean first-passage times, real vs rewired | 147 steps to reach another lab vs 10 (21×); relaxation time 60 vs 7 steps |
| 45 | Clustering is mostly what multi-faculty papers produce | bipartite (paper-reshuffle) null, 100 draws (s24) | clustering 0.32 vs 0.28 bipartite (z = 4.3), 0.13 rewired, 0.03 random; 46% of triangles are one paper |
| 46 | Communities follow labs, not departments | Louvain vs labels, label-permutation null | NMI 0.64 with lab (z = 70), AMI 0.30 with department; the main core (k = 15) is 28 CDRI faculty |
| 47 | Students and staff are the glue | faculty network with and without links through non-faculty lab authors | cross-lab share of links 4.8% → 11.1%; largest component 243 → 256; 7 of 23 isolates connected |
| 48 | Topics do not spread through co-authors | new-subfield adoption after a prior co-author vs future co-authors (placebo) | relative risk 5.2 vs 5.6 for the placebo: homophily, not influence |
| 49 | New collaborations are predictable | time split 2016–20 → 2021–26 | AUC 0.88 (same lab + topic + Adamic-Adar); topic similarity alone 0.58 |
| 50 | The Q1 decline is journal re-grading | quartile frozen at 2017 vs year-matched; JCR IF > 5 share (s26) | Q1 74% → 62% year-matched but 75% → 70% frozen; IF > 5 share rose 19% → 23% |
| 51 | Medical partners do not bring more citations | OLS on log citations with year, field, lab, team size, review | Indian hospital/medical partner −16% (−25% to −5%); foreign partner +23%; industry +64% (79 papers) |
| 52 | Output is a random walk with persistent levels; success persists | Laplace vs normal fit of yearly changes; top-decile persistence vs 2,000 permutations (course paper P1) | Laplace fits better (AIC 10,129 vs 10,740); lag-1 autocorrelation −0.39 (between 0 and −0.50); 62% stay in the top 10% vs 11% by chance |
| 53 | Collaboration decays with distance faster than citation | Poisson gravity model, 2,151 Indian partners (s25) | elasticity −0.58 (joint papers) vs −0.30 (citations), difference −0.27 (p < 10⁻⁴³) |
| 54 | Against 13 Indian biology peers, impact is mid-table | identical OpenAlex query, FWCI and top-10% share | mean FWCI ranks CCMB 4, IGIB 9, IMTECH 11, CDRI 14 of 17; top-10% share 13.3–14.3% vs peer median 17.8%; output shrinking 1–3.5% a year vs +0.8% for the median peer |

### What the new results mean

**41–44. Dynamics.** Spreading processes turn the "lab wall" into something you can feel: an idea, technique or rumour that starts in one lab almost never reaches another (5% of outbreaks, against 23% if the same people kept their number of co-authors but links were random), and a random walker needs about 150 steps to leave its lab. The network is not hostile to spreading in general: hubs give it a lower epidemic threshold than a random network. It is the partition into labs that blocks flow. Simulated interventions show that a few extra cross-lab links help only slightly (5% → 10% reach with 40 hub-to-hub links), because the walls are thick.

**45–49. Structure.** The right baseline for co-authorship is the bipartite null: much of the clustering is what papers with three or more faculty create mechanically, but some (z = 4.3) is genuine triadic closure. Communities reproduce labs far better than departments. Students, postdocs and staff more than double the share of links that cross labs, which supports the instructor's point that excluding them hides part of the collaboration structure. Topic contagion vanishes against the future-co-author placebo, a textbook case of homophily masquerading as influence.

**50–51. Journals and partners.** The fall in the share of Q1 papers is mostly Scimago re-grading journals: with every journal frozen at its 2017 grade, the share falls far less, and the share in journals with JCR IF > 5 rose. Hospital partnerships do not raise citations once team size is held equal; foreign and industry partners do.

**52. Productivity.** As in Zhang et al. (course paper P1), yearly changes in output are Laplace-distributed, and a truncated random walk reproduces the share of years with no paper and the inequality of total output. But scientists' levels persist: 62% of the 2016–20 top decile are top-decile again in 2021–25.

**53–54. Geography and peers.** Distance matters twice as much for writing together as for citing. Against other Indian biology institutes, our labs have world-average-plus impact (FWCI 1.4–2.1) but rank in the lower half on top-10% papers, international co-authorship and growth.

## Methods no other group used (step `s27`)

Our team reviewed the projects of all 29 other groups and catalogued 154 methods and features with who used each (Phase III planning notes). Six methods from the instructor's papers were used by none of them; these are they. The dashboard's "Only here" page sets all of our work against that catalogue: 17 firsts, 16 of the 38 rare items, 104 of 154 items fully and 22 partly, and all 50 items that six or more groups did.

| # | Finding | Test | Result |
|---|---|---|---|
| 55 | Output swings grow over a career, unlike in computer science (P1) | Laplace scale of yearly changes by years since first paper; faculty bootstrap; permutation of career ages; lognormal vs power law | 1.01 papers in the first decade vs 2.07 after 30 years (relative to output 0.48 vs 0.61); Spearman 0.14, p < 0.001; cumulative output lognormal (R = 127) |
| 56 | Research groups do not follow Gibrat's law (P8) | log growth on log size of each PI's yearly group (non-faculty lab co-authors), HC1 | slope -0.49 (95% CI -0.54 to -0.45); median group 7; department size unrelated to papers per faculty (p = 0.55) |
| 57 | Writing together makes people cite each other, beyond shared topics (P6) | logistic model over 74,802 ordered faculty pairs, independent citations only | odds ratio 18 alone, 10.2 with topic, distance, output and lab |
| 58 | A first joint paper raises mutual citation (P3) | event study vs distance-2 pairs that never co-author, difference in differences, Weibull fit | +0.06 citations a year (95% CI +0.03 to +0.10), largest straight after the first paper (Weibull shape 0.9) |
| 59 | Early partner diversity does not predict later success (P9) | Spearman vs 2,000 reshuffles within lab × early-output tercile | no difference from the reshuffled range for output or impact (p > 0.3) |
| 60 | Labs change mostly because the same people change (P10) | entry / exit / within decomposition of the share of internationally collaborative faculty | 70% within-person, 21% entrants, 10% leavers |

## Paper-worthy directions

1. **"Walls between labs, not departments: co-authorship homophily in Indian national laboratories."** Results 1, 6, 7 and 8, extended to more CSIR labs (other groups in the course cover many of them), would test whether the 55× lab effect is general. Data and code are in this repository.
2. **"Self-citation distorts institutional citation centrality."** Results 2–3: a simple, reproducible correction with a large effect on rankings; could be shown across all groups' datasets.
3. **"How far does knowledge travel inside an institute?"** Results 4–5: distance-decay of independent citation, with a field-stratified null that separates topic from proximity.
4. **Credit in big science.** Results 9–10 and the hyperauthorship flags: how much of an Indian lab's visibility comes from middle-author positions in consortia, and what fractional counting changes.

## Limits

- OpenAlex author identities and affiliations contain errors; faculty identities were checked by hand (see the About tab), but co-authors outside the roster were not.
- Citation counts are as of 2026-11-20; recent years have had less time to accumulate citations (handled by year controls and year-matched nulls).
- The COVID-19 classification is a keyword match on titles and topics.
- The faculty network ignores papers with more than 50 authors, as in the submitted authorship network.
- Associations only: none of these designs identifies causes.
