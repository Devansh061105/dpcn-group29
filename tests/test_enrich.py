from dpcn.steps.s06_enrich import core_rank, issn_norm, sjr_quartile
from dpcn.steps.s08_main_csv import clean_title
from dpcn.steps.s12_stats import cagr, h_index, has_foreign

SJR = {
    2018: {"issn": {"12345678": "Q2"}, "title": {"journal of tests": "Q3"}},
    2020: {"issn": {"12345678": "Q1", "0000000X": "Q4"}, "title": {}},
}


def test_issn_norm_handles_dashes_case_and_missing():
    assert issn_norm("1234-567x") == "1234567X"
    assert issn_norm(None) == ""
    assert issn_norm(float("nan")) == ""


def test_quartile_uses_the_publication_year():
    assert sjr_quartile(SJR, 2018, ["1234-5678"], "") == ("Q2", 2018)
    assert sjr_quartile(SJR, 2020, ["1234-5678"], "") == ("Q1", 2020)


def test_quartile_years_after_latest_sjr_use_the_latest():
    assert sjr_quartile(SJR, 2026, ["12345678"], "") == ("Q1", 2020)


def test_quartile_falls_back_to_neighbouring_year_then_title():
    assert sjr_quartile(SJR, 2019, ["12345678"], "") == ("Q2", 2018)      # 2019 missing -> 2018
    assert sjr_quartile(SJR, 2018, ["99999999"], "Journal of Tests") == ("Q3", 2018)


def test_quartile_unknown_is_na():
    assert sjr_quartile(SJR, 2020, ["99999999"], "Nowhere") == ("NA", None)
    assert sjr_quartile({}, 2020, ["12345678"], "") == ("NA", None)


CORE = [{"title": "international conference on machine learning", "acronym": "ICML", "rank": "A*"},
        {"title": "bioinformatics and biomedicine", "acronym": "BIBM", "rank": "B"}]


def test_core_rank_by_acronym_or_title():
    assert core_rank(CORE, "Proceedings of ICML 2021") == "A*"
    assert core_rank(CORE, "IEEE International Conference on Bioinformatics and Biomedicine") == "B"
    assert core_rank(CORE, "Indian Science Congress") == "NA"
    assert core_rank([], "ICML") == "NA"


def test_clean_title_drops_markup_and_spaces():
    assert clean_title("The <i>E. coli</i>  protein\nH<sub>2</sub>O") == "The E. coli protein H2O"


def test_h_index():
    assert h_index([]) == 0
    assert h_index([10, 8, 5, 4, 3]) == 4
    assert h_index([1, 1, 1]) == 1


def test_cagr():
    assert round(cagr(100, 200, 9), 4) == round(2 ** (1 / 9) - 1, 4)
    assert cagr(0, 10, 9) is None


def test_has_foreign():
    assert has_foreign("CSIR-IGIB; University of Oxford (GB)")
    assert not has_foreign("IIT Delhi (IN); CSIR-IGIB")
    assert not has_foreign("")
