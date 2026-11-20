from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from dpcn import phase2 as P

P2 = SimpleNamespace(if_thresholds=[5, 10], multi_author_min=10, hyper_author_min=100, mega_author_min=1000,
                     faculty_flag_share_hyper=0.25, faculty_flag_share_multi=0.60, faculty_flag_min_citations=100,
                     citer_min_cites=150,
                     citer_ratio_min=15)
LABS = ["CSIR-A", "CSIR-B"]


def main_rows():
    """Rows of the submitted dataset (paper x faculty x lab). Papers P1..P6, faculty F1 and F2 (lab A), F3 (lab B)."""
    def r(pid, inst, fid, author, year, cit, n, typ="journal", q="Q1", issn="1111-1111", jour="J1", collab=""):
        return {"openalex_id": pid, "institution": inst, "faculty_id": fid, "author": author, "department": "D",
                "faculty_status": "current", "year": str(year), "citations": str(cit), "n_authors": str(n), "type": typ,
                "quartile": q, "issn": issn, "journal_name": jour, "doi": f"https://doi.org/10/{pid}",
                "title": f"Title {pid}", "coauthor_institutes_all": collab}
    return pd.DataFrame([
        r("P1", "CSIR-A", "F1", "Ann", 2020, 10, 5, issn="1111-1111", collab="Uni X (IN); Lab Y (FR); " + P.ACSIR + " (IN)"),
        r("P2", "CSIR-A", "F1", "Ann", 2021, 20, 12, q="Q2", issn="2222-2222", jour="J2", collab="Uni X (IN)"),
        r("P3", "CSIR-A", "F1", "Ann", 2021, 600, 250, issn="1111-1111", collab="Uni Z (IN); Lab Y (FR)"),   # hyperauthored
        r("P3", "CSIR-A", "F2", "Bob", 2021, 600, 250, issn="1111-1111", collab="Uni Z (IN); Lab Y (FR)"),
        r("P4", "CSIR-A", "F2", "Bob", 2022, 5, 3, typ="conference", q="B", issn="", jour="Conf", collab=""),
        r("P5", "CSIR-B", "F3", "Cy", 2022, 40, 8, issn="3333-3333", jour="J3", collab="Uni X (IN); CSIR-A (IN)"),
        r("P6", "CSIR-A", "F1", "Ann", 2022, 7, 4, q="Q3", issn="2222-2222", jour="J2", collab="Uni X (IN)"),
        r("P6", "CSIR-B", "F3", "Cy", 2022, 7, 4, q="Q3", issn="2222-2222", jour="J2", collab="Uni X (IN)"),
    ])


def impact():
    return pd.DataFrame({"issn_n": ["11111111", "22222222", "33333333"], "impact_factor": [12.0, 4.0, 6.5],
                         "if_source": ["JCR 2023", "OpenAlex 2-year mean citedness (proxy)", "JCR 2023"]})


@pytest.fixture
def d():
    return P.prepare(main_rows(), impact(), LABS, P2)


def test_helpers():
    assert P.norm_issn("1424-3903") == "14243903" and P.norm_issn("2041-172x") == "2041172X" and P.norm_issn(None) == ""
    assert P.h_index([10, 8, 5, 4, 3]) == 4 and P.h_index([]) == 0
    assert P.parse_collab("Groupe Cahors (France) (FR); Odd name (?); Plain") == [
        ("Groupe Cahors (France)", "FR"), ("Odd name", "?"), ("Plain", "?")]
    cls = [P.author_class(n, P2) for n in (3, 9, 10, 99, 100, 999, 1000, 2930, float("nan"))]
    assert cls == ["<10", "<10", "10-99", "10-99", "100-999", "100-999", "1000+", "1000+", "unknown"]
    assert P.class_order(P2) == ["<10", "10-99", "100-999", "1000+"]


def test_prepare_joins_impact_factor_and_drops_acsir(d):
    p1 = d[d["openalex_id"] == "P1"].iloc[0]
    assert p1["impact_factor"] == 12.0 and p1["if_source"] == "JCR 2023"
    assert P.ACSIR not in p1["collab_all"] and p1["collab_all"] == {"Uni X", "Lab Y"}
    assert p1["collab_in"] == {"Uni X"} and p1["collab_foreign"] == {"Lab Y"}
    assert np.isnan(d[d["openalex_id"] == "P4"].iloc[0]["impact_factor"])           # conference: no ISSN, no IF


