from types import SimpleNamespace

import networkx as nx

from dpcn.steps.s09_citation import crosses
from dpcn.steps.s10_authorship import communities, paper_people, person_key


class Reg:
    """Minimal stand-in for InstitutionRegistry: I1 is our lab CCMB, I2 an Indian partner, I9 foreign, U umbrella."""
    lab = {"I1": "CSIR-CCMB", "I3": "CSIR-IGIB"}

    def is_indian(self, i): return i in {"I1", "I2", "I3", "U"}
    def is_umbrella(self, i): return i == "U"
    def is_academy(self, i): return False
    def our_lab(self, i): return self.lab.get(i)
    def label(self, i): return self.lab.get(i, f"Inst {i}")

    def partner_ok(self, i, own_lab=None):
        return self.is_indian(i) and not self.is_umbrella(i) and self.our_lab(i) != own_lab


class Ctx:
    def __init__(self, inst, labs_of):
        self.inst, self.labs_of, self.reg = inst, labs_of, Reg()

    def partners(self, wid, lab):
        return [i for i in self.inst.get(wid, []) if self.reg.partner_ok(i, own_lab=lab)]


def test_crosses_when_the_other_paper_has_a_partner_institution():
    ctx = Ctx({"W1": ["I1"], "W2": ["I2"]}, {"W1": {"CSIR-CCMB"}})
    assert crosses(ctx, "W1", "W2")          # our paper cites an IISc-style partner work (out-flow)
    assert crosses(ctx, "W2", "W1")          # partner work cites our paper (in-flow)


def test_no_cross_for_same_lab_or_umbrella_only():
    ctx = Ctx({"W1": ["I1"], "W2": ["I1"], "W3": ["U"]}, {"W1": {"CSIR-CCMB"}})
    assert not crosses(ctx, "W1", "W2")      # a CCMB paper outside the dataset
    assert not crosses(ctx, "W1", "W3")      # only an umbrella body


def test_cross_between_two_of_our_labs():
    ctx = Ctx({"W1": ["I1"], "W2": ["I3"]}, {"W1": {"CSIR-CCMB"}, "W2": {"CSIR-IGIB"}})
    assert crosses(ctx, "W1", "W2")


def test_person_key():
    assert person_key("A1", "CCMB-001", "x", "W1", 0) == "F:CCMB-001"
    assert person_key("A1", None, "x", "W1", 0) == "A:A1"
    assert person_key(None, None, "x", "W1", 3) == "X:W1:3"


def au(pos, aid, fid=None, lab=None, insts=(), cc=(), name=None):
    return SimpleNamespace(work_id="W1", position_idx=pos, author_id=aid, faculty_id=fid, our_lab=lab,
                           inst_ids=list(insts), country_codes=list(cc), author_name=name or aid, raw_author_name=None)


def test_paper_people_merges_two_profiles_of_one_faculty_member():
    rows = [au(0, "A1", "CCMB-001", "CSIR-CCMB", ["I1"]), au(1, "A2", "CCMB-001", None, []),
            au(2, "A9", None, None, ["I9"], ["GB"]), au(3, "A5", None, None, ["I2"], ["IN"])]
    p = paper_people(rows, Reg(), {"CCMB-001": "Roster Name"})
    assert set(p) == {"F:CCMB-001", "A:A9", "A:A5"}
    assert p["F:CCMB-001"]["internal"] and p["F:CCMB-001"]["name"] == "Roster Name"
    assert p["A:A9"]["inst"] == "Inst I9" and not p["A:A9"]["indian"]
    assert p["A:A5"]["inst"] == "Inst I2" and p["A:A5"]["indian"]


def test_communities_are_deterministic_and_sorted_by_size():
    G = nx.Graph()
    G.add_edges_from([(1, 2), (2, 3), (1, 3), (4, 5)], weight=1)
    cfg = SimpleNamespace(networks=SimpleNamespace(louvain_resolution=1.0, louvain_seed=42))
    comm, q = communities(G, cfg)
    assert comm[1] == comm[2] == comm[3] == 0 and comm[4] == comm[5] == 1
    assert q > 0
