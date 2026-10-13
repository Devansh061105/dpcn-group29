# Scimago (SJR) journal rankings, 2016–2025

`scimagojr_<YEAR>.csv` hold the Scimago Journal Rankings for each year, **filtered to the journals that appear in our dataset** (matched on any ISSN). Columns: `Sourceid;Title;Type;Issn;SJR Best Quartile`, semicolon-separated, the same header as the full download, so S06 reads either.

- Fetched 2026-10-14 from `https://www.scimagojr.com/journalrank.php?year=<YEAR>&out=xls` inside a browser session (the site blocks scripted downloads with a Cloudflare check).
- The 2026 request returns the 2025 edition, so 2025 is the latest; S06 uses it for 2026 papers.
- **If the roster or the inclusion rules change and new journals enter the dataset, re-download** (full files are fine: drop them here with the same names) and re-run `python -m dpcn run all --from s06`.