def test_overview_counts(d):
    ov = P.overview_table(d, LABS, P2, {"CSIR-A": 5, "CSIR-B": 3, "ALL": 8}).set_index("scope")
    a, allv = ov.loc["CSIR-A"], ov.loc["ALL"]
    assert (a["papers"], a["journal_papers"], a["faculty_with_papers"]) == (5, 4, 2)    # P1 P2 P3 P4 P6
    assert a["q1_papers"] == 2 and a["quartile_known"] == 4                              # P1, P3 are Q1; P4 is a conference
    assert a["q1_if_gt5"] == 2 and a["q1_if_gt10"] == 2                                  # both Q1 papers are in the IF-12 journal
    assert a["papers_if_gt5"] == 2                                                       # P2/P6 are in the IF-4 journal
    assert (a["papers_<10"], a["papers_10-99"], a["papers_100-999"]) == (3, 1, 1)
    assert a["citation_share_100-999"] == pytest.approx(600 / 642)
    assert a["if_proxy_share"] == pytest.approx(2 / 4)                                   # P2 and P6 use the proxy, P1 and P3 JCR
    assert allv["papers"] == 6                                                           # P6 is shared by both labs: counted once
    assert ov.loc["CSIR-B"]["collab_inst_all"] == 2                                      # Uni X and (the other lab) CSIR-A
    assert allv["collab_inst_all"] == 3 and allv["collab_inst_indian"] == 2              # Uni X, Uni Z, Lab Y; our labs are not collaborators


def test_yearly_table(d):
    y = P.yearly_table(d, LABS, P2).set_index(["scope", "year"])
    assert y.loc[("CSIR-A", 2021), "papers"] == 2 and y.loc[("CSIR-A", 2021), "papers_hyper"] == 1
    assert y.loc[("CSIR-A", 2021), "collab_inst_all"] == 3                               # Uni X, Uni Z, Lab Y
    assert y.loc[("CSIR-A", 2021), "collab_inst_all_excl_hyper"] == 1                    # without the 250-author paper: only Uni X
    assert y.loc[("CSIR-A", 2020), "papers_lt_multi"] == 1 and y.loc[("ALL", 2022), "papers"] == 3


def test_faculty_flags_and_adjusted_metrics(d):
    fm = pd.DataFrame({"faculty_id": ["F1", "F2", "F3"], "degree": [1, 2, 3], "strength": [1, 1, 1], "betweenness": [0.0] * 3,
                       "community": [0, 0, 1], "n_partner_insts": [2, 2, 1], "h_lifetime": [5, 5, 5], "designation": ["x"] * 3})
    f = P.faculty_table(d, LABS, P2, fm).set_index("faculty_id")
    assert f.loc["F1", "papers"] == 4 and f.loc["F1", "citations"] == 10 + 20 + 600 + 7
    assert f.loc["F1", "citations_excl_hyper"] == 37 and f.loc["F1", "h_all"] == 4 and f.loc["F1", "h_excl_hyper"] == 3
    assert bool(f.loc["F1", "flag_hyper"]) and "100+" in f.loc["F1", "flag"] or "100" in f.loc["F1", "flag"]
    assert not bool(f.loc["F3", "flag_hyper"])                                            # F3: no hyperauthored papers
    assert f.loc["F2", "cit_share_hyper"] == pytest.approx(600 / 605) and f.loc["F2", "top_paper_share"] == pytest.approx(600 / 605)
    assert f.loc["F1", "collab_inst_all"] == 3 and f.loc["F1", "q1_if_gt10"] == 2
    assert f.loc["F1", "rank_productive"] == 1 and f.loc["F2", "rank_productive"] > 1


def test_top_papers_rank_by_if_then_citations(d):
    top = P.top_papers_by_if(d, LABS, n=30)
    a = top[top["scope"] == "CSIR-A"]
    assert list(a["impact_factor"]) == sorted(a["impact_factor"], reverse=True)
    assert a.iloc[0]["title"] == "Title P3"                                               # IF 12 and 600 citations beats IF 12 and 10
    assert "Bob" in a.iloc[0]["faculty"] and "Ann" in a.iloc[0]["faculty"]
    assert "Title P4" not in set(top["title"])                                            # conference paper has no IF
    ft = P.faculty_top_papers(d, n=2)
    f1 = ft[ft["faculty_id"] == "F1"]
    assert list(f1["rank"]) == [1, 2] and list(f1["title"]) == ["Title P3", "Title P1"]


