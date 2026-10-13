import pandas as pd
import pytest
from bs4 import BeautifulSoup

from dpcn.config import load_config
from dpcn.names import clean_name, norm
from dpcn.steps import StepFailed, s01_roster as s01


def test_clean_name():
    assert clean_name("Dr. Pawan Gupta") == ("Pawan Gupta", "")
    assert clean_name("Dr.Neeraj Khatri") == ("Neeraj Khatri", "")
    assert clean_name("Dr. Manoj Kumar (On-lien)") == ("Manoj Kumar", "On-lien")
    assert clean_name("Dr. (Ms.) Vineeta Tripathi ") == ("Vineeta Tripathi", "")
    assert clean_name("Dr. Mohd.S Akhtar") == ("Mohd. S Akhtar", "")
    assert clean_name("Prof. Dr. A K Singh") == ("A K Singh", "")
    assert clean_name("A S Sreedhar") == ("A S Sreedhar", "")


def test_norm():
    assert norm("Dr. R.K. Mishra") == "r k mishra"
    assert norm("Mohd. S Akhtar") == norm("Mohd S. Akhtar")
    assert norm("José Núñez-Gómez") == "jose nunez gomez"


@pytest.mark.parametrize("desig,expected", [
    ("Scientist-G", "TRUE"), ("Scientist F & Head", "TRUE"), ("Director", "TRUE"),
    ("CSIR Bhatnagar Fellow", "TRUE"), ("Emeritus Scientist", "TRUE"),
    ("AcSIR Distinguished Emeritus Professor", "TRUE"),
    ("Private Secretary", "FALSE"), ("Senior Technical Officer", "FALSE"),
    ("Technical Officer", "FALSE"), ("", "REVIEW"), ("Consultant", "REVIEW"),
])
def test_keep_flag(desig, expected):
    assert s01.keep_flag(desig) == expected


def test_extractors():
    text = ("see https://doi.org/10.1016/j.mito.2020.08.001. and doi:10.1002/jcb.29493; "
            "https://orcid.org/0000-0003-0403-0293 pubmed.ncbi.nlm.nih.gov/36180001/ pubmed.ncbi.nlm.nih.gov/9/")
    assert s01._dois(text) == "10.1002/jcb.29493;10.1016/j.mito.2020.08.001"
    assert s01._dois("10.1038/s41598-020-60751-7.â and 10.1021/acs.jpcb.1c02499.s001") ==         "10.1021/acs.jpcb.1c02499;10.1038/s41598-020-60751-7"
    assert s01._orcid(text) == "0000-0003-0403-0293"
    assert s01._orcid("nothing") == ""
    assert s01._pmids(text) == "9;36180001"


def _role(html):
    return BeautifulSoup(html, "html.parser").select_one("p.profile-role")


def test_parse_igib_role_normal_and_director():
    normal = _role('<p class="profile-role"> Scientist-E &nbsp;<span class="sep">|</span>&nbsp; '
                   '<a href="../du-1.html"> Decision Unit 1: Genomics and Genome Biology </a><br> Professor '
                   '<span class="sep">|</span> <a href="https://acsir.res.in">AcSIR</a></p>')
    assert s01.parse_igib_role(normal) == ("Scientist-E", "Decision Unit 1: Genomics and Genome Biology")
    director = _role('<p class="profile-role"><h3>Director</h3><span class="sep"></span>Scientist-G &nbsp;'
                     '<span class="sep">|</span> <a href="../du-3.html"> Decision Unit 3: Chemical Biology </a>'
                     '<br> Professor</p>')
    assert s01.parse_igib_role(director) == ("Director; Scientist-G", "Decision Unit 3: Chemical Biology")
    assert s01.parse_igib_role(None) == ("", "")


def test_scientist_list_blank_designation_is_kept():
    lab = {"short": "CSIR-IGIB"}
    assert s01._row(lab, "Dr. X Y", True)["keep"] == "TRUE"
    assert s01._row(lab, "Dr. X Y")["keep"] == "REVIEW"


def test_dedupe_joins_departments():
    a = {"name": "A B", "department": "Chem"}
    b = {"name": "Dr. A  B", "department": "Bio"}
    c = {"name": "C D", "department": ""}
    out = s01._dedupe([a, {**b, "name": "A B"}, c])
    assert len(out) == 2 and out[0]["department"] == "Chem; Bio"


@pytest.fixture
def cfg(tmp_path):
    c = load_config()
    c.paths.manual = tmp_path / "manual"
    c.paths.review = tmp_path / "review"
    c.paths.review.mkdir(parents=True)
    return c


def _scraped(cfg, key, short, people):
    rows = [{**{c: "" for c in s01.SCRAPED_COLS}, "institution": short, "keep": "TRUE", **p} for p in people]
    pd.DataFrame(rows, columns=s01.SCRAPED_COLS).to_csv(cfg.paths.review / f"roster_{key}_scraped.csv", index=False)


