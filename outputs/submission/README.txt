DPCN Research Mapping Project - Group 29
Institutions: CSIR-CCMB, CSIR-IGIB, CSIR-IMTECH, CSIR-CDRI
Window: 2016-2026 (2026 is a partial year). Data collected from OpenAlex on 2026-10-13.

FILES
  group29_data.csv                 8107 rows
  citation_network.csv            64240 rows
  authorship_network.csv         127062 rows
  indian_connections.csv           6182 rows
  group29_dashboard.html
  group29_report.pptx
  group29_report.pdf

KEY DECISIONS
- Faculty (D2/D25): scientists listed on each lab's website, plus scientists identified from lab-affiliated
  authorship (frequent last/corresponding author) and confirmed by the team; matched to OpenAlex author IDs.
- A paper counts for a faculty member only if their own authorship carries the lab affiliation (D4).
- One row per paper x faculty member x lab (D5); paper-level statistics deduplicate on openalex_id.
- Types (D7): journal articles/reviews/letters and conference papers; no preprints, chapters, errata.
- Quartile (D8): Scimago SJR best quartile of the publication year, joined on ISSN then title; CORE rank for
  conference papers; NA when unknown.
- h-index (D10): window h-index from the dataset; OpenAlex lifetime h shown for context.
- Indian partner (D11): an Indian institution other than the row's lab; umbrella bodies (CSIR HQ, Government of
  India, ministries, DAE/DBT HQ) and AcSIR (CSIR's degree academy) are not counted.
- Citation network (D13/D14): internal edges between dataset papers, plus edges to/from other Indian works when
  the two papers' Indian institutions differ. year = citing paper's year.
- Authorship network (D15/D16): every pair on every dataset paper with <= 50 authors where at least one
  author is at one of our labs; faculty-only and lab-internal graphs are analysed.
- indian_connections total_citations (A8) = cites_in + cites_out; shared_papers_citations is also given.

EXTRA COLUMNS in group29_data.csv: openalex_id, author_openalex_ids, faculty_id, department, dept_source, designation, faculty_status, domain, field, subfield, primary_topic, n_authors, author_position, is_corresponding, coauthor_institutes_all, quartile_source, sjr_year_used, affil_method