def test_journals_table_orders_by_paper_count(d):
    j = P.journals_table(d, LABS, top=5)
    a = j[j["scope"] == "CSIR-A"].set_index("journal_name")
    assert a.loc["J2", "papers"] == 2 and a.loc["J1", "papers"] == 2 and "Conf" not in a.index


def test_author_class_table_and_hyper_list(d):
    t = P.author_class_table(d, LABS, P2).set_index(["scope", "author_class"])
    assert t.loc[("ALL", "100-999"), "papers"] == 1 and t.loc[("ALL", "100-999"), "share_of_citations"] == pytest.approx(600 / 682)
    h = P.hyper_papers(d, LABS, P2)
    assert len(h) == 1 and h.iloc[0]["labs"] == "CSIR-A" and h.iloc[0]["our_faculty"] == "Ann; Bob"


def pairs_df():
    def r(a, b, y, fa="TRUE", fb="TRUE"):
        return {"author_a_id": a, "author_b_id": b, "year": str(y), "a_is_faculty": fa, "b_is_faculty": fb,
                "inst_a": "x", "inst_b": "y", "paper_doi": "d", "indian_link": "TRUE"}
    return pd.DataFrame([r("F:F1", "F:F2", 2020), r("F:F1", "F:F2", 2020), r("F:F1", "F:F3", 2021), r("F:F2", "F:F3", 2021),
                         r("F:F1", "A:A9", 2021, fb="FALSE")])             # a student pair never enters the faculty network


def test_temporal_faculty_network_excludes_students_and_tracks_new_links():
    t = P.temporal_faculty_network(pairs_df(), {"F1": "CSIR-A", "F2": "CSIR-A", "F3": "CSIR-B"}, LABS)
    allyear = t[(t.scope == "ALL") & (t["mode"] == "year")].set_index("year")
    assert allyear.loc[2020, "links"] == 1 and allyear.loc[2021, "links"] == 2          # duplicate rows collapse; student pair ignored
    assert allyear.loc[2021, "new_links"] == 2 and allyear.loc[2021, "cross_lab_links"] == 2
    cum = t[(t.scope == "ALL") & (t["mode"] == "cumulative")].set_index("year")
    assert cum.loc[2021, "links"] == 3 and cum.loc[2021, "faculty_linked"] == 3 and cum.loc[2021, "largest_component_share"] == 1
    lab_a = t[(t.scope == "CSIR-A") & (t["mode"] == "cumulative")].set_index("year")
    assert lab_a.loc[2021, "links"] == 1 and lab_a.loc[2021, "faculty_linked"] == 2     # induced on lab A's two faculty


def test_temporal_citations():
    c = pd.DataFrame({"source_inst": ["CSIR-A", "CSIR-A", "CSIR-A; CSIR-B", "CSIR-A", "Uni X"],
                      "target_inst": ["CSIR-A", "CSIR-B", "CSIR-B", "Uni X", "CSIR-A"],
                      "year": ["2020"] * 5, "edge_scope": ["internal", "internal", "internal", "outflow", "inflow"]})
    t = P.temporal_citations(c, LABS).set_index(["scope", "year"])
    assert t.loc[("ALL", 2020), "internal_citations"] == 3 and t.loc[("ALL", 2020), "within_lab"] == 2
    assert t.loc[("CSIR-A", 2020), "to_other_labs"] == 2 and t.loc[("CSIR-A", 2020), "indian_out"] == 1
    assert t.loc[("CSIR-A", 2020), "indian_in"] == 1


