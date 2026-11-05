import numpy as np
import pandas as pd
import pytest

from dpcn.config import load_config
from dpcn.steps import StepFailed, s16_phase2 as S


class FakeOA:
    """Stands in for the OpenAlex client: serves journal sources by ISSN and records the filters it was asked for."""
    def __init__(self, sources):
        self.sources, self.filters = sources, []

    def paginate(self, path, flt, select=None, per_page=200, **kw):
        assert path == "sources"
        self.filters.append(flt)
        wanted = set(flt.removeprefix("issn:").split("|"))
        for s in self.sources:
            if wanted & set(s["issn"]):
                yield s


def src(sid, name, issns, citedness):
    return {"id": f"https://openalex.org/{sid}", "display_name": name, "issn": issns, "summary_stats": {"2yr_mean_citedness": citedness}}


def main():
    def r(issn, name, typ="journal"):
        return {"type": typ, "issn": issn, "journal_name": name}
    return pd.DataFrame([r("1111-1111", "Alpha Journal"), r("2222-2222", "Beta Journal"), r("1111-1111", "Alpha Journal"),
                         r("", "A Conference", "conference"), r("3333-3333", "Gamma Letters")])


@pytest.fixture
def cfg(tmp_path):
    c = load_config()
    c.root = tmp_path
    return c


def test_proxy_used_when_no_jcr_file(cfg):
    oa = FakeOA([src("S1", "Alpha", ["1111-1111", "1111-111X"], 7.25), src("S2", "Beta", ["2222-2222"], 2.0)])
    j = S.journal_impact(cfg, oa, main()).set_index("issn")
    assert len(j) == 3 and "" not in j.index                                   # one row per ISSN; conferences have none
    assert j.loc["1111-1111", "impact_factor"] == 7.25 and j.loc["1111-1111", "if_source"] == S.PROXY
    assert np.isnan(j.loc["3333-3333", "impact_factor"]) and j.loc["3333-3333", "if_source"] == ""   # unknown to OpenAlex
    assert len(oa.filters) == 1 and set(oa.filters[0].removeprefix("issn:").split("|")) == {"1111-1111", "2222-2222", "3333-3333"}


def test_matches_through_the_other_issn_of_the_journal(cfg):
    oa = FakeOA([src("S1", "Alpha", ["1111-1111", "9999-9999"], 3.0)])
    j = S.journal_impact(cfg, oa, pd.DataFrame([{"type": "journal", "issn": "9999-9999", "journal_name": "Alpha"}]))
    assert j.iloc[0]["impact_factor"] == 3.0                                     # the journal is found through the ISSN we hold


def write_jcr(cfg, text):
    d = cfg.root / "data/manual/jcr"
    d.mkdir(parents=True)
    (d / "jcr_impact_factors.csv").write_text(text, encoding="utf-8")


def test_jcr_overrides_the_proxy_and_is_labelled(cfg):
    write_jcr(cfg, "Journal,ISSN,eISSN,Journal Impact Factor,JCR Year\n"
                   "Alpha Journal,1111-1111,,12.5,2024\n"
                   "Beta Journal,,,5.5,2024\n")                                  # matched by title when there is no ISSN
    oa = FakeOA([src("S1", "Alpha", ["1111-1111"], 7.25), src("S2", "Beta", ["2222-2222"], 2.0), src("S3", "Gamma", ["3333-3333"], 4.0)])
    j = S.journal_impact(cfg, oa, main()).set_index("issn")
    assert j.loc["1111-1111", "impact_factor"] == 12.5 and j.loc["1111-1111", "if_source"] == "JCR 2024"
    assert j.loc["1111-1111", "if_openalex_proxy"] == 7.25                       # the proxy is kept alongside for comparison
    assert j.loc["2222-2222", "impact_factor"] == 5.5 and j.loc["2222-2222", "if_source"] == "JCR 2024"
    assert j.loc["3333-3333", "impact_factor"] == 4.0 and j.loc["3333-3333", "if_source"] == S.PROXY   # not in JCR: falls back


def test_jcr_file_needs_an_impact_factor_column(cfg):
    write_jcr(cfg, "Journal,ISSN\nAlpha,1111-1111\n")
    with pytest.raises(StepFailed, match="impact_factor"):
        S.read_jcr(cfg.root / cfg.phase2.jcr_file)
    assert S.read_jcr(cfg.root / "missing.csv").empty                            # no file: not an error, just no JCR values


def test_ownership_file_is_read_by_id(cfg):
    (cfg.root / "data/manual").mkdir(parents=True)
    (cfg.root / cfg.phase2.ownership_file).write_text(
        "openalex_id,partner_inst,ownership,basis,verified\nI1,Some Univ,private,trust,no\nI2,Other,government,central,no\n", encoding="utf-8")
    own = S.load_ownership(cfg)
    assert own["I1"]["ownership"] == "private" and own["I2"]["verified"] == "no"
    cfg.root = cfg.root / "nowhere"
    assert S.load_ownership(cfg) == {}


def write_scimago(cfg, year, rows):
    d = cfg.root / cfg.phase2.scimago_dir
    d.mkdir(parents=True, exist_ok=True)
    head = "Rank;Sourceid;Title;Type;Issn;SJR;SJR Best Quartile;Citations / Doc. (2years)\n"
    (d / f"scimagojr_{year}.csv").write_text(head + "".join(f'1;1;"{t}";journal;"{i}";1,0;Q1;{v}\n' for t, i, v in rows), encoding="utf-8")


def test_scimago_sits_between_jcr_and_the_proxy(cfg):
    write_scimago(cfg, 2024, [("Old", "11111111", "1,0")])
    write_scimago(cfg, 2025, [("Alpha", "11111111, 1111111X", "9,50"), ("Beta", "22222222", "6,25")])   # newest year wins; decimal comma
    write_jcr(cfg, "Journal,ISSN,Journal Impact Factor,JCR Year\nBeta Journal,2222-2222,5.5,2024\n")
    oa = FakeOA([src("S1", "Alpha", ["1111-1111"], 7.25), src("S2", "Beta", ["2222-2222"], 2.0), src("S3", "Gamma", ["3333-3333"], 4.0)])
    j = S.journal_impact(cfg, oa, main()).set_index("issn")
    assert j.loc["1111-1111", "impact_factor"] == 9.5 and j.loc["1111-1111", "if_source"] == "Scimago Cites/Doc (2y) 2025"
    assert j.loc["2222-2222", "impact_factor"] == 5.5 and j.loc["2222-2222", "if_source"] == "JCR 2024"      # JCR beats Scimago
    assert j.loc["3333-3333", "impact_factor"] == 4.0 and j.loc["3333-3333", "if_source"] == S.PROXY          # not in Scimago: proxy
    assert j.loc["1111-1111", "if_openalex_proxy"] == 7.25                                                    # proxy kept for comparison
