import networkx as nx
import numpy as np
import pandas as pd
import pytest

from dpcn.steps.s21_dynamics import assembly_params, dcsbm_dl, earliest_arrival, fe_ols


def test_assembly_params_counts_incumbents_and_repeats():
    teams = [(2016, "L", ["a", "b"]), (2017, "L", ["a", "b", "c"]), (2017, "L", ["c", "d"])]
    P = assembly_params(teams, 2017).set_index(["lab", "year"])
    r = P.loc[("ALL", 2017)]
    assert r["incumbent_share_p"] == pytest.approx(2 / 5)     # a, b incumbent; c, c, d newcomers
    assert r["repeat_share_q"] == pytest.approx(1.0)          # the only incumbent pair (a, b) wrote together in 2016


def test_earliest_arrival_respects_time_order():
    contacts = {2016: [("b", "c")], 2017: [("a", "b")]}
    one = earliest_arrival(contacts, ["a"], 2016, 2017, multi_hop=False)["a"]
    assert one == {"a": 2015, "b": 2017}                     # c is not reachable: b met c before a met b
    contacts = {2017: [("a", "b"), ("b", "c")]}
    strict = earliest_arrival(contacts, ["a"], 2017, 2017, multi_hop=False)["a"]
    assert strict == {"a": 2016, "b": 2017}                 # one hop per year: c needs a second year
    assert earliest_arrival(contacts, ["a"], 2017, 2017, multi_hop=True)["a"]["c"] == 2017


def test_dcsbm_prefers_the_planted_partition():
    G = nx.planted_partition_graph(2, 30, 0.4, 0.02, seed=1)
    true = {v: v // 30 for v in G}
    rng = np.random.default_rng(1)
    rand = {v: int(rng.integers(2)) for v in G}
    assert dcsbm_dl(G, true)["description_length"] < dcsbm_dl(G, rand)["description_length"]


def test_fe_ols_recovers_within_effect():
    rng = np.random.default_rng(0)
    n, T = 60, 6
    f = np.repeat(np.arange(n), T)
    year = np.tile(np.arange(2017, 2017 + T), n)
    alpha = rng.normal(0, 3, n)[f]
    x = rng.normal(size=n * T) + 0.5 * alpha            # x correlated with the person effect
    y = 2.0 * x + alpha + rng.normal(0, 0.5, n * T)
    P = pd.DataFrame({"faculty_id": f.astype(str), "year": year, "x": x, "y": y})
    r = fe_ols(P, "y", ["x"])[0]
    assert r["coef"] == pytest.approx(2.0, abs=0.1)
    assert r["low"] < 2.0 < r["high"]