def test_institution_network_counts_papers_not_author_pairs():
    r = lambda doi, a, b, y: {"paper_doi": doi, "inst_a": a, "inst_b": b, "year": str(y), "indian_link": "TRUE"}
    pairs = pd.DataFrame([r("d1", "CSIR-A", "Uni X", 2020), r("d1", "CSIR-A", "Uni X", 2020), r("d1", "Uni X", "CSIR-A", 2020),
                          r("d2", "CSIR-A", "Uni X", 2021), r("d2", "CSIR-A", P.ACSIR, 2021), r("d3", "CSIR-A", "Uni Y", 2021)])
    net = P.institution_network(pairs, {"Uni X": "IIT"}, LABS, k=5)
    e = {(x["s"], x["t"]): x for x in net["edges"]}
    assert e[("CSIR-A", "Uni X")]["w"] == 2 and e[("CSIR-A", "Uni X")]["by_year"] == {"2020": 1, "2021": 1}
    assert not any(P.ACSIR in k for k in e) and {n["id"] for n in net["nodes"]} == {"CSIR-A", "CSIR-B", "Uni X", "Uni Y"}
    assert next(n for n in net["nodes"] if n["id"] == "Uni X")["cluster"] == "IIT"


def connections():
    def r(lab, pid, name, cluster, ci, co, sh, acad="FALSE", grp="FALSE"):
        return {"your_inst": lab, "partner_openalex_id": pid, "partner_inst": name, "partner_cluster": cluster,
                "cites_in": str(ci), "cites_out": str(co), "shared_papers": str(sh), "partner_is_csir_academy": acad,
                "partner_in_group": grp}
    return pd.DataFrame([r("CSIR-A", "I1", "Big Private Univ", "University (other)", 300, 20, 10),
                         r("CSIR-B", "I1", "Big Private Univ", "University (other)", 100, 10, 5),
                         r("CSIR-A", "I2", "State Univ", "University (other)", 400, 300, 100),
                         r("CSIR-A", "I3", "AIIMS-like", "Medical", 500, 400, 20),
                         r("CSIR-A", "I4", "Acme Pharma", "Industry", 50, 5, 1),
                         r("CSIR-A", "I5", "AcSIR", "CSIR", 900, 900, 9, acad="TRUE"),
                         r("CSIR-A", "I6", "CSIR-B", "CSIR", 90, 90, 9, grp="TRUE")])


def test_citer_table_flags_private_heavy_citers_not_collaborators():
    own = {"I1": {"ownership": "private"}, "I2": {"ownership": "government"}}
    t = P.citer_table(connections(), own, P2, LABS)
    allv = t[t.scope == "ALL"].set_index("partner_inst")
    assert "AcSIR" not in allv.index and "CSIR-B" not in allv.index                      # not external citers
    big = allv.loc["Big Private Univ"]
    assert big["cites_in"] == 400 and big["shared_papers"] == 15 and big["cites_per_shared_paper"] == pytest.approx(400 / 15)
    assert bool(big["flag_heavy"]) and bool(big["flag_non_government"]) and big["ownership"] == "private"
    st = allv.loc["State Univ"]
    assert bool(st["flag_heavy"]) and not bool(st["flag_non_government"]) and st["ownership_source"] == "classification file"
    assert allv.loc["AIIMS-like", "ownership"] == "unclassified" and allv.loc["Acme Pharma", "ownership"] == "private"
    assert allv.loc["Acme Pharma", "ownership_source"] == "cluster rule" and not bool(allv.loc["Acme Pharma", "flag_heavy"])
    assert t[(t.scope == "CSIR-B")].iloc[0]["cites_in"] == 100


def test_citer_evidence_indicators():
    edges = pd.DataFrame({"partner": ["U"] * 5,
                          "citing_doi": ["c1", "c1", "c2", "c3", "c4"],
                          "cited_doi": ["o1", "o2", "o1", "o1", "o1"]})
    works = {"c1": {"authors": [("A1", "Prof One"), ("A2", "X")], "journal": "J", "type": "article", "year": 2023},
             "c2": {"authors": [("A1", "Prof One")], "journal": "J", "type": "review", "year": 2023},
             "c3": {"authors": [("A1", "Prof One"), ("A9", "Zed")], "journal": "K", "type": "article", "year": 2022},
             "c4": {"authors": [("A5", "Other")], "journal": "J", "type": "article", "year": 2023}}
    ev = P.citer_evidence(edges, works, {"o1": {"A5"}, "o2": set()}, {"o1": "Our Big Paper"}, {"U": "I9"}).iloc[0]
    assert (ev["citations"], ev["citing_papers"], ev["our_papers_cited"]) == (5, 4, 2)
    assert ev["top_citing_author"] == "Prof One" and ev["top_citing_author_share"] == pytest.approx(3 / 4)
    assert ev["top_cited_paper"] == "Our Big Paper" and ev["top_cited_paper_share"] == pytest.approx(4 / 5)
    assert ev["top_citing_journal"] == "J" and ev["top_citing_journal_share"] == pytest.approx(3 / 4)
    assert ev["citations_with_shared_author"] == 1 and ev["review_share"] == pytest.approx(1 / 4)
    assert ev["partner_openalex_id"] == "I9"


