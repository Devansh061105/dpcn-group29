/* Phase II panels (instructor's additional directions). Inlined into app.js's closure, so it shares D, state,
   plot(), table(), kpis() and the other helpers. Every panel reads state.lab. Data: D.p2 (built by S13 from s16). */
const P2 = D.p2;
const P2REG = {};
let P2WIRE = () => {};
const CLUSTER_COLORS = { "IIT": "#8e6bc4", "NIT": "#b08968", "IIIT": "#c46b8a", "Central University": "#4aa3a8",
  "University (other)": "#7fb069", "Medical": "#d9778b", "IISc/TIFR/IISER": "#6b8fc4", "Premier Science": "#a58fd0",
  "DAE": "#9a9a6b", "ICMR": "#c9a227", "DBT": "#6fb3b8", "NIPER": "#c07f4d", "Government": "#8a8f98",
  "Industry": "#b0556b", "Other": "#a8a69f" };
const ownColor = (o) => o === "government" ? css("--lab-1") : o === "government-aided" ? css("--lab-3") : o === "private" ? css("--lab-2") : css("--qna");
let cyInst = null;

if (P2) {
  const TH = P2.summary.thresholds;
  const [IF1, IF2] = TH.if_thresholds;
  const MULTI = TH.multi_author_min, HYPER = TH.hyper_author_min;
  const ovRow = (scope) => P2.overview.find((r) => r.scope === scope) || {};
  const ifFmt = (c) => { const v = c.getValue(); return v === null || v === undefined ? "–" : Number(v).toFixed(1); };
  const ifSrc = (c) => { const s = c.getValue() || ""; return s.startsWith("JCR") || s.startsWith("Scimago") ? s : s ? "OpenAlex proxy" : ""; };
  const txt = (tag, text, cls) => { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; };
  const sc2 = () => state.lab === "ALL" ? [...LABS, "ALL"] : [state.lab, "ALL"];
  const scopeLabel = (s) => s === "ALL" ? "All labs" : short(s);

  function renderNotes() {   // the team's own interpretation (data/manual/phase2_notes.yaml); the dashboard never writes one
    document.querySelectorAll("[data-note]").forEach((box) => {
      const t = (P2.notes || {})[box.dataset.note] || "";
      box.replaceChildren(txt("h2", "Team interpretation"),
        t ? txt("p", t, "note-body") : txt("p", "To be written by the team. The dashboard reports the numbers; our reading of them goes here (data/manual/phase2_notes.yaml).", "muted"));
    });
  }

  // ---------------------------------------------------------------- tab: impact factor and author counts
  function renderImpact() {
    const o = ovRow(state.lab), src = P2.summary.if_sources || {};
    const nJcr = Object.entries(src).filter(([k]) => k.startsWith("JCR")).reduce((a, [, v]) => a + v, 0);
    const nProxy = Object.entries(src).filter(([k]) => k.includes("proxy")).reduce((a, [, v]) => a + v, 0);
    const nSci = Object.entries(src).filter(([k]) => k.startsWith("Scimago")).reduce((a, [, v]) => a + v, 0), nAll = nJcr + nSci + nProxy;
    const jcrParts = Object.entries(src).filter(([k]) => k.startsWith("JCR")).map(([k, v]) => `${fmt(v)} from ${k}`).join(" and ");
    const rest = [nSci ? `${fmt(nSci)} from Scimago's 2-year citations per document (Scopus data)` : "", nProxy ? `${fmt(nProxy)} from OpenAlex's 2-year mean citedness` : ""].filter(Boolean).join(" and ");
    el("if-banner").replaceChildren(txt("h2", "Impact factor: source and caveat"),
      txt("p", `Of ${fmt(nAll)} journals, ${jcrParts || "none"} use Clarivate's Journal Impact Factor (JCR)${rest ? `; the remaining ${fmt(nSci + nProxy)} are not in the JCR lists we hold and use a substitute: ${rest}` : ""}. ${nSci + nProxy ? "The substitutes use the same formula (citations in a year to the previous two years' papers, per paper) on other databases, so they differ from Clarivate's number, and journals that JCR does not cover tend to be small or regional. " : ""}${pct(o.if_borderline_share, 0)} of this view's journal papers lie within 10% of the IF ${IF1} or IF ${IF2} line, so counts near those lines are sensitive to the exact value. The source is shown for every journal.`, "note"));
    kpis("kpis-impact", [
      ["Faculty with papers", fmt(o.faculty_with_papers), `of ${fmt(o.roster_faculty)} on the roster`],
      ["Publications", fmt(o.papers), `${fmt(o.journal_papers)} journal papers`],
      ["Q1 publications", fmt(o.q1_papers), `${pct(o.q1_share, 0)} of journal papers with a known quartile`],
      [`Q1 with IF > ${IF1}`, fmt(o[`q1_if_gt${IF1}`]), `${pct(o[`q1_if_gt${IF1}_share_of_q1`], 0)} of Q1 papers`],
      [`Q1 with IF > ${IF2}`, fmt(o[`q1_if_gt${IF2}`]), `${pct(o[`q1_if_gt${IF2}_share_of_q1`], 0)} of Q1 papers`],
      [`Papers with ${MULTI}+ authors`, fmt(o.papers_multi), `${pct(o.share_multi, 0)} of papers · ${fmt((o[`papers_${HYPER}-999`] || 0) + (o["papers_1000+"] || 0))} with ${HYPER}+`],
      ["Collaborating institutions", fmt(o.collab_inst_all), `${fmt(o.collab_inst_indian)} Indian · ${fmt(o.collab_inst_foreign)} foreign · ${fmt(o.collab_inst_all_excl_hyper)} without ${HYPER}+ author papers`],
    ]);

    const sc = sc2(), q = [["Q1 papers", "q1_papers", css("--q1")], [`Q1 and IF > ${IF1}`, `q1_if_gt${IF1}`, css("--q2")], [`Q1 and IF > ${IF2}`, `q1_if_gt${IF2}`, css("--q3")]];
    plot("c-q1if", q.map(([name, key, color]) => ({ type: "bar", name, x: sc.map(scopeLabel), y: sc.map((s) => ovRow(s)[key]),
      marker: { color, line: { color: css("--surface"), width: 1 } }, text: sc.map((s) => fmt(ovRow(s)[key])), textposition: "outside", cliponaxis: false,
      hovertemplate: `<b>%{y:,}</b> papers<br>%{x} · ${name}<extra></extra>` })), { barmode: "group", yaxis: { title: "Papers" }, legend: { orientation: "h", y: -0.2 } });

    const cls = P2.author_classes.filter((r) => r.scope === state.lab);
    const names = cls.map((r) => `${r.author_class} authors`);
    plot("c-authcls", [
      { type: "bar", name: "Share of papers", x: names, y: cls.map((r) => r.share_of_papers), marker: { color: css("--lab-1") },
        text: cls.map((r) => pct(r.share_of_papers, 1)), textposition: "outside", cliponaxis: false,
        customdata: cls.map((r) => r.papers), hovertemplate: "<b>%{y:.1%}</b> of papers (%{customdata:,})<br>%{x}<extra></extra>" },
      { type: "bar", name: "Share of citations", x: names, y: cls.map((r) => r.share_of_citations), marker: { color: css("--lab-2") },
        text: cls.map((r) => pct(r.share_of_citations, 1)), textposition: "outside", cliponaxis: false,
        customdata: cls.map((r) => r.citations), hovertemplate: "<b>%{y:.1%}</b> of citations (%{customdata:,})<br>%{x}<extra></extra>" }],
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share" }, legend: { orientation: "h", y: -0.2 } });

    const yr = P2.yearly.filter((r) => r.scope === state.lab), py = D.meta.partial_year;
    plot("c-yearly", [
      { type: "bar", name: `Fewer than ${MULTI} authors`, x: yr.map((r) => r.year), y: yr.map((r) => r.papers_lt_multi), marker: { color: css("--lab-1") },
        hovertemplate: "<b>%{y}</b> papers<br>%{x}<extra></extra>" },
      { type: "bar", name: `${MULTI} or more authors`, x: yr.map((r) => r.year), y: yr.map((r) => r.papers_multi), marker: { color: css("--lab-4") },
        hovertemplate: "<b>%{y}</b> papers<br>%{x}<extra></extra>" },
      { type: "scatter", mode: "lines+markers", name: "Collaborating institutions", yaxis: "y2", x: yr.map((r) => r.year),
        y: yr.map((r) => r.collab_inst_all), line: { color: css("--ink"), width: 2 }, marker: { size: 7 },
        hovertemplate: "<b>%{y}</b> distinct institutions<br>%{x}<extra></extra>" },
      { type: "scatter", mode: "lines+markers", name: `Collaborating institutions, without ${HYPER}+ author papers`, yaxis: "y2", x: yr.map((r) => r.year),
        y: yr.map((r) => r.collab_inst_all_excl_hyper), line: { color: css("--ink"), width: 2, dash: "dot" }, marker: { size: 7, symbol: "diamond" },
        hovertemplate: "<b>%{y}</b> distinct institutions without the consortium papers<br>%{x}<extra></extra>" }],
      { barmode: "stack", xaxis: { dtick: 1 }, yaxis: { title: "Papers" },
        yaxis2: { overlaying: "y", side: "right", title: "Collaborating institutions", rangemode: "tozero", showgrid: false, automargin: true },
        margin: { l: 55, r: 70, t: 10, b: 50 }, legend: { orientation: "h", y: -0.2 },
        shapes: [{ type: "rect", xref: "x", yref: "paper", x0: py - 0.5, x1: py + 0.5, y0: 0, y1: 1, fillcolor: css("--grid"), opacity: 0.5, line: { width: 0 }, layer: "below" }] });

    const cl = (name, key, color, dash, symbol) => ({ name, x: yr.map((r) => r.year), y: yr.map((r) => r[key]), mode: "lines+markers",
      line: { color, width: 2, dash }, marker: { size: 7, symbol } });
    plot("c-collab-year", [
      cl("Indian institutions", "collab_inst_indian", css("--lab-3"), "solid", "circle"),
      cl(`Indian, without ${HYPER}+ author papers`, "collab_inst_indian_excl_hyper", css("--lab-3"), "dot", "diamond"),
      cl("Foreign institutions", "collab_inst_foreign", css("--lab-2"), "solid", "circle"),
      cl(`Foreign, without ${HYPER}+ author papers`, "collab_inst_foreign_excl_hyper", css("--lab-2"), "dot", "diamond")],
      { hovermode: "x unified", xaxis: { dtick: 1 }, yaxis: { title: "Distinct institutions" }, legend: { orientation: "h", y: -0.3 } });

    const hist = P2.if_histogram.filter((r) => r.scope === state.lab);
    const bx = hist.map((r) => r.bin_start + 0.5);
    plot("c-ifdist", [
      { type: "bar", name: "Q1", x: bx, y: hist.map((r) => r.q1_papers), marker: { color: css("--q1") }, width: 0.92,
        hovertemplate: "<b>%{y}</b> Q1 papers<extra></extra>" },
      { type: "bar", name: "Other quartiles / unranked", x: bx, y: hist.map((r) => r.papers - r.q1_papers), marker: { color: css("--qna") }, width: 0.92,
        hovertemplate: "<b>%{y}</b> other papers<extra></extra>" }],
      { barmode: "stack", xaxis: { title: "Journal impact factor (last bin = 20 and above)", range: [0, 21] }, yaxis: { title: "Papers" },
        shapes: [IF1, IF2].map((x) => ({ type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1, line: { color: css("--ink"), width: 1, dash: "dash" } })),
        annotations: [IF1, IF2].map((x) => ({ x, y: 1, yref: "paper", text: `IF ${x}`, showarrow: false, yanchor: "bottom", font: { size: 11, color: css("--ink-2") } })),
        margin: { l: 50, r: 16, t: 28, b: 40 }, legend: { orientation: "h", y: -0.25 } });

    table("t-top30", P2.top30_papers.filter((r) => r.scope === state.lab), [
      { title: "#", field: "rank", hozAlign: "right", width: 44 }, { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" },
      { title: "Journal", field: "journal_name", widthGrow: 2, formatter: "textarea" },
      { title: "IF", field: "impact_factor", hozAlign: "right", formatter: ifFmt }, { title: "IF source", field: "if_source", formatter: ifSrc },
      { title: "Quartile", field: "quartile" }, { title: "Year", field: "year" }, { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Authors", field: "n_authors", hozAlign: "right" }, { title: "Our faculty", field: "faculty", widthGrow: 2, formatter: "textarea" },
      { title: "DOI", field: "doi", formatter: doiLink, widthGrow: 2 }], { layout: "fitColumns", maxHeight: 520 });
    table("t-freqj", P2.journals.filter((r) => r.scope === state.lab), [
      { title: "#", field: "rank", hozAlign: "right", width: 44 }, { title: "Journal", field: "journal_name", widthGrow: 3 },
      { title: "Papers", field: "papers", hozAlign: "right" }, { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Quartile", field: "quartile" }, { title: "IF", field: "impact_factor", hozAlign: "right", formatter: ifFmt },
      { title: "IF source", field: "if_source", formatter: ifSrc }], { layout: "fitColumns", maxHeight: 460 });
    renderNotes();
  }

  // ---------------------------------------------------------------- tab: faculty comparison
  const CMP = [["papers", "Papers"], ["q1_papers", "Q1 papers"], ["citations", "Citations"],
    ["citations_excl_hyper", `Citations excluding ${HYPER}+ author papers`], ["collab_inst_all", "Collaborating institutions"],
    ["h_all", "h-index (2016–26)"], ["h_excl_hyper", `h-index excluding ${HYPER}+ author papers`],
    ["degree", "Co-author links (faculty network)"], ["mean_if", "Mean journal IF"]];
  const cmpLabel = (k) => (CMP.find((c) => c[0] === k) || [k, k])[1];

  function renderCompare() {
    const rows = P2.faculty.filter((r) => state.lab === "ALL" || r.lab === state.lab);
    const X = el("cmp-x").value, Y = el("cmp-y").value, S = el("cmp-s").value;
    const maxS = Math.max(1, ...rows.map((r) => r[S] || 0));
    plot("c-fcomp", scopes().map((lab) => {
      const rr = rows.filter((r) => r.lab === lab);
      return { type: "scatter", mode: "markers", name: short(lab), x: rr.map((r) => r[X]), y: rr.map((r) => r[Y]),
        customdata: rr.map((r) => [r.name, r.flag || "", r[S]]),
        marker: { size: rr.map((r) => 7 + 26 * Math.sqrt((r[S] || 0) / maxS)), color: labColor(lab), opacity: 0.78,
          symbol: rr.map((r) => r.flag ? "diamond" : "circle"),
          line: { color: rr.map((r) => r.flag ? css("--ink") : css("--surface")), width: rr.map((r) => r.flag ? 2 : 1) } },
        hovertemplate: `<b>%{customdata[0]}</b><br>${cmpLabel(X)}: %{x}<br>${cmpLabel(Y)}: %{y}<br>${cmpLabel(S)}: %{customdata[2]}<br><i>%{customdata[1]}</i><extra>${short(lab)}</extra>` };
    }), { xaxis: { title: cmpLabel(X), rangemode: "tozero" }, yaxis: { title: cmpLabel(Y), rangemode: "tozero" }, hovermode: "closest" });

    const top = (key, id) => {
      const t = [...rows].sort((a, b) => (b[key] || 0) - (a[key] || 0)).slice(0, 10).reverse();
      plot(id, [{ type: "bar", orientation: "h", y: t.map((r) => r.name), x: t.map((r) => r[key]), text: t.map((r) => fmt(r[key])),
        textposition: "outside", cliponaxis: false, marker: { color: t.map((r) => labColor(r.lab)) },
        customdata: t.map((r) => short(r.lab)), hovertemplate: "<b>%{x:,}</b><br>%{y} · %{customdata}<extra></extra>" }],
        { margin: { l: 150, r: 50, t: 10, b: 40 }, showlegend: false, yaxis: { automargin: true } });
    };
    top("papers", "c-top-prod"); top("collab_inst_all", "c-top-conn");

    table("t-fcomp", rows.map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name", headerFilter: "input", frozen: true, minWidth: 150 }, { title: "Lab", field: "lab", headerFilter: "input" },
      { title: "Department", field: "department", maxWidth: 220 },
      { title: "Papers", field: "papers", hozAlign: "right", sorter: "number" }, { title: "Q1", field: "q1_papers", hozAlign: "right", sorter: "number" },
      { title: `Q1, IF>${IF1}`, field: `q1_if_gt${IF1}`, hozAlign: "right", sorter: "number" }, { title: `Q1, IF>${IF2}`, field: `q1_if_gt${IF2}`, hozAlign: "right", sorter: "number" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: `Cit. excl. ${HYPER}+`, field: "citations_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: `% cit. from ${HYPER}+`, field: "cit_share_hyper", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "h", field: "h_all", hozAlign: "right", sorter: "number" }, { title: `h excl. ${HYPER}+`, field: "h_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: "Collab. inst.", field: "collab_inst_all", hozAlign: "right", sorter: "number" },
      { title: "Co-author links", field: "degree", hozAlign: "right", sorter: "number" },
      { title: "Mean IF", field: "mean_if", hozAlign: "right", sorter: "number", formatter: ifFmt },
      { title: "Flag", field: "flag", widthGrow: 3, formatter: "textarea" }], { maxHeight: 520, initialSort: [{ column: "papers", dir: "desc" }] });

    const pick = el("f-pick"), keep = pick.value;
    pick.replaceChildren();
    [...rows].sort((a, b) => b.papers - a.papers).forEach((r) => { const o = document.createElement("option"); o.value = r.faculty_id;
      o.textContent = `${r.name} (${short(r.lab)}, ${r.papers} papers)`; pick.append(o); });
    if ([...pick.options].some((o) => o.value === keep)) pick.value = keep;
    renderTop10();
    renderNotes();
  }

  function renderTop10() {
    const id = el("f-pick").value;
    table("t-ftop10", P2.faculty_top10.filter((r) => r.faculty_id === id), [
      { title: "#", field: "rank", hozAlign: "right", width: 44 }, { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" },
      { title: "Journal", field: "journal_name", widthGrow: 2, formatter: "textarea" },
      { title: "IF", field: "impact_factor", hozAlign: "right", formatter: ifFmt }, { title: "IF source", field: "if_source", formatter: ifSrc },
      { title: "Quartile", field: "quartile" }, { title: "Year", field: "year" }, { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Authors", field: "n_authors", hozAlign: "right" }, { title: "DOI", field: "doi", formatter: doiLink, widthGrow: 2 }],
      { layout: "fitColumns", maxHeight: 420 });
  }

  // ---------------------------------------------------------------- tab: institutional network and time
  function renderInstGraph() {
    const N = P2.inst_network, y0 = +el("yr-from").value, y1 = +el("yr-to").value, all = state.lab === "ALL";
    const inRange = (by) => Object.entries(by).reduce((a, [y, n]) => a + ((+y >= y0 && +y <= y1) ? n : 0), 0);
    let edges = N.edges.map((e) => ({ ...e, wr: inRange(e.by_year) })).filter((e) => e.wr > 0);
    if (!all) edges = edges.filter((e) => e.s === state.lab || e.t === state.lab);      // one lab: its own partners
    const deg = {}; edges.forEach((e) => { deg[e.s] = (deg[e.s] || 0) + e.wr; deg[e.t] = (deg[e.t] || 0) + e.wr; });
    const nodes = N.nodes.filter((n) => deg[n.id] || (n.kind === "lab" && (all || n.id === state.lab)));
    const maxd = Math.max(1, ...nodes.map((n) => deg[n.id] || 0));
    const topPartners = new Set(nodes.filter((n) => n.kind === "partner").sort((a, b) => (deg[b.id] || 0) - (deg[a.id] || 0)).slice(0, 14).map((n) => n.id));
    const els = [
      ...nodes.map((n) => ({ data: { id: n.id, name: n.id, kind: n.kind, cluster: n.cluster, deg: deg[n.id] || 0,
          size: n.kind === "lab" ? 26 + 30 * Math.sqrt((deg[n.id] || 0) / maxd) : 8 + 30 * Math.sqrt((deg[n.id] || 0) / maxd),
          color: n.kind === "lab" ? labColor(n.id) : (CLUSTER_COLORS[n.cluster] || CLUSTER_COLORS.Other),
          label: n.kind === "lab" ? short(n.id) : (topPartners.has(n.id) ? abbr(n.id, 28) : ""), shape: n.kind === "lab" ? labShape(n.id) : "ellipse" },
        position: { x: n.x, y: n.y } })),
      ...edges.map((e, i) => ({ data: { id: `ie${i}`, source: e.s, target: e.t, w: e.wr } })),
    ];
    if (cyInst) cyInst.destroy();
    cyInst = cytoscape({ container: el("g-inst"), elements: els, layout: { name: "preset", fit: true, padding: 24 }, wheelSensitivity: 0.25,
      minZoom: 0.2, maxZoom: 6, style: [
        { selector: "node", style: { width: "data(size)", height: "data(size)", "background-color": "data(color)", shape: "data(shape)",
          "border-width": 1.5, "border-color": css("--surface"), label: "data(label)", "font-size": 10, color: css("--ink"),
          "text-valign": "bottom", "text-margin-y": 3, "text-outline-width": 2, "text-outline-color": css("--surface") } },
        { selector: "edge", style: { width: "mapData(w, 1, 40, 0.8, 7)", "line-color": css("--muted"), opacity: 0.6, "curve-style": "haystack" } },
        { selector: "node:selected", style: { "border-color": css("--ink"), "border-width": 3 } },
        { selector: ".faded", style: { opacity: 0.1 } }] });
    cyInst.on("tap", "node", (ev) => {
      const d = ev.target.data();
      const nb = edges.filter((e) => e.s === d.id || e.t === d.id).map((e) => [e.s === d.id ? e.t : e.s, e.wr]).sort((a, b) => b[1] - a[1]).slice(0, 8);
      info("inst-info", d.name, [["Cluster", d.cluster], [`Joint papers ${y0}–${y1}`, d.deg], ["Top partners", nb.map(([n, w]) => `${abbr(n, 34)} (${w})`).join("; ") || "–"]]);
      cyInst.elements().addClass("faded"); ev.target.closedNeighborhood().removeClass("faded");
    });
    cyInst.on("tap", (ev) => { if (ev.target === cyInst) cyInst.elements().removeClass("faded"); });
    hoverTip(cyInst, (d) => `${d.name} · ${d.cluster} · ${d.deg} joint papers`);
    el("inst-n").textContent = `${nodes.length} institutions, ${edges.length} links`;
    const present = [...new Set(nodes.filter((n) => n.kind === "partner").map((n) => n.cluster))];
    legend("leg-inst", [...LABS.map((l) => [labColor(l), short(l), labShape(l)]), ...present.map((c) => [CLUSTER_COLORS[c] || CLUSTER_COLORS.Other, c, "ellipse"])]);
  }

  function renderTemporal() {
    const metric = el("tnet-metric").value, mode = document.querySelector('input[name="tmode"]:checked').value, label = el("tnet-metric").selectedOptions[0].textContent;
    plot("c-tnet", sc2().map((s) => {
      const r = P2.temporal_network.filter((x) => x.scope === s && x.mode === mode);
      return { name: scopeLabel(s), x: r.map((x) => x.year), y: r.map((x) => x[metric]), mode: "lines+markers",
        line: { color: s === "ALL" ? css("--ink") : labColor(s), width: s === "ALL" ? 2.5 : 2, dash: s === "ALL" ? "dot" : "solid" }, marker: { size: 7 },
        hovertemplate: `<b>%{y:,.3~f}</b> ${label.toLowerCase()}<br>${scopeLabel(s)} · %{x}<extra></extra>` };
    }), { hovermode: "x unified", xaxis: { dtick: 1 }, yaxis: { title: label } });

    const c = P2.temporal_citations.filter((x) => x.scope === state.lab);
    const line = (name, key, color, dash) => ({ name, x: c.map((x) => x.year), y: c.map((x) => x[key]), mode: "lines+markers", line: { color, width: 2, dash }, marker: { size: 7 } });
    plot("c-tcit", [line("Among our papers: same lab", "within_lab", css("--lab-1")), line("Among our papers: to another lab", "to_other_labs", css("--lab-4")),
      line("Indian citations received", "indian_in", css("--lab-3")), line("Indian citations given", "indian_out", css("--lab-2"), "dot")],
      { hovermode: "x unified", xaxis: { dtick: 1 }, yaxis: { title: "Citations in that year" } });
  }

  function renderInstNet() { renderInstGraph(); renderTemporal(); renderNotes(); }

  // ---------------------------------------------------------------- tab: flags
  function renderFlags() {
    const o = ovRow(state.lab), fac = P2.faculty.filter((r) => state.lab === "ALL" || r.lab === state.lab);
    const hyperShare = (o[`citation_share_${HYPER}-999`] || 0) + (o["citation_share_1000+"] || 0);
    const cit = P2.citers.filter((r) => r.scope === state.lab);
    kpis("kpis-flags", [
      [`Papers with ${HYPER}+ authors`, fmt((o[`papers_${HYPER}-999`] || 0) + (o["papers_1000+"] || 0)), `${pct(((o[`papers_${HYPER}-999`] || 0) + (o["papers_1000+"] || 0)) / o.papers, 1)} of papers`],
      ["Their share of citations", pct(hyperShare, 1), `${fmt((o[`citations_${HYPER}-999`] || 0) + (o["citations_1000+"] || 0))} citations`],
      ["Faculty flagged", fmt(fac.filter((r) => r.flag_hyper || r.flag_multi).length), `of ${fmt(fac.length)} (rules below)`],
      ["Heavy citing institutions", fmt(cit.filter((r) => r.flag_heavy).length), `≥ ${TH.citer_min_cites} citations into the lab`],
      ["Heavy, few shared papers", fmt(cit.filter((r) => r.flag_citation_heavy_vs_collab).length), `≥ ${TH.citer_ratio_min} citations per shared paper`],
      ["Flagged non-government", fmt(cit.filter((r) => r.flag_non_government).length), "private, heavy, few shared papers"],
    ]);
    const sc = state.lab === "ALL" ? [...LABS, "ALL"] : [state.lab, "ALL"];
    const classes = [...new Set(P2.author_classes.map((r) => r.author_class))];
    const palette = [css("--lab-1"), css("--lab-3"), css("--lab-4"), css("--lab-2")];
    plot("c-clsshare", classes.map((c, i) => ({ type: "bar", name: `${c} authors`, orientation: "h", y: sc.map(scopeLabel),
      x: sc.map((s) => (P2.author_classes.find((r) => r.scope === s && r.author_class === c) || {}).share_of_citations || 0),
      marker: { color: palette[i % 4], line: { color: css("--surface"), width: 2 } },
      text: sc.map((s) => { const v = (P2.author_classes.find((r) => r.scope === s && r.author_class === c) || {}).share_of_citations || 0; return v >= 0.06 ? pct(v, 0) : ""; }),
      textposition: "inside", insidetextanchor: "middle", textfont: { color: inkOn(palette[i % 4]) },
      hovertemplate: `<b>%{x:.1%}</b> of citations<br>%{y} · ${c} authors<extra></extra>` })),
      { barmode: "stack", xaxis: { tickformat: ".0%", range: [0, 1] }, yaxis: { autorange: "reversed" }, margin: { l: 70, r: 10, t: 10, b: 50 }, legend: { orientation: "h", y: -0.2, traceorder: "normal" } });

    const dep = fac.filter((r) => r.citations >= TH.faculty_flag_min_citations).sort((a, b) => (b.cit_share_hyper || 0) - (a.cit_share_hyper || 0)).slice(0, 15).reverse();
    plot("c-dep", [{ type: "bar", orientation: "h", y: dep.map((r) => r.name), x: dep.map((r) => r.cit_share_hyper), marker: { color: dep.map((r) => labColor(r.lab)) },
      text: dep.map((r) => `${pct(r.cit_share_hyper, 0)} of ${fmt(r.citations)}`), textposition: "outside", cliponaxis: false, customdata: dep.map((r) => short(r.lab)),
      hovertemplate: "<b>%{x:.0%}</b> of citations from papers with " + HYPER + "+ authors<br>%{y} · %{customdata}<extra></extra>" }],
      { margin: { l: 150, r: 90, t: 10, b: 40 }, showlegend: false, xaxis: { tickformat: ".0%", range: [0, 1.15] }, yaxis: { automargin: true },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: TH.faculty_flag_share_hyper, x1: TH.faculty_flag_share_hyper, y0: 0, y1: 1, line: { color: css("--ink"), width: 1, dash: "dash" } }] });

    table("t-hyper", P2.hyper_papers.filter((r) => inLab(r.labs)), [
      { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" }, { title: "Journal", field: "journal_name", widthGrow: 2, formatter: "textarea" },
      { title: "Year", field: "year" }, { title: "Authors", field: "n_authors", hozAlign: "right", sorter: "number" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: "% of all citations", field: "share_of_all_citations", hozAlign: "right", formatter: (c) => pct(c.getValue(), 1) },
      { title: "Labs", field: "labs", formatter: (c) => String(c.getValue() || "").split(";").map((x) => short(x.trim())).join(", ") },
      { title: "Our faculty", field: "our_faculty", widthGrow: 2, formatter: "textarea" }, { title: "DOI", field: "doi", formatter: doiLink }],
      { layout: "fitColumns", maxHeight: 420, initialSort: [{ column: "citations", dir: "desc" }] });
    table("t-flagfac", fac.filter((r) => r.flag_hyper || r.flag_multi).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name", frozen: true, minWidth: 150 }, { title: "Lab", field: "lab" },
      { title: "Papers", field: "papers", hozAlign: "right" }, { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: `From ${HYPER}+`, field: "cit_share_hyper", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: `From ${MULTI}+`, field: "cit_share_multi", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Cit. without " + HYPER + "+", field: "citations_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: "h", field: "h_all", hozAlign: "right" }, { title: "h without", field: "h_excl_hyper", hozAlign: "right" },
      { title: "Top paper share", field: "top_paper_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }],
      { maxHeight: 420, initialSort: [{ column: "cit_share_hyper", dir: "desc" }] });
    renderCiters();
    renderNotes();
  }

  function renderCiters() {
    const own = el("own-filter").value;
    const rows = P2.citers.filter((r) => r.scope === state.lab && (own === "all" || r.ownership === own));
    const owners = ["government", "government-aided", "private", "unclassified"];
    // label only what matters, so the points stay readable: the 10 largest flagged institutions and the 4 largest overall
    const labelled = new Set([...rows.filter((r) => r.flag_non_government).sort((a, b) => b.cites_in - a.cites_in).slice(0, 10),
      ...[...rows].sort((a, b) => b.cites_in - a.cites_in).slice(0, 4)].map((r) => r.partner_inst));
    plot("c-citers2", owners.map((ow) => {
      const rr = rows.filter((r) => r.ownership === ow);
      return { type: "scatter", mode: "markers+text", name: ow, x: rr.map((r) => Math.max(r.shared_papers, 0.8)), y: rr.map((r) => r.cites_in),
        text: rr.map((r) => labelled.has(r.partner_inst) ? abbr(r.partner_inst, 22) : ""), textposition: "top center", textfont: { size: 10, color: css("--ink-2") },
        marker: { size: rr.map((r) => r.flag_non_government ? 13 : 8), color: ownColor(ow), opacity: 0.8, line: { color: rr.map((r) => r.flag_non_government ? css("--ink") : css("--surface")), width: rr.map((r) => r.flag_non_government ? 2 : 1) } },
        customdata: rr.map((r) => [r.partner_inst, r.shared_papers, r.cites_per_shared_paper]),
        hovertemplate: "<b>%{customdata[0]}</b><br>%{y:,} citations into the lab(s)<br>%{customdata[1]} shared papers · %{customdata[2]:.1f} per shared paper<extra>" + ow + "</extra>" };
    }), { xaxis: { type: "log", title: "Shared papers (co-authored with the lab; 0 shown as 0.8)", tickvals: [1, 3, 10, 30, 100, 300], ticktext: ["1", "3", "10", "30", "100", "300"], range: [Math.log10(0.6), Math.log10(500)] },
      yaxis: { type: "log", title: "Citations received from the institution", rangemode: "normal", tickvals: [30, 100, 300, 1000, 3000], ticktext: ["30", "100", "300", "1,000", "3,000"] },
      shapes: [{ type: "line", xref: "x", yref: "y", x0: 0.8, x1: 300, y0: 0.8 * TH.citer_ratio_min, y1: 300 * TH.citer_ratio_min, line: { color: css("--muted"), width: 1, dash: "dash" } },
               { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: TH.citer_min_cites, y1: TH.citer_min_cites, line: { color: css("--muted"), width: 1, dash: "dot" } }],
      annotations: [{ x: 1, xref: "paper", y: Math.log10(TH.citer_min_cites), yref: "y", text: `${TH.citer_min_cites} citations`, showarrow: false, xanchor: "right", yanchor: "bottom", font: { size: 10, color: css("--muted") } }],
      legend: { orientation: "h", y: -0.22 } });

    table("t-citers", rows.map((r) => ({ ...r, flags: [r.flag_non_government ? "non-government, heavy, few shared papers" : "", r.flag_citation_heavy_vs_collab && !r.flag_non_government ? "heavy, few shared papers" : "", r.flag_heavy && !r.flag_citation_heavy_vs_collab ? "heavy" : ""].filter(Boolean).join("; ") })), [
      { title: "Institution", field: "partner_inst", headerFilter: "input", widthGrow: 3, frozen: true },
      { title: "Ownership", field: "ownership" }, { title: "Cluster", field: "partner_cluster" },
      { title: "Cites in", field: "cites_in", hozAlign: "right", sorter: "number" }, { title: "Cites out", field: "cites_out", hozAlign: "right", sorter: "number" },
      { title: "Shared papers", field: "shared_papers", hozAlign: "right", sorter: "number" },
      { title: "Cites per shared paper", field: "cites_per_shared_paper", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 1) },
      { title: "Flags", field: "flags", widthGrow: 2, formatter: "textarea" }], { maxHeight: 440, initialSort: [{ column: "cites_in", dir: "desc" }] });

    const ev = P2.citer_evidence.filter((r) => own === "all" || r.ownership === own);
    el("ev-note").textContent = state.lab === "ALL" ? "" : "Evidence is computed on all four labs combined, so it does not change with the selected lab.";
    table("t-evidence", ev, [
      { title: "Institution", field: "partner_inst", widthGrow: 3, frozen: true }, { title: "Ownership", field: "ownership" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" }, { title: "Citing papers", field: "citing_papers", hozAlign: "right", sorter: "number" },
      { title: "Shared papers", field: "shared_papers", hozAlign: "right", sorter: "number" },
      { title: "Top citing author", field: "top_citing_author", widthGrow: 2 },
      { title: "Their share of citing papers", field: "top_citing_author_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Citations on a paper sharing an author with the cited paper", field: "shared_author_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Review articles among citing papers", field: "review_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Top citing journal", field: "top_citing_journal", widthGrow: 2 },
      { title: "Its share", field: "top_citing_journal_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Share on one of our papers", field: "top_cited_paper_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }],
      { maxHeight: 460, initialSort: [{ column: "citations", dir: "desc" }] });
  }

  P2WIRE = function () {
    CMP.forEach(([k, label]) => ["cmp-x", "cmp-y", "cmp-s"].forEach((id) => { const o = document.createElement("option"); o.value = k; o.textContent = label; el(id).append(o); }));
    el("cmp-x").value = "papers"; el("cmp-y").value = "q1_papers"; el("cmp-s").value = "citations";
    ["cmp-x", "cmp-y", "cmp-s"].forEach((id) => el(id).addEventListener("change", renderCompare));
    el("f-pick").addEventListener("change", renderTop10);
    const ys = P2.inst_network.years;
    ["yr-from", "yr-to"].forEach((id, i) => {
      ys.forEach((y) => { const o = document.createElement("option"); o.value = y; o.textContent = y; el(id).append(o); });
      el(id).value = ys[i ? ys.length - 1 : 0]; el(id).addEventListener("change", renderInstGraph);
    });
    el("tnet-metric").addEventListener("change", renderTemporal);
    document.querySelectorAll('input[name="tmode"]').forEach((r) => r.addEventListener("change", renderTemporal));
    el("own-filter").addEventListener("change", renderCiters);
  };

  Object.assign(P2REG, { impact: renderImpact, compare: renderCompare, instnet: renderInstNet, flags: renderFlags });
}
