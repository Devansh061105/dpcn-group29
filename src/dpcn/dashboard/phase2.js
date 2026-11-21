/* Phase II panels (instructor's additional directions). Inlined into app.js's closure, so it shares D, state,
   plot(), table(), kpis() and the other helpers. Every panel reads state.lab. Data: D.p2 (built by S13 from s16). */
const P2 = D.p2;
const P2REG = {};
const P2API = {};      // functions the other tabs call (the panels below live in the block's own scope)
let P2WIRE = () => {};
const CLUSTER_COLORS = { "IIT": "#8e6bc4", "NIT": "#b08968", "IIIT": "#c46b8a", "Central University": "#4aa3a8",
  "University (other)": "#7fb069", "Medical": "#d9778b", "IISc/TIFR/IISER": "#6b8fc4", "Premier Science": "#a58fd0",
  "DAE": "#9a9a6b", "ICMR": "#c9a227", "DBT": "#6fb3b8", "NIPER": "#c07f4d", "Government": "#8a8f98",
  "Industry": "#b0556b", "Other": "#a8a69f" };
const ownColor = (o) => o === "government" ? css("--lab-1") : o === "government-aided" ? css("--lab-3") : o === "private" ? css("--lab-2") : o === "international" ? css("--lab-4") : css("--qna");
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
    renderIfSens();
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
      hovertemplate: `<b>%{y:,}</b> papers<br>%{x} · ${name}<extra></extra>` })), { barmode: "group", yaxis: { title: "Papers" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const cls = P2.author_classes.filter((r) => r.scope === state.lab);
    const names = cls.map((r) => `${r.author_class} authors`);
    plot("c-authcls", [
      { type: "bar", name: "Share of papers", x: names, y: cls.map((r) => r.share_of_papers), marker: { color: css("--lab-1") },
        text: cls.map((r) => pct(r.share_of_papers, 1)), textposition: "outside", cliponaxis: false,
        customdata: cls.map((r) => r.papers), hovertemplate: "<b>%{y:.1%}</b> of papers (%{customdata:,})<br>%{x}<extra></extra>" },
      { type: "bar", name: "Share of citations", x: names, y: cls.map((r) => r.share_of_citations), marker: { color: css("--lab-2") },
        text: cls.map((r) => pct(r.share_of_citations, 1)), textposition: "outside", cliponaxis: false,
        customdata: cls.map((r) => r.citations), hovertemplate: "<b>%{y:.1%}</b> of citations (%{customdata:,})<br>%{x}<extra></extra>" }],
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

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
        margin: { l: 55, r: 70, t: 10, b: 50 }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "rect", xref: "x", yref: "paper", x0: py - 0.5, x1: py + 0.5, y0: 0, y1: 1, fillcolor: css("--grid"), opacity: 0.5, line: { width: 0 }, layer: "below" }] });

    const cl = (name, key, color, dash, symbol) => ({ name, x: yr.map((r) => r.year), y: yr.map((r) => r[key]), mode: "lines+markers",
      line: { color, width: 2, dash }, marker: { size: 7, symbol } });
    plot("c-collab-year", [
      cl("Indian institutions", "collab_inst_indian", css("--lab-3"), "solid", "circle"),
      cl(`Indian, without ${HYPER}+ author papers`, "collab_inst_indian_excl_hyper", css("--lab-3"), "dot", "diamond"),
      cl("Foreign institutions", "collab_inst_foreign", css("--lab-2"), "solid", "circle"),
      cl(`Foreign, without ${HYPER}+ author papers`, "collab_inst_foreign_excl_hyper", css("--lab-2"), "dot", "diamond")],
      { hovermode: "x unified", xaxis: { dtick: 1 }, yaxis: { title: "Distinct institutions" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const hist = P2.if_histogram.filter((r) => r.scope === state.lab);
    const bx = hist.map((r) => r.bin_start + 0.5);
    plot("c-ifdist", [
      { type: "bar", name: "Q1", x: bx, y: hist.map((r) => r.q1_papers), marker: { color: css("--q1") }, width: 0.92,
        hovertemplate: "<b>%{y}</b> Q1 papers<extra></extra>" },
      { type: "bar", name: "Other quartiles / unranked", x: bx, y: hist.map((r) => r.papers - r.q1_papers), marker: { color: css("--qna") }, width: 0.92,
        hovertemplate: "<b>%{y}</b> other papers<extra></extra>" }],
      { barmode: "stack", xaxis: { title: "Journal impact factor (last bin = 20 and above)", range: [0, 21] }, yaxis: { title: "Papers" },
        shapes: [IF1, IF2].map((x) => ({ type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1, line: { color: css("--ink"), width: 1, dash: "dash" } })),
        annotations: [IF1, IF2].map((x) => ({ x, y: 1, yref: "paper", text: `IF ${x}`, showarrow: false, yanchor: "bottom", font: { size: 12, color: css("--ink-2") } })),
        margin: { l: 50, r: 16, t: 28, b: 40 }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    renderLabCorpus();
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

  function renderLabCorpus() {   // publication statistics over every lab paper, including those with no roster scientist
    const C = P2.lab_corpus;
    if (!C) return;
    const rows = C.filter((r) => r.scope === state.lab);
    table("t-corpus", rows, [
      { title: "Counted over", field: "basis", widthGrow: 3 }, { title: "Papers", field: "papers", hozAlign: "right" },
      { title: "Share", field: "share_of_lab_papers", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Citations", field: "citations", hozAlign: "right" }, { title: "Q1", field: "q1_papers", hozAlign: "right" },
      { title: "Q1 share", field: "q1_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Quartile known", field: "quartile_known_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: `Q1, IF>${IF1}`, field: `q1_if_gt${IF1}`, hozAlign: "right" }, { title: `Q1, IF>${IF2}`, field: `q1_if_gt${IF2}`, hozAlign: "right" },
      { title: `<${MULTI} authors`, field: `papers_lt${MULTI}`, hozAlign: "right" }, { title: `${MULTI}+ authors`, field: `papers_ge${MULTI}`, hozAlign: "right" }],
      { layout: "fitColumns", maxHeight: 200 });
    const y = (P2.lab_corpus_yearly || []).filter((r) => r.scope === state.lab);
    plot("c-corpus", [
      { type: "bar", name: "With a roster scientist (faculty-attributed)", x: y.map((r) => r.year), y: y.map((r) => r.papers_faculty), marker: { color: css("--lab-1") } },
      { type: "bar", name: "Without one (students, postdocs, staff, unlisted scientists)", x: y.map((r) => r.year), y: y.map((r) => r.papers_without_roster_scientist), marker: { color: css("--qna") } }],
      { barmode: "stack", xaxis: { dtick: 1 }, yaxis: { title: "Lab-affiliated papers" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });
  }

  // ---------------------------------------------------------------- tab: faculty comparison
  const CMP = [["papers", "Papers"], ["q1_papers", "Q1 papers"], ["citations", "Citations"],
    ["citations_excl_hyper", `Citations excluding ${HYPER}+ author papers`], ["collab_inst_excl_hyper", `Collaborating institutions (without ${HYPER}+ author papers)`],
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
    top("papers", "c-top-prod"); top("degree", "c-top-conn");

    table("t-fcomp", rows.map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name", headerFilter: "input", frozen: true, minWidth: 150 }, { title: "Lab", field: "lab", headerFilter: "input" },
      { title: "Department", field: "department", maxWidth: 220 },
      { title: "Papers", field: "papers", hozAlign: "right", sorter: "number" }, { title: "Q1", field: "q1_papers", hozAlign: "right", sorter: "number" },
      { title: `Q1, IF>${IF1}`, field: `q1_if_gt${IF1}`, hozAlign: "right", sorter: "number" }, { title: `Q1, IF>${IF2}`, field: `q1_if_gt${IF2}`, hozAlign: "right", sorter: "number" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: `Cit. excl. ${HYPER}+`, field: "citations_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: `% cit. from ${HYPER}+`, field: "cit_share_hyper", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "h", field: "h_all", hozAlign: "right", sorter: "number" }, { title: `h excl. ${HYPER}+`, field: "h_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: `Collab. inst. excl. ${HYPER}+`, field: "collab_inst_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: "Co-author links", field: "degree", hozAlign: "right", sorter: "number" },
      { title: "Mean IF", field: "mean_if", hozAlign: "right", sorter: "number", formatter: ifFmt },
      { title: "Flag", field: "flag", widthGrow: 3, formatter: "textarea" }], { maxHeight: 520, initialSort: [{ column: "papers", dir: "desc" }] });

    const pick = el("f-pick"), keep = pick.value;
    pick.replaceChildren();
    [...rows].sort((a, b) => b.papers - a.papers).forEach((r) => { const o = document.createElement("option"); o.value = r.faculty_id;
      o.textContent = `${r.name} (${short(r.lab)}, ${r.papers} papers)`; pick.append(o); });
    if ([...pick.options].some((o) => o.value === keep)) pick.value = keep;
    renderDepts();
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
          "border-width": 1.5, "border-color": css("--surface"), label: "data(label)", "font-size": 12, color: css("--ink"),
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
    const flaggedNG = cit.filter((r) => r.flag_non_government && r.norm_group);
    const nAssessed = flaggedNG.length, nOut = flaggedNG.filter((r) => r.flag_norm_outlier).length;
    kpis("kpis-flags", [
      [`Papers with ${HYPER}+ authors`, fmt((o[`papers_${HYPER}-999`] || 0) + (o["papers_1000+"] || 0)), `${pct(((o[`papers_${HYPER}-999`] || 0) + (o["papers_1000+"] || 0)) / o.papers, 1)} of papers`],
      ["Their share of citations", pct(hyperShare, 1), `${fmt((o[`citations_${HYPER}-999`] || 0) + (o["citations_1000+"] || 0))} citations`],
      ["Faculty flagged", fmt(fac.filter((r) => r.flag_hyper || r.flag_multi).length), `of ${fmt(fac.length)} (rules below)`],
      ["Lifetime-citation flags", fmt(fac.filter((r) => r.flag_lifetime).length), `≥ ${fmt(TH.lifetime_flag_citations)} lifetime, or a large lifetime count mostly outside 2016–26`],
      ["Heavy citing institutions", fmt(cit.filter((r) => r.flag_heavy).length), `≥ ${TH.citer_min_cites} citations into the lab`],
      ["Heavy, few shared papers", fmt(cit.filter((r) => r.flag_citation_heavy_vs_collab).length), `≥ ${TH.citer_ratio_min} citations per shared paper`],
      ["Flagged non-government", fmt(cit.filter((r) => r.flag_non_government).length), "private, heavy, few shared papers"],
      ["Still outliers after size adjustment", `${fmt(nOut)} of ${fmt(nAssessed)}`, `citations per 1,000 papers, z ≥ ${TH.citer_norm_z}`],
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
      { barmode: "stack", xaxis: { tickformat: ".0%", range: [0, 1] }, yaxis: { autorange: "reversed" }, margin: { l: 70, r: 10, t: 10, b: 50 }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, traceorder: "normal" } });

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
    renderLifetime(fac);
    renderCiters();
    renderNotes();
  }

  function renderLifetime(fac) {   // "a few top faculty got 1 lakh citations": lifetime OpenAlex citations vs the 2016-26 count
    if (!fac.length || fac[0].lifetime_citations === undefined) return;
    const pts = fac.filter((r) => r.lifetime_citations > 0);
    plot("c-life", scopes().map((lab) => {
      const rr = pts.filter((r) => r.lab === lab);
      return { type: "scatter", mode: "markers+text", name: short(lab), x: rr.map((r) => Math.max(r.citations, 1)), y: rr.map((r) => r.lifetime_citations),
        text: rr.map((r) => r.flag_lifetime ? r.name : ""), textposition: "middle right", textfont: { size: 12, color: css("--ink-2") },
        customdata: rr.map((r) => [r.name, r.flag_lifetime_reason || "", r.window_share_of_lifetime]),
        marker: { size: rr.map((r) => r.flag_lifetime ? 12 : 7), color: labColor(lab), opacity: 0.8, symbol: rr.map((r) => r.flag_lifetime ? "diamond" : "circle"),
          line: { color: rr.map((r) => r.flag_lifetime ? css("--ink") : css("--surface")), width: rr.map((r) => r.flag_lifetime ? 2 : 1) } },
        hovertemplate: "<b>%{customdata[0]}</b><br>%{x:,} citations on 2016–26 lab papers<br>%{y:,} lifetime citations (OpenAlex)<br>%{customdata[2]:.1%} of lifetime in the window<br><i>%{customdata[1]}</i><extra>" + short(lab) + "</extra>" };
    }), { xaxis: { type: "log", title: "Citations on 2016–2026 lab papers" }, yaxis: { type: "log", title: "Lifetime citations (all OpenAlex profiles of the person)" },
      shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: TH.lifetime_flag_citations, y1: TH.lifetime_flag_citations, line: { color: css("--muted"), width: 1, dash: "dash" } }],
      annotations: [{ x: 0, xref: "paper", y: Math.log10(TH.lifetime_flag_citations), yref: "y", text: "1 lakh", showarrow: false, xanchor: "left", yanchor: "bottom", font: { size: 12, color: css("--muted") } }],
      hovermode: "closest", legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });
    table("t-life", fac.filter((r) => r.flag_lifetime).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name", frozen: true, minWidth: 150 }, { title: "Lab", field: "lab" },
      { title: "Lifetime citations", field: "lifetime_citations", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue()) },
      { title: "2016–26 citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: "Share in the window", field: "window_share_of_lifetime", hozAlign: "right", formatter: (c) => pct(c.getValue(), 1) },
      { title: "Largest profile", field: "lifetime_top_profile" },
      { title: "Its share", field: "lifetime_top_profile_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Why flagged", field: "flag_lifetime_reason", widthGrow: 3, formatter: "textarea" }], { maxHeight: 360, initialSort: [{ column: "lifetime_citations", dir: "desc" }] });
  }

  function renderCiters() {
    const own = el("own-filter").value;
    const rows = P2.citers.filter((r) => r.scope === state.lab && (own === "all" || r.ownership === own));
    const owners = ["government", "government-aided", "private", "international", "unclassified"];
    // label only what matters, so the points stay readable: the 10 largest flagged institutions and the 4 largest overall
    const labelled = new Set([...rows.filter((r) => r.flag_non_government).sort((a, b) => b.cites_in - a.cites_in).slice(0, 10),
      ...[...rows].sort((a, b) => b.cites_in - a.cites_in).slice(0, 4)].map((r) => r.partner_inst));
    plot("c-citers2", owners.map((ow) => {
      const rr = rows.filter((r) => r.ownership === ow);
      return { type: "scatter", mode: "markers+text", name: ow, x: rr.map((r) => Math.max(r.shared_papers, 0.8)), y: rr.map((r) => r.cites_in),
        text: rr.map((r) => labelled.has(r.partner_inst) ? abbr(r.partner_inst, 22) : ""), textposition: "top center", textfont: { size: 12, color: css("--ink-2") },
        marker: { size: rr.map((r) => r.flag_non_government ? 13 : 8), color: ownColor(ow), opacity: 0.8, line: { color: rr.map((r) => r.flag_non_government ? css("--ink") : css("--surface")), width: rr.map((r) => r.flag_non_government ? 2 : 1) } },
        customdata: rr.map((r) => [r.partner_inst, r.shared_papers, r.cites_per_shared_paper]),
        hovertemplate: "<b>%{customdata[0]}</b><br>%{y:,} citations into the lab(s)<br>%{customdata[1]} shared papers · %{customdata[2]:.1f} per shared paper<extra>" + ow + "</extra>" };
    }), { xaxis: { type: "log", title: "Shared papers (co-authored with the lab; 0 shown as 0.8)", tickvals: [1, 3, 10, 30, 100, 300], ticktext: ["1", "3", "10", "30", "100", "300"], range: [Math.log10(0.6), Math.log10(500)] },
      yaxis: { type: "log", title: "Citations received from the institution", rangemode: "normal", tickvals: [30, 100, 300, 1000, 3000], ticktext: ["30", "100", "300", "1,000", "3,000"] },
      shapes: [{ type: "line", xref: "x", yref: "y", x0: 0.8, x1: 300, y0: 0.8 * TH.citer_ratio_min, y1: 300 * TH.citer_ratio_min, line: { color: css("--muted"), width: 1, dash: "dash" } },
               { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: TH.citer_min_cites, y1: TH.citer_min_cites, line: { color: css("--muted"), width: 1, dash: "dot" } }],
      annotations: [{ x: 1, xref: "paper", y: Math.log10(TH.citer_min_cites), yref: "y", text: `${TH.citer_min_cites} citations`, showarrow: false, xanchor: "right", yanchor: "bottom", font: { size: 12, color: css("--muted") } }],
      legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    renderCiterRates();

    table("t-citers", rows.map((r) => ({ ...r, flags: [r.flag_norm_outlier ? "outlier after size adjustment" : "", r.flag_non_government ? "non-government, heavy, few shared papers" : "", r.flag_citation_heavy_vs_collab && !r.flag_non_government ? "heavy, few shared papers" : "", r.flag_heavy && !r.flag_citation_heavy_vs_collab ? "heavy" : ""].filter(Boolean).join("; ") })), [
      { title: "Institution", field: "partner_inst", headerFilter: "input", widthGrow: 3, frozen: true },
      { title: "Ownership", field: "ownership" }, { title: "Cluster", field: "partner_cluster" },
      { title: "Cites in", field: "cites_in", hozAlign: "right", sorter: "number" }, { title: "Cites out", field: "cites_out", hozAlign: "right", sorter: "number" },
      { title: "Shared papers", field: "shared_papers", hozAlign: "right", sorter: "number" },
      { title: "Cites per shared paper", field: "cites_per_shared_paper", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 1) },
      { title: "Papers in the labs' fields, 2016–26", field: "works_ls", hozAlign: "right", sorter: "number", formatter: (c) => c.getValue() == null ? "–" : fmt(c.getValue()) },
      { title: "Cites per 1,000 such papers", field: "rate_per_1000", hozAlign: "right", sorter: "number", formatter: (c) => c.getValue() == null ? "–" : fmt(c.getValue(), 1) },
      { title: "× expected for its size", field: "obs_exp", hozAlign: "right", sorter: "number", formatter: (c) => c.getValue() == null ? "–" : fmt(c.getValue(), 2) },
      { title: "Flags", field: "flags", widthGrow: 2, formatter: "textarea" }], { maxHeight: 440, initialSort: [{ column: "cites_in", dir: "desc" }] });

    const ev = P2.citer_evidence.filter((r) => own === "all" || r.ownership === own);
    el("ev-note").textContent = state.lab === "ALL" ? "" : "Evidence is computed on all four labs combined, so it does not change with the selected lab.";
    table("t-evidence", ev, [
      { title: "Institution", field: "partner_inst", widthGrow: 3, frozen: true }, { title: "Ownership", field: "ownership" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" }, { title: "Citing papers", field: "citing_papers", hozAlign: "right", sorter: "number" },
      { title: "Shared papers", field: "shared_papers", hozAlign: "right", sorter: "number" },
      { title: "Top citing author's share of citing papers", field: "top_citing_author_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Citations on a paper sharing an author with the cited paper", field: "shared_author_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Citing papers with a current or former lab scientist on them", field: "lab_member_paper_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Review articles among citing papers", field: "review_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Book chapters", field: "book_chapter_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Top citing journal", field: "top_citing_journal", widthGrow: 2 },
      { title: "Its share", field: "top_citing_journal_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Share on one of our papers", field: "top_cited_paper_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }],
      { maxHeight: 460, initialSort: [{ column: "citations", dir: "desc" }] });
  }

  function renderCiterRates() {   // size-normalised view: citations given per 1,000 papers of the institution in the labs' fields
    const ng = P2.citers.filter((r) => r.scope === state.lab && r.norm_group);
    const box = el("c-citers-norm");
    if (ng.length < 5) { box.textContent = "Too few institutions clear the thresholds for this lab to compare."; return; }
    const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor((s.length - 1) * p)]; };
    const lr = ng.map((r) => Math.log10(r.rate_per_1000)), med = q(lr, 0.5), mad = 1.4826 * q(lr.map((v) => Math.abs(v - med)), 0.5);
    const thr = Math.pow(10, med + TH.citer_norm_z * mad);
    const jit = (s) => { let h = 0; for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) | 0; return ((h >>> 0) % 1000) / 1000 - 0.5; };
    const order = ["government", "government-aided", "private", "international", "unclassified"], groups = order.filter((ow) => ng.some((r) => r.ownership === ow));
    // a few labels only, placed on alternating sides so neighbours in a dense row do not print over each other
    const namedList = [...new Set([...ng.filter((r) => r.flag_non_government).sort((a, b) => b.rate_per_1000 - a.rate_per_1000).slice(0, 2),
      ...[...ng].sort((a, b) => b.rate_per_1000 - a.rate_per_1000).slice(0, 4)].map((r) => r.partner_inst))];
    const spots = ["top right", "top left", "bottom right", "bottom left", "top center", "bottom center"];
    const placed = new Map(namedList.map((n, i) => [n, spots[i % spots.length]]));
    const traces = groups.map((ow, k) => {
      const rr = ng.filter((r) => r.ownership === ow);
      return { type: "scatter", mode: "markers+text", showlegend: false, name: ow, x: rr.map((r) => r.rate_per_1000), y: rr.map((r) => k + 0.34 * jit(r.partner_inst)),
        text: rr.map((r) => placed.has(r.partner_inst) ? abbr(r.partner_inst, 22) : ""), textposition: rr.map((r) => placed.get(r.partner_inst) || "top center"), textfont: { size: 12, color: css("--ink-2") },
        marker: { size: rr.map((r) => r.flag_non_government ? 12 : 7), color: ownColor(ow), opacity: 0.78,
          line: { color: rr.map((r) => r.flag_non_government ? css("--ink") : css("--surface")), width: rr.map((r) => r.flag_non_government ? 2 : 0.6) } },
        customdata: rr.map((r) => [r.partner_inst, r.cites_in, r.works_ls, r.obs_exp, r.shared_papers]),
        hovertemplate: "<b>%{customdata[0]}</b><br>%{x:.0f} citations per 1,000 papers<br>%{customdata[1]:,} citations ÷ %{customdata[2]:,} papers in the labs' fields<br>%{customdata[3]:.1f}× the expected count · %{customdata[4]} shared papers<extra>" + ow + "</extra>" };
    });
    traces.push({ type: "scatter", mode: "markers", showlegend: false, name: "group median", x: groups.map((ow) => q(ng.filter((r) => r.ownership === ow).map((r) => r.rate_per_1000), 0.5)),
      y: groups.map((_, k) => k), marker: { symbol: "line-ns-open", size: 30, color: css("--ink"), line: { color: css("--ink"), width: 2 } },
      hovertemplate: "median %{x:.0f} per 1,000 papers<extra></extra>" });
    plot("c-citers-norm", traces, { xaxis: { type: "log", title: "Citations given to the lab(s) per 1,000 papers of the institution in the labs' fields", tickvals: [10, 30, 100, 300, 1000], ticktext: ["10", "30", "100", "300", "1,000"] },
      yaxis: { tickmode: "array", tickvals: groups.map((_, k) => k), ticktext: groups.map((ow) => `${ow} (${ng.filter((r) => r.ownership === ow).length})`), range: [-0.6, groups.length - 0.4], zeroline: false, rangemode: "normal", automargin: true },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: thr, x1: thr, y0: 0, y1: 1, line: { color: css("--muted"), width: 1, dash: "dash" } }],
      annotations: [{ x: Math.log10(thr), xref: "x", y: 1, yref: "paper", text: `outlier line (z ≥ ${TH.citer_norm_z})`, showarrow: false, xanchor: "left", yanchor: "top", font: { size: 12, color: css("--muted") } }] });
  }

  // ---------------------------------------------------------------- departments
  function renderDepts() {
    const hide = el("dept-small").checked;
    const rows = P2.departments.filter((r) => (state.lab === "ALL" || r.lab === state.lab) && !(hide && r.small));
    const maxC = Math.max(1, ...rows.map((r) => r.cites_per_paper || 0));
    plot("c-dept", LABS.filter((l) => rows.some((r) => r.lab === l)).map((lab) => {
      const rr = rows.filter((r) => r.lab === lab);
      return { type: "scatter", mode: "markers", name: short(lab), x: rr.map((r) => r.papers_per_faculty), y: rr.map((r) => r.q1_share),
        customdata: rr.map((r) => [r.department, r.faculty, r.papers, r.cites_per_paper, r.collab_inst, r.flagged_faculty]),
        marker: { size: rr.map((r) => 8 + 26 * Math.sqrt((r.cites_per_paper || 0) / maxC)), color: labColor(lab), opacity: 0.78, line: { color: css("--surface"), width: 1 } },
        hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} faculty · %{customdata[2]} papers<br>%{x:.1f} papers per faculty<br>Q1 share %{y:.0%}<br>%{customdata[3]:.1f} citations per paper<br>%{customdata[4]} collaborating institutions · %{customdata[5]} faculty flagged<extra>" + short(lab) + "</extra>" };
    }), { xaxis: { title: "Papers per faculty member, 2016–2026", rangemode: "tozero" }, yaxis: { title: "Share of journal papers in Q1 journals", tickformat: ".0%", range: [0, 1] }, hovermode: "closest" });
    table("t-dept", rows.map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Lab", field: "lab", headerFilter: "input", frozen: true }, { title: "Department", field: "department", headerFilter: "input", widthGrow: 3, minWidth: 220 },
      { title: "Faculty", field: "faculty", hozAlign: "right", sorter: "number" }, { title: "Papers", field: "papers", hozAlign: "right", sorter: "number" },
      { title: "Papers / faculty", field: "papers_per_faculty", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 1) },
      { title: "Q1 share", field: "q1_share", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: `Q1, IF>${IF1}`, field: `q1_if_gt${IF1}`, hozAlign: "right", sorter: "number" }, { title: `Q1, IF>${IF2}`, field: `q1_if_gt${IF2}`, hozAlign: "right", sorter: "number" },
      { title: "Mean IF", field: "mean_if", hozAlign: "right", sorter: "number", formatter: ifFmt },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: "Cites / paper", field: "cites_per_paper", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 1) },
      { title: `% cit. from ${HYPER}+`, field: "cit_share_hyper", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Collab. inst.", field: "collab_inst", hozAlign: "right", sorter: "number" },
      { title: `Collab. inst. excl. ${HYPER}+`, field: "collab_inst_excl_hyper", hozAlign: "right", sorter: "number" },
      { title: "Faculty flagged", field: "flagged_faculty", hozAlign: "right", sorter: "number" },
      { title: "Small", field: "small", formatter: (c) => c.getValue() ? "< 3 faculty" : "" }], { maxHeight: 440, initialSort: [{ column: "papers", dir: "desc" }] });
  }

  // ---------------------------------------------------------------- how much does the impact-factor source matter?
  function renderIfSens() {
    const rows = (P2.summary.if_sensitivity || []).map((r, i) => ({ ...r, used: i === 0 }));
    table("t-ifsens", rows, [
      { title: "Impact factor taken from", field: "source", widthGrow: 4, formatter: (c) => (c.getRow().getData().used ? "▸ " : "") + c.getValue() },
      { title: "Q1 papers with a value", field: "journals_with_value_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: `Q1 papers, IF > ${IF1}`, field: `q1_if_gt${IF1}`, hozAlign: "right", sorter: "number" },
      { title: `Q1 papers, IF > ${IF2}`, field: `q1_if_gt${IF2}`, hozAlign: "right", sorter: "number" }], { layout: "fitColumns", maxHeight: 230 });
  }

  // ---------------------------------------------------------------- the questions we ask, answered from the data on the other tabs
  function renderQuestions() {
    const card = el("rq-card"), box = el("rq");
    card.hidden = false; box.replaceChildren();
    const A = ovRow("ALL"), labsOv = LABS.map((l) => ovRow(l)), S = P2.summary, N = S.citer_normalised || {}, sens = S.if_sensitivity || [];
    const by = (key, dir) => [...labsOv].sort((a, b) => dir * (b[key] - a[key]))[0];
    const big = by("papers", 1), hi = by("q1_share", 1), lo = by("q1_share", -1);
    const fac = P2.faculty, ord = (k) => [...fac].sort((a, b) => (b[k] || 0) - (a[k] || 0));
    const topId = (k, n) => new Set(ord(k).slice(0, n).map((r) => r.faculty_id));
    const both = [...topId("citations", 10)].filter((x) => topId("degree", 10).has(x)).length;
    const rankX = (r) => 1 + fac.filter((f) => (f.citations_excl_hyper || 0) > (r.citations_excl_hyper || 0)).length;
    const shift = ord("citations").slice(0, 4).map(rankX);
    const hyperN = (A[`papers_${HYPER}-999`] || 0) + (A["papers_1000+"] || 0);
    const hyperC = (A[`citation_share_${HYPER}-999`] || 0) + (A["citation_share_1000+"] || 0);
    const flagged = fac.filter((r) => r.flag_hyper || r.flag_multi).length;
    const years = P2.temporal_network.filter((r) => r.scope === "ALL" && r.mode === "cumulative"), last = years.reduce((a, b) => (b.year > a.year ? b : a));
    const med = N.median_rate || {}, nums = sens.map((r) => r[`q1_if_gt${IF2}`]);
    const items = [
      ["How productive are the labs, and how much of their work appears in high-impact journals?", "impact",
        `${short(big.scope)} publishes the most (${fmt(big.papers)} papers). The Q1 share runs from ${pct(lo.q1_share, 0)} (${short(lo.scope)}) to ${pct(hi.q1_share, 0)} (${short(hi.scope)}). ${pct(A[`q1_if_gt${IF1}_share_of_q1`], 0)} of Q1 papers are in journals with IF above ${IF1}, and ${pct(A[`q1_if_gt${IF2}_share_of_q1`], 0)} above ${IF2}.`],
      ["Do the same faculty lead on output, citations and connections?", "compare",
        `${ord("papers")[0].name} leads on papers, ${ord("citations")[0].name} on citations and ${ord("degree")[0].name} on co-author links. ${both} of the ten most cited faculty are also among the ten most connected.`],
      ["Do a few many-author papers distort the citation counts?", "flags",
        `${fmt(hyperN)} papers with ${HYPER}+ authors (${pct(hyperN / A.papers, 1)} of papers) carry ${pct(hyperC, 1)} of all citations. ${fmt(flagged)} faculty are flagged, and the four most cited faculty fall from ranks 1–4 to ranks ${Math.min(...shift)}–${Math.max(...shift)} without those papers.`],
      ["Is the labs' collaboration real, or inflated by consortium papers?", "instnet",
        `${fmt(A.collab_inst_all)} institutions appear on the labs' papers, but ${fmt(A.collab_inst_all_excl_hyper)} once papers with ${HYPER}+ authors are set aside. Only ${pct(last.cross_lab_links / last.links, 1)} of faculty co-authorship links (${fmt(last.cross_lab_links)} of ${fmt(last.links)}) join different labs.`],
      ["Do private institutions cite the labs more than their size explains?", "flags",
        `Raw counts flag ${fmt(N.flagged_before)} private institutions. Per 1,000 papers in the labs' fields, ${fmt(N.flagged_still_outliers)} of ${fmt(N.flagged_assessed)} still stand out (median ${fmt(med.private, 0)} for private institutions against ${fmt(med.government, 0)} for government ones).`],
      ["How much do the headline counts depend on the impact-factor source?", "impact",
        `Q1 papers above IF ${IF1}: ${fmt(sens[0] && sens[0][`q1_if_gt${IF1}`])} with the sources we use, up to ${fmt(Math.max(...sens.map((r) => r[`q1_if_gt${IF1}`])))} if a free substitute is used for every journal. Above IF ${IF2} the counts stay between ${fmt(Math.min(...nums))} and ${fmt(Math.max(...nums))}.`],
    ];
    items.forEach(([q, tab, a]) => {
      const d = document.createElement("div"); d.className = "rqi";
      const h = document.createElement("h3"); h.textContent = q;
      const p = document.createElement("p"); p.textContent = a;
      const b = document.createElement("button"); b.type = "button"; b.className = "linkbtn"; b.textContent = "See the evidence →";
      b.addEventListener("click", () => { show(tab); window.scrollTo(0, 0); });
      d.append(h, p, b); box.append(d);
    });
  }

  // ---------------------------------------------------------------- tab: research findings (step s17)
  function renderFindings() {
    const R = P2.research;
    if (!R) { el("fd-list").textContent = "Run step s17 to compute the research analyses."; return; }
    const S = R.summary, H = S.homophily;
    const aud = (R.citation_audience || []).filter((r) => r.citing_scope === "ALL");
    const share = (cls) => (aud.find((r) => r.class === cls) || {}).share || 0;
    const exAll = (R.lab_exchange_null || []).filter((r) => r.basis.startsWith("independent") && r.null.includes("fields"));
    const within = exAll.find((r) => r.cited_lab === "within-lab share") || {};
    const withinYear = (R.lab_exchange_null || []).find((r) => r.basis.startsWith("independent") && r.null === "same cited year" && r.cited_lab === "within-lab share") || {};
    const diag = exAll.filter((r) => r.citing_lab === r.cited_lab);
    const offd = exAll.filter((r) => LABS.includes(r.citing_lab) && r.citing_lab !== r.cited_lab);
    const orSame = (R.coauthor_model || []).filter((r) => r.term === "same_lab");
    const orFull = orSame.find((r) => r.model.includes("department")) || {}, orTopic = orSame.find((r) => r.model === "same lab + topic similarity + size") || {};
    const dl = (R.distance_lift || []).filter((r) => r.basis === "independent citations");
    const lift = (d) => (dl.find((r) => r.distance === d) || {}).lift;
    const led = (R.led_vs_middle || []).filter((r) => r.scope === "ALL");
    const L = led.find((r) => r.role === "lab-led") || {}, M = led.find((r) => r.role !== "lab-led") || {};
    const pers = R.tie_persistence || [];
    const same = pers.find((r) => r.pair_type === "same lab") || {}, cross = pers.find((r) => r.pair_type === "cross-lab") || {};
    const imp = (R.lab_impact || []).filter((r) => r.term.startsWith("lab:") && r.model !== "lab only");
    const cov = (R.covid || []).filter((r) => LABS.includes(r.scope));
    const peak = LABS.map((l) => { const rr = cov.filter((r) => r.scope === l); return rr.reduce((a, b) => (b.covid_share > (a.covid_share || 0) ? b : a), {}); });
    const fw = R.flow_window || [], fwAll = fw.filter((r) => r.scope === "ALL");
    const fwTot = (sc) => { const rr = fw.filter((r) => r.scope === sc); const i = rr.reduce((a, r) => a + r.in_window, 0), o = rr.reduce((a, r) => a + r.out_window, 0); return o ? i / o : NaN; };
    const firstAbove = (fwAll.find((r) => r.ratio_window > 1) || {}).cohort;
    const fc = R.faculty_credit || [], top10 = fc.filter((r) => r.rank_citations <= 10).sort((a, b) => a.rank_citations - b.rank_citations);
    const fracLead = fc.find((r) => r.rank_citations_frac === 1) || {};
    const lc = R.lab_credit || [], lcOf = (sc) => lc.find((r) => r.scope === sc) || {};
    const items = [
      ["Most citations inside the corpus are self-citations.", `${pct(share("self (shared author)"), 0)} of the ${fmt(S.internal_citations)} citations between our papers have an author in common, and another ${pct(share("co-author network"), 0)} come from faculty who had already written together. Only ${pct(share("same lab, independent") + share("other lab, independent"), 0)} are independent.`,
        "Every internal-network measure (PageRank, in-degree, lab-to-lab flows) is mostly a measure of research groups building on their own work."],
      ["Labs cite their own work far more than chance predicts, even among independent citations.", `Among independent citations, ${pct(within.observed, 0)} stay inside the citing lab against ${pct(within.expected, 0)} expected when every paper keeps its citation counts, year and field. Within-lab citation runs at ${diag.map((r) => `${short(r.citing_lab)} ${fmt(r.obs_exp, 1)}×`).join(", ")} the chance level; ${offd.filter((r) => r.obs_exp < 1 && r.q_bh < 0.05).length} of 12 cross-lab cells are significantly below it.`,
        `Topic explains only part of it: keeping just the year, chance would give ${pct(withinYear.expected, 0)}; holding fields as well raises that to ${pct(within.expected, 0)}, still well below what we observe.`],
      ["The four labs barely co-author, and topic does not explain it.", `${pct(H.cross_lab_share_observed, 1)} of faculty co-author links cross labs, against ${pct(H.cross_lab_share_label_permutation, 0)} if lab labels were shuffled (z = ${fmt(H.cross_lab_z_permutation, 0)}). Same-lab pairs are ${fmt(orTopic.odds_ratio, 0)}× more likely to co-author after controlling for topic similarity and output (95% CI ${fmt(orTopic.or_low, 0)}–${fmt(orTopic.or_high, 0)}), and still ${fmt(orFull.odds_ratio, 0)}× within the same department.`,
        "Institutional boundaries shape collaboration between CSIR labs far more than research interests do; sharing a department adds little once the lab is known."],
      ["Citations follow co-authorship distance.", `Independent citations between faculty who are co-authors are ${fmt(lift("1"), 1)}× what citation volumes predict; at distance 2 (a shared co-author) ${fmt(lift("2"), 1)}×, at 3 ${fmt(lift("3"), 1)}×, and between unconnected faculty ${fmt(lift("not connected"), 2)}×.`,
        "The same distance decay Singh et al. (2020) found in physics: knowledge flows along social ties, but only for about two steps."],
      ["A third of citations come from papers the labs do not lead.", `Middle-author papers are ${pct(M.share_of_papers, 0)} of papers but ${pct(M.share_of_citations, 0)} of citations, at ${fmt(M.mean_norm_citations, 2)}× the field-and-year average against ${fmt(L.mean_norm_citations, 2)}× for lab-led papers (median authors ${fmt(M.median_authors)} vs ${fmt(L.median_authors)}).`,
        "Middle-author papers have larger teams; compared within the same team size they are cited about as often as lab-led papers. Headline counts therefore depend heavily on taking part in large collaborations."],
      ["Cross-lab collaborations are less durable.", `${pct(same.share, 0)} of new same-lab pairs (2016–2022) wrote together again within three years, against ${pct(cross.share, 0)} of cross-lab pairs${cross.fisher_p_cross_vs_same !== undefined ? ` (Fisher p = ${Number(cross.fisher_p_cross_vs_same).toPrecision(2)})` : ""}. A shared co-author makes a new link ${fmt(S.triadic_closure_mean_lift, 0)}× more likely in a given year.`,
        "Collaboration grows by closing triangles inside each lab; ties that cross labs are often one-off."],
      ["Raw averages overstate CCMB and IGIB.", `On a log scale, which damps the few huge papers, and with year, field, team size and review type held equal, single-lab papers differ from CDRI's by ${imp.map((r) => `${short(r.term.replace("lab: ", ""))} ${r.pct_effect >= 0 ? "+" : ""}${fmt(r.pct_effect, 0)}% (${fmt(r.pct_low, 0)} to ${fmt(r.pct_high, 0)})`).join(", ")}.`,
        "Raw citations per paper (Overview) put CCMB and IGIB ahead because of a few very highly cited consortium papers; the typical CCMB or IGIB paper is cited less than a CDRI paper, and the typical IMTECH paper more."],
      ["Indian institutions cite the labs more than the labs cite them, and have done so since " + (firstAbove || "the start") + ".", `Counted over the same two-year window, papers of each year receive ${fmt(fwTot("ALL"), 2)}× as many Indian citations as they give (2016–${fwAll.length ? fwAll[fwAll.length - 1].cohort : ""} cohorts): ${LABS.map((l) => `${short(l)} ${fmt(fwTot(l), 2)}×`).join(", ")}. The raw yearly counts suggest outflow led until 2022, but that is citation lag: recent papers have not yet been cited.`,
        "The labs are net sources of knowledge for Indian science, IMTECH and IGIB most of all; comparisons of in and out flows need equal windows."],
      ["Who leads depends on how credit is counted.", `Of the ten most cited faculty, ${top10.filter((r) => r.rank_citations_frac > 25).length} fall below rank 25 when each citation is divided among a paper's authors; ${fracLead.name || ""} leads under fractional counting (rank ${fmt(fracLead.rank_citations)} on full counts).`,
        "Rankings by raw citations mostly reward membership of large consortia; report fractional counts beside them."],
      ["A few papers carry CCMB's citations.", `CCMB's citations spread like ${fmt(lcOf("CSIR-CCMB").effective_papers, 0)} equally cited papers (its top paper alone is ${pct(lcOf("CSIR-CCMB").top_paper_share, 0)}), against ${fmt(lcOf("CSIR-CDRI").effective_papers, 0)} at CDRI. Field-and-year normalised, the four labs are close: MNCS ${LABS.map((l) => `${short(l)} ${fmt(lcOf(l).mncs, 2)}`).join(", ")}, with overlapping intervals.`,
        "Totals and averages for CCMB depend on a handful of consortium and guideline papers; normalised and median measures are fairer."],
      ["COVID-19 reshaped the genomics labs.", `SARS-CoV-2 / COVID-19 papers peaked at ${peak.map((r, i) => `${short(LABS[i])} ${pct(r.covid_share, 0)} (${r.year})`).join(", ")} of each lab's yearly output.`,
        "A sudden, mission-driven shift that the 2021 output peak and the consortium papers both reflect."],
    ];
    const box = el("fd-list"); box.replaceChildren();
    items.forEach(([h, a, so]) => { const d = document.createElement("div"); d.className = "rqi";
      d.append(txt("h3", h), txt("p", a), txt("p", so, "muted")); box.append(d); });

    const classes = ["self (shared author)", "co-author network", "same lab, independent", "other lab, independent"];
    const cc = [css("--lab-2"), css("--lab-4"), css("--lab-1"), css("--lab-3")], scs = [...LABS, "ALL"];
    plot("c-fd-aud", classes.map((c, i) => ({ type: "bar", orientation: "h", name: c, y: scs.map(scopeLabel),
      x: scs.map((s) => ((R.citation_audience || []).find((r) => r.citing_scope === s && r.class === c) || {}).share || 0),
      marker: { color: cc[i], line: { color: css("--surface"), width: 1 } },
      hovertemplate: `<b>%{x:.1%}</b> of citations<br>%{y} · ${c}<extra></extra>` })),
      { barmode: "stack", xaxis: { tickformat: ".0%", range: [0, 1] }, yaxis: { autorange: "reversed" }, margin: { l: 70, r: 10, t: 10, b: 50 }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, traceorder: "normal" } });

    const z = LABS.map((a) => LABS.map((b) => (exAll.find((r) => r.citing_lab === a && r.cited_lab === b) || {}).obs_exp));
    const tx = LABS.map((a) => LABS.map((b) => { const r = exAll.find((x) => x.citing_lab === a && x.cited_lab === b) || {}; return `${fmt(r.obs_exp, 2)}${r.q_bh < 0.05 ? "*" : ""}<br>${fmt(r.observed, 0)} vs ${fmt(r.expected, 0)}`; }));
    plot("c-fd-ex", [{ type: "heatmap", x: LABS.map(short), y: LABS.map(short), z: z.map((row) => row.map((v) => Math.log2(v || 1))), text: tx, texttemplate: "%{text}",
      colorscale: [[0, css("--lab-2")], [0.5, css("--surface")], [1, css("--lab-1")]], zmid: 0, showscale: false,
      hovertemplate: "%{y} cites %{x}<br>%{text}<extra></extra>" }],
      { xaxis: { title: "Cited lab", side: "bottom" }, yaxis: { title: "Citing lab", autorange: "reversed" }, margin: { l: 80, r: 10, t: 10, b: 50 } });

    const orR = (R.coauthor_model || []).filter((r) => r.term !== "log_papers_product");
    const lab_ = orR.map((r) => `${r.term.replace(/_/g, " ")} · ${r.model.replace("same lab only", "alone").replace("same lab + ", "+ ").replace(" + size", "")}`);
    plot("c-fd-or", [{ type: "scatter", mode: "markers", x: orR.map((r) => r.odds_ratio), y: lab_,
      error_x: { type: "data", symmetric: false, array: orR.map((r) => r.or_high - r.odds_ratio), arrayminus: orR.map((r) => r.odds_ratio - r.or_low), color: css("--ink-2") },
      marker: { size: 10, color: orR.map((r) => r.term === "same_lab" ? css("--lab-1") : r.term === "same_department" ? css("--lab-3") : css("--lab-4")) },
      hovertemplate: "<b>odds ratio %{x:.2f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { type: "log", title: "Odds ratio (log scale)" }, yaxis: { automargin: true, autorange: "reversed" }, margin: { l: 260, r: 20, t: 10, b: 50 }, showlegend: false,
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const dists = ["1", "2", "3", "4+", "not connected"];
    plot("c-fd-dist", ["all citations", "independent citations"].map((b, i) => ({ type: "bar", name: b, x: dists.map((d) => d === "not connected" ? "not connected" : `distance ${d}`),
      y: dists.map((d) => ((R.distance_lift || []).find((r) => r.basis === b && r.distance === d) || {}).lift),
      text: dists.map((d) => fmt(((R.distance_lift || []).find((r) => r.basis === b && r.distance === d) || {}).lift, 1) + "×"), textposition: "outside", cliponaxis: false,
      marker: { color: i ? css("--lab-1") : css("--qna") }, hovertemplate: "<b>%{y:.2f}×</b> expected<br>%{x} · " + b + "<extra></extra>" })),
      { barmode: "group", yaxis: { type: "log", title: "Observed ÷ expected (log)", tickvals: [0.1, 0.2, 0.5, 1, 2, 3], ticktext: ["0.1×", "0.2×", "0.5×", "1×", "2×", "3×"] }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 1, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const ledAll = (R.led_vs_middle || []).filter((r) => scs.includes(r.scope));
    const roles = ["lab-led", "middle author only"];
    plot("c-fd-led", [
      ...roles.map((ro, i) => ({ type: "bar", name: `${ro}: share of citations`, x: scs.map(scopeLabel), y: scs.map((s) => (ledAll.find((r) => r.scope === s && r.role === ro) || {}).share_of_citations),
        marker: { color: i ? css("--lab-4") : css("--lab-1") }, hovertemplate: `<b>%{y:.0%}</b> of citations<br>%{x} · ${ro}<extra></extra>` })),
      ...roles.map((ro, i) => ({ type: "scatter", mode: "markers", name: `${ro}: citations vs field-year average`, yaxis: "y2", x: scs.map(scopeLabel),
        y: scs.map((s) => (ledAll.find((r) => r.scope === s && r.role === ro) || {}).mean_norm_citations),
        marker: { size: 11, symbol: "diamond", color: i ? css("--lab-4") : css("--lab-1"), line: { color: css("--ink"), width: 1 } },
        hovertemplate: `<b>%{y:.2f}×</b> field-and-year average<br>%{x} · ${ro}<extra></extra>` }))],
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share of citations" }, yaxis2: { overlaying: "y", side: "right", title: "× average", rangemode: "tozero", showgrid: false },
        legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 55, r: 55, t: 10, b: 60 } });

    const tri = R.triadic_closure || [];
    plot("c-fd-pers", [
      { type: "bar", name: "Repeat within 3 years", x: pers.map((r) => r.pair_type), y: pers.map((r) => r.share),
        error_y: { type: "data", symmetric: false, array: pers.map((r) => r.ci_high - r.share), arrayminus: pers.map((r) => r.share - r.ci_low), color: css("--ink-2") },
        marker: { color: pers.map((r) => r.pair_type === "same lab" ? css("--lab-1") : css("--lab-2")) }, customdata: pers.map((r) => r.new_pairs_2016_2022),
        hovertemplate: "<b>%{y:.0%}</b> repeat<br>%{x} · %{customdata} new pairs<extra></extra>", xaxis: "x", yaxis: "y" },
      { type: "scatter", mode: "lines+markers", name: "Triadic-closure lift", x: tri.map((r) => r.year), y: tri.map((r) => r.lift), xaxis: "x2", yaxis: "y2",
        line: { color: css("--ink"), width: 2 }, marker: { size: 7 }, hovertemplate: "<b>%{y:.0f}×</b> more likely with a shared co-author<br>%{x}<extra></extra>" }],
      { grid: { rows: 1, columns: 2, pattern: "independent" }, yaxis: { tickformat: ".0%", title: "Share", range: [0, 1] }, yaxis2: { title: "Lift (×)", rangemode: "tozero" },
        xaxis2: { dtick: 2 }, showlegend: false, margin: { l: 55, r: 16, t: 10, b: 40 } });

    const impAll = (R.lab_impact || []).filter((r) => r.term.startsWith("lab:"));
    plot("c-fd-imp", ["lab only", "lab + year + field + team size + review"].map((m, i) => {
      const rr = impAll.filter((r) => r.model === m);
      return { type: "scatter", mode: "markers", name: i ? "with controls" : "raw", x: rr.map((r) => r.pct_effect), y: rr.map((r) => short(r.term.replace("lab: ", ""))),
        error_x: { type: "data", symmetric: false, array: rr.map((r) => r.pct_high - r.pct_effect), arrayminus: rr.map((r) => r.pct_effect - r.pct_low), color: css("--ink-2") },
        marker: { size: 10, color: i ? css("--lab-1") : css("--qna"), symbol: i ? "circle" : "diamond" }, hovertemplate: `<b>%{x:+.0f}%</b> vs CDRI<br>%{y} · ${i ? "with controls" : "raw"}<extra></extra>` };
    }), { xaxis: { title: "% difference in citations per paper vs CDRI", zeroline: true }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    plot("c-fd-covid", LABS.map((l) => { const rr = cov.filter((r) => r.scope === l);
      return { name: short(l), x: rr.map((r) => r.year), y: rr.map((r) => r.covid_share), mode: "lines+markers", line: { color: labColor(l), width: 2 }, marker: { size: 7 },
        hovertemplate: `<b>%{y:.0%}</b> of papers<br>${short(l)} · %{x}<extra></extra>` }; }),
      { hovermode: "x unified", xaxis: { dtick: 1 }, yaxis: { tickformat: ".0%", title: "Share of the lab's papers" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    plot("c-fd-flow", [...[...LABS, "ALL"].map((l) => { const rr = fw.filter((r) => r.scope === l);
      return { name: l === "ALL" ? "All labs" : short(l), x: rr.map((r) => r.cohort), y: rr.map((r) => r.ratio_window), mode: "lines+markers",
        line: { color: l === "ALL" ? css("--ink") : labColor(l), width: l === "ALL" ? 3 : 2 }, marker: { size: 6 },
        hovertemplate: `<b>%{y:.2f}×</b> in ÷ out<br>${l === "ALL" ? "All labs" : short(l)} · papers of %{x}<extra></extra>` }; }),
      { name: "All labs, raw yearly", x: fwAll.map((r) => r.cohort), y: fwAll.map((r) => r.ratio_raw), mode: "lines", line: { color: css("--muted"), dash: "dash", width: 2 },
        hovertemplate: "<b>%{y:.2f}×</b> raw<br>%{x}<extra></extra>" }],
      { xaxis: { dtick: 1, title: "Publication year of the labs' papers" }, yaxis: { title: "Citations in ÷ out" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 1, y1: 1, line: { color: css("--muted"), dash: "dot", width: 1 } }] });

    const rk = [["rank_citations", "full counting"], ["rank_citations_frac", "fractional"], ["rank_citations_lt100", "without 100+ author papers"]];
    plot("c-fd-rank", rk.map(([f, nm], i) => ({ type: "scatter", mode: "markers", name: nm, x: top10.map((r) => r[f]), y: top10.map((r) => `${r.name} (${short(r.lab)})`),
      marker: { size: 10, symbol: ["circle", "diamond", "square"][i], color: [css("--ink"), css("--lab-1"), css("--qna")][i] },
      hovertemplate: `<b>rank %{x}</b> ${nm}<br>%{y}<extra></extra>` })),
      { xaxis: { type: "log", title: { text: "Rank among faculty (log; 1 = most cited)", standoff: 8 }, autorange: "reversed" },
        yaxis: { autorange: "reversed", type: "category", dtick: 1, automargin: true, tickfont: { size: 11 } },
        legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 10, r: 16, t: 10, b: 100 } });

    table("t-fd-credit", lc.map((r) => ({ ...r, scope_l: r.scope === "ALL" ? "All labs" : short(r.scope),
      mncs_ci: `${fmt(r.mncs, 2)} (${fmt(r.mncs_low, 2)}–${fmt(r.mncs_high, 2)})`, top10_ci: `${pct(r.top10_share, 1)} (${pct(r.top10_low, 1)}–${pct(r.top10_high, 1)})`,
      gini_ci: `${fmt(r.gini_faculty_citations, 2)} (${fmt(r.gini_low, 2)}–${fmt(r.gini_high, 2)})` })), [
      { title: "Lab", field: "scope_l" }, { title: "Papers", field: "papers", hozAlign: "right" },
      { title: "MNCS (95% CI)", field: "mncs_ci", hozAlign: "right" }, { title: "Top 10% share (95% CI)", field: "top10_ci", hozAlign: "right" },
      { title: "Effective papers", field: "effective_papers", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 0) },
      { title: "Top paper's share of citations", field: "top_paper_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 1) },
      { title: "Gini of faculty citations (95% CI)", field: "gini_ci", hozAlign: "right" }, { title: "Faculty", field: "faculty", hozAlign: "right" }],
      { layout: "fitColumns", maxHeight: 300 });

    const pr = (R.pagerank_independent || []).filter((r) => r.basis === "all citations");
    table("t-fd-pr", pr, [
      { title: "Rank (all)", field: "rank_all", hozAlign: "right", width: 90 }, { title: "Rank without self-citation", field: "rank_independent", hozAlign: "right", width: 120 },
      { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" }, { title: "Year", field: "year" },
      { title: "Labs", field: "labs", formatter: (c) => String(c.getValue() || "").split(";").map((x) => short(x)).join(", ") },
      { title: "Cited inside corpus", field: "in_degree", hozAlign: "right" }, { title: "Citations (all)", field: "citations", hozAlign: "right" }],
      { layout: "fitColumns", maxHeight: 420 });

    const mbox = el("fd-methods"); mbox.replaceChildren();
    const ul = document.createElement("ul");
    ["Citation classes: 'self' = an OpenAlex author on both papers; 'co-author network' = no shared author, but a faculty member on the citing paper had co-written with one on the cited paper by that year.",
     "Lab exchange null: the cited paper of each citation is reshuffled within strata (cited year; and cited year × citing field × cited field), 1,000 times. This keeps each paper's number of citations given and received. A paper shared by two labs counts half for each. Two-sided Monte Carlo p-values, Benjamini–Hochberg across the 16 cells.",
     "Co-authorship: faculty pairs who co-wrote a paper with at most 50 authors (as in the networks). Cross-lab share compared with 2,000 shuffles of lab labels (lab sizes fixed) and 200 degree-preserving rewirings; the logistic model uses all faculty pairs, with topic similarity = cosine of their papers' OpenAlex subfield profiles.",
     "Distance lift: for each citing year, distances in the faculty co-authorship network built from earlier years; expected counts = (i's citing contributions × j's cited contributions) / total, summed over pairs at each distance.",
     "Lab-led = a lab-affiliated author in first, last or corresponding position. Normalised citations = citations ÷ mean of papers in the same OpenAlex field and year, within our corpus (a relative, not world, baseline).",
     "Lab impact: OLS on log(1 + citations) with heteroskedasticity-robust (HC1) errors; papers of one lab only; reference CDRI.",
     "Same-window flow: for papers of year Y, citations from works with another Indian institution published in Y to Y+2, against references to such works published in Y−2 to Y; cohorts up to the last complete year minus two.",
     "Fractional counting: each paper contributes citations ÷ number of authors to each faculty author. MNCS bootstrap: 1,000 resamples of papers; Gini interval: 500 resamples of faculty.",
     "Limits: OpenAlex coverage and author disambiguation; faculty lists cover 71–81% of each lab's output; the corpus-relative normalisation is not a world baseline; associations, not causal effects."]
      .forEach((t) => ul.append(txt("li", t)));
    mbox.append(ul);
    renderNotes();
  }

  // ---------------------------------------------------------------- page: course network models (step s18)
  function renderModels() {
    const N = P2.netmodels;
    if (!N) { el("nm-list").textContent = "Run step s18 to compute the network models."; return; }
    const S = N.summary, tails = N.degree_fits || [], sw = N.small_world || [], rs = N.robustness_summary || [];
    const swF = sw.find((r) => r.network.startsWith("faculty")) || {}, swA = sw.find((r) => r.network.startsWith("all")) || {};
    const rsOf = (s) => rs.find((r) => r.strategy === s) || {};
    const si = N.si || [], siOf = (n) => si.find((r) => r.network === n) || {};
    const lpAll = (S.link_prediction_mean_auc_all || {}), lpX = (S.link_prediction_mean_auc_cross_lab || {});
    const coef = N.tie_formation || [], m4 = (t) => coef.find((r) => r.model === "4 + seniority" && r.term === t) || {};
    const m5 = (t) => coef.find((r) => r.model.startsWith("5") && r.term === t) || {};
    const perm = (N.tie_permutation || []).find((r) => r.term === "same_lab") || {};
    const tailOf = (d) => tails.find((r) => r.distribution === d) || {};
    const verdict = (d) => tails.filter((r) => r.distribution === d).map((r) => `${r.alternative}: ${r.verdict}`).join("; ");
    const cuts = N.lab_cuts || [], iso = cuts.filter((r) => r.side_b.includes("+"));
    const sis = S.sis || {}, hold = S.tie_formation_holdout || {};
    const sameLabCN = Math.exp(Math.log(m5("log_cn").odds_ratio) + Math.log(m5("same_lab_x_log_cn").odds_ratio));
    const items = [
      ["Heavy tails, but not a clean power law.", `Faculty degree: a power-law tail is ${tailOf("faculty co-authorship degree").power_law_plausible ? "plausible" : "rejected"} only above ${fmt(tailOf("faculty co-authorship degree").xmin)} links (${fmt(tailOf("faculty co-authorship degree").n_tail)} faculty, bootstrap p = ${fmt(tailOf("faculty co-authorship degree").gof_p, 2)}); ${verdict("faculty co-authorship degree")}. All-author degree: α = ${fmt(tailOf("all-author co-authorship degree").alpha, 2)} above ${fmt(tailOf("all-author co-authorship degree").xmin)} (p = ${fmt(tailOf("all-author co-authorship degree").gof_p, 2)}); ${verdict("all-author co-authorship degree")}. Paper citations: α = ${fmt(tailOf("paper citations").alpha, 2)} above ${fmt(tailOf("paper citations").xmin)} (p = ${fmt(tailOf("paper citations").gof_p, 2)}); ${verdict("paper citations")}.`,
        "Like most real networks (Broido & Clauset 2019), ours is heavy-tailed but better described by a power law with a cutoff or a log-normal than by a pure scale-free law; 'scale-free' should not be claimed."],
      ["The faculty network is a small world.", `Average path ${fmt(swF.path_length, 2)} steps against ${fmt(swF.er_path_length, 2)} in a random graph of the same size, while clustering is ${fmt(swF.clustering, 2)} against ${fmt(swF.er_clustering, 3)} (σ = ${fmt(swF.sigma_er, 1)}; ${fmt(swF.sigma_degree_preserving, 1)} against degree-preserving graphs). The all-author network: L = ${fmt(swA.path_length, 2)} vs ${fmt(swA.er_path_length, 2)}, C = ${fmt(swA.clustering, 2)} vs ${fmt(swA.er_clustering, 4)}.`,
        "Any two connected faculty are about three and a half co-authors apart, yet their collaborators mostly know each other: tight lab groups joined by a few long links."],
      ["Robust to chance, fragile to losing brokers.", `Random departures halve the largest group only after ${pct(rsOf("random").share_to_halve_lcc, 0)} of faculty leave (configuration-model theory: ${pct(S.molloy_reed.fc_random_theory, 0)}); removing by betweenness halves it after ${fmt(rsOf("betweenness").removed_to_halve_lcc)} people (${pct(rsOf("betweenness").share_to_halve_lcc, 0)}). Taking out the ${fmt(rsOf("brokers").removed_until_no_lab_pair_joined)} faculty with the most cross-lab co-authors leaves no two labs connected; at random that takes ${fmt(rsOf("random").removed_until_no_lab_pair_joined)}. Cutting a lab off needs ${iso.map((r) => `${short(r.side_a)} ${r.min_edge_cut}`).join(", ")} links.`,
        "The labs' connection to one another rests on a couple of dozen people; their departure, not random turnover, is what would split the network."],
      ["Lab walls slow spreading.", `From a random start, something passed along joint papers reaches another lab in a median ${fmt(siOf("observed").median_t_other_lab)} steps and all four in ${fmt(siOf("observed").median_t_all_labs)}, against ${fmt(siOf("degree-preserving null").median_t_other_lab)} and ${fmt(siOf("degree-preserving null").median_t_all_labs)} with the same degrees but random mixing. Without the five main brokers it takes ${fmt(siOf("five brokers removed").median_t_all_labs)} steps. SIS: outbreaks persist from λ ≈ ${fmt(sis.threshold_empirical, 3)}, near the mean-field thresholds 1/Λmax = ${fmt(sis.threshold_qmf, 3)} and ⟨k⟩/⟨k²⟩ = ${fmt(sis.threshold_hmf, 3)}.`,
        "Ideas, methods or reagents that travel through collaboration would move between labs two to three times slower than the same network without lab boundaries."],
      ["Next year's collaborations are predictable, except across labs.", `Mean AUC over test years: logistic model ${fmt(lpAll["logistic model (all features)"], 2)}, same lab alone ${fmt(lpAll.same_lab, 2)}, Katz ${fmt(lpAll.katz, 2)}, Adamic–Adar ${fmt(lpAll.adamic_adar, 2)}, topic similarity ${fmt(lpAll.topic_similarity, 2)}. For cross-lab pairs only: model ${fmt(lpX["logistic model (all features)"], 2)}, Katz ${fmt(lpX.katz, 2)}, topic ${fmt(lpX.topic_similarity, 2)}. Trained on ${hold.train_years} and tested on ${hold.test_years}, the tie model reaches AUC ${fmt(hold.auc, 2)} (lab alone ${fmt(hold.auc_same_lab_only, 2)}).`,
        "Within a lab, new ties follow the network (shared colleagues); across labs, they are rare and close to unpredictable from the network, closer to chance meetings."],
      ["Lab, not department or seniority, drives new ties; shared colleagues matter most across labs.", `With topic, network position, output, seniority and year held equal, a same-lab pair is ${fmt(m4("same_lab").odds_ratio, 0)}× more likely to start collaborating (95% CI ${fmt(m4("same_lab").or_low, 0)}–${fmt(m4("same_lab").or_high, 0)}; permutation p = ${fmt(perm.p_one_sided, 3)}); same department ${fmt(m4("same_department").odds_ratio, 2)}× (${fmt(m4("same_department").or_low, 2)}–${fmt(m4("same_department").or_high, 2)}); each e-fold more shared co-authors ${fmt(m4("log_cn").odds_ratio, 2)}×; seniority level ${fmt(m4("seniority_sum").odds_ratio, 2)}× per grade. Shared co-authors raise the odds ${fmt(m5("log_cn").odds_ratio, 1)}× per e-fold across labs, against ${fmt(sameLabCN, 1)}× within a lab.`,
        "A cross-lab collaboration almost always comes through a colleague who already works with both sides, so brokers are the lever for joint work between labs."],
    ];
    const box = el("nm-list"); box.replaceChildren();
    items.forEach(([h, a, so]) => { const d = document.createElement("div"); d.className = "rqi"; d.append(txt("h3", h), txt("p", a), txt("p", so, "muted")); box.append(d); });

    // tails: complementary CDF on log-log axes with the fitted power law above x_min
    const cc = N.ccdf || [], dists = [...new Set(cc.map((r) => r.distribution))];
    const dc = [css("--lab-1"), css("--lab-2"), css("--lab-4")];
    plot("c-nm-tails", dists.flatMap((d, i) => { const rr = cc.filter((r) => r.distribution === d), ff = rr.filter((r) => r.fit !== null && r.fit !== undefined && r.fit !== "");
      const t = tailOf(d);
      return [{ name: d, x: rr.map((r) => r.x), y: rr.map((r) => r.ccdf), mode: "markers", marker: { size: 4, color: dc[i] }, legendgroup: d,
                hovertemplate: `<b>%{y:.3g}</b> have at least %{x}<br>${d}<extra></extra>` },
              { name: `fit α = ${fmt(t.alpha, 2)}, p = ${fmt(t.gof_p, 2)}`, x: ff.map((r) => r.x), y: ff.map((r) => r.fit), mode: "lines", line: { color: dc[i], width: 2, dash: "dash" },
                legendgroup: d, hoverinfo: "skip" }]; }),
      { xaxis: { type: "log", title: "x (links or citations)" }, yaxis: { type: "log", title: "P(X ≥ x)" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, font: { size: 10 } } });
    table("t-nm-tails", tails.map((r) => ({ ...r })), [
      { title: "Distribution", field: "distribution", widthGrow: 2 }, { title: "x min", field: "xmin", hozAlign: "right" },
      { title: "α", field: "alpha", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) }, { title: "Tail size", field: "n_tail", hozAlign: "right" },
      { title: "Bootstrap p", field: "gof_p", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
      { title: "Alternative", field: "alternative" }, { title: "R", field: "llr", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) },
      { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) }, { title: "Verdict", field: "verdict", widthGrow: 2 }],
      { layout: "fitColumns", maxHeight: 360 });

    const swNames = sw.map((r) => r.network);
    plot("c-nm-sw", [
      ...[["clustering", "observed", css("--lab-1")], ["degree_preserving_clustering", "degree-preserving", css("--lab-4")], ["er_clustering", "Erdős–Rényi", css("--qna")]].map(([f, n, c]) => ({
        type: "bar", name: `C ${n}`, x: swNames, y: sw.map((r) => r[f]), marker: { color: c }, hovertemplate: `<b>C = %{y:.3f}</b><br>%{x} · ${n}<extra></extra>` })),
      ...[["path_length", "observed", css("--lab-1")], ["degree_preserving_path_length", "degree-preserving", css("--lab-4")], ["er_path_length", "Erdős–Rényi", css("--qna")]].map(([f, n, c]) => ({
        type: "scatter", mode: "markers", name: `L ${n}`, yaxis: "y2", x: swNames, y: sw.map((r) => r[f]),
        marker: { size: 12, symbol: "diamond", color: c, line: { color: css("--ink"), width: 1 } }, hovertemplate: `<b>L = %{y:.2f}</b><br>%{x} · ${n}<extra></extra>` }))],
      { barmode: "group", yaxis: { title: "Clustering C" }, yaxis2: { overlaying: "y", side: "right", title: "Path length L", rangemode: "tozero", showgrid: false },
        legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 55, r: 55, t: 10, b: 50 } });

    const rob = N.robustness || [], strats = ["random", "degree", "betweenness", "brokers"];
    const sc = { random: css("--muted"), degree: css("--lab-1"), betweenness: css("--lab-2"), brokers: css("--lab-4") };
    const half = (r) => r.removed_share <= 0.5;
    plot("c-nm-rob", strats.map((s) => { const rr = rob.filter((r) => r.strategy === s && half(r));
      return { name: s, x: rr.map((r) => r.removed_share), y: rr.map((r) => r.lcc_share), mode: "lines", line: { color: sc[s], width: 2 },
        hovertemplate: `<b>%{y:.0%}</b> in the largest group<br>${s} · %{x:.0%} removed<extra></extra>` }; }),
      { xaxis: { tickformat: ".0%", title: "Faculty removed" }, yaxis: { tickformat: ".0%", title: "Largest group", range: [0, 1] }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });
    plot("c-nm-labs", strats.map((s) => { const rr = rob.filter((r) => r.strategy === s && half(r));
      return { name: s, x: rr.map((r) => r.removed_share), y: rr.map((r) => r.lab_pairs_joined), mode: "lines", line: { color: sc[s], width: 2, shape: "hv" },
        hovertemplate: `<b>%{y:.1f}</b> of 6 lab pairs joined<br>${s} · %{x:.0%} removed<extra></extra>` }; }),
      { xaxis: { tickformat: ".0%", title: "Faculty removed" }, yaxis: { title: "Lab pairs joined", range: [0, 6.3], dtick: 1 }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const nets = ["observed", "degree-preserving null", "five brokers removed"];
    plot("c-nm-si", [["median_t_other_lab", "another lab"], ["median_t_all_labs", "all four labs"], ["median_t50", "half the network"], ["median_t90", "90% of the network"]].map(([f, nm], i) => ({
      type: "bar", name: nm, x: nets, y: nets.map((n) => siOf(n)[f]), marker: { color: [css("--lab-1"), css("--lab-3"), css("--lab-2"), css("--lab-4")][i] },
      hovertemplate: `<b>%{y} steps</b> to reach ${nm}<br>%{x}<extra></extra>` })),
      { barmode: "group", yaxis: { title: "Median steps (SI, β = 0.05)" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const sisR = N.sis || [];
    plot("c-nm-sis", ["observed", "degree-preserving null"].map((n, i) => { const rr = sisR.filter((r) => r.network === n);
      return { name: n, x: rr.map((r) => r.lambda_over_qmf), y: rr.map((r) => r.prevalence), mode: "lines+markers",
        error_y: { type: "data", array: rr.map((r) => r.prevalence_sd), visible: true, color: css("--ink-2") },
        line: { color: i ? css("--qna") : css("--lab-1"), width: 2 }, marker: { size: 6 }, hovertemplate: `<b>%{y:.1%}</b> infected<br>λ = %{x:.2f} × threshold · ${n}<extra></extra>` }; }),
      { xaxis: { title: "λ ÷ (1 / Λmax)" }, yaxis: { tickformat: ".0%", title: "Stationary prevalence" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const lp = (N.linkpred || []).filter((r) => r.subset === "all pairs");
    const meths = ["logistic model (all features)", "same_lab", "katz", "adamic_adar", "preferential_attachment", "topic_similarity"];
    const mc = [css("--ink"), css("--lab-1"), css("--lab-2"), css("--lab-3"), css("--lab-4"), css("--qna")];
    plot("c-nm-lp", meths.map((m, i) => { const rr = lp.filter((r) => r.method === m);
      return { name: m.replace(/_/g, " "), x: rr.map((r) => r.test_year), y: rr.map((r) => r.auc), mode: "lines+markers", line: { color: mc[i], width: i ? 2 : 3 }, marker: { size: 6 },
        customdata: rr.map((r) => r.new_links), hovertemplate: `<b>AUC %{y:.2f}</b><br>${m} · %{x} · %{customdata} new links<extra></extra>` }; }),
      { xaxis: { dtick: 1, title: "Test year" }, yaxis: { title: "AUC", range: [0.4, 1] }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 0.5, y1: 0.5, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const NAMES = { same_lab: "same lab", same_department: "same department", topic_similarity: "topic similarity", log_cn: "shared co-authors (log)",
      log_pa: "degree product (log)", log_output_product: "output (log)", seniority_sum: "seniority (sum of grades)", seniority_gap: "seniority gap",
      seniority_missing: "grade unknown", same_lab_x_log_cn: "same lab × shared co-authors" };
    const h4 = coef.filter((r) => r.model === "4 + seniority");
    plot("c-nm-haz", [{ type: "scatter", mode: "markers", x: h4.map((r) => r.odds_ratio), y: h4.map((r) => NAMES[r.term] || r.term),
      error_x: { type: "data", symmetric: false, array: h4.map((r) => r.or_high - r.odds_ratio), arrayminus: h4.map((r) => r.odds_ratio - r.or_low), color: css("--ink-2") },
      marker: { size: 10, color: h4.map((r) => r.term === "same_lab" ? css("--lab-1") : r.term.startsWith("log_cn") ? css("--lab-4") : css("--lab-3")) },
      hovertemplate: "<b>odds ratio %{x:.2f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { type: "log", title: "Odds ratio (log scale)" }, yaxis: { automargin: true, autorange: "reversed" }, margin: { l: 200, r: 20, t: 10, b: 50 }, showlegend: false,
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });
    table("t-nm-haz", coef.map((r) => ({ ...r, term_l: NAMES[r.term] || r.term, or_ci: `${fmt(r.odds_ratio, 2)} (${fmt(r.or_low, 2)}–${fmt(r.or_high, 2)})` })), [
      { title: "Model", field: "model", widthGrow: 2 }, { title: "Term", field: "term_l", widthGrow: 2 }, { title: "Odds ratio (95% CI)", field: "or_ci", hozAlign: "right", widthGrow: 2 },
      { title: "SE naive", field: "se_naive", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }, { title: "SE dyadic", field: "se_dyadic", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) },
      { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) }],
      { layout: "fitColumns", maxHeight: 380 });

    const mbox = el("nm-methods"); mbox.replaceChildren();
    const ul = document.createElement("ul");
    ["Power laws: discrete maximum-likelihood α for every candidate x_min, keeping the x_min with the smallest Kolmogorov–Smirnov distance; goodness of fit from a semi-parametric bootstrap; Vuong likelihood-ratio tests against a discretised log-normal, a discrete exponential and a power law with exponential cutoff (Clauset, Shalizi & Newman 2009).",
     "Small world: average clustering and mean shortest path of the largest component; Erdős–Rényi G(n, m) with the same n and m; degree-preserving nulls by double-edge swaps (faculty network) or a simplified configuration model (all-author network, paths from a sample of 300 sources).",
     "Robustness: one faculty member removed at a time, the next chosen after recomputing degree, betweenness or cross-lab ties; random order averaged over 100 runs. Lab cuts: maximum flow between all members of each side, one unit per co-author link. Molloy–Reed: κ = ⟨k²⟩/⟨k⟩ and f_c = 1 − 1/(κ − 1) for a configuration-model graph.",
     "Spreading: discrete-time SI on the weighted largest component (infection probability 1 − (1 − β)^(joint papers with infected colleagues)); one run from each node; 10 rewired networks with the link weights shuffled. SIS on the unweighted component, recovery 0.2, 10 runs of 600 steps (last 300 averaged) per λ; empirical threshold = first λ with prevalence ≥ 1%.",
     "Link prediction and tie formation: a pair is at risk in year t when both faculty have a paper before t and one in t or later and they have not co-authored yet; the outcome is a first joint paper (≤ 50 authors) in t; all features use the network up to t − 1. AUC by the rank-sum formula. The tie model is a logistic hazard with year effects, dyadic-robust errors (Aronow, Samii & Assenova 2015) and a lab-label permutation test (200 shuffles). It stands in for a stochastic actor-oriented model (RSiena), which would also model each person's choices but needs R.",
     "Limits: seniority is the current CSIR grade, not the grade in each year; papers with more than 50 authors are left out of the network, as in the submitted files; faculty who left the labs are kept with their dates of activity from their papers; associations, not causal effects."]
      .forEach((t) => ul.append(txt("li", t)));
    mbox.append(ul);
  }

  // ---------------------------------------------------------------- page: robustness and dynamics (step s19)
  function renderExtensions() {
    const E = P2.ext;
    if (!E) { el("ex-list").textContent = "Run step s19 to compute the robustness checks and extensions."; return; }
    const S = E.summary, sc = S.spec_curve || {}, sh = S.diffusion_shuffle || {}, cl = S.simplicial_closure || {}, cb = S.citation_before_collab || {}, tr = S.test_registry || {};
    const dm = E.diffusion_models || [], dmOf = (m, t) => dm.find((r) => r.model === m && r.term === t) || {};
    const dose = (E.diffusion_dose || []).filter((r) => r.deg_band === "all");
    const doseOf = (k) => dose.find((r) => String(r.k_band) === k) || {};
    const clos = E.simplicial_closure || [], cOf = (c, l = "all") => clos.find((r) => r.configuration === c && r.labs === l) || {};
    const gen = E.generative || [], gOf = (v, s) => gen.find((r) => r.variant === v && r.statistic === s) || {};
    const cov = E.covid_ties || [], covOf = (pairs, f, o) => cov.find((r) => r.pairs === pairs && r.formed_on === f && r.outcome === o) || {};
    const cit = E.citation_before_collab || [], citOf = (m, t) => cit.find((r) => r.model === m && r.term === t) || {};
    const pc = citOf("model 4 + any prior citation", "any_prior_citation");
    const items = [
      ["The same-lab effect survives every analysis choice.", `Across ${fmt(sc.specifications)} specifications the odds ratio for a same-lab pair starting to collaborate runs from ${fmt(sc.same_lab_or_min, 1)} to ${fmt(sc.same_lab_or_max, 1)} (median ${fmt(sc.same_lab_or_median, 1)}); the lowest lower bound is ${fmt(sc.same_lab_low_min, 1)}. Same department: ${fmt(sc.same_department_or_range && sc.same_department_or_range[0], 2)}–${fmt(sc.same_department_or_range && sc.same_department_or_range[1], 2)}, significant in ${fmt(sc.same_department_significant_specs)} of 24 full-model specifications.`,
        "The headline does not depend on the author cap, on using future activity to define who is at risk, on the pandemic years, on the most connected people or on the controls. Dropping hubs and adding controls shrink it the most, never below about 20×."],
      ["Faculty take up methods their co-authors use, but the shuffle test does not show influence.", `Adoption rates: ${pct(doseOf("0").rate, 1)} a year with no adopting co-author, ${pct(doseOf("1").rate, 1)} with one, ${pct(doseOf("2").rate, 1)} with two, ${pct(doseOf("3+").rate, 1)} with three or more; simple contagion predicts ${pct(doseOf("2").simple_contagion_pred, 1)} and ${pct(doseOf("3+").simple_contagion_pred, 1)} for the last two. Same-lab exposure OR ${fmt(dmOf("same vs cross lab", "same-lab adopting co-authors (log)").odds_ratio, 2)}, cross-lab ${fmt(dmOf("same vs cross lab", "cross-lab adopting co-authors (log)").odds_ratio, 2)} (n.s.). But shuffling adoption years among the adopters gives OR ${fmt(sh.shuffle_or_mean, 2)} against ${fmt(sh.or_observed, 2)} observed (p = ${fmt(sh.p_one_sided, 2)}).`,
        "Co-authors share methods because they belong to the same research groups (homophily and shared projects), not because one passes the method on to the other at a measurable time. The dose-response matches simple contagion for two adopting co-authors and falls below it for three or more, as expected when exposures come from one group and overlap; there is no sign of complex contagion (extra co-authors never add more than independent exposure would)."],
      ["Groups close when every pair has worked together repeatedly.", `Of faculty triples who never shared a paper in ${cl.train_years}, ${pct(cOf("3 pairwise ties, all repeated").closure_rate, 0)} with three repeated pairwise ties wrote one together in ${cl.test_years}, against ${pct(cOf("3 pairwise ties, some single").closure_rate, 1)} with three ties not all repeated, ${pct(cOf("2 pairwise ties").closure_rate, 1)} with two, ${pct(cOf("1 pairwise ties").closure_rate, 2)} with one and ${pct(cOf("0 pairwise ties").closure_rate, 3)} with none. Open wedges close at ${pct(cOf("2 pairwise ties", "one lab").closure_rate, 1)} inside a lab and ${pct(cOf("2 pairwise ties", "mixed labs").closure_rate, 1)} across labs.`,
        "As Benson et al. (2018) found for other collaboration systems, tie strength, not just the presence of ties, drives the formation of groups; and groups that span labs almost never form."],
      ["The tie model reproduces the lab structure, but not the clustering.", `Grown from 2016, the full model gives a cross-lab share of ${pct(gOf("full model", "cross_lab_share").sim_mean, 1)} (real ${pct(gOf("full model", "cross_lab_share").observed, 1)}), path length ${fmt(gOf("full model", "path_length").sim_mean, 2)} (${fmt(gOf("full model", "path_length").observed, 2)}) and lab modularity ${fmt(gOf("full model", "lab_modularity").sim_mean, 2)} (${fmt(gOf("full model", "lab_modularity").observed, 2)}); without the lab term the cross-lab share jumps to ${pct(gOf("without lab", "cross_lab_share").sim_mean, 0)}. Clustering stays at ${fmt(gOf("full model", "clustering").sim_mean, 2)} against ${fmt(gOf("full model", "clustering").observed, 2)}.`,
        "Lab preference alone explains the division into labs. The missing clustering shows that links arrive in groups (a paper links several people at once), which a pair-by-pair model cannot produce: the network has to be modelled as a hypergraph."],
      ["Pandemic collaborations did not outlast the pandemic.", `Of pairs whose first joint paper (2020–22) was on COVID-19, ${pct(covOf("all pairs", "COVID-19 paper", "later_non_covid").share, 0)} later wrote a non-COVID paper together, against ${pct(covOf("all pairs", "other paper", "later_non_covid").share, 0)} of pairs formed on other topics. Only ${fmt(covOf("cross-lab", "COVID-19 paper", "later_any").new_pairs)} cross-lab pairs formed on COVID-19 work, and ${fmt(covOf("cross-lab", "COVID-19 paper", "later_non_covid").continued)} continued on other topics.`,
        "A mission-driven shock created ties, mostly within labs, but they stayed tied to the mission; it did not build lasting bridges between labs."],
      ["Reading each other's work comes before writing together.", `${pct(cb.share_new_links_with_prior_citation, 1)} of new links had an earlier independent citation between the two faculty, against ${pct(cb.share_unlinked_pairs_with_prior_citation, 1)} of pairs that did not link; for new cross-lab links ${pct(cb.cross_lab_new_links_with_prior_citation, 0)}. With lab, topic, network position, output and seniority held equal, a prior citation raises the odds of a new collaboration ${fmt(pc.odds_ratio, 2)}× (${fmt(pc.or_low, 2)}–${fmt(pc.or_high, 2)}).`,
        "Citation is an early signal of collaboration, and more so across labs, where it may be the main way people find each other."],
      ["Almost every reported result survives a paper-wide correction.", `${fmt(tr.tests)} tests across the Findings pages (steps s17–s22): ${fmt(tr.p_below_05)} have p < 0.05 and ${fmt(tr.q_below_05)} keep q < 0.05 after Benjamini–Hochberg across all of them (${fmt(tr.lost_after_correction)} lost).`,
        "Multiple testing does not explain the findings; the tests lost are secondary control terms and borderline cells."],
    ];
    const box = el("ex-list"); box.replaceChildren();
    items.forEach(([h, a, so]) => { const d = document.createElement("div"); d.className = "rqi"; d.append(txt("h3", h), txt("p", a), txt("p", so, "muted")); box.append(d); });

    const spec = [...(E.spec_curve || [])].sort((a, b) => a.same_lab_or - b.same_lab_or);
    const xs = spec.map((_, i) => i + 1);
    const flags = [["author cap 20", (r) => r.author_cap === 20], ["author cap 100", (r) => r.author_cap === 100], ["no look-ahead", (r) => r.risk_set === "no look-ahead"],
      ["without 2020–22", (r) => r.years !== "all years"], ["top 5% hubs dropped", (r) => r.hubs !== "hubs kept"], ["full controls", (r) => r.controls === "full model"]];
    plot("c-ex-spec", [
      { type: "scatter", mode: "markers", x: xs, y: spec.map((r) => r.same_lab_or), xaxis: "x", yaxis: "y", name: "same-lab odds ratio",
        error_y: { type: "data", symmetric: false, array: spec.map((r) => r.same_lab_high - r.same_lab_or), arrayminus: spec.map((r) => r.same_lab_or - r.same_lab_low), color: css("--ink-2"), thickness: 1 },
        marker: { size: 7, color: spec.map((r) => r.controls === "full model" ? css("--lab-1") : css("--lab-4")) },
        customdata: spec.map((r) => `cap ${r.author_cap} · ${r.risk_set} · ${r.years} · ${r.hubs} · ${r.controls} · ${r.new_links} new links`),
        hovertemplate: "<b>OR %{y:.1f}</b><br>%{customdata}<extra></extra>" },
      ...flags.map(([nm, f]) => ({ type: "scatter", mode: "markers", x: xs, y: spec.map(() => nm), xaxis: "x", yaxis: "y2", showlegend: false,
        marker: { size: 7, symbol: "square", color: spec.map((r) => f(r) ? css("--ink") : "rgba(0,0,0,0)"), line: { color: css("--muted"), width: 0.5 } }, hoverinfo: "skip" }))],
      { grid: { rows: 2, columns: 1, roworder: "top to bottom" }, showlegend: false,
        yaxis: { type: "log", title: "Same-lab odds ratio", domain: [0.42, 1], tickvals: [10, 15, 20, 30, 50, 80], ticktext: ["10×", "15×", "20×", "30×", "50×", "80×"] }, yaxis2: { domain: [0, 0.34], type: "category", automargin: true, autorange: "reversed" },
        xaxis: { title: "Specification (sorted)", anchor: "y2" }, margin: { l: 140, r: 16, t: 10, b: 50 } });

    const kb = ["0", "1", "2", "3+"];
    plot("c-ex-dose", [
      { type: "bar", name: "observed", x: kb.map((k) => `${k} adopting co-author${k === "1" ? "" : "s"}`), y: kb.map((k) => doseOf(k).rate), marker: { color: css("--lab-1") },
        error_y: { type: "data", symmetric: false, array: kb.map((k) => doseOf(k).rate_high - doseOf(k).rate), arrayminus: kb.map((k) => doseOf(k).rate - doseOf(k).rate_low), color: css("--ink-2") },
        customdata: kb.map((k) => doseOf(k).faculty_years), hovertemplate: "<b>%{y:.1%}</b> adopt a year<br>%{x} · %{customdata} faculty-years<extra></extra>" },
      { type: "scatter", mode: "markers", name: "simple contagion prediction", x: kb.map((k) => `${k} adopting co-author${k === "1" ? "" : "s"}`), y: kb.map((k) => doseOf(k).simple_contagion_pred),
        marker: { size: 12, symbol: "diamond", color: css("--lab-4"), line: { color: css("--ink"), width: 1 } }, hovertemplate: "<b>%{y:.1%}</b> predicted<br>%{x}<extra></extra>" }],
      { yaxis: { tickformat: ".1%", title: "Yearly adoption rate" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const coefs = (sh.shuffle_coefs || []).map((c) => Math.exp(c));
    plot("c-ex-shuffle", [{ type: "histogram", x: coefs, nbinsx: 30, name: "shuffled", marker: { color: css("--qna") }, hovertemplate: "OR %{x:.2f}: %{y} shuffles<extra></extra>" }],
      { xaxis: { title: "Odds ratio for having an adopting co-author" }, yaxis: { title: "Shuffled data sets" }, showlegend: false,
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: sh.or_observed, x1: sh.or_observed, y0: 0, y1: 1, line: { color: css("--lab-1"), width: 3 } }],
        annotations: [{ x: sh.or_observed, y: 1, xref: "x", yref: "paper", text: `observed ${fmt(sh.or_observed, 2)}`, showarrow: false, yanchor: "bottom", font: { color: css("--lab-1") } }] });
    table("t-ex-diff", dm.map((r) => ({ ...r, or_ci: `${fmt(r.odds_ratio, 2)} (${fmt(r.or_low, 2)}–${fmt(r.or_high, 2)})` })), [
      { title: "Model", field: "model", widthGrow: 3 }, { title: "Term", field: "term", widthGrow: 3 }, { title: "Odds ratio (95% CI)", field: "or_ci", hozAlign: "right", widthGrow: 2 },
      { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) }, { title: "Adoptions", field: "adoptions", hozAlign: "right" }],
      { layout: "fitColumns", maxHeight: 340 });

    const cfgs = ["0 pairwise ties", "1 pairwise ties", "2 pairwise ties", "3 pairwise ties, some single", "3 pairwise ties, all repeated"];
    plot("c-ex-closure", [["all", "all triples", css("--ink")], ["one lab", "one lab", css("--lab-1")], ["mixed labs", "spanning labs", css("--lab-4")]].map(([l, nm, c]) => ({
      type: "bar", name: nm, x: cfgs.map((x) => x.replace("pairwise ties", "ties")), y: cfgs.map((x) => cOf(x, l).closure_rate || null), marker: { color: c },
      customdata: cfgs.map((x) => `${fmt(cOf(x, l).closed)} of ${fmt(cOf(x, l).triples)}`), hovertemplate: `<b>%{y:.2%}</b> close · %{customdata}<br>%{x} · ${nm}<extra></extra>` })),
      { barmode: "group", yaxis: { type: "log", tickformat: ".2%", title: "Share writing a paper together" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const gstats = [["cross_lab_share", "cross-lab share"], ["lab_modularity", "lab modularity"], ["clustering", "clustering"], ["transitivity", "transitivity"], ["path_length", "path length"], ["degree_sd", "degree spread"], ["max_degree", "max degree"]];
    const vars = ["full model", "without lab", "without shared co-authors", "without degree", "random (no terms)"];
    plot("c-ex-gen", vars.map((v, i) => ({ type: "scatter", mode: "markers", name: v, y: gstats.map(([, n]) => n), x: gstats.map(([s]) => gOf(v, s).ratio_to_observed),
      marker: { size: 11, symbol: ["circle", "x", "diamond", "triangle-up", "square"][i], color: [css("--lab-1"), css("--lab-2"), css("--lab-3"), css("--lab-4"), css("--qna")][i] },
      hovertemplate: `<b>%{x:.2f}×</b> the real value<br>%{y} · ${v}<extra></extra>` })),
      { xaxis: { type: "log", title: "Simulated ÷ real (log)", tickvals: [0.1, 0.2, 0.5, 1, 2, 5, 10], ticktext: ["0.1×", "0.2×", "0.5×", "1×", "2×", "5×", "10×"] }, yaxis: { automargin: true, autorange: "reversed" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 120, r: 16, t: 10, b: 50 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const grp = ["all pairs", "same lab", "cross-lab"];
    plot("c-ex-covid", [["COVID-19 paper", "later_any", "formed on COVID-19: any later paper", css("--lab-2")], ["other paper", "later_any", "formed on other topics: any later paper", css("--lab-1")],
      ["COVID-19 paper", "later_non_covid", "formed on COVID-19: later non-COVID paper", css("--lab-4")], ["other paper", "later_non_covid", "formed on other topics: later non-COVID paper", css("--lab-3")]].map(([f, o, nm, c]) => ({
      type: "bar", name: nm, x: grp, y: grp.map((g) => covOf(g, f, o).share), marker: { color: c },
      error_y: { type: "data", symmetric: false, array: grp.map((g) => covOf(g, f, o).high - covOf(g, f, o).share), arrayminus: grp.map((g) => covOf(g, f, o).share - covOf(g, f, o).low), color: css("--ink-2") },
      customdata: grp.map((g) => `${fmt(covOf(g, f, o).continued)} of ${fmt(covOf(g, f, o).new_pairs)}`), hovertemplate: `<b>%{y:.0%}</b> · %{customdata}<br>%{x}<extra></extra>` })),
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share continuing", range: [0, 1] }, legend: { orientation: "h", y: -0.18, yanchor: "top", x: 0, font: { size: 10 } }, margin: { l: 55, r: 16, t: 10, b: 120 } });

    const cr = cit.filter((r) => r.model !== "prior citation only" || r.term === "any_prior_citation");
    const CN = { any_prior_citation: "prior citation (any)", log_prior_citations: "prior citations (log)", same_lab: "same lab", topic_similarity: "topic similarity", log_cn: "shared co-authors (log)" };
    plot("c-ex-cite", [{ type: "scatter", mode: "markers", x: cr.map((r) => r.odds_ratio), y: cr.map((r) => `${CN[r.term] || r.term} · ${r.model === "prior citation only" ? "alone" : r.model.includes("log") ? "full, log citations" : "full model"}`),
      error_x: { type: "data", symmetric: false, array: cr.map((r) => r.or_high - r.odds_ratio), arrayminus: cr.map((r) => r.odds_ratio - r.or_low), color: css("--ink-2") },
      marker: { size: 10, color: cr.map((r) => r.term.includes("citation") ? css("--lab-4") : css("--lab-1")) }, hovertemplate: "<b>odds ratio %{x:.2f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { type: "log", title: "Odds ratio (log scale)" }, yaxis: { automargin: true, autorange: "reversed" }, margin: { l: 10, r: 16, t: 10, b: 50 }, showlegend: false,
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    table("t-ex-reg", E.test_registry || [], [
      { title: "Source", field: "source", widthGrow: 2 }, { title: "Test", field: "test", widthGrow: 5, formatter: "textarea" },
      { title: "Effect", field: "effect", hozAlign: "right", formatter: (c) => (c.getValue() === null || c.getValue() === "" ? "" : fmt(c.getValue(), 2)) },
      { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) },
      { title: "q (BH, all tests)", field: "q_bh_all", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) },
      { title: "q < 0.05", field: "significant_q05", hozAlign: "center", formatter: (c) => (String(c.getValue()) === "true" ? "✓" : "") }],
      { layout: "fitColumns", maxHeight: 420 });

    const mbox = el("ex-methods"); mbox.replaceChildren();
    const ul = document.createElement("ul");
    ["Specification curve: the s18 discrete-time tie model re-estimated for 3 author caps × 2 risk sets × 2 year sets × 2 hub choices × 2 control sets; 'no look-ahead' counts a faculty member as at risk only with a paper in the previous three years, so no future information enters.",
     "Methods: a paper uses a method when its title or OpenAlex topics match a fixed pattern (CRISPR / genome editing, genome or exome sequencing, molecular docking / simulation, machine learning, metagenomics, nanoparticles, proteomics / mass spectrometry, zebrafish). Adoption = first such paper of a faculty member in the window; faculty whose first use is in 2016 are treated as earlier adopters. Exposure = co-authors in the network of earlier years who had adopted. Shuffle test: adoption years permuted among each method's adopters, 200 times.",
     "Simplicial closure: papers with at most 50 authors as hyperedges of faculty; triples active in both periods and never on one 2016–2020 paper; closed = on one 2021–2025 paper. Triples with no tie are counted in full, not sampled.",
     "Generative model: starts from the 2016 network; each year adds the real number of new links among active unlinked pairs, sampled without replacement with weights exp(x′b), with x recomputed on the simulated network; b from a logit with year effects fitted to the real pair-years; 40 simulations per variant.",
     "COVID-19: a paper is on COVID-19 when its title or OpenAlex topics mention SARS-CoV-2, COVID, coronavirus or pandemic; pairs are faculty whose first joint paper (≤ 50 authors) is in 2020–22.",
     "Citation before collaboration: citations between dataset papers where the citing and cited papers share no faculty author, counted for a pair up to the year before; added to the s18 model 4.",
     "Test registry: p-values from s17 (lab exchange, co-author model, led vs middle, persistence, lab impact), s18 (power-law fits, likelihood ratios, tie models, permutation) and s19, with Benjamini–Hochberg across all.",
     "Limits: method detection uses titles and topics, not full text; the shuffle test cannot rule out influence that is simultaneous with collaboration (a method adopted on a joint paper); the COVID comparison has few cross-lab pairs; associations, not causal effects."]
      .forEach((t) => ul.append(txt("li", t)));
    mbox.append(ul);
  }

  // ---------------------------------------------------------------- page: teams, ties and careers (steps s20-s22)
  function renderTeams() {
    const Y = P2.dyn;
    if (!Y) { el("dy-list").textContent = "Run steps s20-s22 to compute this page."; return; }
    const S = Y.summary || {}, ta = S.team_assembly || {}, tp = S.temporal_paths || {}, cm = S.communities || {}, ox = S.openalex_extras || {};
    const tm = Y.team_model || [], tOf = (v, s) => tm.find((r) => r.variant === v && r.statistic === s) || {};
    const rep = Y.tie_repeat || [], rOf = (t) => rep.find((r) => r.term === t) || {};
    const life = Y.tie_life_table || [], lOf = (p, k) => life.find((r) => r.pairs === p && r.years_since_formation === k) || {};
    const bi = Y.brokerage_impact || [], bOf = (m, o, t) => bi.find((r) => r.model === m && r.outcome === o && r.term === t) || {};
    const es = Y.error_sensitivity || [], eOf = (sc, rate) => es.find((r) => r.scenario === sc && (rate === null ? true : Math.abs((r.rate || 0) - rate) < 1e-9)) || {};
    const tps = Y.temporal_paths || [];
    const tObs = (h) => tps.find((r) => r.network === "observed" && r.hops === h) || {};
    const tNull = (h) => { const v = tps.filter((r) => r.network !== "observed" && r.hops === h).map((r) => r.share_reaching_other_lab).sort((a, b) => a - b);
      return v.length ? { mean: v.reduce((a, b) => a + b, 0) / v.length, low: v[Math.floor(0.025 * (v.length - 1))], high: v[Math.ceil(0.975 * (v.length - 1))] } : {}; };
    const comm = Y.communities || [], cOf = (p) => comm.find((r) => r.partition === p) || {};
    const intl = Y.international || [], iOf = (l) => intl.find((r) => r.lab === l) || {};
    const tx = Y.tie_extras || [], xOf = (m, t) => tx.find((r) => r.model === m && r.term === t) || {};
    const si = Y.siena || [], sf = Y.siena_fit || {};
    const m3 = si.filter((r) => String(r.model).startsWith("3"));
    const sOf = (sh, inter) => m3.find((r) => r.short === sh && (inter === undefined || r.interaction === inter)) || {};
    const conv = Object.entries(sf).filter(([k]) => !k.startsWith("_")).map(([k, v]) => `${k.replace(/^\d /, "")}: ${fmt(v.tconv_max, 2)}`).join("; ");
    const design = sf._design || {};
    const india = ox.india_share_of_citing_country_mentions || {};
    const items = [
      ["Papers as groups reproduce the clustering that pairs could not.", `Faculty slots are almost always filled by people already publishing (p = ${fmt(ta.p, 2)}), ${pct(ta.q, 0)} of incumbent pairs repeat a past collaboration and ${pct(ta.h, 0)} of a paper's faculty come from its lead lab. Growing the network paper by paper with these values gives clustering ${fmt(tOf("team model (q, h)", "clustering").sim_mean, 2)} (real ${fmt(tOf("team model (q, h)", "clustering").observed, 2)}), a cross-lab share of ${pct(tOf("team model (q, h)", "cross_lab_share").sim_mean, 1)} (${pct(tOf("team model (q, h)", "cross_lab_share").observed, 1)}) and lab modularity ${fmt(tOf("team model (q, h)", "lab_modularity").sim_mean, 2)} (${fmt(tOf("team model (q, h)", "lab_modularity").observed, 2)}); without lab preference the cross-lab share becomes ${pct(tOf("no lab preference (h = 0)", "cross_lab_share").sim_mean, 0)}.`,
        "Treating papers as groups closes the clustering gap of the pair-by-pair model. The team model gives too few cross-lab links, though: the real ones are not random lapses in lab preference but concentrated in particular people."],
      ["Strong first collaborations last; cross-lab ones fade.", `Five years after their first joint paper, ${pct(1 - (lOf("same lab", 5).share_not_yet_repeated || 0), 0)} of same-lab pairs have written again against ${pct(1 - (lOf("cross-lab", 5).share_not_yet_repeated || 0), 0)} of cross-lab pairs. In the repeat model, each e-fold more papers in the first year multiplies the odds of repeating by ${fmt(rOf("log_first_year_papers").odds_ratio, 1)}; same lab ${fmt(rOf("same_lab").odds_ratio, 2)}× (${fmt(rOf("same_lab").or_low, 2)}–${fmt(rOf("same_lab").or_high, 2)}).`,
        "Ties that start strong survive; most cross-lab ties start as a single paper and are not renewed."],
      ["Brokerage does not pay off in citations.", `Comparing each faculty member with themselves over time, gaining a cross-lab tie changes next-year field-normalised citations by ${fmt(bOf("degree + cross-lab ties", "log_norm_cit", "any_cross_lab").coef, 3)} log points (${fmt(bOf("degree + cross-lab ties", "log_norm_cit", "any_cross_lab").low, 2)} to ${fmt(bOf("degree + cross-lab ties", "log_norm_cit", "any_cross_lab").high, 2)}), and brokerage (1 − Burt's constraint) by ${fmt(bOf("degree + brokerage (1 - constraint)", "log_norm_cit", "brokerage").coef, 2)} (${fmt(bOf("degree + brokerage (1 - constraint)", "log_norm_cit", "brokerage").low, 2)} to ${fmt(bOf("degree + brokerage (1 - constraint)", "log_norm_cit", "brokerage").high, 2)}).`,
        "Within a person, spanning labs brings no measurable citation gain in the following year, which may be one reason cross-lab ties are rarely renewed."],
      ["The results survive plausible data errors.", `With 20% of faculty–paper links dropped the same-lab odds ratio (all faculty pairs) averages ${fmt(eOf("drop links", 0.2).same_lab_or_mean, 0)} (observed ${fmt(eOf("observed", 0).same_lab_or_mean, 0)}); with 5% reassigned to a random faculty member of any lab it is ${fmt(eOf("misassign to any lab", 0.05).same_lab_or_mean, 0)}, with 20% ${fmt(eOf("misassign to any lab", 0.2).same_lab_or_mean, 1)} (95% range ${fmt(eOf("misassign to any lab", 0.2).same_lab_or_low, 1)}–${fmt(eOf("misassign to any lab", 0.2).same_lab_or_high, 1)}). Resampling faculty gives ${fmt(eOf("faculty bootstrap", null).same_lab_or_low, 0)}–${fmt(eOf("faculty bootstrap", null).same_lab_or_high, 0)}; leaving out any one lab keeps it between ${fmt(Math.min(...es.filter((r) => String(r.scenario).startsWith("without")).map((r) => r.same_lab_or_mean)), 0)} and ${fmt(Math.max(...es.filter((r) => String(r.scenario).startsWith("without")).map((r) => r.same_lab_or_mean)), 0)}.`,
        "Dropped links and mix-ups inside a lab leave the effect unchanged; only errors that move papers to people in other labs shrink it, and even 20% of such errors leaves it far above 1. Our affiliation rule makes such cross-lab mix-ups rare."],
      ["In time order, fewer people can reach another lab, but timing is not special.", `The aggregated network joins ${pct(tp.static_share_reaching_other_lab, 0)} of early faculty to every other lab; respecting the order of joint papers with one hop per year, ${pct(tObs("one per year").share_reaching_other_lab, 0)} are reached by 2025 (shuffled years: ${pct(tNull("one per year").mean, 0)}, ${pct(tNull("one per year").low, 0)}–${pct(tNull("one per year").high, 0)}).`,
        "Static networks overstate how far information could have travelled by about seven points, but the real timing of joint papers is no more or less favourable than random timing."],
      ["The network's communities are the labs.", `Louvain runs agree with the lab partition at NMI ${fmt(cm.nmi_runs_mean, 2)}; the consensus has ${fmt(cm.consensus_communities)} communities with a weighted lab purity of ${pct(cm.consensus_mean_lab_purity_weighted, 0)}. The degree-corrected block model compresses the network better with labs (description length ${fmt(cOf("labs").description_length, 0)}) than with departments (${fmt(cOf("lab departments").description_length, 0)}); Louvain consensus ${fmt(cOf("Louvain consensus").description_length, 0)}.`,
        "Data-driven communities and the official labs largely coincide, while departments are too fine a split."],
      ["The actor-oriented model confirms the lab effect and closure, and finds no department effect.", `RSiena on ${fmt(design.actors)} faculty over three waves (ties ${(design.ties_per_wave || []).join(", ")}; Jaccard ${(design.jaccard_between_waves || []).map((j) => fmt(j, 2)).join(", ")}): same lab ${fmt(sOf("sameX", "lab").estimate, 2)} (s.e. ${fmt(sOf("sameX", "lab").se, 2)}; ${fmt(Math.exp(sOf("sameX", "lab").estimate), 1)}× the odds per tie change), same department ${fmt(sOf("sameX", "dept").estimate, 2)} (${fmt(sOf("sameX", "dept").se, 2)}), transitive triads ${fmt(sOf("transTriads").estimate, 2)} (${fmt(sOf("transTriads").se, 2)}), topic similarity ${fmt(sOf("X", "topicSim").estimate, 2)} (${fmt(sOf("X", "topicSim").se, 2)}). Convergence (max ratio, good below 0.25): ${conv}.`,
        "A model in which each faculty member creates and ends ties, with dependence between ties built in and ties allowed to dissolve between waves, gives the same picture as the dyadic models: a large lab effect, no department effect, triadic closure, topic similarity and output."],
      ["Old ties predict new collaborations; shared funders do not.", `Within the tie model, a funder both faculty had already named raises the odds ${fmt(xOf("all extras", "shared_funder").odds_ratio, 2)}× (${fmt(xOf("all extras", "shared_funder").or_low, 2)}–${fmt(xOf("all extras", "shared_funder").or_high, 2)}); a joint paper before 2016 ${fmt(xOf("all extras", "tie_before_2016").odds_ratio, 2)}× (${fmt(xOf("all extras", "tie_before_2016").or_low, 2)}–${fmt(xOf("all extras", "tie_before_2016").or_high, 2)}); career age (sum, per decade) ${fmt(xOf("all extras", "career_age_sum_dec").odds_ratio, 2)}×. The same-lab odds ratio stays ${fmt(xOf("all extras", "same_lab").odds_ratio, 0)}.`,
        `Most pairs share a funder (${pct(ox.shared_funder_share_unlinked, 0)} of unlinked pairs, ${pct(ox.shared_funder_share_new_links, 0)} of new links), so funder data cannot separate them; past collaboration and career stage explain part of who collaborates, but not the lab boundary.`],
      ["The labs reach abroad more easily than to each other.", `${LABS.map((l) => `${short(l)} ${pct(iOf(l).international_share, 0)}`).join(", ")} of papers have a foreign co-author, against ${LABS.map((l) => `${short(l)} ${pct(iOf(l).another_of_our_labs_share, 1)}`).join(", ")} with another of our labs. India's share of country mentions among citing works: ${Object.entries(india).map(([l, v]) => `${short(l)} ${pct(v, 0)}`).join(", ")}.`,
        "The boundary is between the four CSIR labs, not between the labs and the world."],
    ];
    const box = el("dy-list"); box.replaceChildren();
    items.forEach(([h, a, so]) => { const d = document.createElement("div"); d.className = "rqi"; d.append(txt("h3", h), txt("p", a), txt("p", so, "muted")); box.append(d); });

    const gstats = [["cross_lab_share", "cross-lab share"], ["lab_modularity", "lab modularity"], ["clustering", "clustering"], ["transitivity", "transitivity"], ["path_length", "path length"], ["lcc_share", "largest component"], ["links", "links"], ["max_degree", "max degree"]];
    const tv = ["team model (q, h)", "no repeat collaborators (q = 0)", "no lab preference (h = 0)", "neither (q = 0, h = 0)"];
    plot("c-dy-team", tv.map((v, i) => ({ type: "scatter", mode: "markers", name: v, y: gstats.map(([, n]) => n), x: gstats.map(([s]) => tOf(v, s).ratio_to_observed),
      marker: { size: 11, symbol: ["circle", "diamond", "x", "square"][i], color: [css("--lab-1"), css("--lab-3"), css("--lab-2"), css("--qna")][i] },
      hovertemplate: `<b>%{x:.2f}×</b> the real value<br>%{y} · ${v}<extra></extra>` })),
      { xaxis: { type: "log", title: "Simulated ÷ real (log)", tickvals: [0.1, 0.2, 0.5, 1, 2, 5, 10, 20], ticktext: ["0.1×", "0.2×", "0.5×", "1×", "2×", "5×", "10×", "20×"] },
        yaxis: { automargin: true, autorange: "reversed" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 120, r: 16, t: 10, b: 50 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const pq = (Y.team_params || []).filter((r) => r.lab === "ALL");
    plot("c-dy-pq", [["all authors", "incumbent_share_p", "p · all authors", css("--lab-1"), "solid"], ["faculty only", "incumbent_share_p", "p · faculty", css("--lab-1"), "dot"],
      ["all authors", "repeat_share_q", "q · all authors", css("--lab-4"), "solid"], ["faculty only", "repeat_share_q", "q · faculty", css("--lab-4"), "dot"]].map(([t, f, nm, c, d]) => {
      const rr = pq.filter((r) => r.team === t); return { name: nm, x: rr.map((r) => r.year), y: rr.map((r) => r[f]), mode: "lines+markers", line: { color: c, dash: d, width: 2 }, marker: { size: 6 },
        hovertemplate: `<b>%{y:.0%}</b><br>${nm} · %{x}<extra></extra>` }; }),
      { xaxis: { dtick: 1 }, yaxis: { tickformat: ".0%", range: [0, 1.02] }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    plot("c-dy-life", ["same lab", "cross-lab"].map((p, i) => { const rr = [{ years_since_formation: 0, share_not_yet_repeated: 1 }, ...life.filter((r) => r.pairs === p)];
      return { name: p, x: rr.map((r) => r.years_since_formation), y: rr.map((r) => r.share_not_yet_repeated), mode: "lines+markers", line: { color: i ? css("--lab-2") : css("--lab-1"), width: 3, shape: "hv" },
        customdata: rr.map((r) => r.at_risk ?? ""), hovertemplate: `<b>%{y:.0%}</b> not yet repeated<br>${p} · year %{x} · %{customdata} at risk<extra></extra>` }; }),
      { xaxis: { title: "Years since first joint paper", dtick: 1 }, yaxis: { tickformat: ".0%", range: [0, 1.02], title: "Not yet written again" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const BN = { any_cross_lab: "any cross-lab tie", brokerage: "brokerage (1 − constraint)", betweenness_x100: "betweenness (×100)", log_degree: "degree (log)" };
    const bsel = bi.filter((r) => r.term !== "log_degree");
    plot("c-dy-broker", ["log_norm_cit", "log_papers"].map((o, i) => { const rr = bsel.filter((r) => r.outcome === o);
      return { type: "scatter", mode: "markers", name: o === "log_norm_cit" ? "next-year normalised citations (log)" : "next-year papers (log)", x: rr.map((r) => r.coef), y: rr.map((r) => BN[r.term] || r.term),
        error_x: { type: "data", symmetric: false, array: rr.map((r) => r.high - r.coef), arrayminus: rr.map((r) => r.coef - r.low), color: css("--ink-2") },
        marker: { size: 10, color: i ? css("--lab-3") : css("--lab-1"), symbol: i ? "diamond" : "circle" }, hovertemplate: "<b>%{x:.3f}</b><br>%{y}<extra></extra>" }; }),
      { xaxis: { title: "Within-person effect (log points)", zeroline: true }, yaxis: { automargin: true }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 }, margin: { l: 10, r: 16, t: 10, b: 50 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const scen = es.filter((r) => r.scenario !== "observed").map((r) => ({ ...r, label: r.rate ? `${r.scenario} ${pct(r.rate, 0)}` : r.scenario }));
    const obsOR = eOf("observed", 0).same_lab_or_mean;
    plot("c-dy-err", [{ type: "scatter", mode: "markers", x: scen.map((r) => r.same_lab_or_mean), y: scen.map((r) => r.label),
      error_x: { type: "data", symmetric: false, array: scen.map((r) => r.same_lab_or_high - r.same_lab_or_mean), arrayminus: scen.map((r) => r.same_lab_or_mean - r.same_lab_or_low), color: css("--ink-2") },
      marker: { size: 9, color: scen.map((r) => String(r.scenario).startsWith("misassign") ? css("--lab-2") : String(r.scenario).startsWith("drop") ? css("--lab-3") : css("--lab-1")) },
      hovertemplate: "<b>OR %{x:.1f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { type: "log", title: "Same-lab odds ratio (log)", tickvals: [5, 10, 20, 50, 100], ticktext: ["5×", "10×", "20×", "50×", "100×"] }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false,
        margin: { l: 10, r: 16, t: 10, b: 50 }, shapes: [{ type: "line", xref: "x", yref: "paper", x0: obsOR, x1: obsOR, y0: 0, y1: 1, line: { color: css("--ink"), dash: "dash", width: 1 } }] });

    const hops = ["one per year", "several per year"];
    plot("c-dy-temp", [
      { type: "bar", name: "observed", x: hops, y: hops.map((h) => tObs(h).share_reaching_other_lab), marker: { color: css("--lab-1") }, hovertemplate: "<b>%{y:.0%}</b> reached<br>%{x} · observed<extra></extra>" },
      { type: "bar", name: "shuffled contact years", x: hops, y: hops.map((h) => tNull(h).mean), marker: { color: css("--qna") },
        error_y: { type: "data", symmetric: false, array: hops.map((h) => tNull(h).high - tNull(h).mean), arrayminus: hops.map((h) => tNull(h).mean - tNull(h).low), color: css("--ink-2") },
        hovertemplate: "<b>%{y:.0%}</b> reached<br>%{x} · shuffled<extra></extra>" }],
      { barmode: "group", yaxis: { tickformat: ".0%", range: [0, 1], title: "Early faculty × other lab reached" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 },
        shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: tp.static_share_reaching_other_lab, y1: tp.static_share_reaching_other_lab, line: { color: css("--ink"), dash: "dash", width: 1 } }],
        annotations: [{ xref: "paper", yref: "y", x: 1, y: tp.static_share_reaching_other_lab, text: "static network", showarrow: false, xanchor: "right", yanchor: "bottom", font: { size: 11 } }] });

    table("t-dy-comm", comm, [
      { title: "Partition", field: "partition", widthGrow: 2 }, { title: "Blocks", field: "blocks", hozAlign: "right" },
      { title: "Description length (nats)", field: "description_length", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 0) },
      { title: "NMI with labs", field: "nmi_with_labs", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
      { title: "ARI with labs", field: "ari_with_labs", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
      { title: "NMI with departments", field: "nmi_with_departments", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
      { title: "Modularity", field: "modularity", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }], { layout: "fitColumns" });

    const SN = (r) => ({ density: "degree (density)", transTriads: "transitive triads", degPlus: "degree of alter", sameX: `same ${r.interaction === "lab" ? "lab" : "department"}`, X: "topic similarity",
      egoPlusAltX: r.interaction === "senior" ? "seniority (both)" : "output (both)", Rate: "rate" })[r.short] || r.effect;
    const m3e = m3.filter((r) => r.type === "eval" && r.short !== "Rate");
    plot("c-dy-siena", [{ type: "scatter", mode: "markers", x: m3e.map((r) => r.estimate), y: m3e.map((r) => SN(r)),
      error_x: { type: "data", array: m3e.map((r) => 1.96 * r.se), color: css("--ink-2") },
      marker: { size: 10, color: m3e.map((r) => r.short === "sameX" && r.interaction === "lab" ? css("--lab-1") : css("--lab-3")) },
      hovertemplate: "<b>%{x:.2f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { title: "Estimate (log-odds)", zeroline: true }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false, margin: { l: 10, r: 16, t: 10, b: 50 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });
    table("t-dy-siena", si.map((r) => ({ ...r, eff: SN(r), conv: fmt((sf[r.model] || {}).tconv_max, 3) })), [
      { title: "Model", field: "model", widthGrow: 2 }, { title: "Effect", field: "eff", widthGrow: 2 },
      { title: "Estimate", field: "estimate", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }, { title: "s.e.", field: "se", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) },
      { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toPrecision(2) },
      { title: "Convergence t", field: "t_conv", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }, { title: "Model max ratio", field: "conv", hozAlign: "right" }],
      { layout: "fitColumns", maxHeight: 380 });

    const XN = { shared_funder: "shared funder", tie_before_2016: "joint paper before 2016", career_age_sum_dec: "career age, sum (per decade)", career_age_gap_dec: "career age gap (per decade)", same_lab: "same lab" };
    const xe = tx.filter((r) => r.model === "all extras" && XN[r.term]);
    plot("c-dy-extra", [{ type: "scatter", mode: "markers", x: xe.map((r) => r.odds_ratio), y: xe.map((r) => XN[r.term]),
      error_x: { type: "data", symmetric: false, array: xe.map((r) => r.or_high - r.odds_ratio), arrayminus: xe.map((r) => r.odds_ratio - r.or_low), color: css("--ink-2") },
      marker: { size: 10, color: xe.map((r) => r.term === "same_lab" ? css("--lab-1") : css("--lab-4")) }, hovertemplate: "<b>odds ratio %{x:.2f}</b><br>%{y}<extra></extra>" }],
      { xaxis: { type: "log", title: "Odds ratio (log)" }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false, margin: { l: 10, r: 16, t: 10, b: 50 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: css("--muted"), dash: "dash", width: 1 } }] });

    const sc = [...LABS, "ALL"];
    plot("c-dy-intl", [["international_share", "foreign co-author", css("--lab-1")], ["other_indian_institution_share", "another Indian institution", css("--lab-3")], ["another_of_our_labs_share", "another of our four labs", css("--lab-2")]].map(([f, nm, c]) => ({
      type: "bar", name: nm, x: sc.map(scopeLabel), y: sc.map((l) => iOf(l)[f]), marker: { color: c }, hovertemplate: `<b>%{y:.1%}</b> of papers<br>%{x} · ${nm}<extra></extra>` })),
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share of papers" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const wc = (Y.world_citers || []).filter((r) => r.kind === "country");
    const topC = [...new Set(wc.sort((a, b) => b.citing_works - a.citing_works).map((r) => r.name))].slice(0, 8);
    plot("c-dy-world", LABS.map((l) => ({ type: "bar", name: short(l), x: topC, y: topC.map((c) => (wc.find((r) => r.lab === l && r.name === c) || {}).share_of_country_mentions || 0),
      marker: { color: labColor(l) }, hovertemplate: `<b>%{y:.1%}</b> of country mentions<br>%{x} · ${short(l)}<extra></extra>` })),
      { barmode: "group", yaxis: { tickformat: ".0%", title: "Share of citing country mentions" }, legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0 } });

    const mbox = el("dy-methods"); mbox.replaceChildren();
    const ul = document.createElement("ul");
    ["Team assembly: full author teams rebuilt from the submitted authorship network (papers with ≤ 50 authors) and faculty teams from the main file; incumbent = appeared on a paper in an earlier year of the window (2016 is burn-in).",
     "Tie survival: pairs whose first joint paper is in 2016–2024, followed for up to five years; discrete-time logit of a second joint paper with years-since and cohort effects, dyadic-robust errors.",
     "Brokerage: faculty network of the previous three years; Burt's constraint, effective size and betweenness; outcomes = mean field-and-year normalised citations and log papers in the year; faculty and year fixed effects by within-faculty demeaning; errors clustered by faculty.",
     "Error sensitivity: static all-pairs logit (same lab, topic similarity, output) re-estimated after random drops or reassignments of faculty–paper rows (20 runs per rate), 200 faculty bootstraps and leave-one-lab-out.",
     "Temporal paths: earliest-arrival search from faculty with a paper by 2017 through yearly contact lists; null = contact years permuted across contacts (100 runs).",
     "Communities: 100 Louvain runs, consensus by clustering the co-occurrence matrix (Lancichinetti & Fortunato 2012); degree-corrected SBM log-likelihood (Karrer & Newman 2011) plus block-matrix and partition costs as description length.",
     "RSiena: actors = faculty with a paper by 2018 and in 2022–25; three waves; modelType 2 (one actor can create or end a tie); effects degree, transitive triads, degree of alter, same lab, same department, topic similarity, seniority and output of both actors; estimates repeated from the previous answer until the maximum convergence ratio is below 0.25 (up to four runs).",
     "OpenAlex extras (step s20, 698 calls): funders on each paper; author countries; each faculty member's publication years anywhere (first years before 1960 treated as merged profiles); faculty pairs on papers before 2016; citing works 2016–2026 grouped by author country and field (works citing papers in several batches can be counted more than once).",
     "Limits: OpenAlex funder and country coverage is incomplete; the brokerage panel is short (2017–2025); RSiena uses a fixed set of continuously active faculty; associations, not causal effects."]
      .forEach((t) => ul.append(txt("li", t)));
    mbox.append(ul);
  }

  // ---------------------------------------------------------------- author and affiliation checks (About tab)
  function renderQualityPanel(add, list) {
    const Q = P2.summary.quality, M = P2.summary.meeting_abstracts || { papers: 0 };
    if (!Q) return;
    const cur = Q.per_lab.reduce((a, r) => a + r.current, 0), former = Q.per_lab.reduce((a, r) => a + r.former, 0);
    add("h3", "Author and affiliation checks");
    list([
      `Faculty lists: ${fmt(Q.roster)} faculty on the four rosters (${fmt(cur)} current, ${fmt(former)} former). ${fmt(Q.faculty_with_papers)} have at least one paper in the window and ${fmt(Q.faculty_without_papers)} have none (${Q.per_lab.map((r) => `${short(r.lab)} ${r.without_papers}`).join(", ")}).`,
      `Identity: a profile is matched to an OpenAlex author by ORCID first (${fmt(Q.roster_with_orcid)} roster entries carry one), then by the papers listed on the lab profile page (${fmt(Q.roster_with_profile_dois)} entries), then by an unambiguous display name; ${fmt(Q.manual_match_decisions)} matches were decided by hand. Checks that must come out at zero: OpenAlex author IDs shared by two faculty = ${Q.openalex_ids_shared_by_two_faculty}; faculty in more than one lab = ${Q.faculty_in_more_than_one_lab}; duplicate names on the roster = ${Q.duplicate_roster_names}; faculty without an author ID = ${Q.faculty_without_openalex_id}.`,
      `Affiliation: a paper counts for a faculty member only when that person's own authorship carries the lab. ${fmt(Q.affiliation_lineage_rows)} of ${fmt(Q.rows)} faculty-paper rows (${pct(Q.affiliation_lineage_rows / Q.rows, 1)}) show it through OpenAlex's institution record and ${fmt(Q.affiliation_text_rows)} through the raw affiliation text.`,
      `Departments come from the lab websites for ${fmt(Q.dept_from_website_rows)} rows and from OpenAlex for ${fmt(Q.dept_from_openalex_rows)}. Journal quartiles come from SJR for ${fmt(Q.quartile_sjr_rows)} rows; ${fmt(Q.quartile_none_rows)} rows have no quartile (conference papers and journals SJR does not list).`,
      "Students and other non-faculty lab authors appear only in the all-authors network; the faculty-only network and its yearly measures use roster faculty only. Their papers stay in every publication count.",
      `${fmt(M.papers)} conference or poster abstracts that journals print in supplements (for example in the European Heart Journal) are counted as publications but kept out of the impact-factor ranked top-30 and top-10 lists, because they inherit the journal's impact factor.`,
    ]);
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
    el("dept-small").addEventListener("change", renderDepts);
  };

  Object.assign(P2API, { questions: renderQuestions, quality: renderQualityPanel });
  Object.assign(P2REG, { impact: renderImpact, compare: renderCompare, instnet: renderInstNet, flags: renderFlags, findings: renderFindings, models: renderModels, extensions: renderExtensions, teams: renderTeams });
}