def test_borderline_and_if_histogram(d):
    ov = P.overview_table(d, LABS, P2, {}).set_index("scope")
    assert ov.loc["CSIR-A", "if_borderline_papers"] == 0                      # IFs here are 12 and 4: not within 10% of 5 or 10
    near = d.assign(impact_factor=d["impact_factor"].replace({12.0: 10.5, 4.0: 4.6}))
    ov2 = P.overview_table(near, LABS, P2, {}).set_index("scope")
    assert ov2.loc["CSIR-A", "if_borderline_papers"] == 4                       # 10.5 is within 10% of 10, and 4.6 within 10% of 5
    h = P.if_histogram(d, LABS, top=20)
    a = h[h.scope == "CSIR-A"].set_index("bin_start")
    assert a.loc[12, "papers"] == 2 and a.loc[12, "q1_papers"] == 2 and a.loc[4, "papers"] == 2 and a.loc[4, "q1_papers"] == 0
    assert bool(a.loc[20, "open_ended"]) and a["papers"].sum() == 4


def test_faculty_flag_needs_a_meaningful_citation_total():
    rows = main_rows()
    extra = rows[rows["faculty_id"] == "F2"].iloc[[0]].copy()     # F2's hyperauthored paper, but give a new faculty only that
    extra["faculty_id"], extra["author"], extra["citations"], extra["openalex_id"] = "F9", "Tiny", "8", "P9"
    extra["n_authors"] = "300"
    d9 = P.prepare(pd.concat([rows, extra], ignore_index=True), impact(), LABS, P2)
    fm = pd.DataFrame({"faculty_id": ["F1", "F2", "F3", "F9"], "degree": 1, "strength": 1, "betweenness": 0.0, "community": 0,
                       "n_partner_insts": 1, "h_lifetime": 1, "designation": "x"})
    f = P.faculty_table(d9, LABS, P2, fm).set_index("faculty_id")
    assert f.loc["F9", "cit_share_hyper"] == 1.0 and not bool(f.loc["F9", "flag_hyper"]) and f.loc["F9", "flag"] == ""
    assert bool(f.loc["F2", "flag_hyper"])                                         # a large total still flags


# ---------------------------------------------------------------- size-normalised citers

P2N = SimpleNamespace(citer_norm_min_cites=30, citer_norm_min_works=300, citer_norm_z=2.0)


def norm_inputs():
    """Ten institutions that give 100 citations per 1,000 field papers, one that gives 1,000, one with too few papers."""
    rows, out = [], []
    for i in range(10):
        rows.append(("I%d" % i, "Gov %d" % i, "government", 100 + 10 * i, 5))
        out.append(("I%d" % i, 2000, 1000))                       # rate 100 .. 190 per 1,000 field papers
    rows.append(("IP", "Private Big", "private", 2000, 2))
    out.append(("IP", 4000, 1000))                                # rate 2,000: an outlier even though its size is average
    rows.append(("IS", "Private Small", "private", 500, 2))
    out.append(("IS", 150, 100))                                  # below the paper floor: not assessable
    rows.append(("IL", "Gov Large", "government", 900, 50))
    out.append(("IL", 60000, 50000))                              # large output: many citations, low rate
    rows.append(("IT", "Tiny", "private", 10, 1))
    out.append(("IT", 5000, 5000))                                # below the citation floor
    t = pd.DataFrame(rows, columns=["partner_openalex_id", "partner_inst", "ownership", "cites_in", "shared_papers"])
    t["scope"] = "ALL"
    t["flag_non_government"] = t["partner_inst"].isin(["Private Big", "Private Small"])
    return t, pd.DataFrame(out, columns=["partner_openalex_id", "works_all", "works_ls"])


