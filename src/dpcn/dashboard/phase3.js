/* Phase III pages: Explorer (filter & find), Person profile, Compare anything, More results (s26), Questions & verdicts,
   Science context and Benchmark (s25). Inlined into app.js's closure after phase2.js, so it shares D, state, plot(),
   table(), kpis(), show() and the other helpers. Data: D.explorer (s26), D.p2.research.* (s17 and s23-s26), D.science. */
const R3 = (D.p2 && D.p2.research) || {};
const X = D.explorer || (D.p2 && D.p2.explorer) || null;
const SCI = D.science || (D.p2 && D.p2.science) || {};
const RJ = R3.json || {};      // s23-s26 summary JSONs: dynamics, structure, benchmark, extras
const P3REG = {};
const P3API = {};
const mk = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined && text !== null) e.textContent = text; if (cls) e.className = cls; return e; };
const hIndex = (cs) => { const s = [...cs].sort((a, b) => b - a); let h = 0; while (h < s.length && s[h] >= h + 1) h++; return h; };
const fmtShare = (v) => v === null || v === undefined ? "–" : v <= 1 ? pct(v, 1) : fmt(v, 1);
const median = (a) => { const s = a.filter((x) => x !== null && x !== undefined && !Number.isNaN(x)).sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const mean = (a) => { const s = a.filter((x) => x !== null && x !== undefined && !Number.isNaN(x)); return s.length ? s.reduce((x, y) => x + y, 0) / s.length : null; };
const pctile = (vals, v) => { const s = vals.filter((x) => x !== null && x !== undefined); if (!s.length || v === null || v === undefined) return null; return 100 * s.filter((x) => x <= v).length / s.length; };
const signed = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(d)}`;
const goBtn = (label, tab, extra) => { const b = mk("button", label, "linkbtn"); b.type = "button"; b.addEventListener("click", () => { if (extra) extra(); show(tab); window.scrollTo(0, 0); }); return b; };
const ROLE = ["middle", "first author", "last author", "corresponding"];
function findingCards(id, sentences, empty) {
  const box = el(id); if (!box) return; box.replaceChildren();
  if (!sentences || !sentences.length) { box.append(mk("p", empty || "Not computed yet.", "muted")); return; }
  sentences.forEach((s, i) => { const d = mk("div", null, "fd-card"); d.append(mk("span", String(i + 1).padStart(2, "0"), "fd-no"), mk("p", pretty(s))); box.append(d); });
}
const pretty = (s) => String(s).replace(/beta\/mu/g, "β/μ").replace(/\bbeta\b/g, "β").replace(/\bmu\b/g, "μ").replace(/Lambda_max/g, "Λmax")
  .replace(/<k>\/<k2>/g, "⟨k⟩/⟨k²⟩").replace(/Erdos-Renyi/g, "Erdős–Rényi").replace(/\brho\b/g, "ρ").replace(/ -> /g, " → ").replace(/(\d)-(\d)/g, "$1–$2")
  .replace(/CSIR-(CCMB|IGIB|IMTECH|CDRI)/g, "$1").replace(/N\^([\d.]+)/g, "N^$1").replace(/>= /g, "≥ ");
const missing = (id, step) => { const b = el(id); if (b) { b.replaceChildren(mk("p", `Run step ${step} to compute this.`, "muted")); } };

// ------------------------------------------------------------------ explorer data model
let XP = [], XF = [], byPaper = [], byPerson = [];
if (X) {
  const c = X.papers;
  XP = c.id.map((id, i) => ({ i, id, title: c.title[i], year: c.year[i], journal: X.journals[c.j[i]], if: c.if[i], q: c.q[i], c: c.c[i],
    na: c.na[i], field: X.fields[c.f[i]], subfield: X.subfields[c.sf[i]], ncs: c.ncs[i], ind: c.ind[i], cov: c.cov[i], rev: c.rev[i],
    abs: c.abs[i], doi: c.doi[i], labs: c.labs[i].map((k) => LABS[k]) }));
  XF = X.people.map((p, i) => Object.assign({ i }, p));
  byPaper = XP.map(() => []); byPerson = XF.map(() => []);
  X.links.forEach(([p, f, r]) => { byPaper[p].push([f, r]); byPerson[f].push([p, r]); });
  XF.forEach((p) => {        // whole-window measures used by profiles and comparisons
    const ps = byPerson[p.i].map(([k]) => XP[k]);
    p.papers = ps.length; p.citations = ps.reduce((a, x) => a + x.c, 0); p.h = hIndex(ps.map((x) => x.c));
    p.h_lt100 = hIndex(ps.filter((x) => x.na < 100).map((x) => x.c));
    p.led_share = ps.length ? byPerson[p.i].filter(([, r]) => r > 0).length / ps.length : null;
    p.median_if = median(ps.map((x) => x.if)); p.q1_share = ps.length ? ps.filter((x) => x.q === "Q1").length / ps.length : null;
    p.mean_ncs = mean(ps.map((x) => x.ncs)); p.if10 = ps.filter((x) => x.if > 10 && x.na < 100).length;
  });
}
const personById = (id) => XF.find((p) => p.id === id);
const doiUrl = (d) => d ? `https://doi.org/${d}` : null;
const openDoi = (d) => { const u = doiUrl(d); if (u) window.open(u, "_blank", "noopener"); };

// ------------------------------------------------------------------ Explorer: filter & find
const EXDEF = { y0: 2016, y1: 2026, na: 100, if: 0, c: 0, q: "", f: "", role: "", cov: "", h: 0, t: "" };
const PRESETS = [
  ["h-index above 10, papers under 100 authors", { na: 100, h: 10 }],
  ["Impact factor above 10, under 100 authors", { na: 100, if: 10.0001 }],
  ["Lab-led Q1 papers since 2021", { y0: 2021, q: "Q1", role: "led" }],
  ["COVID-19 papers", { cov: "1", na: 5000 }],
  ["Cited 100+ times, small teams (< 10 authors)", { c: 100, na: 10 }],
  ["Everything", { na: 5000 }],
];
function exRead() {
  const v = (id) => el(id).value;
  return { y0: +v("ex-y0") || 2016, y1: +v("ex-y1") || 2026, na: +v("ex-na") || 100000, if: +v("ex-if") || 0, c: +v("ex-c") || 0,
    q: v("ex-q"), f: v("ex-f"), role: v("ex-role"), cov: v("ex-cov"), h: +v("ex-h") || 0, t: v("ex-t").trim().toLowerCase() };
}
function exSet(o) {
  const f = Object.assign({}, EXDEF, o);
  const map = { y0: "ex-y0", y1: "ex-y1", na: "ex-na", if: "ex-if", c: "ex-c", q: "ex-q", f: "ex-f", role: "ex-role", cov: "ex-cov", h: "ex-h", t: "ex-t" };
  for (const [k, id] of Object.entries(map)) el(id).value = k === "if" && f[k] > 10 && f[k] < 10.01 ? 10 : f[k];
  el("ex-if").dataset.strict = f.if > 10 && f.if < 10.01 ? "1" : "";
}
function paperPass(p, F) {
  if (p.year < F.y0 || p.year > F.y1 || p.na >= F.na || p.c < F.c) return false;
  if (F.if > 0) { if (p.if === null || p.if === undefined) return false; if (el("ex-if").dataset.strict ? p.if <= F.if : p.if < F.if) return false; }
  if (F.q === "Q1" && p.q !== "Q1") return false;
  if (F.q === "Q12" && !(p.q === "Q1" || p.q === "Q2")) return false;
  if (F.f && p.field !== F.f) return false;
  if (F.cov !== "" && String(p.cov) !== F.cov) return false;
  if (F.t && !p.title.toLowerCase().includes(F.t)) return false;
  if (state.lab !== "ALL" && !p.labs.includes(state.lab)) return false;
  return true;
}
const roleOk = (r, F) => !F.role || (F.role === "led" ? r > 0 : r === 0);
function renderExplorer() {
  if (!X) { missing("t-ex-people", "s26"); return; }
  const F = exRead();
  const pass = XP.map((p) => paperPass(p, F));
  const people = [];
  XF.forEach((pr) => {
    if (state.lab !== "ALL" && pr.lab !== state.lab) return;
    const mine = byPerson[pr.i].filter(([k, r]) => pass[k] && roleOk(r, F)).map(([k, r]) => [XP[k], r]);
    if (!mine.length) return;
    const cs = mine.map(([p]) => p.c);
    people.push({ id: pr.id, name: pr.name, lab: short(pr.lab), dept: pr.dept, papers: mine.length, citations: cs.reduce((a, b) => a + b, 0),
      h: hIndex(cs), max_if: Math.max(...mine.map(([p]) => p.if ?? 0)) || null, led: mine.filter(([, r]) => r > 0).length / mine.length,
      ncs: mean(mine.map(([p]) => p.ncs)), if10: mine.filter(([p]) => p.if > 10).length });
  });
  const keep = people.filter((p) => p.h > F.h);
  const keepIds = new Set(keep.map((p) => p.id));
  const papers = XP.filter((p) => pass[p.i] && byPaper[p.i].some(([f, r]) => roleOk(r, F) && (state.lab === "ALL" || XF[f].lab === state.lab) && (F.h <= 0 || keepIds.has(XF[f].id))));
  kpis("ex-kpis", [["People", fmt(keep.length), F.h > 0 ? `with h-index above ${F.h} on these papers` : "with at least one matching paper"],
    ["Papers", fmt(papers.length), `of ${fmt(XP.length)} in the dataset`], ["Citations", fmt(papers.reduce((a, p) => a + p.c, 0)), "to the matching papers"],
    ["Median impact factor", fmt(median(papers.map((p) => p.if)), 1), "journal papers with a known IF"],
    ["Median authors", fmt(median(papers.map((p) => p.na))), "per matching paper"]]);
  const bits = [];
  if (F.y0 > 2016 || F.y1 < 2026) bits.push(`${F.y0}–${F.y1}`);
  if (F.na < 5000) bits.push(`fewer than ${F.na} authors`);
  if (F.if > 0) bits.push(`impact factor ${el("ex-if").dataset.strict ? "above" : "at least"} ${F.if}`);
  if (F.c > 0) bits.push(`at least ${F.c} citations`);
  if (F.q) bits.push(F.q === "Q1" ? "Q1 journals" : "Q1 or Q2 journals");
  if (F.f) bits.push(F.f); if (F.role) bits.push(F.role === "led" ? "lab-led" : "middle-author");
  if (F.cov === "1") bits.push("COVID-19 only"); if (F.cov === "0") bits.push("no COVID-19");
  if (F.t) bits.push(`title contains “${F.t}”`); if (state.lab !== "ALL") bits.push(short(state.lab));
  el("ex-desc").textContent = `${fmt(keep.length)} people and ${fmt(papers.length)} papers match${bits.length ? `: ${bits.join(", ")}` : ""}${F.h > 0 ? `, people with h-index above ${F.h}` : ""}.`;
  const t = table("t-ex-people", keep, [
    { title: "Name", field: "name", headerFilter: "input", minWidth: 150, cssClass: "clickable" }, { title: "Lab", field: "lab" },
    { title: "Papers", field: "papers", hozAlign: "right" }, { title: "Citations", field: "citations", hozAlign: "right" },
    { title: "h-index", field: "h", hozAlign: "right" }, { title: "Max IF", field: "max_if", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) },
    { title: "IF > 10", field: "if10", hozAlign: "right" }, { title: "Lab-led", field: "led", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
    { title: "Mean norm. cit.", field: "ncs", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) }],
    { initialSort: [{ column: "h", dir: "desc" }], maxHeight: 460, layout: "fitColumns" });
  if (t) t.on("rowClick", (e, row) => P3API.openPerson(row.getData().id));
  plot("c-ex-scatter", LABS.map((l) => { const ps = papers.filter((p) => p.labs[0] === l && p.if); return { type: "scattergl", mode: "markers", name: short(l),
    x: ps.map((p) => p.if), y: ps.map((p) => p.c + 1), customdata: ps.map((p) => [p.title.slice(0, 90), p.year, p.na, p.doi]),
    marker: { color: labColor(l), size: ps.map((p) => Math.min(18, 4 + 2.2 * Math.log2(p.na))), opacity: 0.7, line: { width: 0 } },
    hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} · IF %{x:.1f} · %{customdata[2]} authors<br>%{y} − 1 citations<extra></extra>" }; }),
    { xaxis: { type: "log", title: "Journal impact factor" }, yaxis: { type: "log", title: "Citations + 1" }, margin: { l: 60, r: 10, t: 30, b: 50 } });
  el("c-ex-scatter").on?.("plotly_click", (ev) => openDoi(ev.points[0].customdata[3]));
  const yrs = [...new Set(XP.map((p) => p.year))].sort();
  plot("c-ex-year", LABS.map((l) => ({ type: "bar", name: short(l), x: yrs, y: yrs.map((y) => papers.filter((p) => p.year === y && p.labs[0] === l).length), marker: { color: labColor(l) } })),
    { barmode: "stack", margin: { l: 50, r: 10, t: 30, b: 40 } });
  const fc = {}; papers.forEach((p) => { fc[p.field] = (fc[p.field] || 0) + 1; });
  const fs = Object.entries(fc).sort((a, b) => b[1] - a[1]).slice(0, 10).reverse();
  plot("c-ex-field", [{ type: "bar", orientation: "h", x: fs.map((x) => x[1]), y: fs.map((x) => x[0]), marker: { color: css("--sec") || css("--lab-1") }, hovertemplate: "%{y}: %{x} papers<extra></extra>" }],
    { margin: { l: 10, r: 10, t: 10, b: 40 }, yaxis: { automargin: true } });
  const rows = papers.map((p) => ({ title: p.title, year: p.year, journal: p.journal, if: p.if, q: p.q, c: p.c, na: p.na, lab: p.labs.map(short).join(", "),
    people: byPaper[p.i].map(([f]) => XF[f].name).join("; "), doi: p.doi }));
  table("t-ex-papers", rows, [
    { title: "Title", field: "title", formatter: "textarea", widthGrow: 4, minWidth: 260, headerFilter: "input" }, { title: "Year", field: "year" },
    { title: "Journal", field: "journal", widthGrow: 2, headerFilter: "input" }, { title: "IF", field: "if", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) },
    { title: "Q", field: "q" }, { title: "Citations", field: "c", hozAlign: "right" }, { title: "Authors", field: "na", hozAlign: "right" },
    { title: "Lab", field: "lab" }, { title: "Our faculty", field: "people", formatter: "textarea", widthGrow: 2 },
    { title: "DOI", field: "doi", formatter: (c) => { const v = c.getValue(); if (!v) return ""; const a = mk("a", "open ↗"); a.href = doiUrl(v); a.target = "_blank"; a.rel = "noopener"; return a; } }],
    { initialSort: [{ column: "c", dir: "desc" }], maxHeight: 520, layout: "fitColumns" });
}
P3REG.explorer = renderExplorer;

