import pytest

from dpcn.config import load_config
from dpcn.institutions import InstitutionRegistry


def inst(iid, name, cc="IN", typ="education", lineage=None):
    return {"id": f"https://openalex.org/{iid}", "display_name": name, "country_code": cc, "type": typ,
            "ror": f"https://ror.org/{iid.lower()}", "lineage": [f"https://openalex.org/{x}" for x in (lineage or [iid])]}


CSIR = "I66760702"


@pytest.fixture
def reg():
    r = InstitutionRegistry(load_config(), overrides={})
    for i in [
        inst("I1", "Indian Institute of Technology Delhi"),
        inst("I2", "Indian Institute of Science Education and Research Pune"),
        inst("I3", "Indian Institute of Science"),
        inst("I4", "Bhabha Atomic Research Centre", typ="facility", lineage=["I4", "I3149292468"]),
        inst("I5", "All India Institute of Medical Sciences, New Delhi"),
        inst("I6", "CSIR-Indian Institute of Chemical Technology", typ="facility", lineage=["I6", CSIR]),
        inst("I7", "Central Drug Research Institute", typ="facility", lineage=["I7", CSIR]),
        inst("I185249246", "Central Drug Research Institute", typ="facility", lineage=["I185249246", CSIR]),
        inst("I8", "Academy of Scientific and Innovative Research"),
        inst("I99364266", "Academy of Scientific and Innovative Research"),
        inst(CSIR, "Council of Scientific and Industrial Research", typ="government"),
        inst("I9", "Stanford University", cc="US"),
        inst("I10", "Acme Pharma Pvt Ltd", typ="company"),
        inst("I11", "Indian Institute of Information Technology, Allahabad"),
        inst("I12", "National Institute of Technology Rourkela"),
        inst("I13", "Jawaharlal Nehru University"),
        inst("I14", "Savitribai Phule Pune University"),
    ]:
        r.add(i)
    return r


@pytest.mark.parametrize("iid,expected", [
    ("I1", "IIT"), ("I2", "IISc/TIFR/IISER"), ("I3", "IISc/TIFR/IISER"), ("I4", "DAE"), ("I5", "Medical"),
    ("I6", "CSIR"), ("I185249246", "CSIR"), ("I11", "IIIT"), ("I12", "NIT"), ("I13", "Central University"),
    ("I14", "University (other)"), ("I10", "Industry"), ("I9", "University (other)"),
])
def test_cluster(reg, iid, expected):
    assert reg.cluster(iid) == expected


def test_our_lab_flags_and_labels(reg):
    assert reg.our_lab("I185249246") == "CSIR-CDRI"
    assert reg.our_lab("I7") is None                 # a name match is not enough: identity is by id/lineage
    assert reg.label("I185249246") == "CSIR-CDRI" and reg.label("I1") == "Indian Institute of Technology Delhi"
    assert reg.is_umbrella(CSIR) and not reg.is_umbrella("I6")
    assert reg.is_academy("I99364266")


def test_partner_ok(reg):
    assert reg.partner_ok("I1", own_lab="CSIR-CDRI")
    assert reg.partner_ok("I6", own_lab="CSIR-CDRI")                 # another CSIR lab is a partner
    assert not reg.partner_ok("I185249246", own_lab="CSIR-CDRI")     # the lab itself
    assert reg.partner_ok("I185249246", own_lab="CSIR-IGIB")         # but a partner of another of our labs
    assert not reg.partner_ok(CSIR, own_lab="CSIR-CDRI")             # umbrella body
    assert not reg.partner_ok("I9", own_lab="CSIR-CDRI")             # foreign
    assert not reg.partner_ok("I99364266", own_lab="CSIR-CDRI")      # AcSIR: PhD registration, not collaboration


def test_overrides_win(reg):
    reg.overrides = {"I14": {"cluster": "State University", "short_name": "SPPU"}}
    assert reg.cluster("I14") == "State University" and reg.label("I14") == "SPPU"


def test_to_frame(reg):
    df = reg.to_frame().set_index("inst_id")
    assert df.loc["I185249246", "our_lab"] == "CSIR-CDRI" and df.loc["I1", "cluster"] == "IIT"
    assert bool(df.loc[CSIR, "is_umbrella"]) is True
