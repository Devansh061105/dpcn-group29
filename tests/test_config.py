from dpcn.config import load_config


def test_config_loads_group29_labs():
    cfg = load_config()
    assert cfg.group == 29
    assert [lab["short"] for lab in cfg.labs] == ["CSIR-CCMB", "CSIR-IGIB", "CSIR-IMTECH", "CSIR-CDRI"]
    assert cfg.lab_ids == {"I185638415", "I177828482", "I4210147764", "I185249246"}
    assert cfg.lab_by_short["CSIR-CDRI"]["ror"] == "04t8qjg16"
    assert cfg.year_filter == "publication_year:2016-2026"
    assert cfg.paths.interim == cfg.root / "data" / "interim"


def test_cluster_rules_present():
    cfg = load_config()
    assert "I66760702" in cfg.rules["umbrella_ids"]
    assert cfg.rules["lineage_rules"]["I3149292468"] == "DAE"
