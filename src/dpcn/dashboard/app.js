/* Group 29 dashboard. Every panel reads `state.lab` (a lab short name or "ALL") and re-renders from the
   embedded data bundle (built by S13 from outputs/stats and outputs/networks). */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("data").textContent);
  const LABS = D.meta.labs;
  const SHAPES = ["ellipse", "round-rectangle", "triangle", "diamond"];
  const state = { lab: "ALL", tab: "overview", layer: "faculty", colorby: "lab" };
  const rendered = {};
  const tables = {};
  let cyCit = null, cyAu = null;

  // ------------------------------------------------------------------ helpers
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const labColor = (lab) => { const i = LABS.indexOf(lab); return i < 0 ? css("--multi") : css(`--lab-${i + 1}`); };
  const labShape = (lab) => { const i = LABS.indexOf(lab); return i < 0 ? "star" : SHAPES[i]; };
  const short = (lab) => (lab || "").replace("CSIR-", "");
  const inkOn = (hex) => {   // text colour for a label sitting on a filled mark
    const n = parseInt(hex.replace("#", ""), 16), r = n >> 16 & 255, g = n >> 8 & 255, b = n & 255;
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.55 ? "#0b0b0b" : "#ffffff";
  };
  const ABBR = [["National Institute of Pharmaceutical Education and Research", "NIPER"], ["All India Institute of Medical Sciences", "AIIMS"],
    ["Post Graduate Institute of Medical Education and Research", "PGIMER"], ["Indian Institute of Technology", "IIT"],
    ["International Journal of", "Int. J."], ["Journal of", "J."], ["Institute", "Inst."], ["University", "Univ."]];
  const abbr = (t, n = 40) => { let o = String(t); for (const [a, b] of ABBR) { if (o.length <= n) break; o = o.split(a).join(b); }
    return o.length > n ? o.slice(0, n - 1) + "…" : o; };
  // horizontal bars keyed by full name (unique) but labelled with a short form
  const ticks = (names) => ({ tickmode: "array", tickvals: names, ticktext: names.map((x) => abbr(x)), automargin: true });
  const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? "–" :
    Number(x).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
  const pct = (x, d = 1) => (x === null || x === undefined) ? "–" : `${(100 * x).toFixed(d)}%`;
  const byScope = (rows, key = "scope") => rows.filter((r) => r[key] === state.lab);
  const inLab = (labsField) => state.lab === "ALL" || String(labsField || "").split(/;\s*/).includes(state.lab);
  const scopes = () => state.lab === "ALL" ? LABS : [state.lab];
  const el = (id) => document.getElementById(id);
  const doiLink = (cell) => { const v = cell.getValue(); if (!v) return ""; const a = document.createElement("a");
    a.href = v; a.target = "_blank"; a.rel = "noopener"; a.textContent = v.replace("https://", ""); return a; };

  function layout(extra = {}) {
    const ink2 = css("--ink-2"), grid = css("--grid");
    return Object.assign({
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui, -apple-system, Segoe UI, sans-serif", size: 12, color: ink2 },
      margin: { l: 50, r: 16, t: 10, b: 40 },
      xaxis: { gridcolor: grid, linecolor: css("--axis"), zeroline: false },
      yaxis: { gridcolor: grid, linecolor: css("--axis"), zeroline: false, rangemode: "tozero", automargin: true },
      legend: { orientation: "h", y: -0.18, font: { color: ink2 } },
      hoverlabel: { bgcolor: css("--surface"), bordercolor: css("--axis"), font: { color: css("--ink") } },
    }, extra);
  }
  const plot = (id, traces, lay) => Plotly.react(id, traces, layout(lay), { displaylogo: false, responsive: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] });

  function plainTable(id, rows, columns, opts) {   // screenshot mode: a static table drawn synchronously
    const box = el(id); box.replaceChildren();
    const t = document.createElement("table"); t.className = "plain";
    const tr = document.createElement("tr");
    columns.forEach((c) => { const th = document.createElement("th"); th.textContent = c.title; tr.append(th); });
    t.append(tr);
    let data = [...rows];
    const s0 = (opts.initialSort || [])[0];
    if (s0) data.sort((a, b) => (s0.dir === "desc" ? -1 : 1) * ((a[s0.column] ?? -Infinity) > (b[s0.column] ?? -Infinity) ? 1 : -1));
    data.slice(0, opts.shotRows || 12).forEach((r) => {
      const row = document.createElement("tr");
      columns.forEach((c) => {
        const td = document.createElement("td"); const v = r[c.field];
        const out = typeof c.formatter === "function" ? c.formatter({ getValue: () => v }) : v;
        if (out instanceof Node) td.append(out); else td.textContent = out ?? "";
        if (c.hozAlign === "right") td.style.textAlign = "right";
        row.append(td);
      });
      t.append(row);
    });
    box.append(t);
    return null;
  }

  function table(id, rows, columns, opts = {}) {
    if (document.body.classList.contains("shot")) return plainTable(id, rows, columns, opts);
    // tables are small: rebuild on every render (updating a Tabulator that is still building throws)
    if (tables[id]) { try { tables[id].destroy(); } catch (e) { /* not built yet */ } }
    const t = new Tabulator(`#${id}`, Object.assign({ data: rows, columns, layout: "fitDataStretch",
      maxHeight: opts.maxHeight || 420, pagination: false, renderVertical: "basic", placeholder: "No rows for this selection" }, opts));
    t.on("tableBuilt", () => { t.built = true; });
    tables[id] = t;
    return t;
  }

  function kpis(id, items) {
    const box = el(id); box.replaceChildren();
    for (const [label, value, sub] of items) {
      const k = document.createElement("div"); k.className = "kpi";
      const v = document.createElement("div"); v.className = "v"; v.textContent = value;
      const l = document.createElement("div"); l.className = "l"; l.textContent = label;
      k.append(v, l);
      if (sub) { const s = document.createElement("div"); s.className = "s"; s.textContent = sub; k.append(s); }
      box.append(k);
    }
  }

  function legend(id, items) {
    const box = el(id); box.replaceChildren();
    for (const [color, label, shape] of items) {
      const s = document.createElement("span"); const i = document.createElement("i"); i.style.background = color;
      if (shape === "triangle") i.style.clipPath = "polygon(50% 0, 100% 100%, 0 100%)";
      if (shape === "diamond") i.style.clipPath = "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)";
      if (shape === "ellipse") i.style.borderRadius = "50%";
      if (shape === "dash") { i.style.height = "0"; i.style.borderTop = `2px dashed ${color}`; i.style.background = "none"; }
      s.append(i, document.createTextNode(label)); box.append(s);
    }
  }

  function info(id, title, pairs, link) {
    const box = el(id); box.replaceChildren();
    const h = document.createElement("h3"); h.textContent = title; box.append(h);
    const dl = document.createElement("dl");
    for (const [k, v] of pairs) { const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v; dl.append(dt, dd); }
    box.append(dl);
    if (link) { const a = document.createElement("a"); a.href = link; a.target = "_blank"; a.rel = "noopener";
      a.textContent = "Open DOI ↗"; const p = document.createElement("p"); p.append(a); box.append(p); }
  }

  // ------------------------------------------------------------------ tab: overview
  function renderOverview() {
    const s = D.summary.find((r) => r.scope === state.lab);
    const cagrKey = Object.keys(s).find((k) => k.startsWith("cagr_"));
    kpis("kpis", [
      ["Papers", fmt(s.papers), `${fmt(s.journal_papers)} journal · ${fmt(s.conference_papers)} conference`],
      ["Citations", fmt(s.citations), `median ${fmt(s.median_citations)} per paper`],
      ["Faculty with papers", fmt(s.faculty_with_papers), `of ${fmt(s.roster_faculty)} on the roster`],
      ["Q1 fraction", pct(s.q1_fraction), `quartile known for ${pct(s.quartile_coverage, 0)}`],
      ["Institutional h-index", fmt(s.institutional_h), "over 2016–2026 papers"],
      ["Growth (CAGR)", pct(s[cagrKey]), cagrKey.replace("cagr_", "").replace("_", "–")],
      ["Indian partner co-authors", pct(s.pct_indian_partner_collab, 0), `foreign co-authors ${pct(s.pct_foreign_collab, 0)}`],
    ]);
    const py = D.meta.partial_year;
    const traces = scopes().map((lab) => {
      const rows = D.trend.filter((r) => r.scope === lab);
      return { x: rows.map((r) => r.year), y: rows.map((r) => r.papers), name: short(lab), mode: "lines+markers",
        line: { color: labColor(lab), width: 2 }, marker: { size: 8, line: { color: css("--surface"), width: 2 } },
        hovertemplate: `<b>%{y}</b> papers<br>${short(lab)} · %{x}<extra></extra>` };
    });
    plot("c-trend", traces, { hovermode: "x unified", xaxis: { dtick: 1, gridcolor: css("--grid") },
      shapes: [{ type: "rect", xref: "x", yref: "paper", x0: py - 0.5, x1: py + 0.5, y0: 0, y1: 1,
                 fillcolor: css("--grid"), opacity: 0.5, line: { width: 0 }, layer: "below" }],
      margin: { l: 50, r: 70, t: 10, b: 40 },
      annotations: [{ x: py, y: 1, yref: "paper", text: "partial", showarrow: false, font: { size: 11, color: css("--muted") } },
        ...traces.map((t) => { const i = t.x.indexOf(py - 1);   // label the last full year; the partial year crowds
          return { x: t.x[i], y: t.y[i], text: t.name, xanchor: "left", yanchor: "bottom", xshift: 4, yshift: 4,
            showarrow: false, font: { size: 11, color: css("--ink-2") } }; })] });
    plot("c-cites", scopes().map((lab) => {
      const rows = D.trend.filter((r) => r.scope === lab);
      return { type: "bar", x: rows.map((r) => r.year), y: rows.map((r) => r.citations), name: short(lab),
        marker: { color: labColor(lab), line: { color: css("--surface"), width: 1 } },
        hovertemplate: `<b>%{y:,}</b> citations<br>${short(lab)} · %{x}<extra></extra>` };
    }), { barmode: "stack", xaxis: { dtick: 1 }, legend: { orientation: "h", y: -0.18, traceorder: "normal" } });
    table("t-summary", D.summary.map((r) => ({ ...r, scope: short(r.scope) })), [
      { title: "Scope", field: "scope", frozen: true }, { title: "Papers", field: "papers", hozAlign: "right" },
      { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Q1 %", field: "q1_fraction", hozAlign: "right", formatter: (c) => pct(c.getValue()) },
      { title: "h (inst.)", field: "institutional_h", hozAlign: "right" },
      { title: "Papers / faculty", field: "papers_per_faculty", hozAlign: "right" },
      { title: "% uncited", field: "pct_uncited", hozAlign: "right", formatter: (c) => pct(c.getValue()) },
      { title: "Authors / paper", field: "mean_authors", hozAlign: "right" },
    ]);
  }

  // ------------------------------------------------------------------ tab: journals
  function renderJournals() {
    const sc = state.lab === "ALL" ? [...LABS, "ALL"] : [state.lab, "ALL"];
    const qs = ["Q1", "Q2", "Q3", "Q4", "NA"];
    const qc = { Q1: css("--q1"), Q2: css("--q2"), Q3: css("--q3"), Q4: css("--q4"), NA: css("--qna") };
    plot("c-quart", qs.map((q) => ({ type: "bar", orientation: "h", name: q === "NA" ? "No quartile" : q,
      y: sc.map(short), x: sc.map((s) => (D.quartiles.find((r) => r.scope === s && r.quartile === q) || {}).share_of_journal || 0),
      customdata: sc.map((s) => (D.quartiles.find((r) => r.scope === s && r.quartile === q) || {}).papers || 0),
      marker: { color: qc[q], line: { color: css("--surface"), width: 2 } },
      text: sc.map((s) => { const v = (D.quartiles.find((r) => r.scope === s && r.quartile === q) || {}).share_of_journal || 0; return v >= 0.08 ? pct(v, 0) : ""; }),
      textposition: "inside", insidetextanchor: "middle", textfont: { color: inkOn(qc[q]) },
      hovertemplate: `<b>%{x:.1%}</b> (%{customdata} papers)<br>%{y} · ${q}<extra></extra>` })),
      { barmode: "stack", xaxis: { tickformat: ".0%", range: [0, 1] }, yaxis: { autorange: "reversed" }, margin: { l: 70, r: 10, t: 10, b: 50 },
        legend: { orientation: "h", y: -0.18, traceorder: "normal" } });

    const tj = D.top_journals.filter((r) => r.scope === state.lab);
    const rev = [...tj].reverse();
    plot("c-journals", [{ type: "bar", orientation: "h", y: rev.map((r) => r.journal_name),
      x: rev.map((r) => r.papers), text: rev.map((r) => `${r.papers} · ${r.quartile}`), textposition: "outside", cliponaxis: false,
      marker: { color: state.lab === "ALL" ? css("--multi") : labColor(state.lab) },
      customdata: rev.map((r) => [r.journal_name, r.citations]),
      hovertemplate: "<b>%{x} papers</b><br>%{customdata[0]}<br>%{customdata[1]:,} citations<extra></extra>" }],
      { margin: { l: 230, r: 60, t: 10, b: 40 }, showlegend: false, yaxis: ticks(rev.map((r) => r.journal_name)) });
    table("t-journals", (state.lab === "ALL" ? D.top_journals.filter((r) => r.scope !== "ALL") : tj).map((r) => ({ ...r, scope: short(r.scope) })), [
      { title: "Lab", field: "scope" }, { title: "#", field: "rank", hozAlign: "right" }, { title: "Journal", field: "journal_name", widthGrow: 3 },
      { title: "Papers", field: "papers", hozAlign: "right" }, { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Quartile", field: "quartile" }]);

    const core = D.core.filter((r) => r.scope === state.lab);
    const n = core.length ? core[0].conference_papers : 0;
    const ranked = core.filter((r) => r.rank !== "NA").reduce((a, r) => a + r.papers, 0);
    el("core-note").textContent = `CORE ranks computer-science venues, so it rarely applies to biology labs: ${ranked} of ${n} conference papers (${short(state.lab)}) are in a CORE-ranked venue. All other papers are journal papers ranked by SJR quartile.`;
    plot("c-core", [{ type: "bar", x: core.map((r) => r.rank === "NA" ? "Unranked" : r.rank), y: core.map((r) => r.papers),
      marker: { color: core.map((r) => r.rank === "NA" ? css("--qna") : css("--q2")) }, text: core.map((r) => String(r.papers)),
      textposition: "outside", cliponaxis: false, hovertemplate: "<b>%{y}</b> conference papers<br>%{x}<extra></extra>" }],
      { showlegend: false, yaxis: { dtick: 1 } });
  }

  // ------------------------------------------------------------------ tab: faculty
  function renderFaculty() {
    const rows = D.faculty.filter((r) => state.lab === "ALL" || r.lab === state.lab).map((r) => ({ ...r, lab: short(r.lab) }));
    const compact = el("compact").checked;
    const full = [
      { title: "Name", field: "name", headerFilter: "input", frozen: true, minWidth: 150 },
      { title: "Lab", field: "lab", headerFilter: "input" },
      { title: "Department", field: "department", headerFilter: "input", maxWidth: 260 },
      { title: "Designation", field: "designation" },
      { title: "Papers", field: "papers", hozAlign: "right", sorter: "number" },
      { title: "Citations", field: "citations", hozAlign: "right", sorter: "number" },
      { title: "Cites/paper", field: "cites_per_paper", hozAlign: "right", sorter: "number" },
      { title: "h (2016–26)", field: "h_window", hozAlign: "right", sorter: "number" },
      { title: "h (lifetime)", field: "h_lifetime", hozAlign: "right", sorter: "number" },
      { title: "Top journal", field: "top_journal", maxWidth: 240 },
      { title: "Q1 %", field: "q1_fraction", hozAlign: "right", sorter: "number", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Co-author degree", field: "degree", hozAlign: "right", sorter: "number" },
      { title: "Betweenness", field: "betweenness", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 3) },
      { title: "Status", field: "status" },
    ];
    const cols = compact ? full.filter((c) => ["name", "department", "h_window", "papers", "lab"].includes(c.field)) : full;
    table("t-faculty", rows, cols, { maxHeight: 520, initialSort: [{ column: "papers", dir: "desc" }] });

    const bins = [...new Set(D.hindex.filter((r) => r.bin !== "summary").map((r) => r.bin_start))].sort((a, b) => a - b);
    plot("c-hindex", scopes().map((lab) => {
      const rr = D.hindex.filter((r) => r.scope === lab && r.bin !== "summary");
      return { type: "bar", name: short(lab), x: bins.map((b) => `${b}–${b + 4}`),
        y: bins.map((b) => (rr.find((r) => r.bin_start === b) || {}).faculty || 0),
        marker: { color: labColor(lab), line: { color: css("--surface"), width: 1 } },
        hovertemplate: `<b>%{y}</b> faculty<br>${short(lab)} · h %{x}<extra></extra>` };
    }), { barmode: state.lab === "ALL" ? "stack" : "group", yaxis: { title: "Faculty", automargin: true }, legend: { orientation: "h", y: -0.18, traceorder: "normal" } });

    table("t-dept", D.departments.filter((r) => state.lab === "ALL" || r.lab === state.lab).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Lab", field: "lab" }, { title: "Department", field: "department", widthGrow: 3 },
      { title: "Faculty", field: "faculty", hozAlign: "right" }, { title: "Papers", field: "papers", hozAlign: "right" },
      { title: "Citations", field: "citations", hozAlign: "right" },
      { title: "Q1 %", field: "q1_fraction", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
      { title: "Mean h", field: "mean_h_window", hozAlign: "right" }], { maxHeight: 340 });
  }

  // ------------------------------------------------------------------ tab: research
  function renderResearch() {
    const rows = D.areas.filter((r) => r.scope === state.lab);
    const fields = {};
    rows.forEach((r) => { fields[r.field] = (fields[r.field] || 0) + r.papers; });
    const ids = [], labels = [], parents = [], values = [];
    Object.entries(fields).forEach(([f, v]) => { ids.push(`f:${f}`); labels.push(f); parents.push(""); values.push(v); });
    rows.forEach((r) => { ids.push(`s:${r.field}:${r.subfield}`); labels.push(r.subfield); parents.push(`f:${r.field}`); values.push(r.papers); });
    plot("c-areas", [{ type: "sunburst", ids, labels, parents, values, branchvalues: "total", maxdepth: 2,
      insidetextorientation: "radial", marker: { line: { color: css("--surface"), width: 1 } },
      hovertemplate: "<b>%{value} papers</b><br>%{label}<br>%{percentRoot:.1%} of papers<extra></extra>" }],
      { margin: { l: 0, r: 0, t: 0, b: 0 } });
    const top = Object.entries(fields).sort((a, b) => b[1] - a[1]);
    const total = top.reduce((a, [, v]) => a + v, 0);
    const shown = top.slice(0, 12).reverse();
    plot("c-fields", [{ type: "bar", orientation: "h", y: shown.map(([f]) => f), x: shown.map(([, v]) => v / total),
      text: shown.map(([, v]) => pct(v / total, 1)), textposition: "outside", cliponaxis: false,
      marker: { color: state.lab === "ALL" ? css("--multi") : labColor(state.lab) },
      hovertemplate: "<b>%{x:.1%}</b> of papers<br>%{y}<extra></extra>" }],
      { margin: { l: 230, r: 50, t: 10, b: 40 }, xaxis: { tickformat: ".0%" }, showlegend: false });
    table("t-cited", D.top_cited.filter((r) => r.scope === state.lab), [
      { title: "#", field: "rank", hozAlign: "right", width: 44 }, { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" },
      { title: "Journal", field: "journal", widthGrow: 2, formatter: "textarea" }, { title: "Year", field: "year" },
      { title: "Citations", field: "citations", hozAlign: "right" }, { title: "Labs", field: "labs" },
      { title: "DOI", field: "doi", formatter: doiLink, widthGrow: 2 }], { layout: "fitColumns" });
  }

  // ------------------------------------------------------------------ tab: citation network
  function renderCitation() {
    const cs = D.citation_summary;
    const fs = D.flow_summary.filter((r) => state.lab === "ALL" || r.lab === state.lab);
    const sum = (k) => fs.reduce((a, r) => a + (r[k] || 0), 0);
    kpis("kpis-cit", [
      ["Papers (nodes)", fmt(cs.nodes), "all dataset papers"], ["Internal citations", fmt(cs.internal_edges), "paper → paper edges"],
      ["Largest component", fmt(cs.largest_wcc), `${pct(cs.largest_wcc / cs.nodes, 0)} of papers`],
      ["Never cited internally", pct(cs.share_indeg_0, 0), `max in-degree ${cs.max_indeg}`],
      ["Cites in (Indian)", fmt(sum("cites_in")), state.lab === "ALL" ? "all four labs" : short(state.lab)], ["Cites out (Indian)", fmt(sum("cites_out")), state.lab === "ALL" ? "all four labs" : short(state.lab)],
      ["Impact ratio in/out", fmt(sum("cites_out") ? sum("cites_in") / sum("cites_out") : null, 2), "citations received ÷ given"],
    ]);
    const G = D.citation_graph;
    el("cit-n").textContent = String(G.nodes.length);
    const keep = new Set(G.nodes.filter((n) => inLab(n.labs)).map((n) => n.id));
    const maxPr = Math.max(...G.nodes.map((n) => n.pr));
    const elements = [
      ...G.nodes.filter((n) => keep.has(n.id)).map((n) => ({ data: { ...n, size: 10 + 40 * Math.sqrt(n.pr / maxPr),
        color: labColor(n.lab), shape: labShape(n.lab) }, position: { x: n.x, y: n.y } })),
      ...G.edges.filter((e) => keep.has(e.s) && keep.has(e.t)).map((e, i) => ({ data: { id: `e${i}`, source: e.s, target: e.t } })),
    ];
    if (cyCit) cyCit.destroy();
    cyCit = cytoscape({ container: el("g-cit"), elements, layout: { name: "preset", fit: true, padding: 20 },
      wheelSensitivity: 0.25, minZoom: 0.1, maxZoom: 6,
      style: [
        { selector: "node", style: { width: "data(size)", height: "data(size)", "background-color": "data(color)", shape: "data(shape)",
          "border-width": 1.5, "border-color": css("--surface") } },
        { selector: "edge", style: { width: 0.8, "line-color": css("--axis"), "target-arrow-color": css("--axis"),
          "target-arrow-shape": "triangle", "arrow-scale": 0.6, "curve-style": "straight", opacity: 0.7 } },
        { selector: "node:selected", style: { "border-color": css("--ink"), "border-width": 3 } },
        { selector: ".faded", style: { opacity: 0.12 } },
      ] });
    cyCit.on("tap", "node", (ev) => {
      const d = ev.target.data();
      info("cit-info", d.label, [["Year", d.year], ["Labs", d.labs.split(";").map(short).join(", ")], ["PageRank", d.pr.toFixed(5)],
        ["Cited by corpus", d.indeg], ["Total citations", fmt(d.cit)]], d.doi);
      cyCit.elements().addClass("faded"); ev.target.closedNeighborhood().removeClass("faded");
    });
    cyCit.on("tap", (ev) => { if (ev.target === cyCit) cyCit.elements().removeClass("faded"); });
    hoverTip(cyCit, (d) => `${d.label} (${d.year}) · PageRank ${d.pr.toFixed(4)}`);
    legend("leg-cit", [...LABS.map((l) => [labColor(l), short(l), labShape(l)]), [css("--multi"), "Multi-lab", "star"]]);

    table("t-pr", D.pagerank_top.filter((r) => r.scope === state.lab), [
      { title: "Title", field: "title", widthGrow: 4, formatter: "textarea" }, { title: "Year", field: "year" },
      { title: "Labs", field: "labs", formatter: (c) => String(c.getValue() || "").split(";").map(short).join(", ") },
      { title: "In-degree", field: "indeg", hozAlign: "right" }, { title: "PageRank", field: "pagerank", hozAlign: "right", formatter: (c) => c.getValue().toFixed(5) },
      { title: "DOI", field: "doi", formatter: doiLink, widthGrow: 2 }], { layout: "fitColumns" });

    const ind = D.indegree.filter((r) => r.in_degree > 0);
    plot("c-indeg", [{ x: ind.map((r) => r.in_degree), y: ind.map((r) => r.papers), mode: "markers",
      marker: { size: 8, color: css("--accent"), line: { color: css("--surface"), width: 1.5 } },
      hovertemplate: "<b>%{y} papers</b><br>in-degree %{x}<extra></extra>" }],
      { xaxis: { type: "log", title: "In-degree" }, yaxis: { type: "log", title: "Papers" }, showlegend: false });

    const fy = D.flow_year;
    const tr = [];
    for (const lab of scopes()) {
      const r = fy.filter((x) => x.lab === lab);
      tr.push({ x: r.map((x) => x.year), y: r.map((x) => x.in), name: `${short(lab)} in`, mode: "lines+markers",
        line: { color: labColor(lab), width: 2 }, marker: { size: 8 }, hovertemplate: `<b>%{y}</b> citations received<br>${short(lab)} · %{x}<extra></extra>` });
      tr.push({ x: r.map((x) => x.year), y: r.map((x) => x.out), name: `${short(lab)} out`, mode: "lines+markers",
        line: { color: labColor(lab), width: 2, dash: "dot" }, marker: { size: 8, symbol: "diamond" },
        hovertemplate: `<b>%{y}</b> citations given<br>${short(lab)} · %{x}<extra></extra>` });
    }
    plot("c-flow", tr, { hovermode: "x unified", xaxis: { dtick: 1 } });

    const ci = D.top_citing_insts.filter((r) => state.lab === "ALL" || r.your_inst === state.lab);
    let rows = ci;
    if (state.lab === "ALL") {   // combine the four labs' top lists by institution
      const m = {}; ci.forEach((r) => { m[r.partner_inst] = (m[r.partner_inst] || 0) + r.cites_in; });
      rows = Object.entries(m).map(([k, v]) => ({ partner_inst: k, cites_in: v })).sort((a, b) => b.cites_in - a.cites_in).slice(0, 10);
    }
    const rv = [...rows].reverse();
    plot("c-citers", [{ type: "bar", orientation: "h", y: rv.map((r) => r.partner_inst),
      x: rv.map((r) => r.cites_in), text: rv.map((r) => fmt(r.cites_in)), textposition: "outside", cliponaxis: false,
      customdata: rv.map((r) => r.partner_inst),
      marker: { color: state.lab === "ALL" ? css("--multi") : labColor(state.lab) },
      hovertemplate: "<b>%{x:,}</b> citations<br>%{customdata}<extra></extra>" }], { margin: { l: 240, r: 50, t: 10, b: 40 }, showlegend: false,
      yaxis: ticks(rv.map((r) => r.partner_inst)) });

    const M = D.lab_matrix;
    plot("c-matrix", [{ type: "heatmap", z: M.z, x: M.labs.map(short), y: M.labs.map(short),
      colorscale: [[0, css("--surface")], [1, css("--q1")]], showscale: false, xgap: 2, ygap: 2,
      text: M.z.map((r) => r.map(String)), texttemplate: "%{text}", hovertemplate: "<b>%{z}</b> citations<br>%{y} cites %{x}<extra></extra>" }],
      { yaxis: { autorange: "reversed", title: "citing" }, xaxis: { title: "cited", side: "bottom" }, margin: { l: 70, r: 10, t: 10, b: 50 } });

    table("t-citers-papers", D.top_citing_papers.filter((r) => state.lab === "ALL" || r.lab === state.lab).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Lab", field: "lab" }, { title: "Citing paper", field: "title", widthGrow: 4, formatter: "textarea" }, { title: "Year", field: "year" },
      { title: "Its citations", field: "cited_by_count", hozAlign: "right" }, { title: "Institutions", field: "institutions", widthGrow: 2, formatter: "textarea" },
      { title: "DOI", field: "doi", formatter: doiLink }], { layout: "fitColumns", maxHeight: 360 });
  }

  // ------------------------------------------------------------------ tab: collaboration
  function commColor(c) {   // the 7 largest communities get categorical slots in fixed order; the rest fold into "Other"
    const pal = ["--lab-1", "--lab-2", "--lab-3", "--lab-4"].map(css).concat(["#e87ba4", "#008300", "#4a3aa7"]);
    return c >= 0 && c < pal.length ? pal[c] : css("--qna");
  }

  function renderCollab() {
    const fg = D.authorship_summary.faculty_graph, ig = D.authorship_summary.internal_graph;
    kpis("kpis-au", [
      ["Faculty nodes", fmt(fg.nodes), `${fmt(fg.isolates)} with no faculty co-author`], ["Faculty co-author links", fmt(fg.edges), `${fmt(fg.cross_lab_edges)} between labs`],
      ["Communities (Louvain)", fmt(fg.communities), `modularity Q = ${fg.modularity.toFixed(3)}`],
      ["All lab authors", fmt(ig.nodes), `${fmt(ig.edges)} links, Q = ${ig.modularity.toFixed(3)}`],
      ["Pair rows exported", fmt(D.authorship_summary.pairs_rows), `${fmt(D.authorship_summary.indian_link_rows)} Indian inter-institute`],
      ["Papers skipped for pairs", fmt(D.authorship_summary.papers_skipped_over_max_authors), `> ${D.meta.max_authors_for_pairs} authors`],
    ]);
    const G = D.authorship[state.layer];
    const keep = new Set(G.nodes.filter((n) => state.lab === "ALL" || n.lab === state.lab).map((n) => n.id));
    const maxDeg = Math.max(1, ...G.nodes.map((n) => n.deg));
    const elements = [
      ...G.nodes.filter((n) => keep.has(n.id)).map((n) => ({ data: { ...n, size: state.layer === "faculty" ? 8 + 34 * Math.sqrt(n.deg / maxDeg) : 4 + 16 * Math.sqrt(n.deg / maxDeg),
        color: state.colorby === "lab" ? labColor(n.lab) : commColor(n.comm), shape: labShape(n.lab) }, position: { x: n.x, y: n.y } })),
      ...G.edges.filter((e) => keep.has(e.s) && keep.has(e.t)).map((e, i) => ({ data: { id: `a${i}`, source: e.s, target: e.t, w: e.w,
        cross: e.cross ? 1 : 0 } })),
    ];
    if (cyAu) cyAu.destroy();
    cyAu = cytoscape({ container: el("g-au"), elements, layout: { name: "preset", fit: true, padding: 20 },
      wheelSensitivity: 0.25, minZoom: 0.1, maxZoom: 6,
      style: [
        { selector: "node", style: { width: "data(size)", height: "data(size)", "background-color": "data(color)", shape: "data(shape)",
          "border-width": 1.5, "border-color": css("--surface") } },
        { selector: "edge", style: { width: "mapData(w, 1, 20, 0.6, 5)", "line-color": css("--axis"), opacity: 0.6, "curve-style": "haystack" } },
        { selector: "edge[cross = 1]", style: { "line-style": "dashed", "line-color": css("--muted"), "curve-style": "straight" } },
        { selector: "node:selected", style: { "border-color": css("--ink"), "border-width": 3 } },
        { selector: ".faded", style: { opacity: 0.1 } },
      ] });
    cyAu.on("tap", "node", (ev) => {
      const d = ev.target.data();
      const c = D.centrality.find((r) => `F:${r.faculty_id}` === d.id);
      const pairs = [["Lab / institution", short(d.lab)], ["Co-authors in view", ev.target.degree()], ["Degree", d.deg],
        ["Betweenness", d.btw.toFixed(4)], ["Community", d.comm]];
      if (d.dept) pairs.splice(1, 0, ["Department", d.dept]);
      if (c) pairs.push(["Indian partner institutions", c.n_partner_insts]);
      info("au-info", d.name, pairs);
      cyAu.elements().addClass("faded"); ev.target.closedNeighborhood().removeClass("faded");
    });
    cyAu.on("tap", (ev) => { if (ev.target === cyAu) cyAu.elements().removeClass("faded"); });
    hoverTip(cyAu, (d) => `${d.name} · ${short(d.lab)} · degree ${d.deg}`);
    const shapes = LABS.map((l) => [state.colorby === "lab" ? labColor(l) : css("--muted"), short(l), labShape(l)]);
    const comms = state.colorby === "comm" ? [0, 1, 2, 3, 4, 5, 6].map((c) => [commColor(c), `Community ${c}`]).concat([[css("--qna"), "Other communities"]]) : [];
    legend("leg-au", [...shapes, ...comms, [css("--muted"), "cross-lab link", "dash"]]);

    table("t-cent", D.centrality.filter((r) => state.lab === "ALL" || r.lab === state.lab).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name", headerFilter: "input", frozen: true }, { title: "Lab", field: "lab" },
      { title: "Degree", field: "degree", hozAlign: "right", sorter: "number" },
      { title: "Deg. centrality", field: "degree_centrality", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 3) },
      { title: "Joint papers", field: "strength", hozAlign: "right", sorter: "number" },
      { title: "Betweenness", field: "betweenness", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 4) },
      { title: "Betw. (all authors)", field: "betweenness_internal", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 4) },
      { title: "Community", field: "community", hozAlign: "right" }], { maxHeight: 380, initialSort: [{ column: "degree", dir: "desc" }] });
    table("t-comm", D.communities.filter((r) => state.lab === "ALL" || String(r.labs).includes(state.lab)), [
      { title: "#", field: "community", hozAlign: "right", width: 44 }, { title: "Size", field: "size", hozAlign: "right" },
      { title: "Labs", field: "labs", formatter: "textarea", widthGrow: 2 }, { title: "Top departments", field: "top_departments", formatter: "textarea", widthGrow: 3 },
      { title: "Most connected members", field: "top_members", formatter: "textarea", widthGrow: 3 }], { layout: "fitColumns", maxHeight: 380 });
    table("t-partners", D.partners.filter((r) => state.lab === "ALL" || r.your_inst === state.lab).map((r) => ({ ...r, your_inst: short(r.your_inst) })), [
      { title: "Lab", field: "your_inst" }, { title: "#", field: "rank", hozAlign: "right", width: 44 },
      { title: "Partner", field: "partner_inst", headerFilter: "input", widthGrow: 3 }, { title: "Cluster", field: "pair_label", headerFilter: "input" },
      { title: "Shared papers", field: "shared_papers", hozAlign: "right", sorter: "number" },
      { title: "Cites in", field: "cites_in", hozAlign: "right", sorter: "number" }, { title: "Cites out", field: "cites_out", hozAlign: "right", sorter: "number" },
      { title: "Jaccard (topics)", field: "jaccard_topics", hozAlign: "right", sorter: "number", formatter: (c) => fmt(c.getValue(), 3) }],
      { maxHeight: 400, initialSort: [{ column: "shared_papers", dir: "desc" }] });

    const cc = D.cross_cluster.filter((r) => state.lab === "ALL" || r.your_inst === state.lab);
    const labels = [...new Set(cc.map((r) => r.pair_label))];
    const tot = (l) => cc.filter((r) => r.pair_label === l).reduce((a, r) => a + r.shared_papers, 0);
    labels.sort((a, b) => tot(a) - tot(b));
    plot("c-cluster", scopes().map((lab) => ({ type: "bar", orientation: "h", name: short(lab), y: labels,
      x: labels.map((l) => (cc.find((r) => r.your_inst === lab && r.pair_label === l) || {}).shared_papers || 0),
      marker: { color: labColor(lab), line: { color: css("--surface"), width: 1 } },
      hovertemplate: `<b>%{x}</b> shared papers<br>${short(lab)} · %{y}<extra></extra>` })),
      { barmode: "stack", margin: { l: 170, r: 16, t: 10, b: 50 } });
    table("t-hubs", D.hubs.filter((r) => state.lab === "ALL" || r.lab === state.lab).map((r) => ({ ...r, lab: short(r.lab) })), [
      { title: "Name", field: "name" }, { title: "Lab", field: "lab" }, { title: "Department", field: "department", widthGrow: 2 },
      { title: "Indian partner institutions", field: "n_partner_insts", hozAlign: "right" }, { title: "Degree", field: "degree", hozAlign: "right" },
      { title: "Betweenness", field: "betweenness", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 4) }], { layout: "fitColumns", maxHeight: 360 });
  }

  function hoverTip(cy, text) {
    const tip = el("tip");
    cy.on("mouseover", "node", (ev) => { tip.textContent = text(ev.target.data()); tip.hidden = false; });
    cy.on("mousemove", (ev) => { const o = ev.originalEvent; if (o) { tip.style.left = `${o.clientX + 14}px`; tip.style.top = `${o.clientY + 12}px`; } });
    cy.on("mouseout", "node", () => { tip.hidden = true; });
  }

  // ------------------------------------------------------------------ tab: about
  function renderAbout() {
    const box = el("about"); box.replaceChildren();
    const add = (tag, text) => { const e = document.createElement(tag); e.textContent = text; box.append(e); return e; };
    add("h2", "About the data");
    add("p", `DPCN Research Mapping Project, Group ${D.meta.group}. Institutions: ${LABS.map((l) => `${l} (${D.meta.lab_names[l]})`).join("; ")}. Window ${D.meta.window[0]}–${D.meta.window[1]}; ${D.meta.partial_year} is partial. Source: OpenAlex, collected ${D.meta.collected}; journal quartiles from Scimago (SJR); conference ranks from CORE2023.`);
    const items = [
      "Faculty: scientists listed on each lab's website, plus scientists identified from lab-affiliated papers (frequent last or corresponding author) and confirmed by the team.",
      "A paper counts for a faculty member only when their own authorship on it carries the lab's affiliation.",
      "Paper counts are unique papers; a paper shared by two labs counts once for each lab and once for 'All labs'.",
      "Q1 fraction = Q1 papers ÷ journal papers with a known SJR quartile (coverage shown beside it).",
      "h-index (2016–26) is computed from this dataset's citation counts; lifetime h-index is OpenAlex's and includes work elsewhere.",
      "Indian partner = an Indian institution other than the paper's own lab; CSIR HQ, government ministries and AcSIR (CSIR's degree academy) are not counted.",
      "Citation network: dataset papers citing dataset papers (analysis), plus citations to or from works with another Indian institution (flows).",
      `Authorship network: co-author pairs on papers with at most ${D.meta.max_authors_for_pairs} authors; the faculty graph merges each person's OpenAlex profiles into one node.`,
    ];
    const ul = document.createElement("ul"); items.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.append(li); }); box.append(ul);
  }

  // ------------------------------------------------------------------ wiring
  const RENDER = { overview: renderOverview, journals: renderJournals, faculty: renderFaculty, research: renderResearch,
    citation: renderCitation, collab: renderCollab, about: renderAbout };
  function render() { RENDER[state.tab](); rendered[state.tab] = state.lab; }
  function show(tab) {
    state.tab = tab;
    document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== `tab-${tab}`; });
    if (rendered[tab] !== state.lab) render();
    window.dispatchEvent(new Event("resize"));
    Object.values(tables).forEach((t) => { if (t.built && t.element.offsetParent) t.redraw(true); });
  }
  const sel = el("lab");
  [["ALL", "All four labs"], ...LABS.map((l) => [l, `${l} — ${D.meta.lab_names[l]}`])].forEach(([v, t]) => {
    const o = document.createElement("option"); o.value = v; o.textContent = t; sel.append(o); });
  sel.addEventListener("change", () => { state.lab = sel.value; Object.keys(rendered).forEach((k) => delete rendered[k]); render(); });
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
  el("compact").addEventListener("change", renderFaculty);
  document.querySelectorAll('input[name="layer"]').forEach((r) => r.addEventListener("change", () => { state.layer = r.value; renderCollab(); }));
  document.querySelectorAll('input[name="colorby"]').forEach((r) => r.addEventListener("change", () => { state.colorby = r.value; renderCollab(); }));
  el("theme").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    Object.keys(rendered).forEach((k) => delete rendered[k]); render();
  });
  el("subtitle").textContent = `Group ${D.meta.group} · ${LABS.map(short).join(", ")} · OpenAlex snapshot ${D.meta.collected} · ${fmt(D.meta.rows)} faculty–paper rows`;
  document.querySelectorAll(".collected").forEach((e) => { e.textContent = D.meta.collected; });
  // deep links: #tab=citation&lab=CSIR-IGIB&theme=light open that view directly
  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.get("theme")) document.documentElement.dataset.theme = hp.get("theme");
  if (hp.get("shot")) document.body.classList.add("shot");     // screenshot mode: no chart toolbars
  for (const k of ["layer", "colorby"]) {
    const r = document.querySelector(`input[name="${k}"][value="${hp.get(k)}"]`);
    if (r) { r.checked = true; state[k] = r.value; }
  }
  if (LABS.includes(hp.get("lab"))) { state.lab = hp.get("lab"); sel.value = state.lab; }
  if (hp.get("focus")) {        // show only the panels holding these element ids (for screenshots and links)
    const ids = hp.get("focus").split(",").map((x) => document.getElementById(x)).filter(Boolean);
    document.querySelectorAll("main .card, main .kpis").forEach((c) => { if (!ids.some((e) => c.contains(e))) c.hidden = true; });
    document.querySelectorAll("main .grid2").forEach((g) => { if (![...g.children].some((c) => !c.hidden)) g.hidden = true; });
  }
  show(RENDER[hp.get("tab")] ? hp.get("tab") : "overview");
})();
