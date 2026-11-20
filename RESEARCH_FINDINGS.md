# Research findings · Group 29

What the data on four CSIR biology labs (CCMB, IGIB, IMTECH, CDRI; 2016–2026; 6,027 papers, 274 faculty) shows beyond descriptive counts. Each result below is tested against a randomised baseline or a model with controls. All numbers come from `outputs/stats/research_*.csv` and `research_summary.json` (step `s17`), and the Findings tab of the dashboard draws them. They are observational associations from OpenAlex data, not causal effects.

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

**6–7. Cross-lab ties are short-lived; new ties come through friends.** Only 12% of new cross-lab pairs repeat within three years, against 34% of same-lab pairs. New links are about 16 times more likely between faculty who already share a co-author. Together these explain why the 94 cross-lab links are scattered and do not build into bridges: they are rarely renewed and rarely seed further links. The 2021 spike (23 cross-lab links, COVID genomics) did not carry over.

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
