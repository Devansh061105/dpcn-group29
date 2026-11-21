import networkx as nx
import numpy as np
import pytest

from dpcn import netmodels as M
from dpcn.steps.s19_extensions import M_wilson, bh, cluster_cov, graph_stats, or_row, year_fe


def test_bh_matches_hand_computation():
    q = bh([0.01, 0.04, 0.03, 0.20])
    assert q == pytest.approx([0.04, 0.0533333, 0.0533333, 0.20], rel=1e-4)
    assert len(bh([])) == 0


def test_wilson_interval_contains_rate():
    lo, hi = M_wilson(10, 100)
    assert lo < 0.1 < hi and 0 < lo and hi < 1
    assert all(np.isnan(M_wilson(0, 0)))


def test_or_row_reports_symmetric_log_interval():
    r = or_row("m", "t", np.log(2), 0.1)
    assert r["odds_ratio"] == pytest.approx(2)
    assert r["or_low"] * r["or_high"] == pytest.approx(4)
    assert r["p"] < 1e-6


def test_year_fe_drops_reference_level():
    X = year_fe([2017, 2018, 2018, 2019])
    assert X.shape == (4, 2) and X[0].sum() == 0


def test_cluster_cov_inflates_with_clustered_noise():
    rng = np.random.default_rng(0)
    g = np.repeat(np.arange(40), 50)
    u = rng.normal(0, 1.5, 40)[g]
    x = rng.normal(size=len(g))
    y = (rng.random(len(g)) < 1 / (1 + np.exp(-(-1 + 0.3 * x + u)))).astype(float)
    X = np.column_stack([np.ones(len(g)), x])
    b, bread = M.logit_fit(X, y)
    V = cluster_cov(X, y, b, bread, g)
    assert V[0, 0] > bread[0, 0]


def test_graph_stats_on_two_triangles():
    G = nx.Graph([(1, 2), (2, 3), (1, 3), (4, 5), (5, 6), (4, 6), (3, 4)])
    lab = {1: "A", 2: "A", 3: "A", 4: "B", 5: "B", 6: "B"}
    s = graph_stats(G, lab)
    assert s["cross_lab_share"] == pytest.approx(1 / 7)
    assert s["lcc_share"] == 1.0
    assert s["lab_modularity"] > 0.3