def test_merge_is_additive_and_never_overwrites(cfg):
    _scraped(cfg, "ccmb", "CSIR-CCMB", [{"name": "A B", "designation": "Scientist-E", "department": "Genomics", "profile_url": "http://x/1"},
                                        {"name": "C D", "designation": "Scientist-F"}])
    s01.merge(cfg)
    roster = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False)
    assert roster["faculty_id"].tolist() == ["CCMB-001", "CCMB-002"]

    # a human edits the roster, then the site data changes and we merge again
    roster.loc[0, "name"] = "A. B. Corrected"
    roster.loc[0, "department"] = "Hand edited"
    roster.loc[len(roster)] = {**{c: "" for c in s01.ROSTER_COLS}, "faculty_id": "CCMB-050", "name": "Former Person",
                               "institution": "CSIR-CCMB", "status": "former", "source": "annual report"}
    roster.to_csv(cfg.paths.manual / "faculty_roster.csv", index=False)
    _scraped(cfg, "ccmb", "CSIR-CCMB", [{"name": "A B", "designation": "Scientist-G", "department": "Different", "profile_url": "http://x/1"},
                                        {"name": "C D", "designation": "Scientist-F"},
                                        {"name": "E F", "designation": "Scientist-D"}])
    s01.merge(cfg)
    out = pd.read_csv(cfg.paths.manual / "faculty_roster.csv", dtype=str, keep_default_na=False).set_index("faculty_id")
    assert out.loc["CCMB-001", "department"] == "Hand edited"          # not overwritten
    assert out.loc["CCMB-001", "name"] == "A. B. Corrected"          # re-matched by profile_url despite the new name
    assert out.loc["CCMB-001", "designation"] == "Scientist-E"       # existing value kept, not replaced by "Scientist-G"
    assert out.loc["CCMB-050", "status"] == "former"                    # kept
    assert out.loc["CCMB-051", "name"] == "E F"                         # new id continues after the max
    assert len(out) == 4


def test_validate_catches_problems(cfg):
    path = cfg.paths.manual / "faculty_roster.csv"
    path.parent.mkdir(parents=True)
    good = [{**{c: "" for c in s01.ROSTER_COLS}, "faculty_id": f"{p}-001", "name": f"Person {p}",
             "institution": lab, "status": "current"}
            for p, lab in [("CCMB", "CSIR-CCMB"), ("IGIB", "CSIR-IGIB"), ("IMTECH", "CSIR-IMTECH"), ("CDRI", "CSIR-CDRI")]]
    pd.DataFrame(good).to_csv(path, index=False)
    assert len(s01.validate(cfg)) == 4

    bad = pd.DataFrame(good + [{**good[0], "faculty_id": "CCMB-002", "name": "Dr. Person CCMB"}])   # same person twice
    bad.to_csv(path, index=False)
    with pytest.raises(StepFailed, match="same person twice"):
        s01.validate(cfg)
    pd.DataFrame(good[:3]).to_csv(path, index=False)
    with pytest.raises(StepFailed, match="labs with no faculty"):
        s01.validate(cfg)


def _uncovered(cfg, rows):
    cols = ["lab", "author_id", "name", "uncovered_papers", "last_or_corresponding", "first_author", "first_year",
            "last_year", "orcid", "works_count", "at_lab_now", "suspect_merged", "add", "status", "note"]
    df = pd.DataFrame([{**{c: "" for c in cols}, **r} for r in rows], columns=cols)
    df.to_csv(cfg.paths.review / "uncovered_lab_authors.csv", index=False)


def test_add_uncovered_adds_roster_rows_and_preaccepts_the_author(cfg):
    path = cfg.paths.manual / "faculty_roster.csv"
    path.parent.mkdir(parents=True)
    pd.DataFrame([{**{c: "" for c in s01.ROSTER_COLS}, "faculty_id": "IGIB-001", "name": "Ann Lee",
                   "institution": "CSIR-IGIB", "status": "current"}]).to_csv(path, index=False)
    _uncovered(cfg, [
        {"lab": "CSIR-IGIB", "author_id": "A10", "name": "Vinod  Scaria", "add": "TRUE", "status": "Current"},
        {"lab": "CSIR-IGIB", "author_id": "A11", "name": "Not Chosen", "add": "", "status": ""},
        {"lab": "CSIR-IGIB", "author_id": "A12", "name": "Ann Lee", "add": "TRUE", "status": "current"},   # already there
        {"lab": "CSIR-IMTECH", "author_id": "A13", "name": "G P S Raghava", "add": "yes", "status": "former",
         "orcid": "0000-0001-0000-0000"}])
    s01.add_uncovered(cfg)
    roster = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("faculty_id")
    assert roster.loc["IGIB-002", "name"] == "Vinod Scaria" and roster.loc["IGIB-002", "status"] == "current"
    assert roster.loc["IMTECH-001", "status"] == "former" and roster.loc["IMTECH-001", "orcid"] == "0000-0001-0000-0000"
    assert "Not Chosen" not in set(roster["name"]) and (roster["name"] == "Ann Lee").sum() == 1
    ov = pd.read_csv(cfg.paths.manual / "faculty_match_overrides.csv", dtype=str)
    assert sorted(zip(ov.faculty_id, ov.author_id, ov.decision)) == [
        ("IGIB-002", "A10", "accept"), ("IMTECH-001", "A13", "accept")]
    s01.add_uncovered(cfg)                                   # idempotent
    assert len(pd.read_csv(path)) == 3 and len(pd.read_csv(cfg.paths.manual / "faculty_match_overrides.csv")) == 2


def test_add_uncovered_requires_a_status(cfg):
    (cfg.paths.manual).mkdir(parents=True)
    pd.DataFrame(columns=s01.ROSTER_COLS).to_csv(cfg.paths.manual / "faculty_roster.csv", index=False)
    _uncovered(cfg, [{"lab": "CSIR-IGIB", "author_id": "A10", "name": "Vinod Scaria", "add": "TRUE", "status": ""}])
    with pytest.raises(StepFailed, match="status"):
        s01.add_uncovered(cfg)
