import pytest

from dpcn.steps.s05_normalise import (alias_regex, authorship_lab_method, classify_work, dedupe_key,
                                      faculty_links, resolve_duplicates, work_row)

TYPES = {"article", "review", "letter", "conference-paper"}
LAB = {"short": "CSIR-CCMB", "openalex_id": "I185638415", "aliases": ["ccmb", "cellular and molecular biology"]}
RX = alias_regex(LAB)
LABS = {"CSIR-CCMB": {"id": "I185638415", "rx": RX}}
FAC = {"A1": ("CCMB-001", "CSIR-CCMB"), "A2": ("CCMB-002", "CSIR-CCMB")}


def work(wtype="article", stype="journal", **kw):
    w = {"id": "https://openalex.org/W1", "type": wtype, "is_retracted": False,
         "primary_location": {"source": {"id": "https://openalex.org/S1", "type": stype, "display_name": "J"}}}
    w.update(kw)
    return w


@pytest.mark.parametrize("kw,expected", [
    (dict(), ("journal", None)),
    (dict(wtype="review"), ("journal", None)),
    (dict(wtype="conference-paper", stype="journal"), ("conference", None)),
    (dict(wtype="article", stype="conference"), ("conference", None)),
    (dict(wtype="preprint", stype="repository"), (None, "type: preprint")),
    (dict(wtype="book-chapter", stype="book series"), (None, "type: book-chapter")),
    (dict(wtype="article", stype="repository"), (None, "source: repository")),
    (dict(is_retracted=True), (None, "retracted")),
])
def test_classify_work(kw, expected):
    assert classify_work(work(**kw), TYPES) == expected


def test_classify_work_without_source():
    assert classify_work({"id": "x", "type": "article", "primary_location": None}, TYPES) == (None, "source: none")


def au(aid, insts=(), raw=()):
    return {"author": {"id": f"https://openalex.org/{aid}", "display_name": aid},
            "institutions": [{"id": f"https://openalex.org/{i}", "lineage": [f"https://openalex.org/{i}"]} for i in insts],
            "raw_affiliation_strings": list(raw)}


def test_authorship_lab_method():
    assert authorship_lab_method(au("A1", ["I185638415"]), "I185638415", RX) == "lineage"
    sub_unit = {"institutions": [{"id": "https://openalex.org/I999",
                                  "lineage": ["https://openalex.org/I999", "https://openalex.org/I185638415"]}]}
    assert authorship_lab_method(sub_unit, "I185638415", RX) == "lineage"
    assert authorship_lab_method(au("A1", ["I5"], ["CSIR-CCMB, Hyderabad"]), "I185638415", RX) == "raw_string"
    assert authorship_lab_method(au("A1", ["I5"], ["Centre for Cellular and Molecular Biology"]),
                                 "I185638415", RX) == "raw_string"
    assert authorship_lab_method(au("A1", ["I5"], ["University of Hyderabad"]), "I185638415", RX) is None
    assert authorship_lab_method(au("A1", ["I5"], ["Accra Medical Centre"]), "I185638415", RX) is None


def test_faculty_link_requires_the_faculty_members_own_affiliation():
    # A1 is affiliated; A2 wrote it before joining (other affiliation); A9 is a student, not faculty
    w = work(authorships=[au("A1", ["I185638415"]), au("A2", ["I5"], ["Stanford University"]),
                          au("A9", ["I185638415"])])
    assert faculty_links(w, FAC, LABS) == [{"faculty_id": "CCMB-001", "institution": "CSIR-CCMB",
                                            "affil_method": "lineage"}]


def test_faculty_link_prefers_lineage_and_dedupes_split_profiles():
    two_profiles = {"A1": ("CCMB-001", "CSIR-CCMB"), "A3": ("CCMB-001", "CSIR-CCMB")}
    w = work(authorships=[au("A1", ["I5"], ["CCMB"]), au("A3", ["I185638415"])])
    assert faculty_links(w, two_profiles, LABS) == [
        {"faculty_id": "CCMB-001", "institution": "CSIR-CCMB", "affil_method": "lineage"}]


def meta(wid, doi=None, title="", year=2020, cited=0, date="2020-01-01", dataset=False):
    return {"work_id": wid, "doi": doi, "title": title, "year": year, "cited": cited, "pub_date": date,
            "dataset": dataset}


