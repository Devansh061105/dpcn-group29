"""Unit tests for the Phase III helpers (s26) and the dashboard wiring."""
from pathlib import Path

import numpy as np

from dpcn.steps.s26_extras import gini_np, h_index, lotka_mle

DASH = Path(__file__).resolve().parents[1] / "src" / "dpcn" / "dashboard"


def test_h_index():
    assert h_index([10, 8, 5, 4, 3]) == 4
    assert h_index([0, 0]) == 0
    assert h_index([]) == 0
    assert h_index([100]) == 1


def test_gini_bounds():
    assert gini_np([1, 1, 1, 1]) == 0
    assert abs(gini_np([0, 0, 0, 10]) - 0.75) < 1e-9


def test_lotka_recovers_exponent():
    rng = np.random.default_rng(1)
    a, se = lotka_mle(rng.zipf(2.0, 200_000))                    # discrete power law with exponent exactly 2
    assert abs(a - 2) < 0.02 and se < 0.01


def test_every_page_has_a_renderer_and_a_section():
    html = (DASH / "template.html").read_text(encoding="utf-8")
    js = "".join((DASH / f).read_text(encoding="utf-8") for f in ("app.js", "phase2.js", "phase3.js", "dynamics.js", "chat.js"))
    for tab in ["explorer", "person", "versus", "extras", "verdicts", "structure", "epidemics", "walks", "benchmark", "science"]:
        assert f'id="tab-{tab}"' in html, tab
        assert f'"{tab}"' in js, tab
    for marker in ("/*__PHASE3__*/", "/*__DYNAMICS__*/", "/*__CHAT__*/"):
        assert marker in (DASH / "app.js").read_text(encoding="utf-8")


def test_chatbot_has_no_external_calls():
    js = (DASH / "chat.js").read_text(encoding="utf-8")
    assert "fetch(" not in js and "XMLHttpRequest" not in js and "api_key" not in js.lower()


def test_novelty_map_is_consistent():
    import csv
    rows = list(csv.DictReader(open(Path(__file__).resolve().parents[1] / "data" / "manual" / "novelty_map.csv", encoding="utf-8")))
    assert rows and all(r["ours"] in ("yes", "partial", "no") for r in rows)
    firsts = [r for r in rows if r["other_groups"] == "0"]
    assert firsts and all(r["ours"] == "yes" and r["page"] for r in firsts)
    html = (DASH / "template.html").read_text(encoding="utf-8")
    pages = {r["page"] for r in rows if r["page"]}
    missing = [p for p in pages if f'id="tab-{p}"' not in html]
    assert not missing, missing