// ------------------------------------------------------------------ Person profile
state.person = null;
P3API.openPerson = (id) => { state.person = id; delete rendered.person; show("person"); window.scrollTo(0, 0); };
let cyEgo = null;
function renderPerson() {
  if (!X) { missing("pp-head", "s26"); return; }
  if (!state.person || !personById(state.person)) {
    const pool = XF.filter((p) => state.lab === "ALL" || p.lab === state.lab);
    state.person = (pool.sort((a, b) => b.citations - a.citations)[0] || XF[0]).id;
  }
  const P = personById(state.person), mine = byPerson[P.i].map(([k, r]) => [XP[k], r]);
  el("pp-q").value = `${P.name} (${short(P.lab)})`;
  const head = el("pp-head"); head.replaceChildren();
  const chip = mk("span", short(P.lab), "pchip"); chip.style.setProperty("--chip", labColor(P.lab));
  const h = mk("h2", P.name, "pname"); h.prepend(chip);
  const meta = [P.designation, P.dept, P.status ? `${P.status} faculty` : null].filter(Boolean).join(" · ");
  head.append(h, mk("p", meta, "muted"));
  const flags = [];
  if (P.flag) flags.push(`Flag: ${P.flag}`);
  if (P.flag_lifetime) flags.push("Lifetime-citation check: the OpenAlex profile may merge several people");
  flags.forEach((f) => head.append(mk("p", f, "pflag")));
  const fc = (R3.faculty_credit || []).find((r) => r.faculty_id === P.id) || {};
  kpis("pp-kpis", [["Papers", fmt(P.papers), `${pct(P.led_share, 0)} lab-led`], ["Citations", fmt(P.citations), "2016–2026 papers"],
    ["h-index", fmt(P.h), `${fmt(P.h_lt100)} without 100+ author papers`], ["Lifetime h-index", fmt(P.h_lifetime), "OpenAlex profile, all years"],
    ["Fractional citations", fmt(P.citations_frac, 0), fc.rank_citations_frac ? `rank ${fmt(fc.rank_citations_frac)} (full: ${fmt(fc.rank_citations)})` : "citations ÷ authors"],
    ["Normalised impact", fmt(P.mncs ?? P.mean_ncs, 2), "1 = field-and-year average"], ["Faculty co-authors", fmt(P.degree), "in the faculty network"],
    ["Partner institutions", fmt(P.collab_inst), `${fmt(P.collab_inst_indian)} Indian`]]);
  const yrs = []; for (let y = D.meta.window[0]; y <= D.meta.window[1]; y++) yrs.push(y);
  plot("c-pp-year", [["lab-led", (r) => r > 0, css("--lab-1")], ["middle author", (r) => r === 0, css("--lab-4")]].map(([n, f, col]) => ({ type: "bar", name: n,
    x: yrs, y: yrs.map((y) => mine.filter(([p, r]) => p.year === y && f(r)).length), marker: { color: col } })),
    { barmode: "stack", margin: { l: 50, r: 10, t: 30, b: 40 } });
  const peers = XF.filter((p) => p.lab === P.lab);
  const M = [["Papers", "papers"], ["Citations", "citations"], ["h-index", "h"], ["h (< 100 authors)", "h_lt100"], ["Fractional citations", "citations_frac"],
    ["Normalised impact", "mean_ncs"], ["Faculty co-authors", "degree"], ["Partner institutions", "collab_inst"], ["Share lab-led", "led_share"]];
  const pv = M.map(([, k]) => pctile(peers.map((p) => p[k]), P[k]));
  plot("c-pp-pct", [{ type: "bar", orientation: "h", y: M.map((m) => m[0]), x: pv, marker: { color: pv.map((v) => v >= 75 ? css("--lab-1") : v >= 40 ? css("--lab-4") : css("--lab-2")) },
    text: pv.map((v) => v === null ? "" : `${Math.round(v)}`), textposition: "outside", hovertemplate: "%{y}: percentile %{x:.0f} in the lab<extra></extra>" }],
    { xaxis: { range: [0, 110], title: `Percentile among ${peers.length} ${short(P.lab)} faculty` }, yaxis: { autorange: "reversed", automargin: true }, margin: { l: 10, r: 20, t: 10, b: 50 }, showlegend: false });
  const pj = mine.filter(([p]) => p.if);
  plot("c-pp-papers", [{ type: "scatter", mode: "markers", x: pj.map(([p]) => p.if), y: pj.map(([p]) => p.c + 1),
    customdata: pj.map(([p, r]) => [p.title.slice(0, 90), p.year, p.na, ROLE[r], p.doi]),
    marker: { size: pj.map(([p]) => Math.min(22, 5 + 2.4 * Math.log2(p.na))), color: pj.map(([, r]) => r > 0 ? css("--lab-1") : css("--lab-4")),
      symbol: pj.map(([p]) => p.na >= 100 ? "circle-open" : "circle"), opacity: 0.8, line: { width: 1.5 } },
    hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} · IF %{x:.1f} · %{customdata[2]} authors · %{customdata[3]}<extra></extra>" }],
    { xaxis: { type: "log", title: "Journal impact factor" }, yaxis: { type: "log", title: "Citations + 1" }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 50 } });
  el("c-pp-papers").on?.("plotly_click", (ev) => openDoi(ev.points[0].customdata[4]));
  // ego network among faculty
  const nb = X.pairs.filter(([a, b]) => a === P.i || b === P.i).map(([a, b, w, y]) => ({ f: a === P.i ? b : a, w, y }));
  const ids = new Set([P.i, ...nb.map((x) => x.f)]);
  const among = X.pairs.filter(([a, b]) => ids.has(a) && ids.has(b) && a !== P.i && b !== P.i);
  const els = [...ids].map((k) => ({ data: { id: `f${k}`, label: XF[k].name, col: labColor(XF[k].lab), sz: k === P.i ? 34 : 14 + 3 * Math.sqrt(byPerson[k].length) } }))
    .concat(nb.map((x) => ({ data: { id: `e${x.f}`, source: `f${P.i}`, target: `f${x.f}`, w: Math.min(10, 1 + Math.log2(1 + x.w) * 2), cross: XF[x.f].lab !== P.lab ? 1 : 0 } })))
    .concat(among.map(([a, b, w]) => ({ data: { id: `x${a}_${b}`, source: `f${a}`, target: `f${b}`, w: 1, cross: 0, faint: 1 } })));
  if (cyEgo) cyEgo.destroy();
  if (nb.length && typeof cytoscape !== "undefined") {
    cyEgo = cytoscape({ container: el("g-pp-ego"), elements: els, wheelSensitivity: 0.2,
      style: [{ selector: "node", style: { "background-color": "data(col)", width: "data(sz)", height: "data(sz)", label: "data(label)", "font-size": 11, color: css("--ink-2"),
        "text-valign": "bottom", "text-margin-y": 3, "border-width": 1, "border-color": css("--surface") } },
        { selector: "edge", style: { width: "data(w)", "line-color": css("--axis"), opacity: 0.8, "curve-style": "haystack" } },
        { selector: "edge[cross = 1]", style: { "line-style": "dashed", "line-color": css("--lab-2") } },
        { selector: "edge[faint = 1]", style: { opacity: 0.25 } }],
      layout: { name: "concentric", concentric: (n) => (n.id() === `f${P.i}` ? 2 : 1), levelWidth: () => 1, minNodeSpacing: 18, animate: false } });
    cyEgo.on("tap", "node", (e) => { const k = +e.target.id().slice(1); if (k !== P.i) P3API.openPerson(XF[k].id); });
  } else { el("g-pp-ego").replaceChildren(mk("p", "No faculty co-authors on papers with up to 50 authors.", "muted pad")); }
  // related (random walk with restart, s23)
  const rel = (R3.rw_related || []).filter((r) => r.faculty_id === P.id).sort((a, b) => a.rank - b.rank);
  const rb = el("pp-related"); rb.replaceChildren();
  if (!R3.rw_related) rb.append(mk("p", "Run step s23 to compute this.", "muted"));
  else if (!rel.length) rb.append(mk("p", "Not in the connected part of the faculty network.", "muted"));
  else { const ul = mk("ol", null, "rel-list"); rel.forEach((r) => { const li = mk("li"); const b = mk("button", r.related_name, "linkbtn"); b.type = "button";
    b.addEventListener("click", () => P3API.openPerson(r.related_id)); li.append(b, mk("span", ` · ${short(r.related_lab)}`, "muted")); ul.append(li); }); rb.append(ul); }
  const cb = el("pp-credit"); cb.replaceChildren();
  const dl = mk("dl", null, "credit");
  [["Rank by citations, full counting", fc.rank_citations], ["Rank, fractional counting (÷ authors)", fc.rank_citations_frac],
    ["Rank without papers of 100+ authors", fc.rank_citations_lt100], ["Papers, fractional", fmt(P.papers_frac, 1)],
    ["Papers in IF > 10 journals with < 100 authors", P.if10], ["Median journal impact factor", fmt(P.median_if, 1)], ["Share in Q1 journals", pct(P.q1_share, 0)]]
    .forEach(([k, v]) => { if (v === undefined) return; dl.append(mk("dt", k), mk("dd", typeof v === "number" ? `${fmt(v)}${k.startsWith("Rank") ? ` of ${XF.length}` : ""}` : v)); });
  cb.append(dl);
  table("t-pp-papers", mine.map(([p, r]) => ({ title: p.title, year: p.year, journal: p.journal, if: p.if, q: p.q, c: p.c, na: p.na, role: ROLE[r], ncs: p.ncs, doi: p.doi })), [
    { title: "Title", field: "title", formatter: "textarea", widthGrow: 4, minWidth: 260, headerFilter: "input" }, { title: "Year", field: "year" },
    { title: "Journal", field: "journal", widthGrow: 2 }, { title: "IF", field: "if", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) },
    { title: "Q", field: "q" }, { title: "Citations", field: "c", hozAlign: "right" }, { title: "Authors", field: "na", hozAlign: "right" },
    { title: "Role", field: "role" }, { title: "Norm. cit.", field: "ncs", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
    { title: "DOI", field: "doi", formatter: (c) => { const v = c.getValue(); if (!v) return ""; const a = mk("a", "open ↗"); a.href = doiUrl(v); a.target = "_blank"; a.rel = "noopener"; return a; } }],
    { initialSort: [{ column: "c", dir: "desc" }], maxHeight: 520, layout: "fitColumns" });
}
P3REG.person = renderPerson;