def test_dedupe_key():
    assert dedupe_key(meta("W1", doi="https://doi.org/10.1/ABC")) == dedupe_key(meta("W2", doi="https://doi.org/10.1/abc"))
    long = "A long enough title about heat shock proteins in cancer"
    assert dedupe_key(meta("W1", title=long)) == dedupe_key(meta("W2", title=long.upper() + "."))
    assert dedupe_key(meta("W1", title="Editorial")) != dedupe_key(meta("W2", title="Editorial"))   # too short to trust
    assert dedupe_key(meta("W1", title=long, year=2019)) != dedupe_key(meta("W2", title=long, year=2020))


def test_resolve_duplicates_never_loses_a_linked_paper():
    m = {w["work_id"]: w for w in [
        meta("W1", doi="d:1", cited=50, dataset=False),
        meta("W2", doi="d:1", cited=5, dataset=True),     # fewer citations but the only one with a lab link
        meta("W3", doi="d:2", cited=5, date="2021-05-01", dataset=True),
        meta("W4", doi="d:2", cited=5, date="2020-02-01", dataset=True),
        meta("W5", doi="d:3")]}
    assert resolve_duplicates(m) == {"W1": "W2", "W3": "W4"}      # tie on citations: earlier date wins


def test_work_row_flattens_openalex_record():
    w = work(id="https://openalex.org/W7", doi="https://doi.org/10.1/x", title="  Spaced \n title ",
             publication_year=2021, cited_by_count=3,
             referenced_works=["https://openalex.org/W1", "https://openalex.org/W2"], authorships=[au("A1")],
             primary_topic={"id": "https://openalex.org/T1", "display_name": "Topic",
                            "subfield": {"id": "https://openalex.org/subfields/1", "display_name": "Sub"},
                            "field": {"display_name": "Fld"}, "domain": {"display_name": "Dom"}})
    w["primary_location"]["source"].update(issn_l="1234-5678", issn=["1234-5678"])
    r = work_row(w, "journal", "W7")
    assert r["title"] == "Spaced title" and r["referenced_works"] == ["W1", "W2"] and r["topic_id"] == "T1"
    assert (r["issn_l"], r["issns"], r["source_id"], r["n_authors"], r["field"]) == (
        "1234-5678", ["1234-5678"], "S1", 1, "Fld")


def test_profile_year_link_only_when_the_authorship_has_no_institution():
    from dpcn.steps.s05_normalise import profile_year_links
    years_at = {("CSIR-CCMB", "A1"): {2018, 2019}}
    bare = au("A1")                                    # no institutions at all
    assert profile_year_links(work(publication_year=2018, authorships=[bare]), FAC, years_at) == [
        {"faculty_id": "CCMB-001", "institution": "CSIR-CCMB", "affil_method": "profile_years"}]
    assert profile_year_links(work(publication_year=2022, authorships=[bare]), FAC, years_at) == []   # not there that year
    elsewhere = au("A1", ["I5"])                       # affiliated somewhere else: never linked by the weak rule
    assert profile_year_links(work(publication_year=2018, authorships=[elsewhere]), FAC, years_at) == []


def test_integrity_check_catches_bad_tables():
    import pandas as pd
    from dpcn.config import load_config
    from dpcn.steps import StepFailed
    from dpcn.steps.s05_normalise import check_integrity
    cfg = load_config()
    works = pd.DataFrame({"work_id": ["W1", "W2"], "doi": ["https://doi.org/10.1/a", None], "year": [2020, 2021],
                          "kind": ["journal", "conference"]})
    links = pd.DataFrame({"work_id": ["W1", "W2"], "faculty_id": ["F1", "F2"]})
    auths = pd.DataFrame({"work_id": ["W1", "W2"]})
    check_integrity(cfg, works, auths, links)                                            # fine
    with pytest.raises(StepFailed, match="duplicate DOIs"):
        check_integrity(cfg, works.assign(doi=["https://doi.org/10.1/A", "https://doi.org/10.1/a"]), auths, links)
    with pytest.raises(StepFailed, match="year window"):
        check_integrity(cfg, works.assign(year=[2020, 2012]), auths, links)
    with pytest.raises(StepFailed, match="no faculty link"):
        check_integrity(cfg, works, auths, links.iloc[:1])
