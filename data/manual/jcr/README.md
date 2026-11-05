# Journal impact factors (JCR)

The dashboard needs an impact factor (IF) for each journal to count Q1 papers with IF > 5 and IF > 10 and to rank
papers by journal. Clarivate's JCR is licensed, so the raw lists are not committed. Sources, in order of preference:

1. **`jcr_impact_factors.csv` in this folder** (supplied by the team). Where a journal is found here, this value is
   used and labelled "JCR <year>". Matching is by ISSN or eISSN first, then by journal title.
2. **Scimago "Citations / Doc. (2years)"** from the full download in `data/manual/sjr_full/` (newest year).
3. **OpenAlex 2-year mean citedness** (fetched by step s16), labelled as a proxy.

## How the current `jcr_impact_factors.csv` was built

* **JCR 2024** (19,727 rows): the team's `JCRImpactFactors2025.xlsx` export, which carries ISSN, eISSN and the 2024 JIF.
  Values checked against published ones (Nature 48.5, Science 45.8, Cell 42.5). Journals with "<0.1" are left out.
* **JCR 2025** (2,808 rows, title only): from the team's `JCR-Impact-Factor-2026.pdf` (columns Journal Name, IF 2025,
  Quartile; no ISSN, long names clipped). Only titles that the 2024 export does not contain are used, so each journal
  has one value. Titles that appear twice with different values are dropped.
  The PDF's values run about 10% above 2024 for the typical journal, and its provenance could not be verified,
  so it is a fill-in and not the main source. Replacing 2024 with 2025 wherever both exist would raise the number of
  Q1 papers above IF 5 from 1,221 to 1,733 (all labs).

## Format of the file

Columns `issn, eissn, journal, impact_factor, jcr_year` (header names are matched loosely; `impact_factor` plus an
`issn` or `journal` column are required). See `jcr_impact_factors.example.csv`.
Then run `python -m dpcn run s16` and `python -m dpcn run s13`.
