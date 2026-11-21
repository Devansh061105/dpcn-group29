import networkx as nx
import numpy as np
import pytest

from dpcn import netmodels as M
from dpcn.steps.s18_netmodels import seniority_rank


def test_power_law_recovers_alpha():
    rng = np.random.default_rng(1)
    x = M._sample_power_law(5000, 5, 2.5, rng)
    fit = M.fit_power_law(x)
    assert abs(fit["alpha"] - 2.5) < 0.15
    assert fit["xmin"] <= 10


def test_power_law_beats_exponential_on_power_law_data():
    rng = np.random.default_rng(2)
    x = M._sample_power_law(3000, 3, 2.2, rng)
    fit = M.fit_power_law(x)
    res = {r["alternative"]: r for r in M.compare_tails(x, fit)}
    assert res["exponential"]["llr"] > 0 and res["exponential"]["p"] < 0.05


def test_exponential_data_is_not_power_law():
    rng = np.random.default_rng(3)
    x = np.floor(rng.exponential(10, 3000)) + 1
    fit = M.fit_power_law(x)
    res = {r["alternative"]: r for r in M.compare_tails(x, fit)}
    assert res["exponential"]["llr"] < 0


def test_auc_and_average_precision():
    y = np.array([1, 0, 1, 0, 0], bool)
    assert M.auc(np.array([5, 1, 4, 2, 3]), y) == 1.0
    assert M.auc(np.array([1, 5, 2, 4, 3]), y) == 0.0
    assert M.auc(np.ones(5), y) == 0.5
    assert M.average_precision(np.array([5, 1, 4, 2, 3]), y) == 1.0


def test_pair_features_on_a_square_with_diagonal():
    G = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    f = M.pair_features(G, [(1, 3)])
    assert f["common_neighbours"][0] == 2     # 1-0-3 and 1-2-3
    assert f["preferential_attachment"][0] == 4
    assert f["jaccard"][0] == pytest.approx(1.0)
    assert f["adamic_adar"][0] == pytest.approx(2 / np.log(3))


def test_small_world_on_ring_lattice_rewired():
    G = nx.connected_watts_strogatz_graph(400, 8, 0.05, seed=1)
    sw = M.small_world(G, n_null=3, seed=1)
    assert sw["clustering"] > 5 * sw["er_clustering"]
    assert sw["sigma_er"] > 3


def test_attack_hits_star_hub_first():
    G = nx.star_graph(10)
    lab = {v: "A" if v % 2 else "B" for v in G}
    curve = M.attack(G, lab, "degree")
    assert curve[1][1] == pytest.approx(1 / 11)       # hub gone: only isolates remain
    assert curve[0][2] == 1 and curve[1][2] == 0


def test_lab_edge_cut_counts_bridges():
    G = nx.Graph([("a1", "a2"), ("b1", "b2"), ("a1", "b1"), ("a2", "b2")])
    lab = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
    cut = M.lab_edge_cuts(G, lab)[0]
    assert cut["min_edge_cut"] == 2 and cut["direct_links"] == 2


def test_sis_dies_below_and_lives_above_threshold():
    G = nx.random_regular_graph(6, 200, seed=1)
    A = nx.to_numpy_array(G)
    th = M.sis_theory(A)
    assert th["threshold_qmf"] == pytest.approx(1 / 6, rel=1e-6)
    low, _ = M.sis_prevalence(A, beta=0.3 * th["threshold_qmf"] * 0.2, mu=0.2, reps=3)
    high, _ = M.sis_prevalence(A, beta=3 * th["threshold_qmf"] * 0.2, mu=0.2, reps=3)
    assert low < 0.01 < high


def test_si_reaches_whole_component():
    W = nx.to_numpy_array(nx.path_graph(6))
    r = M.si_runs(W, np.array([0, 0, 0, 1, 1, 1]), beta=1.0, seeds=[0])[0]
    assert r["t_all_labs"] == 3 and r["t90"] == 5


def test_dyadic_robust_cov_is_larger_with_shared_nodes():
    rng = np.random.default_rng(0)
    n_nodes, n = 30, 3000
    a, b = rng.integers(0, n_nodes, n), rng.integers(0, n_nodes, n)
    node_effect = rng.normal(0, 1.5, n_nodes)
    x = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(-2 + 0.5 * x + node_effect[a] + node_effect[b])))).astype(float)
    X = np.column_stack([np.ones(n), x])
    beta, bread = M.logit_fit(X, y)
    V = M.dyadic_robust_cov(X, y, beta, bread, a, b)
    assert np.sqrt(V[0, 0]) > np.sqrt(bread[0, 0])


@pytest.mark.parametrize("d,r", [("Scientist G", 5), ("Scientist-G & Head", 5), ("Chief Scientist", 5),
                                 ("Senior Principal Scientist", 4), ("Scientist F", 4), ("Principal Scientist", 3),
                                 ("Scientist E", 3), ("Senior Scientist", 2), ("Scientist D", 2),
                                 ("CSIR Bhatnagar Fellow", 6), ("J C Bose Fellow", 6), ("Scientist", 1), ("", None)])
def test_seniority_rank(d, r):
    v = seniority_rank(d)
    assert (np.isnan(v) if r is None else v == r)
