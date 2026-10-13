import pandas as pd
import pytest

from dpcn.steps import StepFailed, s02_candidates as s02

LAB = {"short": "CSIR-CCMB", "openalex_id": "I185638415"}


def author(**kw):
    base = {
        "id": "https://openalex.org/A1", "display_name": "Rakesh K Mishra",
        "display_name_alternatives": ["R. K. Mishra", "", "Rakesh Mishra"],
        "orcid": "https://orcid.org/0000-0001-2345-6789", "works_count": 120, "cited_by_count": 5000,
        "summary_stats": {"h_index": 31, "i10_index": 60},
        "affiliations": [
            {"institution": {"id": "https://openalex.org/I185638415"}, "years": [2014, 2016, 2019, 2026]},
            {"institution": {"id": "https://openalex.org/I999"}, "years": [2010, 2016]},
        ],
        "last_known_institutions": [{"id": "https://openalex.org/I185638415", "display_name": "CCMB"}],
    }
    return {**base, **kw}


def test_candidate_row_years_and_flags():
    r = s02.candidate_row(author(), LAB, 2016, 2026)
    assert r["author_id"] == "A1" and r["orcid"] == "0000-0001-2345-6789"
    assert r["years_at_lab"] == [2014, 2016, 2019, 2026]          # only years at THIS lab
    assert r["n_years_at_lab"] == 4 and r["n_years_at_lab_window"] == 3
    assert (r["first_year_at_lab"], r["last_year_at_lab"]) == (2014, 2026)
    assert r["alternatives"] == ["R. K. Mishra", "Rakesh Mishra"]   # blanks dropped
    assert r["h_index"] == 31 and r["at_lab_now"] is True and r["suspect_merged"] is False


def test_candidate_row_handles_missing_data():
    r = s02.candidate_row(author(affiliations=None, orcid=None, summary_stats=None,
                                 last_known_institutions=None, display_name_alternatives=None), LAB, 2016, 2026)
    assert r["years_at_lab"] == [] and r["first_year_at_lab"] is None
    assert r["orcid"] == "" and r["h_index"] == 0 and r["at_lab_now"] is False and r["alternatives"] == []


def test_suspect_merged_thresholds():
    many = [{"institution": {"id": f"https://openalex.org/I{i}"}, "years": [2020]} for i in range(40)]
    assert s02.candidate_row(author(affiliations=many), LAB, 2016, 2026)["suspect_merged"] is True
    assert s02.candidate_row(author(works_count=5510), LAB, 2016, 2026)["suspect_merged"] is True


class FakeOA:
    def __init__(self, results, count):
        self.results, self._count = results, count

    def count(self, path, filter):
        return self._count

    def paginate(self, path, filter, select=None, **kw):
        yield from self.results


def test_fetch_lab_checks_counts_and_duplicates():
    from dpcn.config import load_config
    cfg = load_config()
    ok = s02.fetch_lab(cfg, FakeOA([author(), author(id="https://openalex.org/A2")], 2), LAB)
    assert list(ok["author_id"]) == ["A1", "A2"]
    with pytest.raises(StepFailed, match="reports 3"):
        s02.fetch_lab(cfg, FakeOA([author(), author(id="https://openalex.org/A2")], 3), LAB)
    with pytest.raises(StepFailed, match="duplicates"):
        s02.fetch_lab(cfg, FakeOA([author(), author()], 2), LAB)


def test_summarise():
    df = pd.DataFrame([s02.candidate_row(author(), LAB, 2016, 2026),
                       s02.candidate_row(author(id="https://openalex.org/A2", orcid=None, works_count=9999), LAB, 2016, 2026)])
    s = s02.summarise(df).loc["CSIR-CCMB"]
    assert (s["authors"], s["with_orcid"], s["suspect_merged"], s["at_lab_now"]) == (2, 1, 1, 2)
