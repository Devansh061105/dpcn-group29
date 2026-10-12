# QA log — Group 29

Record every manual decision and spot-check here (guide §13): anomalies, roster gaps, match and quartile overrides, and spot-check results.

| Date | Step | Who | Finding / decision |
|---|---|---|---|
| 2026-10-13 | S00 | Claude | All 4 labs verified: ROR matches config, country IN. 2016–2026 work counts (all types) are CCMB 2333, IGIB 2643, IMTECH 1636, CDRI 3952, a 0.0% drift from reconnaissance. Every year 2016–2026 present for every lab. |
| 2026-10-13 | S00 | Claude | **Open:** IMTECH 2026 = 261 works versus ~140/yr typical. Investigate in S05 before trusting the trend. |
| 2026-10-13 | Scope | Team | **Open:** CDRI inclusion (plan A1). Awaiting instructor confirmation. |
| 2026-10-13 | S01 | Claude | Scraped rosters from the 4 lab sites: CCMB 41 (website "All Faculty"), IGIB 42 (ScientistDirectory.html), IMTECH 48 (/en/.../scientists; the default site serves Hindi), CDRI 101 (12 division pages). **Total 232 faculty**, below the plan's ~300 estimate. Only scientists/PIs are listed on these sites, which matches the A6 definition. |
| 2026-10-13 | S01 | Claude | CDRI: excluded 1 non-scientist (Private Secretary). The 13th "division" tab (S&T Infrastructure & Services) links to a different page layout and is not scraped, so any scientists listed only there are missing. **Open:** check that page by hand. |
| 2026-10-13 | S01 | Claude | **IMTECH has no department data:** the site's focus-area filter returns all 48 people whatever is selected. `department` is blank for all 48. Plan D20 fallback applies (OpenAlex modal subfield, `dept_source=openalex`); the site's per-person "expertise" text is kept in the `expertise` column. |
| 2026-10-13 | S01 | Claude | IGIB: Shivanshu Kukrety's profile page is a "coming soon" stub, so designation and department are blank (kept, as the directory lists scientists only). The directory spells the surname "Kukrety" but the profile URL says "Kukreti"; S03 matching should try both. The Director's page (Souvik Maiti) has a different layout; parsed as "Director; Scientist-G". |
| 2026-10-13 | S01 | Claude | Matching evidence for S03: ORCID scraped for 28 IGIB people (none on the other sites); 1,023 DOIs from profile publication lists (CCMB 39 people, IGIB 14, IMTECH 15, CDRI none); 21 IGIB people have PubMed IDs. **Open:** a second team member should review `data/manual/faculty_roster.csv` (plan exit criterion for P1) and add former faculty (plan D3) if wanted. |
