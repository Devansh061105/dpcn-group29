"""S10: authorship (co-authorship) network (guide §7, S10; plan D15-D18).

  raw edges   every author pair on every dataset paper with at most networks.max_authors_for_pairs authors,
              where at least one of the two is affiliated with one of our labs on that paper (D15, D16)
  G_fac       primary analysis graph: nodes = roster faculty with a dataset paper (all their OpenAlex IDs merged),
              edge weight = number of joint dataset papers
  G_internal  every author affiliated with one of our labs on a dataset paper (faculty, students, postdocs)

Metrics: degree centrality, strength, betweenness (exact on G_fac, sampled on G_internal), Louvain communities with
modularity, and hub authors (faculty whose co-authors span the most Indian partner institutions).

Outputs: outputs/submission/authorship_network.csv; outputs/networks/authorship_faculty.gexf,
authorship_internal.gexf, authorship_dash.json; outputs/stats/authorship_centrality.csv, communities.csv,
hub_authors.csv, authorship_network_summary.json.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import pandas as pd

from ..netdata import load_context

log = logging.getLogger("dpcn.s10")

COLUMNS = ["author_a", "author_b", "paper_doi", "inst_a", "inst_b", "year", "author_a_id", "author_b_id",
           "a_is_faculty", "b_is_faculty", "cross_institution", "indian_link"]


def person_key(author_id: str | None, faculty_id: str | None, name: str, wid: str, pos: int) -> str:
    if faculty_id:
        return f"F:{faculty_id}"
    if author_id:
        return f"A:{author_id}"
    return f"X:{wid}:{pos}"          # an authorship OpenAlex could not resolve: unique to this paper


def paper_people(rows, reg, fac_name: dict) -> dict[str, dict]:
    """key -> {name, inst, internal, indian} for the authorships of one paper (first occurrence wins,
    but a faculty member counts as internal if any of their authorships on the paper is)."""
    people: dict[str, dict] = {}
    for r in rows:
        k = person_key(r.author_id, r.faculty_id, r.author_name, r.work_id, r.position_idx)
        lab = r.our_lab
        indian = [i for i in r.inst_ids if reg.is_indian(i) and not reg.is_umbrella(i) and not reg.is_academy(i)]
        if lab:
            inst = lab
        elif indian:
            inst = reg.label(indian[0])
        elif len(r.inst_ids):
            inst = reg.label(r.inst_ids[0])
        else:
            inst = "Unknown"
        is_indian = bool(lab) or bool(indian) or "IN" in list(r.country_codes)
        name = fac_name.get(r.faculty_id) or r.author_name or r.raw_author_name or "Unknown"
        if k in people:
            people[k]["internal"] |= bool(lab)
            if lab and not people[k]["internal_inst"]:
                people[k].update(inst=inst, internal_inst=True)
            continue
        people[k] = {"name": name, "inst": inst, "internal": bool(lab), "internal_inst": bool(lab),
                     "indian": is_indian, "faculty": bool(r.faculty_id)}
    return people


def centrality_frame(G: nx.Graph, k_sample: int | None = None) -> pd.DataFrame:
    if not len(G):
        return pd.DataFrame(columns=["node", "degree", "degree_centrality", "strength", "betweenness"])
    deg = nx.degree_centrality(G)
    strength = dict(G.degree(weight="weight"))
    if k_sample and len(G) > k_sample:
        btw = nx.betweenness_centrality(G, k=k_sample, seed=42, normalized=True)
    else:
        btw = nx.betweenness_centrality(G, normalized=True)
    return pd.DataFrame({"node": list(G), "degree": [G.degree(n) for n in G], "degree_centrality": [deg[n] for n in G],
                         "strength": [strength[n] for n in G], "betweenness": [btw[n] for n in G]})


def communities(G: nx.Graph, cfg) -> tuple[dict, float]:
    if G.number_of_edges() == 0:
        return {n: i for i, n in enumerate(G)}, 0.0
    comms = nx.community.louvain_communities(G, weight="weight", resolution=cfg.networks.louvain_resolution,
                                             seed=cfg.networks.louvain_seed)
    comms = sorted(comms, key=len, reverse=True)
    q = nx.community.modularity(G, comms, weight="weight")
    return {n: i for i, c in enumerate(comms) for n in c}, q


def layout(G: nx.Graph, k_scale: float = 3.5) -> dict:
    """Spring layout per connected component: the largest fills a 1000 x 1000 box, the smaller ones are laid out
    in a grid of small cells underneath, so no component is flung to the edge of the drawing."""
    if not len(G):
        return {}
    U = G.to_undirected() if G.is_directed() else G
    comps = sorted(nx.connected_components(U), key=len, reverse=True)
    out = {}

    def place(nodes, x0, y0, size):
        sub = U.subgraph(nodes)
        if len(sub) == 1:
            pos = {next(iter(nodes)): (0.0, 0.0)}
        else:
            pos = nx.spring_layout(sub, seed=42, weight="weight", k=k_scale / len(sub) ** 0.5, iterations=300)
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        for n, (x, y) in pos.items():
            out[n] = (round(x0 + (x - min(xs)) / span * size, 1), round(y0 + (y - min(ys)) / span * size, 1))

    place(comps[0], 0, 0, 1000)
    top = max(y for _, y in out.values()) + 60       # small components in rows just below the main one
    cell, cols = 110, 9
    for i, c in enumerate(comps[1:]):
        place(c, (i % cols) * cell, top + (i // cols) * cell, cell * 0.7 if len(c) > 1 else 0)
    return out


def run(cfg, oa, argv=()) -> None:
    ctx = load_context(cfg, need_flows=False)
    reg = ctx.reg
    max_auth = cfg.networks.max_authors_for_pairs
    fac_name = dict(zip(ctx.roster["faculty_id"], ctx.roster["name"]))
    fac_lab = dict(zip(ctx.roster["faculty_id"], ctx.roster["institution"]))
    dept = pd.read_parquet(cfg.paths.interim / "faculty_dept.parquet").set_index("faculty_id")["department"].to_dict()
    by_work = defaultdict(list)
    for r in ctx.authorships.itertuples():
        by_work[r.work_id].append(r)

    rows, skipped = [], 0
    Gf, Gi = nx.Graph(), nx.Graph()
    fac_with_papers = set(ctx.links["faculty_id"])
    for fid in sorted(fac_with_papers):
        Gf.add_node(f"F:{fid}", name=fac_name.get(fid, fid), lab=fac_lab.get(fid, ""), department=dept.get(fid, ""))
    hub_partners: dict[str, set] = defaultdict(set)
    internal_name, internal_lab = {}, {}
    for w in ctx.works.itertuples():
        auths = by_work.get(w.work_id, [])
        if len(auths) > max_auth:
            skipped += 1
            continue
        people = paper_people(auths, reg, fac_name)
        for k, p in people.items():
            if p["internal"]:
                internal_name.setdefault(k, p["name"])
                internal_lab.setdefault(k, p["inst"])
        doi = ctx.doi[w.work_id]
        for (ka, pa), (kb, pb) in combinations(sorted(people.items()), 2):
            if not (pa["internal"] or pb["internal"]):
                continue
            rows.append((pa["name"], pb["name"], doi, pa["inst"], pb["inst"], int(w.year), ka, kb,
                         pa["faculty"], pb["faculty"], pa["inst"] != pb["inst"],
                         pa["indian"] and pb["indian"] and pa["inst"] != pb["inst"]))
            if pa["internal"] and pb["internal"]:
                d = Gi.get_edge_data(ka, kb)
                if d:
                    d["weight"] += 1
                else:
                    Gi.add_edge(ka, kb, weight=1)
            if ka in Gf and kb in Gf:
                d = Gf.get_edge_data(ka, kb)
                if d:
                    d["weight"] += 1
                else:
                    Gf.add_edge(ka, kb, weight=1, cross_lab=Gf.nodes[ka]["lab"] != Gf.nodes[kb]["lab"])

    # hub authors use every dataset paper (consortium papers too): distinct Indian partner institutions
    for l in ctx.links.itertuples():
        hub_partners[l.faculty_id].update(ctx.partners(l.work_id, l.institution))

    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("a_is_faculty", "b_is_faculty", "cross_institution", "indian_link"):
        df[c] = df[c].map({True: "TRUE", False: "FALSE"})
    sub = cfg.paths.submission
    sub.mkdir(parents=True, exist_ok=True)
    df.to_csv(sub / "authorship_network.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ---- analysis
    for n in Gi:
        Gi.nodes[n]["name"] = internal_name.get(n, n)
        Gi.nodes[n]["lab"] = internal_lab.get(n, "")
        Gi.nodes[n]["is_faculty"] = n.startswith("F:")
    comm_f, q_f = communities(Gf, cfg)
    comm_i, q_i = communities(Gi, cfg)
    cf = centrality_frame(Gf)
    ci = centrality_frame(Gi, k_sample=cfg.networks.betweenness_k_internal)
    nx.set_node_attributes(Gf, comm_f, "community")
    nx.set_node_attributes(Gi, comm_i, "community")
    for G, c in ((Gf, cf), (Gi, ci)):
        for col in ("degree_centrality", "betweenness"):
            nx.set_node_attributes(G, dict(zip(c["node"], c[col])), col)

    net, stats = cfg.paths.networks, cfg.paths.stats
    net.mkdir(parents=True, exist_ok=True)
    stats.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(Gf, net / "authorship_faculty.gexf")
    nx.write_gexf(Gi, net / "authorship_internal.gexf")

    cent = cf.rename(columns={"node": "key"})
    cent["faculty_id"] = cent["key"].str[2:]
    cent["name"] = cent["faculty_id"].map(fac_name)
    cent["lab"] = cent["faculty_id"].map(fac_lab)
    cent["department"] = cent["faculty_id"].map(dept)
    cent["community"] = cent["key"].map(comm_f)
    ci_f = ci[ci["node"].str.startswith("F:")].set_index("node")
    cent["degree_internal"] = cent["key"].map(ci_f["degree"]).fillna(0).astype(int)
    cent["betweenness_internal"] = cent["key"].map(ci_f["betweenness"]).fillna(0.0)
    cent["community_internal"] = cent["key"].map(comm_i)
    cent["n_partner_insts"] = cent["faculty_id"].map(lambda f: len(hub_partners.get(f, ())))
    cent = cent[["faculty_id", "name", "lab", "department", "degree", "degree_centrality", "strength", "betweenness",
                 "community", "degree_internal", "betweenness_internal", "community_internal", "n_partner_insts"]]
    cent = cent.sort_values("degree", ascending=False)
    cent.to_csv(stats / "authorship_centrality.csv", index=False, encoding="utf-8", lineterminator="\n")

    crow = []
    for cid in sorted(set(comm_f.values())):
        members = cent[cent["community"] == cid].sort_values("strength", ascending=False)
        crow.append({"community": cid, "size": len(members),
                     "labs": "; ".join(f"{k} ({v})" for k, v in Counter(members["lab"]).most_common()),
                     "top_departments": "; ".join(f"{k} ({v})" for k, v in Counter(members["department"]).most_common(3)),
                     "top_members": "; ".join(members["name"].head(3))})
    pd.DataFrame(crow).to_csv(stats / "communities.csv", index=False, encoding="utf-8", lineterminator="\n")

    hubs = cent.sort_values(["n_partner_insts", "betweenness"], ascending=False)[
        ["faculty_id", "name", "lab", "department", "n_partner_insts", "degree", "betweenness", "betweenness_internal"]]
    hubs.head(30).to_csv(stats / "hub_authors.csv", index=False, encoding="utf-8", lineterminator="\n")

    def comm_sizes(c):
        return sorted(Counter(c.values()).values(), reverse=True)
    cross_lab_edges = sum(1 for _, _, d in Gf.edges(data=True) if d.get("cross_lab"))
    summary = {
        "pairs_rows": len(df), "papers_skipped_over_max_authors": skipped, "max_authors_for_pairs": max_auth,
        "cross_institution_rows": int((df["cross_institution"] == "TRUE").sum()),
        "indian_link_rows": int((df["indian_link"] == "TRUE").sum()),
        "faculty_graph": {"nodes": Gf.number_of_nodes(), "edges": Gf.number_of_edges(), "density": nx.density(Gf),
                          "isolates": nx.number_of_isolates(Gf), "components": nx.number_connected_components(Gf),
                          "largest_component": len(max(nx.connected_components(Gf), key=len)) if len(Gf) else 0,
                          "cross_lab_edges": cross_lab_edges, "modularity": q_f, "communities": len(set(comm_f.values())),
                          "community_sizes": comm_sizes(comm_f)},
        "internal_graph": {"nodes": Gi.number_of_nodes(), "edges": Gi.number_of_edges(), "density": nx.density(Gi),
                           "components": nx.number_connected_components(Gi) if len(Gi) else 0,
                           "modularity": q_i, "communities": len(set(comm_i.values())),
                           "community_sizes_top10": comm_sizes(comm_i)[:10]},
    }
    (stats / "authorship_network_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- dashboard: full G_fac and the best-connected part of G_internal, positions precomputed
    # faculty with no faculty co-author are counted in the summary but left out of the drawing, so the connected
    # part is not squeezed by isolates pushed to the edges
    Sf = Gf.subgraph([n for n in Gf if Gf.degree(n) > 0]).copy()
    pf = layout(Sf)
    keep = [n for n, _ in sorted(Gi.degree(), key=lambda kv: -kv[1])[:cfg.networks.dashboard_internal_nodes]]
    Si = Gi.subgraph(keep).copy()
    Si.remove_nodes_from([n for n in list(Si) if Si.degree(n) == 0])
    pi = layout(Si)
    btw_f = dict(zip(cf["node"], cf["betweenness"]))
    btw_i = dict(zip(ci["node"], ci["betweenness"]))

    def nodes(G, pos, btw, comm):
        return [{"id": n, "name": G.nodes[n].get("name", n), "lab": G.nodes[n].get("lab", ""),
                 "dept": G.nodes[n].get("department", ""), "fac": n.startswith("F:"), "deg": G.degree(n),
                 "btw": round(btw.get(n, 0.0), 5), "comm": comm.get(n, -1), "x": pos[n][0], "y": pos[n][1]} for n in G]

    def edges(G):
        return [{"s": a, "t": b, "w": d["weight"], "cross": G.nodes[a].get("lab") != G.nodes[b].get("lab")}
                for a, b, d in G.edges(data=True)]
    dash = {"faculty": {"nodes": nodes(Sf, pf, btw_f, comm_f), "edges": edges(Sf)},
            "internal": {"nodes": nodes(Si, pi, btw_i, comm_i), "edges": edges(Si)}}
    (net / "authorship_dash.json").write_text(json.dumps(dash), encoding="utf-8")

    fg = summary["faculty_graph"]
    print(f"\nauthorship_network.csv: {len(df)} pair rows ({skipped} papers with > {max_auth} authors skipped); "
          f"cross-institution {summary['cross_institution_rows']}, Indian links {summary['indian_link_rows']}")
    print(f"G_fac: {fg['nodes']} faculty, {fg['edges']} edges ({cross_lab_edges} cross-lab), {fg['isolates']} isolates, "
          f"{fg['communities']} communities, modularity {q_f:.3f}")
    ig = summary["internal_graph"]
    print(f"G_internal: {ig['nodes']} authors, {ig['edges']} edges, {ig['communities']} communities, modularity {q_i:.3f}")
    print("Top 10 faculty by degree:")
    print(cent.head(10)[["name", "lab", "degree", "strength", "betweenness", "community"]].to_string(index=False))