// ------------------------------------------------------------------ Compare anything
state.cmp = []; state.cmpKind = "people";
const VSM = [["Papers", "papers"], ["Citations", "citations"], ["h-index", "h"], ["h (< 100 authors)", "h_lt100"], ["Fractional citations", "citations_frac"],
  ["Normalised impact", "mean_ncs"], ["Faculty co-authors", "degree"], ["Partner institutions", "collab_inst"], ["Share lab-led", "led_share"], ["Median IF", "median_if"]];
function labAgg(l) {
  const ps = XP.filter((p) => p.labs.includes(l)), fac = XF.filter((p) => p.lab === l);
  return { name: short(l), lab: l, papers: ps.length, citations: ps.reduce((a, p) => a + p.c, 0), h: hIndex(ps.map((p) => p.c)), h_lt100: hIndex(ps.filter((p) => p.na < 100).map((p) => p.c)),
    citations_frac: fac.reduce((a, p) => a + (p.citations_frac || 0), 0), mean_ncs: mean(ps.map((p) => p.ncs)), degree: mean(fac.map((p) => p.degree)),
    collab_inst: mean(fac.map((p) => p.collab_inst)), led_share: mean(fac.map((p) => p.led_share)), median_if: median(ps.map((p) => p.if)), faculty: fac.length,
    years: ps.map((p) => p.year) };
}
function renderVersus() {
  if (!X) { missing("t-vs", "s26"); return; }
  state.cmpKind = el("vs-kind").value;
  el("vs-q").hidden = state.cmpKind === "labs";
  const chips = el("vs-chips"); chips.replaceChildren();
  let ents;
  if (state.cmpKind === "labs") ents = LABS.map(labAgg);
  else {
    if (!state.cmp.length) state.cmp = [...XF].sort((a, b) => b.citations - a.citations).slice(0, 3).map((p) => p.id);
    ents = state.cmp.map(personById).filter(Boolean);
    ents.forEach((p) => { const c = mk("span", null, "chip"); c.style.setProperty("--chip", labColor(p.lab)); c.append(mk("i"), mk("b", p.name), mk("span", ` ${short(p.lab)}`, "muted"));
      const x = mk("button", "×", "chip-x"); x.type = "button"; x.title = "Remove"; x.addEventListener("click", () => { state.cmp = state.cmp.filter((i) => i !== p.id); renderVersus(); });
      const o = mk("button", "profile", "linkbtn"); o.type = "button"; o.addEventListener("click", () => P3API.openPerson(p.id)); c.append(o, x); chips.append(c); });
  }
  const pal = [css("--lab-1"), css("--lab-2"), css("--lab-3"), css("--lab-4"), "#8e6bc4", "#c46b8a"];
  const colOf = (e, i) => state.cmpKind === "labs" ? labColor(e.lab) : pal[i % pal.length];
  const score = (e, k) => state.cmpKind === "labs" ? (e[k] === null ? 0 : 100 * e[k] / Math.max(...ents.map((x) => x[k] || 0))) : pctile(XF.map((p) => p[k]), e[k]);
  plot("c-vs-radar", ents.map((e, i) => ({ type: "scatterpolar", fill: "toself", name: e.name, r: [...VSM.map(([, k]) => score(e, k)), score(e, VSM[0][1])],
    theta: [...VSM.map((m) => m[0]), VSM[0][0]], line: { color: colOf(e, i) }, opacity: 0.55, hovertemplate: `${e.name}<br>%{theta}: %{r:.0f}<extra></extra>` })),
    { polar: { bgcolor: "rgba(0,0,0,0)", radialaxis: { range: [0, 100], gridcolor: css("--grid"), tickfont: { size: 11 } }, angularaxis: { gridcolor: css("--grid"), tickfont: { size: 12 } } },
      margin: { l: 60, r: 60, t: 40, b: 40 } });
  const yrs = []; for (let y = D.meta.window[0]; y <= D.meta.window[1]; y++) yrs.push(y);
  plot("c-vs-year", ents.map((e, i) => { const ys = state.cmpKind === "labs" ? e.years : byPerson[e.i].map(([k]) => XP[k].year);
    return { type: "scatter", mode: "lines+markers", name: e.name, x: yrs, y: yrs.map((y) => ys.filter((v) => v === y).length), line: { color: colOf(e, i), width: 2.5, shape: "spline" } }; }),
    { yaxis: { title: "Papers" }, margin: { l: 50, r: 10, t: 30, b: 40 } });
  const rows = VSM.map(([lab, k]) => { const r = { measure: lab }; ents.forEach((e, i) => { r[`e${i}`] = e[k]; }); return r; });
  const isShare = (k) => k === "led_share";
  table("t-vs", rows, [{ title: "Measure", field: "measure", minWidth: 180 }, ...ents.map((e, i) => ({ title: e.name, field: `e${i}`, hozAlign: "right",
    formatter: (c) => { const v = c.getValue(), m = c.getRow().getData().measure; return m === "Share lab-led" ? pct(v, 0) : Number.isInteger(v) ? fmt(v) : fmt(v, 2); } }))],
    { layout: "fitColumns", maxHeight: 520 });
  void isShare;
}
P3REG.versus = renderVersus;
P3API.addCompare = (id) => { if (!state.cmp.includes(id)) state.cmp = [...state.cmp, id].slice(-6); el("vs-kind").value = "people"; delete rendered.versus; show("versus"); };

