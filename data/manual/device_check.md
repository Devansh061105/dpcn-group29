# Device and browser check (T-13)

Checked by Aman on 2026-11-23, on `outputs/submission/group29_dashboard.html` served locally and opened in a Chromium browser. Every section and sub-page was opened at each width. A script then looked for anything wider than the screen; I also looked at screenshots.

| Setting | Result |
|---|---|
| Laptop, 1366 × 768, light | All 26 pages fit: no sideways scrolling. Wide tables (faculty list, rankings, peer institutes, flags, co-authorship centrality) scroll inside their own frame, as intended. |
| Laptop, 1366 × 768, dark | Text, cards, KPI tiles, the network and the live simulator are readable; chart colours keep their contrast. |
| Desktop, 1920 × 1080, light | All pages fit. |
| Phone, 375 × 812 | All 26 pages fit with no sideways scrolling; the section bar scrolls sideways to reach Flags and About. |

## Issues found

1. **Phone:** the floating "Ask the data" button covers the last line of the overview hero (the team names) until you scroll. Minor.
2. **Benchmark → "Size against impact":** labels overlap where institutes cluster around 1,500–2,500 papers (IGIB sits under ICGEB-ND, and CIMAP under IICB). Hovering shows the right name. Minor.

## Not checked

- **Firefox, and a real phone:** only Chromium was available here. The page uses no browser-specific features, but someone should open it once in Firefox before the viva.