def test_normalising_moves_a_large_institution_out_of_the_spotlight():
    t, out = norm_inputs()
    n = P.citer_normalised(t, out, P2N).set_index("partner_inst")
    assert n.loc["Gov Large", "rate_per_1000"] == pytest.approx(900 / 50000 * 1000)       # 18 per 1,000: big, but not unusual
    assert n.loc["Gov Large", "cites_in"] > n.loc["Gov 0", "cites_in"] * 5                # yet 9x the raw count of Gov 0
    assert not n.loc["Gov Large", "flag_norm_outlier"]
    assert n.loc["Private Big", "rate_per_1000"] == pytest.approx(2000.0)
    assert bool(n.loc["Private Big", "flag_norm_outlier"]) and bool(n.loc["Private Big", "flag_non_government_norm"])


def test_institutions_outside_the_comparison_group_get_no_rate():
    t, out = norm_inputs()
    n = P.citer_normalised(t, out, P2N).set_index("partner_inst")
    for name in ("Private Small", "Tiny"):                       # too few papers / too few citations
        assert not n.loc[name, "norm_group"] and np.isnan(n.loc[name, "rate_z"]) and not n.loc[name, "flag_norm_outlier"]
    assert int(n["norm_group"].sum()) == 12                       # ten small government + Private Big + Gov Large


def test_observed_over_expected_uses_the_pooled_rate_of_the_group():
    t, out = norm_inputs()
    n = P.citer_normalised(t, out, P2N)
    g = n[n["norm_group"]]
    pooled = g["cites_in"].sum() / g["works_ls"].sum()
    assert (g["expected_cites"] / g["works_ls"]).round(9).eq(round(pooled, 9)).all()
    assert (g["obs_exp"] * g["expected_cites"]).round(6).eq(g["cites_in"].astype(float).round(6)).all()
    gov = g[g["ownership"] == "government"]
    big = n[n["partner_inst"] == "Private Big"].iloc[0]
    assert big["rate_vs_gov"] == pytest.approx(big["rate_per_1000"] / (gov["cites_in"] / gov["works_ls"] * 1000).median())


def test_scopes_are_compared_separately_and_summary_counts_the_flagged():
    t, out = norm_inputs()
    other = t.copy(); other["scope"] = "CSIR-A"; other["cites_in"] = (other["cites_in"] / 10).round().astype(int)   # 3 or fewer: below the floor
    n = P.citer_normalised(pd.concat([t, other], ignore_index=True), out, P2N)
    assert not n[n["scope"] == "CSIR-A"]["norm_group"].any()      # only 2 institutions clear the floor there: too few to compare, so none is rated
    assert n[(n["scope"] == "ALL") & n["norm_group"]]["rate_z"].notna().all()
    s = P.norm_summary(n, P2N)
    assert s["flagged_before"] == 2 and s["flagged_assessed"] == 1 and s["flagged_still_outliers"] == 1
    assert s["flagged_not_assessed"] == ["Private Small"] and s["still_outliers"] == ["Private Big"]


# ---------------------------------------------------------------- abstracts, departments, sensitivity, quality

def fm_for(ids):
    return pd.DataFrame({"faculty_id": ids, "degree": 1, "strength": 1, "betweenness": 0.0, "community": 0,
                         "n_partner_insts": 1, "h_lifetime": 1, "designation": "x"})


def test_meeting_abstracts_stay_in_totals_but_not_in_ranked_lists():
    for title, doi, expect in [("P5108Demographic profile of patients", "https://doi.org/10.1093/x.p5108", True),
                               ("241PMultisystemic manifestations", "https://doi.org/10.1016/y", True),
                               ("AB062. DNA damage in children", "https://doi.org/10.1/z", True),
                               ("A poster", "https://doi.org/10.1099/acmi.cc2021.po0042", True),
                               ("2-aryl benzimidazole conjugates", "https://doi.org/10.1/q", False),
                               ("16S rRNA profiling of the gut", "https://doi.org/10.1/r", False)]:
        assert P.is_meeting_abstract(title, doi) is expect, title
    rows = main_rows()
    rows.loc[rows["openalex_id"] == "P1", ["title", "doi"]] = ["P5108Demographic profile", "https://doi.org/10.1093/x.p5108"]
    d9 = P.prepare(rows, impact(), LABS, P2)
    assert set(d9.loc[d9["is_abstract"], "openalex_id"]) == {"P1"}
    assert d9.drop_duplicates("openalex_id").shape[0] == 6                           # still counted as a publication
    assert "P5108Demographic profile" not in set(P.top_papers_by_if(d9, LABS, 30)["title"])
    assert "P5108Demographic profile" not in set(P.faculty_top_papers(d9, 10)["title"])