// ------------------------------------------------------------------ More results (s26)
function renderExtras() {
  const E = RJ.extras;
  if (!E) { findingCards("x-list", null, "Run step s26 to compute these analyses."); return; }
  findingCards("x-list", E.findings);
  const scope = state.lab;
  const rg = (R3.regrading || []).filter((r) => r.scope === scope && r.year < D.meta.partial_year);
  plot("c-x-regrade", [["q1_actual", "Q1, year-matched quartile", css("--lab-1"), "solid"], ["q1_frozen", "Q1, quartile frozen at 2017", css("--lab-3"), "dash"],
    ["if5_share", "JCR impact factor above 5", css("--lab-2"), "dot"]].map(([k, n, c, d]) => ({ type: "scatter", mode: "lines+markers", name: n, x: rg.map((r) => r.year), y: rg.map((r) => r[k]),
    line: { color: c, dash: d, width: 2.5 }, hovertemplate: `${n}<br>%{x}: %{y:.1%}<extra></extra>` })), { yaxis: { tickformat: ".0%", range: [0, 1] }, margin: { l: 56, r: 10, t: 40, b: 40 } });
  const qs = R3.q1_signal || [];
  plot("c-x-q1", [{ type: "bar", orientation: "h", y: qs.map((r) => r.model), x: qs.map((r) => r.pct_effect),
    error_x: { type: "data", symmetric: false, array: qs.map((r) => 100 * (Math.exp(r.ci_hi) - 1) - r.pct_effect), arrayminus: qs.map((r) => r.pct_effect - 100 * (Math.exp(r.ci_lo) - 1)), color: css("--ink-2") },
    marker: { color: css("--lab-1") }, hovertemplate: "%{y}: %{x:+.0f}% citations<extra></extra>" }], { xaxis: { title: "% more citations", ticksuffix: "%" }, yaxis: { automargin: true }, margin: { l: 10, r: 20, t: 10, b: 50 }, showlegend: false });
  const q = E.q1_signal || {};
  el("x-q1-note").textContent = `Within a year, a journal's impact factor and a paper's own citations correlate at Spearman ${fmt(q.if_citation_spearman_median, 2)} (median over years): useful on average, weak for any single paper. ${pct(q.share_nonq1_beats_median_q1, 0)} of papers outside Q1 are cited more (field-and-year normalised) than the median Q1 paper.`;
  const pp = R3.partner_payoff || [], terms = ["indian_healthcare", "indian_university", "industry", "foreign"];
  const tl = { indian_healthcare: "Indian hospital / medical", indian_university: "Indian university", industry: "Industry", foreign: "Foreign institution" };
  plot("c-x-payoff", ["without team size", "with team size"].map((m, j) => { const rr = terms.map((t) => pp.find((r) => r.term === t && r.model === m) || {});
    return { type: "scatter", mode: "markers", name: m === "with team size" ? "+ team size, review" : "year, field, lab", y: terms.map((t) => `${tl[t]} (${fmt((rr[terms.indexOf(t)] || {}).papers_with)})`), x: rr.map((r) => r.pct_effect),
      error_x: { type: "data", symmetric: false, array: rr.map((r) => 100 * (Math.exp(r.ci_hi) - 1) - r.pct_effect), arrayminus: rr.map((r) => r.pct_effect - 100 * (Math.exp(r.ci_lo) - 1)), color: j ? css("--lab-1") : css("--axis") },
      marker: { size: 12, color: j ? css("--lab-1") : css("--axis") }, hovertemplate: "%{y}: %{x:+.0f}%<extra></extra>" }; }),
    { xaxis: { title: "% difference in citations", ticksuffix: "%", zeroline: true, zerolinecolor: css("--muted") }, yaxis: { automargin: true }, margin: { l: 10, r: 20, t: 40, b: 50 } });
  const ty = (R3.partner_types || []).filter((r) => r.scope === scope);
  const types = [...new Set(ty.map((r) => r.type))].sort((a, b) => (ty.find((r) => r.type === b) || {}).joint_papers - (ty.find((r) => r.type === a) || {}).joint_papers);
  plot("c-x-types", [{ type: "bar", x: types, y: types.map((t) => (ty.find((r) => r.type === t) || {}).share_of_papers), marker: { color: types.map((_, i) => [css("--lab-1"), css("--lab-2"), css("--lab-3"), css("--lab-4")][i % 4]) },
    customdata: types.map((t) => [(ty.find((r) => r.type === t) || {}).partners, (ty.find((r) => r.type === t) || {}).joint_papers]),
    hovertemplate: "%{x}: %{y:.1%} of papers<br>%{customdata[0]} partners, %{customdata[1]} joint papers<extra></extra>" }], { yaxis: { tickformat: ".0%", title: "Share of the lab's papers" }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 60 } });
  const cc = (R3.citers_collab || []).filter((r) => r.cites_in >= 5);
  const owns = ["government", "government-aided", "private", "international", "unclassified"];
  plot("c-x-cc", owns.map((o) => { const rr = cc.filter((r) => (r.ownership || "unclassified") === o); return { type: "scattergl", mode: "markers", name: o,
    x: rr.map((r) => r.shared_papers + 1), y: rr.map((r) => r.cites_in + 1), text: rr.map((r) => r.partner_inst), marker: { color: ownColor(o), size: 8, opacity: 0.75 },
    hovertemplate: "<b>%{text}</b><br>%{y} − 1 citations, %{x} − 1 joint papers<extra></extra>" }; }),
    { xaxis: { type: "log", title: "Joint papers + 1" }, yaxis: { type: "log", title: "External citations + 1" }, margin: { l: 60, r: 10, t: 40, b: 50 } });
  table("t-x-rising", R3.rising_citers || [], [{ title: "Institution", field: "partner_inst", widthGrow: 3, formatter: "textarea" }, { title: "2022", field: "citing_papers_2022", hozAlign: "right" },
    { title: "2025", field: "citing_papers_2025", hozAlign: "right" }, { title: "Increase", field: "increase", hozAlign: "right" }, { title: "× growth", field: "growth", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) }],
    { layout: "fitColumns", maxHeight: 460 });
  table("t-x-mech", R3.citer_mechanisms || [], [{ title: "Institution", field: "partner_inst", widthGrow: 3, headerFilter: "input" }, { title: "Ownership", field: "ownership" },
    { title: "Citations", field: "citations", hozAlign: "right" }, { title: "Citing papers", field: "citing_papers", hozAlign: "right" },
    { title: "Our papers per citing paper", field: "refs_per_citing_paper", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
    { title: "Stacked share", field: "stacked_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }, { title: "Top citing journal", field: "top_journal", widthGrow: 2 },
    { title: "Its share", field: "top_journal_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }, { title: "Joint papers", field: "joint_papers", hozAlign: "right" }],
    { layout: "fitColumns", maxHeight: 460, initialSort: [{ column: "citations", dir: "desc" }] });
  table("t-x-local", R3.local_global || [], [{ title: "Kind", field: "kind" }, { title: "Title", field: "title", formatter: "textarea", widthGrow: 4, minWidth: 220 },
    { title: "Year", field: "year" }, { title: "Lab", field: "lab" }, { title: "Citations", field: "citations", hozAlign: "right" },
    { title: "From India", field: "indian_ext_citations", hozAlign: "right" }, { title: "Share", field: "indian_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }],
    { layout: "fitColumns", maxHeight: 460, groupBy: "kind" });
  table("t-x-backbone", (R3.backbone || []).slice(0, 150), [{ title: "Institution A", field: "a_name", widthGrow: 2, formatter: "textarea", headerFilter: "input" },
    { title: "Institution B", field: "b_name", widthGrow: 2, formatter: "textarea", headerFilter: "input" }, { title: "Joint papers", field: "w", hozAlign: "right" },
    { title: "p", field: "p", hozAlign: "right", formatter: (c) => Number(c.getValue()).toExponential(1) }], { layout: "fitColumns", maxHeight: 460 });
  const verdict = (c) => { const v = c.getValue(); const s = mk("span", v === true ? "holds" : v === false ? "does not hold" : "context", `badge ${v === true ? "ok" : v === false ? "no" : "mid"}`); return s; };
  table("t-x-laws", R3.laws || [], [{ title: "Law", field: "law", minWidth: 130 }, { title: "What it says", field: "statement", formatter: "textarea", widthGrow: 3 },
    { title: "Expected", field: "expected" }, { title: "Our data", field: "observed", formatter: "textarea", widthGrow: 2 }, { title: "Verdict", field: "holds", formatter: verdict }],
    { layout: "fitColumns", maxHeight: 460 });
  walkCharts("c-x-walk-d", "c-x-walk-c", "x-walk-note");
  table("t-x-frag", R3.fragility || [], [{ title: "Headline", field: "headline", widthGrow: 2 }, { title: "Removed", field: "removed", widthGrow: 2 },
    { title: "Full data", field: "full", widthGrow: 2 }, { title: "Without", field: "without", widthGrow: 2 }, { title: "Holds?", field: "holds", formatter: verdict }],
    { layout: "fitColumns", maxHeight: 460 });
  table("t-x-jumps", (R3.jumps || []).filter((r) => scope === "ALL" || r.scope === scope).map((r) => Object.assign({}, r, { scope: short(r.scope) })),
    [{ title: "Lab", field: "scope" }, { title: "Measure", field: "metric" }, { title: "Year", field: "year" }, { title: "From", field: "previous", hozAlign: "right" },
      { title: "To", field: "value", hozAlign: "right" }, { title: "Change", field: "change", hozAlign: "right", formatter: (c) => `${signed(100 * c.getValue(), 0)}%` },
      { title: "Drivers", field: "drivers", formatter: "textarea", widthGrow: 4 }], { layout: "fitColumns", maxHeight: 460 });
  const hf = (R3.h_filtered || []).filter((r) => r.h_gt10_lt100 && (scope === "ALL" || r.lab === scope));
  const t = table("t-x-h", hf.map((r) => Object.assign({}, r, { lab: short(r.lab) })), [{ title: "Name", field: "name", headerFilter: "input", minWidth: 150 }, { title: "Lab", field: "lab" },
    { title: "h, all papers", field: "h_all", hozAlign: "right" }, { title: "h, < 100 authors", field: "h_lt100", hozAlign: "right" },
    { title: "Papers < 100 authors", field: "papers_lt100", hozAlign: "right" }, { title: "Citations < 100", field: "citations_lt100", hozAlign: "right" },
    { title: "IF > 10 papers (< 100 authors)", field: "if10_papers_lt100", hozAlign: "right" }, { title: "Max IF", field: "max_if_lt100", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) }],
    { layout: "fitColumns", maxHeight: 520, initialSort: [{ column: "h_lt100", dir: "desc" }] });
  if (t) t.on("rowClick", (e, row) => P3API.openPerson(row.getData().faculty_id));
}
function walkCharts(idD, idC, idNote) {
  const W = (RJ.extras || {}).walk || {};
  const wd = R3.walk_delta || [];
  if (el(idD)) plot(idD, [{ type: "bar", name: "observed", x: wd.map((r) => r.delta), y: wd.map((r) => r.count), marker: { color: css("--lab-4") } },
    { type: "scatter", mode: "lines", name: "Laplace fit", x: wd.map((r) => r.delta), y: wd.map((r) => r.laplace), line: { color: css("--lab-1"), width: 3 } },
    { type: "scatter", mode: "lines", name: "normal fit", x: wd.map((r) => r.delta), y: wd.map((r) => r.normal), line: { color: css("--lab-2"), width: 2, dash: "dash" } }],
    { yaxis: { type: "log", title: "Faculty-years", range: [-0.3, Math.log10(Math.max(1, ...wd.map((r) => r.count))) + 0.3] }, xaxis: { title: "Change in papers from one year to the next", range: [-15, 15] }, margin: { l: 60, r: 10, t: 40, b: 50 } });
  const wc = R3.walk_cumulative || [];
  const mx = Math.max(1, ...wc.map((r) => Math.max(r.observed, r.random_walk)));
  if (idC && el(idC)) plot(idC, [{ type: "scatter", mode: "markers", x: wc.map((r) => r.random_walk), y: wc.map((r) => r.observed), marker: { color: css("--lab-1"), size: 8 },
    customdata: wc.map((r) => r.quantile), hovertemplate: "quantile %{customdata:.2f}<br>random walk %{x:.0f}, observed %{y:.0f}<extra></extra>", name: "quantiles" },
    { type: "scatter", mode: "lines", x: [0, mx], y: [0, mx], line: { color: css("--muted"), dash: "dash" }, name: "equal", hoverinfo: "skip" }],
    { xaxis: { title: "Random walk: total papers 2016–2025" }, yaxis: { title: "Observed: total papers" }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 50 } });
  if (idNote && el(idNote)) el(idNote).textContent = W.faculty ? `${W.faculty} faculty. Laplace fits better than normal (AIC ${fmt(W.aic_laplace)} vs ${fmt(W.aic_normal)}). Zero-output years: ${pct(W.zero_years_observed, 0)} observed, ${pct(W.zero_years_random_walk, 0)} simulated. Gini of total output: ${fmt(W.gini_observed, 2)} observed, ${fmt(W.gini_random_walk, 2)} simulated. Lag-1 autocorrelation of changes ${fmt(W.lag1_autocorr, 2)} (pure random walk: 0; noise around a fixed level: ${fmt(W.lag1_null_mean, 2)}).` : "";
}
P3API.walkCharts = walkCharts;
P3REG.extras = renderExtras;

// ------------------------------------------------------------------ Questions & verdicts
function verdictItems() {
  const S = R3.summary || {}, H = S.homophily || {}, E = RJ.extras || {}, ST = RJ.structure || {}, DY = RJ.dynamics || {}, BM = RJ.benchmark || {};
  const aud = (R3.citation_audience || []).filter((r) => r.citing_scope === "ALL"), share = (c) => (aud.find((r) => r.class === c) || {}).share;
  const within = (R3.lab_exchange_null || []).find((r) => r.basis.startsWith("independent") && r.null.includes("fields") && r.cited_lab === "within-lab share") || {};
  const dl = (R3.distance_lift || []).filter((r) => r.basis === "independent citations"), lift = (d) => (dl.find((r) => r.distance === d) || {}).lift;
  const pers = R3.tie_persistence || [], same = pers.find((r) => r.pair_type === "same lab") || {}, cross = pers.find((r) => r.pair_type === "cross-lab") || {};
  const fw = (R3.flow_window || []).filter((r) => r.scope === "ALL"), fwr = fw.reduce((a, r) => a + r.in_window, 0) / Math.max(1, fw.reduce((a, r) => a + r.out_window, 0));
  const fc = R3.faculty_credit || [], drop = fc.filter((r) => r.rank_citations <= 10 && r.rank_citations_frac > 25).length;
  const rg = E.regrading || {}, W = E.walk || {}, q = E.q1_signal || {};
  const pp = (R3.partner_payoff || []).find((r) => r.term === "indian_healthcare" && r.model === "with team size") || {};
  const laws = R3.laws || [], held = laws.filter((r) => r.holds === true).length, tested = laws.filter((r) => r.holds === true || r.holds === false).length;
  const gv = (BM.gravity || {});
  const gj = (gv.distance_elasticity_joint_papers || {}).coef, gc = (gv.distance_elasticity_citations || {}).coef;
  const ranks = BM.ranks_of_our_labs || {};
  const V = [];
  const add = (q, test, num, v, tab, why) => V.push({ q, test, num, v, tab, why });
  add("Is the lab, rather than the department or the topic, the unit of collaboration?", "Lab labels shuffled 2,000 times; logistic model with topic similarity",
    `${pct(H.cross_lab_share_observed, 1)} of links cross labs vs ${pct(H.cross_lab_share_label_permutation, 0)} by chance (z = ${fmt(H.cross_lab_z_permutation, 0)})`, H.cross_lab_z_permutation < -3 ? "yes" : "partly", "findings");
  add("Do labs cite their own work more than topic and timing explain?", "Citations reshuffled within year × field strata (1,000 times)",
    `${pct(within.observed, 0)} within lab vs ${pct(within.expected, 0)} expected`, within.observed > within.expected * 1.15 ? "yes" : "partly", "findings");
  add("Is the internal citation network mostly self-citation?", "Each of the internal citations classified by the closest author tie",
    `${pct(share("self (shared author)"), 0)} share an author`, share("self (shared author)") > 0.5 ? "yes" : "no", "findings");
  add("Do citations fall with co-authorship distance (Singh et al.)?", "Observed ÷ volume-only expectation by network distance",
    `${fmt(lift("1"), 1)}× at distance 1, ${fmt(lift("2"), 1)}× at 2, ${fmt(lift("3"), 1)}× at 3`, lift("1") > lift("2") && lift("2") > (lift("3") || 0) ? "yes" : "partly", "findings");
  const lvm = (R3.led_vs_middle || []).filter((r) => r.scope === "ALL"), Ld = lvm.find((r) => r.role === "lab-led") || {}, Md = lvm.find((r) => r.role !== "lab-led") || {};
  add("Are middle-author papers better papers?", "Field-and-year normalised citations, overall and within team-size bands",
    `${fmt(Md.mean_norm_citations, 2)}× vs ${fmt(Ld.mean_norm_citations, 2)}× the field average overall (median ${fmt(Md.median_authors)} vs ${fmt(Ld.median_authors)} authors); similar within the same team size`,
    "no", "findings", "The premium is team size: big consortia, not better work by the lab.");
  add("Are cross-lab collaborations as durable as same-lab ones?", "Repeat within 3 years of the first joint paper; Fisher test",
    `${pct(cross.share, 0)} vs ${pct(same.share, 0)} repeat`, cross.share < same.share ? "no" : "yes", "findings");
  const li = (R3.lab_impact || []).filter((r) => r.term.startsWith("lab:") && r.model !== "lab only");
  add("Are CCMB and IGIB the most cited labs?", "Raw citations per paper vs OLS on log citations with year, field, team size and review",
    `Ahead on raw averages; with controls vs CDRI: ${li.map((r) => `${short(r.term.replace("lab: ", ""))} ${signed(r.pct_effect, 0)}%`).join(", ")}`,
    li.some((r) => /CCMB|IGIB/.test(r.term) && r.pct_high < 0) ? "no" : "partly", "findings", "A few huge consortium papers lift their averages; the typical paper is cited less than CDRI's.");
  add("Did Indian citations into the labs overtake those going out only in 2022?", "Same two-year window both ways, per cohort",
    `Labs receive ${fmt(fwr, 2)}× what they give, every cohort since 2017`, "no", "findings", "The 2022 crossover was citation lag.");
  add("Do faculty rankings survive fractional counting?", "Citations ÷ authors; rank shifts", `${drop} of the top 10 fall below rank 25`, drop >= 3 ? "no" : "partly", "findings");
  if (rg.q1_actual) add("Did the labs move to weaker journals?", "Quartile frozen at 2017 vs year-matched; JCR IF > 5 share",
    `Q1 ${pct(rg.q1_actual[0], 0)} → ${pct(rg.q1_actual[1], 0)} year-matched, ${pct(rg.q1_frozen[0], 0)} → ${pct(rg.q1_frozen[1], 0)} frozen; IF > 5 ${pct(rg.if5[0], 0)} → ${pct(rg.if5[1], 0)}`,
    rg.if5[1] >= rg.if5[0] && (rg.q1_frozen[0] - rg.q1_frozen[1]) < (rg.q1_actual[0] - rg.q1_actual[1]) / 2 ? "no" : "partly", "extras", "Most of the Q1 fall is Scimago re-grading journals; on a fixed impact-factor yardstick the share rose.");
  if (q.if_citation_spearman_median !== undefined) add("Does a high-impact journal mean a highly cited paper?", "Q1 premium with controls; within-year IF–citation correlation",
    `Spearman ${fmt(q.if_citation_spearman_median, 2)}; ${pct(q.share_nonq1_beats_median_q1, 0)} of non-Q1 papers beat the median Q1 paper`, "partly", "extras", "True on average, unreliable for one paper (Seglen 1997).");
  if (pp.pct_effect !== undefined) add("Do hospital and medical partners bring more citations?", "OLS with year, field, lab, team size and review",
    `${signed(pp.pct_effect, 0)}% (95% CI ${signed(100 * (Math.exp(pp.ci_lo) - 1), 0)}% to ${signed(100 * (Math.exp(pp.ci_hi) - 1), 0)}%)`, pp.ci_hi < 0 ? "no" : pp.ci_lo > 0 ? "yes" : "partly", "extras");
  if (W.faculty) add("Is a scientist's yearly output a random walk (Zhang et al., P1)?", "Laplace vs normal fit; lag-1 autocorrelation vs shuffled years",
    `Laplace fits better; autocorrelation ${fmt(W.lag1_autocorr, 2)} between 0 and ${fmt(W.lag1_null_mean, 2)}`, "partly", "walks", "Changes are Laplace-shaped as in P1, but each person has a slowly drifting level.");
  if (W.top_decile_persistence !== undefined) add("Is there a Matthew effect in output?", "Top-decile persistence 2016–20 → 2021–25 vs 2,000 permutations",
    `${pct(W.top_decile_persistence, 0)} stay in the top 10% vs ${pct(W.top_decile_null, 0)} by chance`, W.top_decile_p < 0.05 ? "yes" : "no", "walks");
  if (tested) add("Do the classic bibliometric laws hold here?", "Lotka, Price, Bradford, Seglen, Pareto tested on our data", `${held} of ${tested} hold`, held === tested ? "yes" : held ? "partly" : "no", "science");
  if (gj !== undefined) add("Does collaboration fall with distance faster than citation?", "Poisson gravity model, partner size and lab controlled",
    `elasticity ${fmt(gj, 2)} for joint papers vs ${fmt(gc, 2)} for citations`, gj < gc ? "yes" : "no", "benchmark");
  if (ranks && Object.keys(ranks).length) {
    const rk = Object.entries(ranks).map(([l, x]) => [short(l), (x.mean_fwci || {}).rank, (x.top10_share || {}).rank, (x.mean_fwci || {}).of]);
    const n = (rk[0] || [])[3] || 17, top = rk.filter((x) => x[1] <= n / 2).length;
    add("Do our labs match other Indian biology institutes on normalised impact?", "Mean FWCI and top-10% share, identical OpenAlex query for 13 peers",
      `Mean FWCI ranks ${rk.map((x) => `${x[0]} ${x[1]}`).join(", ")} of ${n}; top-10% share ranks ${rk.map((x) => x[2]).join(", ")}`, top === rk.length ? "yes" : top ? "partly" : "no", "benchmark"); }
  const F1 = ((D.p2 || {}).firsts || {}).summary;
  if (F1) {
    const c1 = ((D.p2 || {}).firsts || {}).p1_career || [], a = c1[0] || {}, z = c1[c1.length - 1] || {};
    add("Does output become steadier over a career, as Zhang et al. (P1) found?", "Laplace scale of yearly changes by career age; faculty bootstrap; permutation",
      `absolute ${fmt(a.laplace_alpha, 2)} → ${fmt(z.laplace_alpha, 2)} papers, relative ${fmt(a.relative_alpha, 2)} → ${fmt(z.relative_alpha, 2)} from the first decade to 30+ years`,
      z.relative_alpha < a.relative_alpha ? "yes" : "no", "novelty", "Unlike the computer scientists in P1, swings grow with seniority in these labs.");
    add("Do research groups grow in proportion to their size (Gibrat's law, P8)?", "Log growth on log size of each PI's yearly group",
      `slope ${fmt(F1.p8.gibrat_slope, 2)} (95% CI ${fmt(F1.p8.gibrat_ci[0], 2)} to ${fmt(F1.p8.gibrat_ci[1], 2)}); 0 would be Gibrat`, F1.p8.gibrat_ci[1] < 0 || F1.p8.gibrat_ci[0] > 0 ? "no" : "yes", "novelty", "Large groups grow more slowly than small ones.");
    add("Does writing together make people cite each other, beyond shared topics (P6)?", "Logistic model over all ordered faculty pairs",
      `odds ratio ${fmt(F1.p6.or_coauthor_alone, 0)} alone, ${fmt(F1.p6.or_coauthor_full, 1)} with topic, distance, output and lab`, F1.p6.or_coauthor_full > 1.5 ? "yes" : "no", "novelty");
    add("Does a first joint paper change how a pair cites each other (P3)?", "Event study vs distance-2 pairs, difference in differences",
      `${signed(F1.p3.did, 2)} citations a year (95% CI ${signed(F1.p3.did_ci[0], 2)} to ${signed(F1.p3.did_ci[1], 2)})`, F1.p3.did_ci[0] > 0 ? "yes" : "partly", "novelty");
    const p9 = (((D.p2 || {}).firsts || {}).p9_diversity || []);
    add("Does early partner diversity predict later success (P9)?", "Spearman against 2,000 reshuffles within lab and early-output tercile",
      p9.map((r) => `${r.outcome === "late_papers" ? "output" : "impact"} ρ ${fmt(r.spearman, 2)} vs ${fmt(r.null_mean, 2)} (p = ${fmt(r.p, 2)})`).join("; "), p9.every((r) => r.p >= 0.05) ? "no" : "partly", "novelty");
    add("Do labs change mainly through who joins and leaves (P10)?", "Entry / exit / within-person decomposition of the share of internationally collaborative faculty",
      `${pct(F1.p10.share_from_within, 0)} within-person, ${pct(F1.p10.share_from_entry, 0)} joiners, ${pct(F1.p10.share_from_exit, 0)} leavers`, F1.p10.share_from_within > 0.5 ? "no" : "yes", "novelty");
  }
  if (DY.crosslab_reach) {
    const cr = DY.crosslab_reach, is = DY.influence_spearman || {}, mr = DY.mfpt_ratio || {}, tn = DY.threshold_numeric || {};
    add("Do the lab walls slow the spread of ideas between labs?", "SIR outbreaks from each lab, real vs degree-preserving rewired networks",
      `An outbreak reaches another lab in ${pct(cr.observed, 0)} of runs vs ${pct(cr.rewired, 0)} on rewired networks`, cr.observed < cr.rewired / 2 ? "yes" : "partly", "epidemics");
    add("Does the network's structure make spreading easier than chance?", "SIS epidemic threshold (susceptibility peak) on real, rewired and random networks",
      `threshold λ = ${fmt(tn.observed, 3)} vs ${fmt(tn.rewired, 3)} rewired and ${fmt(tn.ER, 3)} random`, tn.observed < tn.ER ? "yes" : "no", "epidemics", "Hubs lower the threshold (Pastor-Satorras & Vespignani 2001), but the lab walls keep outbreaks inside one lab.");
    add("Do core members spread better than well-connected ones (Kitsak et al.)?", "SIR outbreak size from every faculty member as the first case",
      `Spearman: k-shell ${fmt((is.kshell || {}).rho_sir, 2)}, degree ${fmt((is.degree || {}).rho_sir, 2)}, eigenvector ${fmt((is.eigenvector || {}).rho_sir, 2)}`, (is.kshell || {}).rho_sir > (is.degree || {}).rho_sir ? "yes" : "no", "epidemics");
    add("Is a random walker trapped inside its lab?", "Mean first-passage time to another lab, real vs rewired",
      `${fmt(mr.mfpt_obs_mean, 0)} steps vs ${fmt(mr.mfpt_null_mean, 0)} (${fmt(mr.mean, 0)}× longer)`, mr.mean > 2 ? "yes" : "no", "walks");
  }
  if (ST.findings) {
    const nt = R3.null_table || [], bip = nt.find((r) => r.metric === "average clustering" && /bipartite/i.test(r.model)) || {};
    const gl = (R3.students_glue || []).filter((r) => r.scope === "ALL"), cs = gl.find((r) => /cross/.test(r.metric) && /share/.test(r.metric)) || {};
    const ct = (R3.contagion || [])[0] || {}, plc = (R3.contagion || []).find((r) => /future/.test(r.exposure)) || {};
    const lp = (R3.link_prediction || []).slice().sort((a, b) => b.auc - a.auc)[0] || {};
    const fr = (R3.crosslab_fragility || []).find((r) => r.lab_pair === "ALL") || {};
    if (bip.z !== undefined) add("Is the faculty network more clustered than its papers alone explain?", "Bipartite null: papers reshuffled keeping team sizes and output",
      `clustering ${fmt(bip.observed, 2)} vs ${fmt(bip.null_mean, 2)} (z = ${fmt(bip.z, 1)})`, bip.z > 2 ? "yes" : "no", "structure", "Most clustering comes from multi-faculty papers; the remainder is real triadic closure.");
    if (cs.metric) add("Are students and staff the glue between faculty and labs?", "Faculty network with and without links through non-faculty lab authors",
      `cross-lab share of links ${fmtShare(cs.faculty_only)} → ${fmtShare(cs.with_students)}`, cs.with_students > 1.5 * cs.faculty_only ? "yes" : "partly", "structure");
    if (ct.rr) add("Do research topics spread from co-author to co-author?", "New-subfield adoption after a co-author, vs future co-authors (placebo)",
      `relative risk ${fmt(ct.rr, 1)} vs ${fmt(plc.rr, 1)} for the placebo`, ct.rr_lo > plc.rr_hi ? "yes" : "no", "structure", "Co-authors share topics before they collaborate: homophily, not influence.");
    if (lp.auc) add("Can new collaborations be predicted?", "Time split: train 2016–20, test links new in 2021–26", `best AUC ${fmt(lp.auc, 2)} (${lp.method.replace(/,? fit .*$/, "")})`, lp.auc > 0.75 ? "yes" : "partly", "structure");
    if (fr.cross_links) add("Are the bridges between labs robust?", "Cross-lab links by number of joint papers; removing the papers that create them",
      `${pct(fr.single_paper_share, 0)} of ${fr.cross_links} cross-lab links rest on a single paper`, "no", "structure");
  }
  return V;
}
P3API.verdicts = verdictItems;
const VLAB = { yes: ["supported", "ok"], no: ["not supported", "no"], partly: ["partly", "mid"] };
function renderVerdicts() {
  const box = el("vd-list"); box.replaceChildren();
  verdictItems().forEach((x, i) => {
    const d = mk("button", null, "vd"); d.type = "button";
    const [lab, cls] = VLAB[x.v] || VLAB.partly;
    d.append(mk("span", String(i + 1).padStart(2, "0"), "vd-no"), mk("span", lab, `badge ${cls}`));
    const b = mk("div", null, "vd-body"); b.append(mk("h3", x.q), mk("p", x.num, "vd-num"), mk("p", `Test: ${x.test}`, "muted"));
    if (x.why) b.append(mk("p", x.why, "vd-why"));
    d.append(b, mk("span", "Evidence →", "vd-go"));
    d.addEventListener("click", () => { show(x.tab); window.scrollTo(0, 0); });
    box.append(d);
  });
  const audit = ((RJ.extras || {}).precision_audit) || {};
  const nd = [
    `Measured precision of the faculty–paper matching: a seeded sample of ${audit.sample || 50} links is ready in data/manual/precision_audit.csv; ${audit.checked || 0} have been checked by hand so far.`,
    "Career-age analyses (variance by career stage, as in paper P1): the roster has no joining dates or PhD years, and OpenAlex first-paper years are unreliable for senior staff.",
    "Gender and hiring analyses (papers P7, P9, P10): the roster holds no gender data, and inferring it from names would be unreliable and inappropriate.",
    "Patents, clinical trials and policy citations: not in OpenAlex; linking them needs other sources (e.g. Reliance on Science, CTRI).",
    "Whether heavy citers are former lab members: citing authors are not stored, and naming individual citing authors was dropped for ethical reasons.",
    "Google Scholar and Scopus cross-checks of citation counts: only a 10-paper Crossref check was done.",
    "Causal claims: every result here is an association, tested against baselines, not an experiment.",
    "The Scimago 2025 file was blocked by a bot check, so 62 fallback impact factors are frozen from an earlier run.",
  ];
  const ul = el("vd-notdone"); ul.replaceChildren(...nd.map((t) => mk("li", t)));
  const bs = ["Research quality beyond citations: originality, rigour and reproducibility are not in any count.", "Teaching, mentoring and training of students, the labs' other main output.",
    "Translation: drugs, diagnostics, technologies and services (e.g. CDRI's drug development, IGIB's genome surveillance).",
    "Work in Indian-language or regional journals, books, datasets and software that OpenAlex indexes poorly.",
    "Informal collaboration and advice that never becomes a co-authored paper.", "Funding, equipment and staffing, which drive output but are not in the data.",
    "Very recent papers, which have not had time to be cited."];
  el("vd-blind").replaceChildren(...bs.map((t) => mk("li", t)));
}
P3REG.verdicts = renderVerdicts;

// ------------------------------------------------------------------ Science context
function scienceOurs(id) {
  const L = R3.laws || [], law = (n) => (L.find((r) => r.law.startsWith(n)) || {}).observed;
  const S = R3.summary || {}, H = S.homophily || {}, DY = RJ.dynamics || {}, ST = RJ.structure || {}, E = RJ.extras || {}, BM = RJ.benchmark || {};
  const dl = (R3.distance_lift || []).filter((r) => r.basis === "independent citations"), lift = (d) => (dl.find((r) => r.distance === d) || {}).lift;
  const team = (R3.lab_impact || []).find((r) => /author/.test(r.term) && r.model !== "lab only");
  const lc = R3.lab_credit || [];
  const nt = (R3.null_table || []).find((r) => /clustering/i.test(r.metric) && /rewir|config/i.test(r.model)) || (R3.null_table || []).find((r) => /clustering/i.test(r.metric));
  const W = E.walk || {};
  const m = {
    lotka: law("Lotka"), price: law("Price"), bradford: law("Bradford"), seglen: law("Seglen"),
    matthew: W.top_decile_persistence !== undefined ? `${pct(W.top_decile_persistence, 0)} of the top 10% of faculty by 2016–20 output are again top 10% in 2021–25, against ${pct(W.top_decile_null, 0)} by chance.` : null,
    teams: team ? `Holding year, field and lab fixed, each doubling of the team adds about ${fmt(team.pct_effect, 0)}% citations.` : null,
    newman: nt ? `Our faculty network's clustering is ${fmt(nt.observed, 2)} against ${fmt(nt.null_mean, 2)} for the ${nt.model} baseline (z = ${fmt(nt.z, 0)}).` : null,
    smallworld: DY.interventions_summary || (DY.findings || []).find((s) => /add|link/i.test(s)) || null,
    weakties: H.cross_lab_share_observed !== undefined ? `Only ${pct(H.cross_lab_share_observed, 1)} of our faculty links cross labs, and only ${pct(((R3.tie_persistence || []).find((r) => r.pair_type === "cross-lab") || {}).share, 0)} of new cross-lab pairs repeat within three years.` : null,
    threshold: (DY.findings || []).find((s) => /threshold/i.test(s)) || null,
    kshell: (DY.findings || []).find((s) => /k-shell|kshell|core/i.test(s)) || null,
    distance: lift("1") ? `Independent citations run at ${fmt(lift("1"), 1)}× chance between co-authors and ${fmt(lift("2"), 1)}× at distance 2 among our faculty.` : null,
    disparity: E.backbone ? `The backbone keeps ${fmt(E.backbone.backbone_edges)} of ${fmt(E.backbone.edges)} Indian institution links (${pct(E.backbone.weight_kept, 0)} of the weight).` : null,
    leiden: lc.length ? `Normalised impact (MNCS) is ${LABS.map((l) => `${short(l)} ${fmt((lc.find((r) => r.scope === l) || {}).mncs, 2)}`).join(", ")}, with overlapping intervals; raw citations rank them differently.` : null,
    fwci: (BM.findings || [])[0] || null,
  };
  void ST;
  return m[id];
}
function renderScience() {
  const box = el("sc-list"); box.replaceChildren();
  const items = SCI.items || [];
  if (!items.length) { box.append(mk("p", "Add data/manual/science_context.yaml.", "muted")); return; }
  items.forEach((it) => {
    const c = mk("article", null, "sc");
    c.append(mk("span", it.topic, "sc-topic"), mk("p", it.claim, "sc-claim"));
    const o = scienceOurs(it.id);
    if (o) { const d = mk("div", null, "sc-ours"); d.append(mk("b", "Our data: "), document.createTextNode(o)); c.append(d); }
    c.append(mk("p", it.source, "sc-src"));
    box.append(c);
  });
}
P3REG.science = renderScience;

// ------------------------------------------------------------------ Benchmark (s25)
const BMM = [["mean_fwci", "Mean FWCI", (v) => fmt(v, 2), "mean_fwci_lo", "mean_fwci_hi"], ["median_fwci", "Median FWCI", (v) => fmt(v, 2)],
  ["top10_share", "Top-10% share", (v) => pct(v, 1), "top10_lo", "top10_hi"], ["top1_share", "Top-1% share", (v) => pct(v, 1), "top1_lo", "top1_hi"],
  ["citations_per_paper", "Citations per paper", (v) => fmt(v, 1)], ["papers", "Papers 2016–2026", (v) => fmt(v)], ["cagr", "Growth (CAGR)", (v) => pct(v, 1)],
  ["intl_share", "International co-authorship", (v) => pct(v, 0), "intl_lo", "intl_hi"], ["oa_share", "Open access", (v) => pct(v, 0), "oa_lo", "oa_hi"],
  ["h_index", "h-index of the window's papers", (v) => fmt(v)], ["gini_citations", "Gini of citations", (v) => fmt(v, 2)], ["subfield_entropy", "Breadth (subfield entropy)", (v) => fmt(v, 2)]];
function renderBenchmark() {
  const tab = Array.isArray(R3.benchmark) ? R3.benchmark : null, J = RJ.benchmark || null;
  const inst = tab || [];
  if (!inst.length) { findingCards("bm-list", null, "Run step s25 to fetch the peer institutes."); return; }
  findingCards("bm-list", (J || {}).findings);
  const ours = (r) => r.group === "ours";
  const col = (r) => ours(r) ? labColor(r.short) : css("--muted");
  const ySel = el("bm-y").value;
  const yName = (BMM.find((m) => m[0] === ySel) || [, ySel])[1];
  plot("c-bm-scatter", [{ type: "scatter", mode: "markers+text", x: inst.map((r) => r.papers), y: inst.map((r) => r[ySel]), text: inst.map((r) => r.short.replace("CSIR-", "")),
    textposition: "top center", textfont: { size: 12, color: css("--ink-2") },
    marker: { size: inst.map((r) => 10 + Math.sqrt(r.papers * (r.top10_share || 0.1)) * 0.9), color: inst.map(col), opacity: 0.8, line: { width: inst.map((r) => ours(r) ? 3 : 1), color: inst.map((r) => ours(r) ? css("--ink") : css("--surface")) } },
    customdata: inst.map((r) => [r.name, r.city]), hovertemplate: `<b>%{customdata[0]}</b>, %{customdata[1]}<br>%{x:,} papers · ${yName} %{y:.2f}<extra></extra>` }],
    { xaxis: { type: "log", title: "Papers 2016–2026 (log)" }, yaxis: { title: yName, tickformat: /share/.test(ySel) ? ".0%" : undefined }, showlegend: false, margin: { l: 60, r: 20, t: 20, b: 50 } });
  const mSel = el("bm-m"); if (!mSel.options.length) { BMM.forEach(([k, n]) => mSel.append(new Option(n, k))); }
  const M = BMM.find((m) => m[0] === mSel.value) || BMM[0];
  const sorted = [...inst].filter((r) => r[M[0]] !== null && r[M[0]] !== undefined).sort((a, b) => a[M[0]] - b[M[0]]);
  plot("c-bm-rank", [{ type: "bar", orientation: "h", y: sorted.map((r) => r.short), x: sorted.map((r) => r[M[0]]), marker: { color: sorted.map(col) },
    error_x: M[3] ? { type: "data", symmetric: false, array: sorted.map((r) => r[M[4]] - r[M[0]]), arrayminus: sorted.map((r) => r[M[0]] - r[M[3]]), color: css("--ink-2") } : undefined,
    customdata: sorted.map((r) => r.name), hovertemplate: `<b>%{customdata}</b><br>${M[1]}: %{x:.3g}<extra></extra>` }],
    { xaxis: { title: M[1], tickformat: /share|cagr/.test(M[0]) ? ".0%" : undefined }, yaxis: { automargin: true }, showlegend: false, margin: { l: 10, r: 20, t: 10, b: 50 } });
  const yr = R3.benchmark_yearly || [];
  plot("c-bm-year", inst.map((r) => { const rr = yr.filter((x) => x.short === r.short && x.year < D.meta.partial_year);
    return { type: "scatter", mode: "lines", name: r.short.replace("CSIR-", ""), x: rr.map((x) => x.year), y: rr.map((x) => x.mean_fwci), line: { color: col(r), width: ours(r) ? 3 : 1 }, opacity: ours(r) ? 1 : 0.45 }; }),
    { yaxis: { title: "Mean FWCI" }, margin: { l: 56, r: 10, t: 40, b: 40 } });
  const iSel = el("bm-inst"); if (!iSel.options.length) inst.forEach((r) => iSel.append(new Option(`${r.short} — ${r.name}`, r.short)));
  if (LABS.includes(state.lab) && !iSel.dataset.touched) iSel.value = state.lab;
  const rc = (R3.rca_india || []).filter((r) => r.short === iSel.value).sort((a, b) => b.rca - a.rca).slice(0, 12).reverse();
  plot("c-bm-rca", [{ type: "bar", orientation: "h", y: rc.map((r) => r.subfield), x: rc.map((r) => r.rca), marker: { color: labColor(iSel.value) === css("--multi") ? css("--lab-4") : labColor(iSel.value) },
    customdata: rc.map((r) => [r.papers, r.share]), hovertemplate: "%{y}: RCA %{x:.1f}<br>%{customdata[0]} papers (%{customdata[1]:.1%})<extra></extra>" }],
    { xaxis: { type: "log", title: "RCA vs India (log)" }, yaxis: { automargin: true }, showlegend: false, margin: { l: 10, r: 20, t: 10, b: 50 } });
  const g = (R3.gravity || []).filter((r) => r.term === "log_distance");
  plot("c-bm-grav", [{ type: "scatter", mode: "markers", y: g.map((r) => r.outcome.replace("_", " ")), x: g.map((r) => r.coef), error_x: { type: "data", symmetric: false, array: g.map((r) => r.ci_hi - r.coef), arrayminus: g.map((r) => r.coef - r.ci_lo), color: css("--ink-2") },
    marker: { size: 13, color: [css("--lab-1"), css("--lab-3"), css("--lab-2")] }, hovertemplate: "%{y}: elasticity %{x:.2f}<extra></extra>" }],
    { xaxis: { title: "Distance elasticity", zeroline: true, zerolinecolor: css("--muted") }, yaxis: { automargin: true }, showlegend: false, margin: { l: 10, r: 20, t: 10, b: 50 } });
  const gv = (J || {}).gravity || {};
  el("bm-grav-note").textContent = gv.partners ? `${fmt(gv.partners)} Indian partners, median distance ${fmt(gv.median_distance_km)} km. Another course group reported −0.70 for joint papers and −0.17 for citations.` : "";
  table("t-bm", inst.map((r) => Object.assign({}, r, { kind: ours(r) ? "our lab" : "peer" })), [{ title: "Institute", field: "short", frozen: true }, { title: "", field: "kind" },
    { title: "Name", field: "name", widthGrow: 2 }, { title: "City", field: "city" }, ...BMM.map(([k, n, f]) => ({ title: n, field: k, hozAlign: "right", formatter: (c) => f(c.getValue()) }))],
    { initialSort: [{ column: "mean_fwci", dir: "desc" }], maxHeight: 560 });
  el("bm-cav").replaceChildren(...((J || {}).caveats || []).map((t) => mk("li", t)));
}
P3REG.benchmark = renderBenchmark;


// ------------------------------------------------------------------ Only here: firsts against the 29 other groups
const NOV = (D.p2 && D.p2.novelty) || [];
const FIRST = (D.p2 && D.p2.firsts) || null;
const tierOf = (r) => r.other_groups < 0 ? "baseline" : r.other_groups === 0 ? "first" : r.other_groups <= 2 ? "rare" : r.other_groups <= 5 ? "uncommon" : "common";
const TIER = { first: ["First", "nobody else"], rare: ["Rare", "1–2 groups"], uncommon: ["Uncommon", "3–5 groups"], common: ["Common", "6+ groups"], baseline: ["Baseline", "nearly all groups"] };
const DOCKEY = [[/RSiena/, "Finding 40:"], [/Specification curve/, "Finding 22:"], [/Guimerà/, "Finding 31:"], [/Tie survival/, "Finding 32:"],
  [/author-matching errors/, "Finding 34:"], [/Time-respecting/, "Finding 35:"], [/first-passage/, "Finding 44:"], [/k-shell/, "Finding 43:"], [/outbreak simulator/, "Finding 41:"]];
function docResult(item) {
  const bb = ((RJ.extras || {}).backbone) || {}, hf = ((RJ.extras || {}).h_filtered) || {};
  if (/backbone/.test(item) && bb.edges) return `Keeps ${fmt(bb.backbone_edges)} of ${fmt(bb.edges)} institution links, carrying ${pct(bb.weight_kept, 0)} of the joint-paper weight.`;
  if (/h-index recomputed/.test(item) && hf.faculty_h_gt10_lt100 !== undefined) return `e.g. ${hf.faculty_h_gt10_lt100} faculty keep an h-index above 10 on papers with fewer than 100 authors (${hf.faculty_h_gt10_all} on all papers); any threshold works.`;
  const k = DOCKEY.find(([re]) => re.test(item)); if (!k) return "";
  const row = (((D.p2 || {}).findings_doc) || []).find((r) => r.text.startsWith(k[1])); if (!row) return "";
  const m = row.text.match(/Result: (.*)\.$/); return m ? m[1].charAt(0).toUpperCase() + m[1].slice(1) + "." : "";
}
function renderNovelty() {
  if (!NOV.length) { el("nv-firsts").replaceChildren(mk("p", "Add data/manual/novelty_map.csv.", "muted")); return; }
  const cat = NOV.filter((r) => /^\d/.test(r.id)), firsts = NOV.filter((r) => r.other_groups === 0), base = NOV.filter((r) => r.other_groups < 0);
  const yes = (r) => r.ours === "yes", part = (r) => r.ours === "partial";
  const common = cat.filter((r) => r.other_groups >= 6), rare = cat.filter((r) => r.other_groups > 0 && r.other_groups <= 2);
  kpis("nv-kpis", [["Firsts", fmt(firsts.length), "methods and features no other group did"],
    ["Rare, and we did them", fmt(rare.filter(yes).length), `of ${rare.length} items only 1–2 groups did`],
    ["Catalogue covered", `${fmt(cat.filter(yes).length)} / ${fmt(cat.length)}`, `plus ${fmt(cat.filter(part).length)} in part`],
    ["Common ground kept", `${fmt(common.filter((r) => yes(r) || part(r)).length)} / ${fmt(common.length)}`, "items 6+ groups did"],
    ["Baseline kept", `${fmt(base.filter(yes).length)} / ${fmt(base.length)}`, "what nearly every group has"]]);
  const fs = (FIRST && FIRST.summary && FIRST.summary.findings) || [];
  const resOf = (code) => { const t = (fs.find((x) => x.startsWith(code + " ")) || "").replace(/^P\d+ [^:]*: /, ""); return t.charAt(0).toUpperCase() + t.slice(1); };
  const box = el("nv-firsts"); box.replaceChildren();
  firsts.forEach((r) => {
    const c = mk("button", null, "nv-first"); c.type = "button";
    c.append(mk("span", r.id === "new" ? "new method" : `course paper ${r.id}`, "nv-tag"), mk("h3", r.item));
    const res = r.id.startsWith("P") ? resOf(r.id) : docResult(r.item); if (res) c.append(mk("p", pretty(res)));
    c.append(mk("span", `${r.what_we_did} · open →`, "nv-go"));
    c.addEventListener("click", () => { show(r.page); window.scrollTo(0, 0); }); box.append(c); });
  // strip: every catalogue item by number of other groups
  const jit = (i) => ((i * 9301 + 49297) % 233280) / 233280 - 0.5;
  const ST = { yes: ["we did it", css("--lab-1"), "circle"], partial: ["partly", css("--lab-4"), "circle"], no: ["not done", css("--muted"), "circle-open"] };
  const themes = [...new Set(cat.map((r) => r.theme))];
  plot("c-nv-strip", Object.entries(ST).map(([k, [name, col, sym]]) => { const rr = cat.filter((r) => r.ours === k);
    return { type: "scatter", mode: "markers", name, x: rr.map((r, i) => Math.min(r.other_groups, 12) + 0.55 * jit(i + 7 * r.other_groups)), y: rr.map((r, i) => themes.indexOf(r.theme) + 0.6 * jit(i * 3 + 1)),
      customdata: rr.map((r) => [r.item, r.other_groups, r.what_we_did || "", r.page]), marker: { size: 11, color: col, symbol: sym, line: { width: 1.5, color: col }, opacity: 0.85 },
      hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} other groups<br>%{customdata[2]}<extra></extra>" }; }),
    { xaxis: { title: "Other groups that did it (of 29)", range: [0.3, 12.6], dtick: 1 }, yaxis: { tickvals: themes.map((_, i) => i), ticktext: themes, autorange: "reversed", automargin: true, zeroline: false },
      margin: { l: 10, r: 10, t: 40, b: 50 },
      shapes: [{ type: "rect", xref: "x", yref: "paper", x0: 0.3, x1: 2.5, y0: 0, y1: 1, fillcolor: css("--lab-2"), opacity: 0.07, line: { width: 0 } }],
      annotations: [{ xref: "x", yref: "paper", x: 1.4, y: 1.0, yanchor: "bottom", showarrow: false, text: "rare", font: { size: 12, color: css("--muted") } }] });
  el("c-nv-strip").on?.("plotly_click", (ev) => { const pg = ev.points[0].customdata[3]; if (pg) { show(pg); window.scrollTo(0, 0); } });
  const th = [...themes, "Common baseline"];
  const cnt = (t, f) => NOV.filter((r) => r.theme === t && f(r)).length;
  plot("c-nv-theme", [["first or rare, done", (r) => r.other_groups >= 0 && r.other_groups <= 2 && r.ours !== "no" && /^\d/.test(r.id), css("--lab-2")],
    ["common or baseline, done", (r) => (r.other_groups > 2 || r.other_groups < 0) && r.ours !== "no", css("--lab-1")],
    ["not done", (r) => r.ours === "no", css("--axis")]].map(([n, f, c]) => ({ type: "bar", orientation: "h", name: n, y: th, x: th.map((t) => cnt(t, f)), marker: { color: c },
      hovertemplate: `%{y}: %{x} ${n}<extra></extra>` })), { barmode: "stack", yaxis: { autorange: "reversed", automargin: true }, xaxis: { title: "Catalogue items" }, margin: { l: 10, r: 10, t: 40, b: 50 } });
  // the firsts' results
  if (FIRST) {
    const P1 = FIRST.p1_career || [];
    plot("c-nv-p1", [{ type: "bar", name: "absolute swing (papers)", x: P1.map((r) => r.career_age), y: P1.map((r) => r.laplace_alpha), marker: { color: css("--lab-3") },
      error_y: { type: "data", symmetric: false, array: P1.map((r) => r.alpha_hi - r.laplace_alpha), arrayminus: P1.map((r) => r.laplace_alpha - r.alpha_lo), color: css("--ink-2") },
      customdata: P1.map((r) => [r.faculty, r.faculty_years]), hovertemplate: "career age %{x}: %{y:.2f} papers<br>%{customdata[0]} faculty, %{customdata[1]} faculty-years<extra></extra>" },
      { type: "scatter", mode: "lines+markers", name: "relative to mean output", x: P1.map((r) => r.career_age), y: P1.map((r) => r.relative_alpha), yaxis: "y2", line: { color: css("--lab-2"), width: 3 } }],
      { xaxis: { title: "Years since first paper" }, yaxis: { title: "Laplace scale (papers)" }, yaxis2: { overlaying: "y", side: "right", title: "relative", rangemode: "tozero", showgrid: false }, margin: { l: 60, r: 60, t: 40, b: 50 } });
    const P3 = FIRST.p3_event || [];
    plot("c-nv-p3", ["first joint paper", "distance-2 control"].map((g, i) => { const rr = P3.filter((r) => r.group === g);
      return { type: "scatter", mode: "lines+markers", name: g === "first joint paper" ? "pairs who start writing together" : "pairs with a shared co-author who never do",
        x: rr.map((r) => r.tau), y: rr.map((r) => r.mean), line: { color: i ? css("--muted") : css("--lab-1"), width: 3, dash: i ? "dash" : "solid" },
        error_y: { type: "data", symmetric: false, array: rr.map((r) => r.hi - r.mean), arrayminus: rr.map((r) => r.mean - r.lo), color: i ? css("--muted") : css("--lab-1"), thickness: 1 } }; }),
      { xaxis: { title: "Years from the first joint paper", zeroline: true }, yaxis: { title: "Citations between the pair per year" }, margin: { l: 60, r: 10, t: 40, b: 50 },
        shapes: [{ type: "line", x0: 0, x1: 0, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: css("--muted") } }] });
    const P6 = (FIRST.p6_citation_model || []).filter((r) => r.term === "coauthor" || r.term === "topic");
    plot("c-nv-p6", ["coauthor", "topic"].map((t, i) => { const rr = P6.filter((r) => r.term === t);
      return { type: "scatter", mode: "markers", name: t === "coauthor" ? "co-authored before" : "topic similarity", y: rr.map((r) => r.model), x: rr.map((r) => r.odds_ratio),
        error_x: { type: "data", symmetric: false, array: rr.map((r) => r.or_hi - r.odds_ratio), arrayminus: rr.map((r) => r.odds_ratio - r.or_lo), color: i ? css("--lab-3") : css("--lab-1") },
        marker: { size: 13, color: i ? css("--lab-3") : css("--lab-1") }, hovertemplate: "%{y}: odds ratio %{x:.1f}<extra></extra>" }; }),
      { xaxis: { type: "log", title: "Odds ratio of citing (log)" }, yaxis: { automargin: true, autorange: "reversed" }, margin: { l: 10, r: 10, t: 40, b: 50 },
        shapes: [{ type: "line", x0: 1, x1: 1, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: css("--muted") } }] });
    const P10 = (FIRST.p10_flows || []).filter((r) => state.lab === "ALL" || r.lab === state.lab);
    const agg = (k) => { const ys = [...new Set(P10.map((r) => r.year))].sort(); return [ys, ys.map((y) => P10.filter((r) => r.year === y).reduce((a, r) => a + r[k], 0) / Math.max(1, P10.filter((r) => r.year === y).length))]; };
    plot("c-nv-p10", [["within", "same people changing", css("--lab-1")], ["entry", "people joining", css("--lab-2")], ["exit", "people leaving", css("--lab-3")]].map(([k, n, c]) => { const [x, y] = agg(k);
      return { type: "bar", name: n, x, y, marker: { color: c }, hovertemplate: `${n}: %{y:+.1%}<extra></extra>` }; }),
      { barmode: "relative", yaxis: { tickformat: "+.0%", title: `Change in share (${state.lab === "ALL" ? "mean of the four labs" : short(state.lab)})` }, margin: { l: 60, r: 10, t: 40, b: 40 } });
    const P8 = FIRST.p8_group_sizes || [], s8 = (FIRST.summary || {}).p8 || {};
    plot("c-nv-p8", [{ type: "bar", x: P8.map((r) => r.group_size), y: P8.map((r) => r.faculty_years), marker: { color: css("--lab-4") }, hovertemplate: "group of %{x}: %{y} PI-years<extra></extra>" }],
      { xaxis: { title: "Group size (students, postdocs, staff)", range: [0, 40] }, yaxis: { title: "PI-years" }, showlegend: false, margin: { l: 56, r: 10, t: 10, b: 50 } });
    el("nv-p8").textContent = s8.gibrat_slope !== undefined ? `Gibrat slope ${fmt(s8.gibrat_slope, 2)} (95% CI ${fmt(s8.gibrat_ci[0], 2)} to ${fmt(s8.gibrat_ci[1], 2)}): below 0, so large groups grow more slowly than small ones (mean reversion), not proportionally. Median group ${fmt(s8.median_group)}, largest ${fmt(s8.max_group)}. Department size and papers per faculty: slope ${fmt(s8.dept_size_slope, 2)} (p = ${fmt(s8.dept_size_p, 2)}).` : "";
    const P9 = FIRST.p9_diversity || [];
    plot("c-nv-p9", [{ type: "scatter", mode: "markers", y: P9.map((r) => r.outcome === "late_papers" ? "2021–26 papers" : "2021–26 normalised impact"), x: P9.map((r) => r.spearman), marker: { size: 14, color: css("--lab-1") }, name: "observed",
      error_x: { type: "data", symmetric: false, array: P9.map((r) => r.null_hi - r.spearman), arrayminus: P9.map((r) => r.spearman - r.null_lo), color: css("--axis"), thickness: 6, width: 0 },
      customdata: P9.map((r) => [r.null_mean, r.p]), hovertemplate: "Spearman %{x:.2f}<br>reshuffled mean %{customdata[0]:.2f}, p = %{customdata[1]:.2f}<extra></extra>" }],
      { xaxis: { title: "Spearman with early partner diversity (grey: reshuffled 95% range)", zeroline: true }, yaxis: { automargin: true }, showlegend: false, margin: { l: 10, r: 10, t: 10, b: 50 } });
  }
  const t = table("t-nv", NOV.map((r) => Object.assign({}, r, { tier: TIER[tierOf(r)][0], groups: r.other_groups < 0 ? "most" : r.other_groups })), [
    { title: "Item", field: "item", formatter: "textarea", widthGrow: 4, minWidth: 240, headerFilter: "input" }, { title: "Theme", field: "theme", headerFilter: "input", widthGrow: 2 },
    { title: "Other groups", field: "groups", hozAlign: "right", sorter: (a, b) => (a === "most" ? 99 : a) - (b === "most" ? 99 : b) },
    { title: "Tier", field: "tier", headerFilter: "input", formatter: (c) => mk("span", c.getValue(), `badge ${{ First: "ok", Rare: "ok", Uncommon: "mid", Common: "mid", Baseline: "mid" }[c.getValue()]}`) },
    { title: "Ours", field: "ours", headerFilter: "input", formatter: (c) => mk("span", { yes: "done", partial: "partly", no: "not done" }[c.getValue()], `badge ${{ yes: "ok", partial: "mid", no: "no" }[c.getValue()]}`) },
    { title: "What we did", field: "what_we_did", formatter: "textarea", widthGrow: 3 }], { layout: "fitColumns", initialSort: [{ column: "groups", dir: "asc" }] });
  if (t) t.on("rowClick", (e, row) => { const pg = row.getData().page; if (pg) { show(pg); window.scrollTo(0, 0); } });
}
P3REG.novelty = renderNovelty;

// ------------------------------------------------------------------ About: completeness and the precision audit
P3API.about = function () {
  const cm = (R3.completeness || []).filter((r) => r.scope === state.lab);
  if (cm.length) plot("c-ab-complete", [{ type: "bar", orientation: "h", y: cm.map((r) => r.item), x: cm.map((r) => r.share), text: cm.map((r) => pct(r.share, 0)), textposition: "outside",
    marker: { color: cm.map((r) => r.share >= 0.9 ? css("--lab-1") : r.share >= 0.6 ? css("--lab-4") : css("--lab-2")) }, customdata: cm.map((r) => r.n),
    hovertemplate: "%{y}: %{x:.1%} of %{customdata}<extra></extra>" }], { xaxis: { tickformat: ".0%", range: [0, 1.12] }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false, margin: { l: 10, r: 20, t: 10, b: 40 } });
  const a = ((RJ.extras || {}).precision_audit) || {}, box = el("ab-audit"); if (!box) return; box.replaceChildren();
  const pr = R3.precision || [];
  if (pr.length) {
    const all = pr.find((r) => r.method === "all") || pr[0];
    const big = mk("div", null, "bigstat"); big.append(mk("b", pct(all.precision, 0)), mk("span", `of ${all.checked} checked links are correct (95% CI ${pct(all.ci_lo, 0)}–${pct(all.ci_hi, 0)}). Checked by ${(a.checkers || []).join(", ") || "the team"}.`));
    box.append(big);
    table("t-ab-audit", pr, [{ title: "Matched by", field: "method" }, { title: "Checked", field: "checked", hozAlign: "right" }, { title: "Correct", field: "correct", hozAlign: "right" },
      { title: "Precision", field: "precision", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }], { layout: "fitColumns" });
  } else {
    box.append(mk("p", `${a.sample || 50} links sampled; ${a.checked || 0} checked so far. Each row in data/manual/precision_audit.csv gets a verdict (correct, wrong or unsure) and the checker's name; re-running step s26 then shows the measured precision here.`, "note"));
  }
};

// ------------------------------------------------------------------ "How to read" panels
const EXPLAIN = {
  "c-trend": "Bars are papers per year for each lab. The last year is partial, so its drop is not a real decline.",
  "c-cites": "Citations received by the papers of each year. Older papers have had longer to be cited, so recent bars are always lower: compare labs within a year, not years with each other.",
  "c-fd-ex": "Each cell is how often one lab cites another, divided by what a random reshuffle predicts. Diagonal cells above 1 mean labs read their own work more than topic and year explain.",
  "c-fd-or": "Dots are odds ratios on a log scale; bars are 95% intervals. A bar crossing the dashed line at 1 means no clear effect.",
  "c-fd-dist": "Distance 1 = co-authors, 2 = a co-author in common. Values above 1 mean more citations than the two people's citation volumes predict.",
  "c-fd-flow": "Above 1 the lab receives more Indian citations than it gives. Use the coloured lines (same window); the grey dashed line is biased by citation lag.",
  "c-fd-rank": "Lower is better (rank 1 at the top). Long horizontal spreads mean a person's rank depends on how credit for big papers is counted.",
  "c-x-regrade": "If only the solid line falls while the dashed (frozen) line holds, journals changed grade, not the labs' choices. The dotted line uses one fixed impact-factor cut-off.",
  "c-x-payoff": "Each dot is the citation difference for papers with that kind of partner. Intervals crossing 0 mean no clear difference. Dark dots also hold team size equal, which matters because big teams bring more partners.",
  "c-x-cc": "Points on a rising diagonal cite in proportion to how much they collaborate. Points far above it cite a lot with little collaboration; that needs an explanation (fields, alumni, reviews), not suspicion.",
  "c-x-walk-d": "A straight-sided tent on this log scale is a Laplace distribution; a normal distribution curves down faster in the tails. Bars following the solid line mean Laplace fits better.",
  "c-x-walk-c": "Each dot is a quantile (e.g. the median person). On the diagonal, chance alone (a random walk) reproduces that part of the spread of output.",
  "c-ep-sis": "Below the threshold an outbreak dies out; above it a share of faculty stays infected. The real network (blue) catches on at a lower λ than a random network, because of hubs.",
  "c-ep-cross": "Each cell: the chance that an outbreak starting in the row's lab reaches the column's lab. Compare with the rewired value in brackets: the gap is what the lab walls cost.",
  "c-ep-spread": "Each dot is a faculty member as the first case. Higher = bigger outbreak. A tight rising cloud means that centrality predicts spreading power well.",
  "c-ep-int": "How much the chance of crossing labs rises as links are added. Flat lines mean a few new links do little; the error bars show the spread over random draws.",
  "c-rw-mfpt": "Steps a random walker needs to reach another lab, as a multiple of the rewired network's value. 20× means the labs are 20 times harder to reach than if links were random.",
  "c-rw-ret": "Solid lines staying high for many steps mean walkers stay home. Dashed lines (rewired) drop fast, as they should without lab structure.",
  "c-st-grow": "On log axes a straight line means a power law. A slope above 1 means links grow faster than people: the network densifies.",
  "c-st-pa": "A slope of 1 on log axes is linear preferential attachment (the rich get richer in proportion). Below 1, well-connected faculty gain links less than proportionally.",
  "c-st-lp": "AUC is the chance a real new link scores above a random non-link. 0.5 is a coin toss.",
  "c-bm-scatter": "Bubbles to the right publish more; higher has more impact. Our labs are outlined. FWCI corrects for field and year, so biology and chemistry institutes compare fairly.",
  "c-bm-rank": "Bars are sorted values; error bars are 95% intervals. Overlapping intervals mean the ranks are not clearly different.",
  "c-ex-scatter": "Higher-IF journals are on the right. The vertical spread at any IF shows how differently papers in the same journals are cited.",
  "c-pp-pct": "Each bar is this person's percentile within their own lab; 50 is the lab's median faculty member.",
  "c-vs-radar": "Each axis is a percentile among all 274 faculty (or share of the best lab). A larger shape is not always better: big shapes on citations with small fractional citations point to consortium papers.",
};
function addExplain() {
  for (const [id, text] of Object.entries(EXPLAIN)) {
    const e = el(id); if (!e) continue; const card = e.closest(".card"); if (!card || card.querySelector("details.explain")) continue;
    const d = mk("details", null, "explain"); d.append(mk("summary", "How to read this chart"), mk("p", text)); card.append(d);
  }
}

// ------------------------------------------------------------------ wiring (called once from app.js)
function P3WIRE() {
  addExplain();
  if (X) {
    const pre = el("ex-presets");
    PRESETS.forEach(([n, o]) => { const b = mk("button", n, "preset"); b.type = "button"; b.addEventListener("click", () => {
      pre.querySelectorAll(".preset").forEach((x) => x.classList.toggle("on", x === b)); exSet(o); renderExplorer(); }); pre.append(b); });
    X.fields.forEach((f) => el("ex-f").append(new Option(f, f)));
    let tm = null;
    document.querySelectorAll("#tab-explorer .filters input, #tab-explorer .filters select").forEach((i) => i.addEventListener(i.tagName === "SELECT" ? "change" : "input", () => {
      if (i.id === "ex-if") i.dataset.strict = ""; pre.querySelectorAll(".preset").forEach((x) => x.classList.remove("on"));
      clearTimeout(tm); tm = setTimeout(renderExplorer, 180); }));
    el("ex-reset").addEventListener("click", () => { exSet(EXDEF); pre.querySelectorAll(".preset").forEach((x) => x.classList.remove("on")); renderExplorer(); });
    exSet(PRESETS[0][1]); pre.firstChild.classList.add("on");
    const dlst = el("pp-names");
    [...XF].sort((a, b) => a.name.localeCompare(b.name)).forEach((p) => dlst.append(new Option(`${p.name} (${short(p.lab)})`)));
    const byLabel = (v) => XF.find((p) => `${p.name} (${short(p.lab)})` === v) || XF.find((p) => p.name.toLowerCase() === v.trim().toLowerCase());
    el("pp-q").addEventListener("change", (e) => { const p = byLabel(e.target.value); if (p) P3API.openPerson(p.id); });
    el("pp-cmp").addEventListener("click", () => P3API.addCompare(state.person));
    el("pp-rand").addEventListener("click", () => P3API.openPerson(XF[Math.floor(Math.random() * XF.length)].id));
    el("vs-q").addEventListener("change", (e) => { const p = byLabel(e.target.value); if (p) { e.target.value = ""; P3API.addCompare(p.id); } });
    el("vs-kind").addEventListener("change", renderVersus);
    el("vs-clear").addEventListener("click", () => { state.cmp = []; renderVersus(); });
  }
  ["bm-y", "bm-m"].forEach((id) => el(id) && el(id).addEventListener("change", renderBenchmark));
  if (el("bm-inst")) el("bm-inst").addEventListener("change", (e) => { e.target.dataset.touched = "1"; renderBenchmark(); });
}
