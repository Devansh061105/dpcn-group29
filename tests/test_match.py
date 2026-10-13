import pytest

from dpcn.names import initials_compatible, name_score, name_tokens, weak_name_match
from dpcn.steps.s03_match import Cand, decide


def cand(aid, name, lab_works=10, **kw):
    return Cand(aid, name, n_lab_works=lab_works, years_at_lab_window=kw.pop("years", 5), **kw)


@pytest.mark.parametrize("a,b,expected", [
    ("R. K. Mishra", "Rakesh Kumar Mishra", True),
    ("A S Sreedhar", "Amere Subbarao Sreedhar", True),
    ("A S Sreedhar", "Sreedhar Amere Subbarao", True),      # surname first
    ("A S Sreedhar", "Sreedhar AS", True),                  # run-together initials
    ("Vinay K Nandicoori", "Vinay Kumar Nandicoori", True),
    ("Vinay Nandicoori", "Vinay Nandicori", True),          # one-letter typo in a long name
    ("Pankaj Gupta", "Pawan Gupta", False),
    ("Sandeep Kumar", "Sanjay Kumar", False),
    ("Anil Kumar", "Anil Sharma", False),                   # different surnames
    ("Sachin Kumar", "Sanjay Kumar", False),
    ("Prem P Yadav", "Pooja Yadav", False),                 # a full name must not match a middle initial
    ("Chandra B Tripathi", "Chakrapani Tripathi", False),
    ("Venkat R Chalamcharla", "Venkata R. Chalamcharla", True),
    ("Mohammad I Siddiqi", "Mohammad Imran Siddiqui", True),
    ("Arunava Dasgupta", "Arunava Das Gupta", True),
    ("Damodara Reddy N", "Damodara N. Reddy", True),        # trailing initial
    ("Ranvir Singh", "Singh Rajender", False),
    ("Pradeep Kumar", "Pradeep Kumar Tiwari", False),       # 'Pradeep' must not become the family name
    ("Mohammad I Siddiqi", "Mohmmad Imran", False),
    ("Mohammad I Siddiqi", "Siddiqi Mohammad Imran", True), # genuine surname-first
    ("Chalamcharla VR", "Chalamcharla Venkata R", True),
    ("Souvik Maiti", "Sudipta Maiti", False),
    ("J Venkatesh Pratap", "Venkatesh Pratap Jonnala", False),
    ("Pawan Gupta", "P Gupta", True),
])
def test_initials_compatible(a, b, expected):
    assert initials_compatible(a, b) is expected


def test_name_tokens_and_weak_match():
    assert name_tokens("Sreedhar AS") == ["sreedhar", "a", "s"]
    assert name_tokens("RAKESH KUMAR MISHRA") == ["rakesh", "kumar", "mishra"]   # all caps: not split
    assert name_tokens("Patrick, Thévenon") == ["patrick", "thevenon"]
    assert weak_name_match("Pawan Gupta", "P Gupta") is True
    assert weak_name_match("Pawan Gupta", "Pawan K Gupta") is False
    assert weak_name_match("A S Sreedhar", "Sreedhar") is False    # roster itself only has one full word
    assert name_score("Pawan Gupta", ["Pawan Gupta"]) == 100
    assert name_score("Pawan Gupta", ["Ravi Mishra"]) < 50


def test_unambiguous_name_match_is_auto_accepted_including_split_profiles():
    d = decide("Vinay K Nandicoori", [cand("A1", "Vinay Kumar Nandicoori"), cand("A2", "Nandicoori Vinay K", 3)])
    assert set(d.accepted) == {"A1", "A2"} and {v["method"] for v in d.accepted.values()} == {"auto"}
    assert d.review == []


def test_two_different_people_with_the_same_name_go_to_review():
    d = decide("Pawan Gupta", [cand("A1", "Pawan Gupta"), cand("A2", "Pankaj Gupta")])
    assert set(d.accepted) == {"A1"} and d.review == []    # Pankaj is a different person: neither accepted nor offered
    d = decide("Anil Singh", [cand("A1", "Anil Kumar Singh"), cand("A2", "Anil Pratap Singh")])
    assert d.accepted == {}
    assert {x["cand"].author_id for x in d.review} == {"A1", "A2"}
    assert all("ambiguous" in x["reason"] for x in d.review)