def test_department_table_counts_each_paper_once_per_department(d):
    fac = P.faculty_table(d, LABS, P2, fm_for(["F1", "F2", "F3"]))
    t = P.department_table(d, LABS, P2, fac).set_index("lab")
    a, b = t.loc["CSIR-A"], t.loc["CSIR-B"]
    assert a["faculty"] == 2 and a["papers"] == 5 and bool(a["small"])                 # P3 is shared by F1 and F2 but counts once
    assert a["q1_papers"] == 2 and a["q1_share"] == pytest.approx(2 / 4)               # the conference paper has no quartile
    assert a["q1_if_gt5"] == 2 and a["q1_if_gt10"] == 2 and a["citations"] == 642
    assert a["cit_share_hyper"] == pytest.approx(600 / 642)
    assert a["collab_inst"] == 3 and a["collab_inst_excl_hyper"] == 2                  # the consortium paper brings one extra institution
    assert a["flagged_faculty"] == 2 and b["flagged_faculty"] == 0
    assert b["papers"] == 2 and b["q1_share"] == 0.5 and b["q1_if_gt5"] == 1 and b["q1_if_gt10"] == 0


def test_if_sensitivity_changes_only_the_source_not_the_papers(d):
    imp = pd.DataFrame({"issn_n": ["11111111", "22222222", "33333333"], "impact_factor": [12.0, 4.0, 6.5],
                        "if_jcr": [12.0, np.nan, 6.5], "if_scimago": [8.0, 6.0, 4.0], "if_openalex_proxy": [15.0, 4.0, 9.0]})
    s = {r["source"].split(":")[0].split(" for")[0].split(" where")[0]: r for r in P.if_sensitivity(d, imp, P2)}
    rows = P.if_sensitivity(d, imp, P2)
    assert [(r["q1_if_gt5"], r["q1_if_gt10"]) for r in rows] == [(3, 2), (3, 2), (2, 0), (3, 2)]   # 3 Q1 journal papers in every variant
    assert all(r["journals_with_value_share"] == 1.0 for r in rows) and len(s) == 4


def test_quality_summary_counts_checks_that_should_be_zero():
    main = pd.DataFrame({"faculty_id": ["F1", "F1", "F2", "F3"], "institution": ["A", "A", "A", "B"],
                         "author_openalex_ids": ["A1;A1", "A1;A1", "A2", "A2"],             # A2 sits on two people: an identity clash
                         "affil_method": ["lineage", "raw_string", "lineage", "lineage"], "dept_source": ["website", "website", "openalex", "website"],
                         "quartile_source": ["sjr", "sjr", "none", "sjr"]})
    roster = pd.DataFrame({"faculty_id": ["F1", "F2", "F3", "F4"], "name": ["a", "b", "c", "c"], "institution": ["A", "A", "B", "B"],
                           "status": ["current", "former", "current", "current"], "orcid": ["0000", "", "", ""], "profile_dois": ["10.1/x", "", "", ""]})
    q = P.quality_summary(main, roster, pd.DataFrame({"faculty_id": ["F2"]}), ["A", "B"])
    assert q["roster"] == 4 and q["faculty_with_papers"] == 3 and q["faculty_without_papers"] == 1
    assert q["openalex_ids_shared_by_two_faculty"] == 1 and q["duplicate_roster_names"] == 1 and q["faculty_in_more_than_one_lab"] == 0
    assert q["affiliation_lineage_rows"] == 3 and q["affiliation_text_rows"] == 1 and q["manual_match_decisions"] == 1
    assert q["roster_with_orcid"] == 1 and q["roster_with_profile_dois"] == 1
    lab_b = [r for r in q["per_lab"] if r["lab"] == "B"][0]
    assert lab_b["roster"] == 2 and lab_b["with_papers"] == 1 and lab_b["without_papers"] == 1


def test_dashboard_json_has_no_nan():
    import json
    import math
    from dpcn.steps.s13_dashboard import json_safe
    out = json_safe({"a": float("nan"), "b": [1.0, math.inf, {"c": -math.inf}], "d": "x"})
    assert out == {"a": None, "b": [1.0, None, {"c": None}], "d": "x"}
    json.dumps(out, allow_nan=False)
