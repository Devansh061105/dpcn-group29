# Chatbot test (T-12)

Tested by Aman on 2026-11-23, on the dashboard built from this commit. I asked 30 questions a viva examiner might ask, mixing names, labs, comparisons, thresholds, definitions and findings.

**First run:** 21 of 30 answers were right. Every wrong or unhelpful answer is listed below with what it should have said, and each was fixed in `src/dpcn/dashboard/chat.js` (and `phase3.js` for the limitations list).

**Second run:** all 30, plus 4 extra checks, gave a correct and relevant answer.

## Wrong or unhelpful answers in the first run

| # | Question | What it answered | What it should say | Fix |
|---|---|---|---|---|
| 21 | how accurate is the faculty matching? | The error-simulation finding plus an unrelated spreading result | The hand-checked precision: 98% of 55 sampled links correct (95% CI 90–100%) | Added a FAQ entry built from the precision audit (`R3.precision`) |
| 22 | how many faculty are on the roster? | The "not scale-free" finding and one lab's summary | 294 on the roster (232 from websites, 61 from papers, 1 in review; 35 former); 274 with papers | Added a FAQ entry from the About tab's manual-work counts |
| 23 | which journal do the labs publish in most? | Top 10 faculty by citations ("most" triggered the faculty ranking) | Scientific Reports (182 papers), then Int. J. Biol. Macromol. (97) and Eur. J. Med. Chem. (68) | New `journalAnswer()`; the faculty ranking now skips questions about journals |
| 24 | which lab has the highest Q1 share? | Top 10 faculty by citations | IMTECH 76.6%, CCMB 71.4%, CDRI 63.1%, IGIB 62.2% | New `labRank()` for "which lab…" questions (Q1, papers, citations, h-index, foreign or Indian partners) |
| 25 | did COVID-19 change the labs? | The P10 joiner/leaver decomposition ("labs change") | COVID-19 work was 26% of IGIB's 2021 papers and 47% of its 2022 citations; CCMB 13% | A clearly distinctive query word (here "covid-19") must now appear in the answer |
| 26 | are private universities heavy citers? | The raw list of top citing institutions | After dividing by each institution's output, none of the 18 flagged non-government citers is an outlier | The "who cites" shortcut now steps aside for private/government/heavy/flag questions |
| 29 | what are the limitations? | "I couldn't find that" | The "not done" and "blind spots" lists on the Verdicts page | Those lists are now in the chatbot's knowledge (`P3API.limits`) |
| 30 | is anything causal? | Unrelated findings (COVID ties, matching errors) | No: every result is an association tested against a baseline, not an experiment | Same as #29 |

## Answers that were right in the first run

1. what did we do that no other group did? (later removed, with the comparison page)
2. h-index of Thangaraj
3. who is Rajesh Pandey?
4. compare CCMB and IGIB
5. compare Vinod Scaria and Rajesh Pandey
6. top 5 by citations in CDRI
7. top 5 by fractional citations
8. faculty with h-index above 10 and fewer than 100 authors
9. papers with impact factor above 10 (it says it counts papers with fewer than 100 authors)
10. what is fwci?
11. what is a null model?
12. what is the epidemic threshold?
13. what is RSiena?
14. what is modularity?
15. why does fractional counting change the leaders?
16. is the lab the unit of collaboration?
17. how much of internal citation is self-citation?
18. do lab walls slow spreading?
19. is the network scale-free?
20. is it a small world?
27. who cites the labs?
28. how does NCBS compare?

## Extra checks after the fixes (all right)

- which lab publishes the most papers?
- most used journals in CDRI
- does department matter?
- what is triadic closure?

## Known limits

- The bot matches words; it does not understand questions.
- Very open questions ("tell me everything about IGIB") return the lab summary only.
- Questions about a single paper by title work only through the Filter & find page.