def test_weak_merged_and_unaffiliated_candidates_are_not_auto_accepted():
    d = decide("Pawan Gupta", [cand("A1", "P Gupta")])
    assert d.accepted == {} and "initials-only" in d.review[0]["reason"]
    d = decide("Pawan Gupta", [cand("A1", "Pawan Gupta", suspect_merged=True)])
    assert d.accepted == {} and "merged" in d.review[0]["reason"]
    d = decide("Pawan Gupta", [cand("A1", "Pawan Gupta", lab_works=0)])
    assert d.accepted == {} and "no lab-affiliated" in d.review[0]["reason"]
    d = decide("Pawan Gupta", [cand("A1", "Pawan Gupta", lab_works=0, years=0)])   # no tie to the lab at all
    assert d.accepted == {} and d.review == []


def test_orcid_and_doi_evidence_accept_without_name_certainty():
    d = decide("Mary K Ekka", [cand("A1", "Mary Krishna Ekka", suspect_merged=True)], orcid_ids=["A1"])
    assert d.accepted["A1"]["method"] == "orcid"          # decisive even for a flagged profile
    d = decide("Pawan Gupta", [cand("A1", "Pawan Gupta", 1), cand("A2", "P Gupta", 0, years=0)], doi_ids={"A2": 2})
    assert d.accepted["A2"]["method"] == "doi"            # the profile with no lab affiliation, found via a listed paper
    assert d.accepted["A1"]["method"] == "auto"           # a compatible split profile may join the evidence-based ID


def test_candidate_clashing_with_evidence_profile_is_held_back():
    d = decide("Anil Singh", [cand("A1", "Anil Kumar Singh"), cand("A2", "Anil Pratap Singh")], doi_ids={"A1": 1})
    assert set(d.accepted) == {"A1"}
    assert d.review and d.review[0]["cand"].author_id == "A2" and "clashes" in d.review[0]["reason"]


def test_review_list_is_capped_and_ordered_by_score():
    cands = [cand(f"A{i}", f"Anil Kumar{'x' * i} Singh", 2) for i in range(8)]
    d = decide("Anil K Singh", cands, max_review=3)
    assert len(d.review) <= 3
    scores = [x["score"] for x in d.review]
    assert scores == sorted(scores, reverse=True)


def test_dominant_profile_beats_namesakes_but_close_calls_go_to_review():
    d = decide("Anil Singh", [cand("A1", "Anil Kumar Singh", 73), cand("A2", "Anil Pratap Singh", 2)])
    assert set(d.accepted) == {"A1"} and "dominant" in d.accepted["A1"]["evidence"]
    assert d.accepted["A1"]["method"] == "auto"
    # the namesake stays visible to the reviewer, clearly labelled
    assert [(x["cand"].author_id, x["reason"]) for x in d.review] ==         [("A2", "minor same-name profile (a dominant one was accepted)")]
    # two plausible people with comparable output: a human must decide
    d = decide("Anil Singh", [cand("A1", "Anil Kumar Singh", 37), cand("A2", "Anil Pratap Singh", 20)])
    assert d.accepted == {} and all("ambiguous" in x["reason"] for x in d.review)
    # a big lead is not enough when the leader itself has little evidence
    d = decide("Anil Singh", [cand("A1", "Anil Kumar Singh", 8), cand("A2", "Anil Pratap Singh", 1)])
    assert d.accepted == {}


def test_alternate_name_alone_never_auto_accepts():
    merged = Cand("A1", "Sanjay Kumar", alternatives=["Sachin Kumar"], n_lab_works=12, years_at_lab_window=5)
    d = decide("Sachin Kumar", [merged])
    assert d.accepted == {} and d.review[0]["reason"] == "matches only an alternate name"


def test_orcid_from_web_page_must_agree_with_the_name():
    d = decide("Jitendra Narayan", [cand("A1", "Arpan Parichha")], orcid_ids=["A1"])
    assert d.accepted == {} and "ORCID" in d.review[0]["reason"]
    d = decide("Malabika Dutta", [cand("A2", "Malabika Datta", 20)], orcid_ids=["A2"])   # spelling variant: fine
    assert d.accepted["A2"]["method"] == "orcid"
