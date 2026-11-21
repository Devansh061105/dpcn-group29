/* Dynamics pages: Epidemics (s23 results + a live SIS/SIR simulator), Random walks (s23 + s26) and Structure (s24).
   Inlined into app.js's closure after phase3.js; shares D, state, plot(), table(), kpis(), mk(), R3, RJ, findingCards(). */
const DYREG = {};
const DY = RJ.dynamics || null;
const NET = (D.authorship && D.authorship.faculty) || { nodes: [], edges: [] };

// ------------------------------------------------------------------ Epidemics: precomputed results
function renderEpidemics() {
  if (!DY) { findingCards("ep-list", null, "Run step s23 to simulate the epidemic models."); return; }
  findingCards("ep-list", DY.findings);
  const tn = DY.threshold_numeric || {}, cr = DY.crosslab_reach || {};
  kpis("ep-kpis", [["Epidemic threshold", fmt(tn.observed, 3), `λ = β/μ on the real network (rewired ${fmt(tn.rewired, 3)}, random ${fmt(tn.ER, 3)})`],
    ["Mean-field prediction", fmt(DY.threshold_hmf_observed, 3), `⟨k⟩/⟨k²⟩; quenched 1/Λmax = ${fmt(DY.threshold_qmf_observed, 3)}`],
    ["Best spreading predictor", DY.best_centrality || "–", `Spearman ${fmt(((DY.influence_spearman || {})[DY.best_centrality] || {}).rho_sir, 2)}; k-shell ${fmt(((DY.influence_spearman || {}).kshell || {}).rho_sir, 2)}, degree ${fmt(((DY.influence_spearman || {}).degree || {}).rho_sir, 2)}`],
    ["Reaches another lab", pct(cr.observed, 0), `of outbreaks, against ${pct(cr.rewired, 0)} on rewired networks`],
    ["Network", `${fmt(DY.lcc_n)} / ${fmt(DY.n)}`, `faculty in the largest component; ⟨k⟩ = ${fmt(DY.k_mean, 1)}`]]);
  const sis = R3.epi_sis_curve || [], th = R3.epi_threshold || [];
  const NC = { observed: css("--lab-1"), rewired: css("--lab-3"), ER: css("--muted") };
  const NL = { observed: "real network", rewired: "rewired (same degrees)", ER: "random (Erdős–Rényi)" };
  const tr = [];
  Object.keys(NC).forEach((n) => { const rr = sis.filter((r) => r.network === n);
    tr.push({ type: "scatter", mode: "lines", x: rr.map((r) => r.lam), y: rr.map((r) => r.prevalence_hi), line: { width: 0 }, showlegend: false, hoverinfo: "skip" });
    tr.push({ type: "scatter", mode: "lines", name: NL[n], x: rr.map((r) => r.lam), y: rr.map((r) => r.prevalence_lo), fill: "tonexty", fillcolor: NC[n] + "33", line: { width: 0 }, showlegend: false, hoverinfo: "skip" });
    tr.push({ type: "scatter", mode: "lines+markers", name: NL[n], x: rr.map((r) => r.lam), y: rr.map((r) => r.prevalence_mean), line: { color: NC[n], width: 2.5 }, marker: { size: 5 },
      hovertemplate: `${NL[n]}<br>λ = %{x:.3f}: %{y:.1%} infected<extra></extra>` }); });
  const shapes = th.filter((r) => /numeric/.test(r.method)).map((r) => ({ type: "line", xref: "x", yref: "paper", x0: r.lambda_c, x1: r.lambda_c, y0: 0, y1: 1, line: { color: NC[r.network], dash: "dot", width: 1.5 } }));
  plot("c-ep-sis", tr, { xaxis: { type: "log", title: "λ = β / μ (log)" }, yaxis: { title: "Share infected in the long run", tickformat: ".0%" }, shapes, margin: { l: 60, r: 10, t: 40, b: 50 } });
  const st = R3.epi_strategies || [];
  plot("c-ep-strat", [{ type: "bar", orientation: "h", y: st.map((r) => `${r.strategy}${r.seeds > 1 ? ` (${r.seeds} seeds)` : ""}`), x: st.map((r) => r.size_mean),
    error_x: { type: "data", symmetric: false, array: st.map((r) => r.size_hi - r.size_mean), arrayminus: st.map((r) => r.size_mean - r.size_lo), color: css("--ink-2") },
    marker: { color: st.map((r) => r.strategy === DY.best_strategy ? css("--lab-2") : css("--lab-4")) }, customdata: st.map((r) => [r.p_major_outbreak, r.t_half_median]),
    hovertemplate: "%{y}: %{x:.1f} faculty on average<br>major outbreak in %{customdata[0]:.0%} of runs<extra></extra>" }],
    { xaxis: { title: "Faculty infected (SIR final size)" }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false, margin: { l: 10, r: 20, t: 10, b: 50 } });
  const sp = R3.epi_spreaders || [], xk = el("ep-x").value;
  plot("c-ep-spread", LABS.map((l) => { const rr = sp.filter((r) => r.lab === l); return { type: "scatter", mode: "markers", name: short(l), x: rr.map((r) => r[xk]), y: rr.map((r) => r.sir_size_mean),
    text: rr.map((r) => r.name), customdata: rr.map((r) => r.faculty_id), marker: { color: labColor(l), size: 9, opacity: 0.75, symbol: labShape(l) === "triangle" ? "triangle-up" : labShape(l) === "diamond" ? "diamond" : labShape(l) === "round-rectangle" ? "square" : "circle" },
    hovertemplate: "<b>%{text}</b><br>" + xk + " %{x:.3g}: %{y:.1f} faculty infected<extra></extra>" }; }),
    { xaxis: { title: el("ep-x").selectedOptions[0].text, type: xk === "betweenness" ? "log" : "linear" }, yaxis: { title: "Mean outbreak size" }, margin: { l: 60, r: 10, t: 40, b: 50 } });
  el("c-ep-spread").on?.("plotly_click", (ev) => P3API.openPerson(ev.points[0].customdata));
  const cx = (R3.epi_crosslab || []).filter((r) => r.seed_lab !== r.target_lab);
  const z = (net) => LABS.map((a) => LABS.map((b) => a === b ? null : (cx.find((r) => r.network === net && r.seed_lab === a && r.target_lab === b) || {}).p_reach));
  const zo = z("observed"), zr = z("rewired");
  plot("c-ep-cross", [{ type: "heatmap", x: LABS.map(short), y: LABS.map(short), z: zo, zmin: 0, zmax: Math.max(...zr.flat().filter((v) => v !== null)),
    colorscale: [[0, css("--surface")], [1, css("--lab-1")]], showscale: false,
    text: LABS.map((a, i) => LABS.map((b, j) => i === j ? "" : `${pct(zo[i][j], 0)} (rewired ${pct(zr[i][j], 0)})`)), texttemplate: "%{text}",
    hovertemplate: "Started in %{y}, reaches %{x}<br>%{text}<extra></extra>" }],
    { xaxis: { title: "Reaches lab" }, yaxis: { title: "Outbreak starts in", autorange: "reversed" }, margin: { l: 80, r: 10, t: 10, b: 50 } });
  const iv = R3.epi_intervention || [], base = iv.find((r) => r.k === 0) || {};
  const SC = [css("--lab-1"), css("--lab-2"), css("--lab-3")];
  plot("c-ep-int", [...new Set(iv.filter((r) => r.k > 0).map((r) => r.strategy))].map((s, i) => { const rr = [base, ...iv.filter((r) => r.strategy === s)];
    return { type: "scatter", mode: "lines+markers", name: s, x: rr.map((r) => r.k), y: rr.map((r) => r.reach_mean), line: { color: SC[i % 3], width: 2.5 },
      error_y: { type: "data", symmetric: false, array: rr.map((r) => (r.reach_hi ?? r.reach_mean) - r.reach_mean), arrayminus: rr.map((r) => r.reach_mean - (r.reach_lo ?? r.reach_mean)), color: SC[i % 3], thickness: 1 },
      hovertemplate: `${s}<br>%{x} new links: %{y:.1%} cross-lab reach<extra></extra>` }; }),
    { xaxis: { title: "Cross-lab links added" }, yaxis: { title: "Chance an outbreak reaches another lab", tickformat: ".0%" }, margin: { l: 60, r: 10, t: 40, b: 50 } });
  const t = table("t-ep-spread", sp.slice().sort((a, b) => a.rank_influence - b.rank_influence).map((r) => Object.assign({}, r, { lab: short(r.lab) })), [
    { title: "#", field: "rank_influence", width: 60 }, { title: "Name", field: "name", headerFilter: "input", minWidth: 150 }, { title: "Lab", field: "lab" },
    { title: "Outbreak size", field: "sir_size_mean", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 1) }, { title: "k-shell", field: "kshell", hozAlign: "right" },
    { title: "Degree", field: "degree", hozAlign: "right" }, { title: "SIS survival", field: "sis_survival", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) }],
    { layout: "fitColumns", maxHeight: 420 });
  if (t) t.on("rowClick", (e, row) => P3API.openPerson(row.getData().faculty_id));
  simInit();
}
DYREG.epidemics = renderEpidemics;

// ------------------------------------------------------------------ the live simulator
const SIM = { cy: null, adj: null, ids: [], lab: [], st: null, t: 0, hist: [], timer: null, seed: null, rng: null };
function mulberry(a) { return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function simInit() {
  if (SIM.cy || !NET.nodes.length || typeof cytoscape === "undefined") return;
  SIM.ids = NET.nodes.map((n) => n.id); SIM.lab = NET.nodes.map((n) => n.lab);
  const ix = Object.fromEntries(SIM.ids.map((id, i) => [id, i]));
  SIM.adj = SIM.ids.map(() => []);
  NET.edges.forEach((e) => { const a = ix[e.s], b = ix[e.t]; if (a === undefined || b === undefined) return; SIM.adj[a].push(b); SIM.adj[b].push(a); });
  const deg = SIM.adj.map((a) => a.length);
  SIM.seed = deg.indexOf(Math.max(...deg));
  SIM.cy = cytoscape({ container: el("g-sim"), wheelSensitivity: 0.2, layout: { name: "preset", fit: true, padding: 16 },
    elements: [...NET.nodes.map((n, i) => ({ data: { id: n.id, label: n.name, col: labColor(n.lab), sz: 7 + 2.2 * Math.sqrt(deg[i]) }, position: { x: n.x, y: n.y } })),
      ...NET.edges.map((e, i) => ({ data: { id: `se${i}`, source: e.s, target: e.t, cross: e.cross ? 1 : 0 } }))],
    style: [{ selector: "node", style: { "background-color": "data(col)", width: "data(sz)", height: "data(sz)", opacity: 0.55, "border-width": 0 } },
      { selector: "node.I", style: { "background-color": "#e11d48", opacity: 1, "border-width": 2, "border-color": "#fecdd3", width: "mapData(sz, 7, 30, 12, 36)", height: "mapData(sz, 7, 30, 12, 36)" } },
      { selector: "node.R", style: { "background-color": css("--muted"), opacity: 0.35 } },
      { selector: "node.seed", style: { "border-width": 3, "border-color": css("--ink"), opacity: 1 } },
      { selector: "node:selected", style: { label: "data(label)", "font-size": 11, color: css("--ink") } },
      { selector: "edge", style: { width: 0.6, "line-color": css("--axis"), opacity: 0.35, "curve-style": "haystack" } },
      { selector: "edge[cross = 1]", style: { "line-color": css("--lab-2"), opacity: 0.6, "line-style": "dashed" } }] });
  SIM.cy.on("tap", "node", (e) => { if (el("sim-seed").value !== "click") el("sim-seed").value = "click"; SIM.seed = SIM.ids.indexOf(e.target.id()); simReset(); });
  SIM.cy.on("mouseover", "node", (e) => e.target.select()); SIM.cy.on("mouseout", "node", (e) => e.target.unselect());
  simReset();
}
function simSeeds(rng) {
  const mode = el("sim-seed").value, n = SIM.ids.length, deg = SIM.adj.map((a) => a.length);
  if (mode === "degree") return [deg.indexOf(Math.max(...deg))];
  if (mode === "random") { let k; do { k = Math.floor(rng() * n); } while (!deg[k]); return [k]; }
  if (mode === "lab") return LABS.map((l) => { const c = SIM.lab.map((x, i) => [x, i]).filter(([x, i]) => x === l && deg[i]); return c.length ? c[Math.floor(rng() * c.length)][1] : null; }).filter((x) => x !== null);
  return [SIM.seed];
}
function simStepState(st, rng, beta, mu, model) {   // st: 0 = S, 1 = I, 2 = R; returns the new state
  const nx = st.slice();
  for (let i = 0; i < st.length; i++) {
    if (st[i] !== 1) continue;
    for (const j of SIM.adj[i]) if (st[j] === 0 && nx[j] === 0 && rng() < beta) nx[j] = 1;
    if (rng() < mu) nx[i] = model === "SIS" ? 0 : 2;
  }
  return nx;
}
function simParams() { return { beta: +el("sim-b").value, mu: +el("sim-m").value, model: el("sim-model").value, rs: +el("sim-rng").value || 1 }; }
function simReset() {
  if (!SIM.cy) return;
  clearInterval(SIM.timer); SIM.timer = null; el("sim-run").textContent = "▶ Run";
  const p = simParams(); SIM.rng = mulberry(p.rs);
  SIM.st = new Array(SIM.ids.length).fill(0); const seeds = simSeeds(SIM.rng); seeds.forEach((k) => { SIM.st[k] = 1; });
  SIM.t = 0; SIM.hist = [[0, seeds.length, 0]]; SIM.seeds = seeds; SIM.everI = null;
  el("sim-bv").textContent = ` ${p.beta.toFixed(2)}`; el("sim-mv").textContent = ` ${p.mu.toFixed(2)} (λ = ${(p.beta / p.mu).toFixed(2)})`;
  simDraw();
}
function simDraw() {
  const n = SIM.ids.length;
  SIM.cy.batch(() => SIM.cy.nodes().forEach((nd, i) => { nd.toggleClass("I", SIM.st[i] === 1); nd.toggleClass("R", SIM.st[i] === 2); nd.toggleClass("seed", SIM.seeds.includes(i)); }));
  const inf = SIM.st.filter((s) => s === 1).length, rec = SIM.st.filter((s) => s === 2).length;
  const ever = SIM.st.map((s, i) => s > 0 || SIM.everI?.[i]);
  SIM.everI = ever;
  const seedNames = SIM.seeds.map((k) => NET.nodes[k].name).join(", ");
  el("sim-status").textContent = `Step ${SIM.t}: ${inf} infected now${el("sim-model").value === "SIR" ? `, ${rec} recovered` : ""}; ${ever.filter(Boolean).length} of ${n} faculty ever infected. Seed: ${seedNames}.${inf === 0 ? " The outbreak has died out." : ""}`;
  plot("c-sim-curve", [{ type: "scatter", mode: "lines", x: SIM.hist.map((h) => h[0]), y: SIM.hist.map((h) => h[1] / n), name: "infected", line: { color: "#e11d48", width: 2.5 }, fill: "tozeroy", fillcolor: "rgba(225,29,72,.15)" },
    ...(el("sim-model").value === "SIR" ? [{ type: "scatter", mode: "lines", x: SIM.hist.map((h) => h[0]), y: SIM.hist.map((h) => h[2] / n), name: "recovered", line: { color: css("--muted"), width: 2 } }] : [])],
    { yaxis: { tickformat: ".0%", title: "" }, xaxis: { title: "step" }, margin: { l: 44, r: 6, t: 26, b: 36 }, showlegend: true, transition: undefined });
  const box = el("sim-labs"); box.replaceChildren();
  LABS.forEach((l) => { const idx = SIM.lab.map((x, i) => [x, i]).filter(([x]) => x === l).map(([, i]) => i);
    const e = idx.filter((i) => ever[i]).length, row = mk("div", null, "sim-lab");
    const bar = mk("i"); bar.style.width = `${100 * e / Math.max(1, idx.length)}%`; bar.style.background = labColor(l);
    row.append(mk("b", short(l)), mk("span", `${e} / ${idx.length} ever infected`, "muted"), mk("span", null, "sim-bar")); row.lastChild.append(bar); box.append(row); });
}
function simStep() {
  const p = simParams();
  SIM.st = simStepState(SIM.st, SIM.rng, p.beta, p.mu, p.model); SIM.t++;
  SIM.hist.push([SIM.t, SIM.st.filter((s) => s === 1).length, SIM.st.filter((s) => s === 2).length]);
  simDraw();
  if (!SIM.st.includes(1) || SIM.t >= 250) { clearInterval(SIM.timer); SIM.timer = null; el("sim-run").textContent = "▶ Run"; }
}
function simMany() {
  const p = simParams(), n = SIM.ids.length, out = [], cross = [];
  for (let r = 0; r < 100; r++) {
    const rng = mulberry(p.rs + 1000 + r); let st = new Array(n).fill(0); const seeds = simSeeds(rng); seeds.forEach((k) => { st[k] = 1; });
    const ever = st.map((s) => s > 0);
    for (let t = 0; t < 200 && st.includes(1); t++) { st = simStepState(st, rng, p.beta, p.mu, p.model); st.forEach((s, i) => { if (s) ever[i] = true; }); }
    out.push(ever.filter(Boolean).length);
    const sl = new Set(seeds.map((k) => SIM.lab[k])); cross.push(ever.some((e, i) => e && !sl.has(SIM.lab[i])) ? 1 : 0);
  }
  const box = el("c-sim-many"); box.hidden = false;
  plot("c-sim-many", [{ type: "histogram", x: out, nbinsx: 30, marker: { color: "#e11d48" }, hovertemplate: "%{x} faculty ever infected: %{y} runs<extra></extra>" }],
    { xaxis: { title: `Faculty ever infected, 100 random seeds (mean ${fmt(mean(out), 1)}; reached another lab in ${pct(mean(cross), 0)} of runs)` }, yaxis: { title: "Runs" }, margin: { l: 50, r: 10, t: 10, b: 50 } });
}

// ------------------------------------------------------------------ Random walks
function renderWalks() {
  if (!DY) findingCards("rw-list", null, "Run step s23 to compute the random walks.");
  else findingCards("rw-list", (DY.findings || []).filter((s) => /walk|first-passage|spectral|step/i.test(s)).concat(((RJ.extras || {}).findings || []).filter((s) => /Laplace|random walk|Matthew|persists/i.test(s))));
  const rw = (DY || {}).random_walk || {}, mr = (DY || {}).mfpt_ratio || {}, W = (RJ.extras || {}).walk || {};
  kpis("rw-kpis", [["Steps to leave a lab", fmt(mr.mfpt_obs_mean, 0), `mean first-passage time; ${fmt(mr.mfpt_null_mean, 0)} on rewired networks`],
    ["Harder than chance", `${fmt(mr.mean, 0)}×`, `range ${fmt(mr.min, 0)}–${fmt(mr.max, 0)}× across lab pairs`],
    ["Relaxation time", fmt(rw.relaxation_time_obs, 0), `steps to forget the start; ${fmt(rw.relaxation_time_null_mean, 0)} rewired`],
    ["Top 10% stay on top", pct(W.top_decile_persistence, 0), `of 2016–20's most productive, in 2021–25 (chance ${pct(W.top_decile_null, 0)})`]]);
  const m = R3.rw_mfpt || [];
  const z = LABS.map((a) => LABS.map((b) => a === b ? null : (m.find((r) => r.from_lab === a && r.to_lab === b) || {}).ratio));
  plot("c-rw-mfpt", [{ type: "heatmap", x: LABS.map(short), y: LABS.map(short), z, colorscale: [[0, css("--surface")], [1, css("--lab-2")]], showscale: false,
    text: LABS.map((a) => LABS.map((b) => { const r = m.find((x) => x.from_lab === a && x.to_lab === b); return r ? `${fmt(r.ratio, 1)}×<br>${fmt(r.mfpt_obs, 0)} vs ${fmt(r.mfpt_null_mean, 0)} steps` : ""; })),
    texttemplate: "%{text}", hovertemplate: "From %{y} to %{x}: %{text}<extra></extra>" }], { xaxis: { title: "To lab" }, yaxis: { title: "From lab", autorange: "reversed" }, margin: { l: 80, r: 10, t: 10, b: 50 } });
  const ret = R3.rw_retention || [];
  plot("c-rw-ret", LABS.flatMap((l) => { const rr = ret.filter((r) => r.lab === l); return [
    { type: "scatter", mode: "lines", name: short(l), x: rr.map((r) => r.step), y: rr.map((r) => r.p_stay_obs), line: { color: labColor(l), width: 2.5 } },
    { type: "scatter", mode: "lines", name: `${short(l)} rewired`, x: rr.map((r) => r.step), y: rr.map((r) => r.p_stay_null), line: { color: labColor(l), width: 1.5, dash: "dash" }, showlegend: false }]; }),
    { xaxis: { title: "Steps" }, yaxis: { title: "Still in the starting lab", tickformat: ".0%", range: [0, 1] }, margin: { l: 60, r: 10, t: 40, b: 50 } });
  P3API.walkCharts("c-rw-delta");
  const b = el("rw-matthew"); b.replaceChildren();
  if (W.faculty) {
    const big = mk("div", null, "bigstat"); big.append(mk("b", pct(W.top_decile_persistence, 0)), mk("span", `of the faculty in the top 10% by output in 2016–20 are again in the top 10% in 2021–25. If ranks were reshuffled at random, ${pct(W.top_decile_null, 0)} would be (p ${W.top_decile_p < 0.001 ? "< 0.001" : "= " + fmt(W.top_decile_p, 3)}, 2,000 permutations).`));
    b.append(big, mk("p", `Rank correlation between the two periods: Spearman ${fmt(W.rank_rho, 2)}. This is the Matthew effect (Merton 1968) in output: success persists. Yet a simple truncated random walk with Laplace steps reproduces the share of years with no paper (${pct(W.zero_years_random_walk, 0)} vs ${pct(W.zero_years_observed, 0)}) and much of the inequality (Gini ${fmt(W.gini_random_walk, 2)} vs ${fmt(W.gini_observed, 2)}), so luck explains a lot of the spread, while persistence explains who stays on top.`, "note"));
  } else b.append(mk("p", "Run step s26.", "muted"));
}
DYREG.walks = renderWalks;

// ------------------------------------------------------------------ Structure (s24)
function renderStructure() {
  const S = RJ.structure;
  if (!S) { findingCards("st-list", null, "Run step s24 to compute the structural analyses."); return; }
  findingCards("st-list", S.findings);
  const nt = R3.null_table || [];
  table("t-st-null", nt.map((r) => Object.assign({}, r, { model: r.model.replace("Erdos-Renyi", "Erdős–Rényi") })), [
    { title: "Measure", field: "metric", minWidth: 170 }, { title: "Observed", field: "observed", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) },
    { title: "Baseline", field: "model", widthGrow: 2 }, { title: "Baseline mean", field: "null_mean", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) },
    { title: "z", field: "z", hozAlign: "right", formatter: (c) => { const v = c.getValue(); const e = mk("span", fmt(v, 1), `badge ${Math.abs(v) >= 3 ? "ok" : Math.abs(v) >= 2 ? "mid" : "no"}`); return e; } },
    { title: "p", field: "p_two_sided", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }], { layout: "fitColumns", maxHeight: 520, groupBy: "metric" });
  const gl = (R3.students_glue || []).filter((r) => r.scope === "ALL");
  table("t-st-glue", gl, [{ title: "Measure", field: "metric", minWidth: 150 }, { title: "Faculty only", field: "faculty_only", hozAlign: "right", formatter: (c) => fmtAuto(c.getValue()) },
    { title: "+ via students & staff", field: "with_students", hozAlign: "right", formatter: (c) => fmtAuto(c.getValue()) },
    { title: "+ short-tenure only", field: "with_short_tenure_only", hozAlign: "right", formatter: (c) => fmtAuto(c.getValue()) }], { layout: "fitColumns", maxHeight: 320 });
  const gp = R3.glue_people || [];
  plot("c-st-glue", [{ type: "bar", orientation: "h", y: gp.slice(0, 12).map((r) => `${r.name} (${short(r.lab)})`).reverse(), x: gp.slice(0, 12).map((r) => r.n_pairs).reverse(),
    marker: { color: gp.slice(0, 12).map((r) => labColor(r.lab)).reverse() }, customdata: gp.slice(0, 12).map((r) => [r.n_faculty, r.n_papers, r.n_cross_lab_pairs]).reverse(),
    hovertemplate: "%{y}<br>bridges %{x} faculty pairs (%{customdata[2]} cross-lab)<br>%{customdata[0]} faculty, %{customdata[1]} papers<extra></extra>" }],
    { xaxis: { title: "Unlinked faculty pairs this person bridges" }, yaxis: { automargin: true, tickfont: { size: 12 } }, showlegend: false, margin: { l: 10, r: 10, t: 10, b: 50 } });
  table("t-st-comm", R3.community_validation || [], [{ title: "Comparison", field: "comparison", formatter: "textarea", widthGrow: 3 }, { title: "NMI", field: "nmi", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
    { title: "ARI", field: "ari", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) }, { title: "AMI", field: "ami", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) },
    { title: "Shuffled NMI", field: "null_nmi_mean", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 2) }, { title: "z", field: "z", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 0) }], { layout: "fitColumns" });
  const kc = (R3.kcore || []).find((r) => r.is_main_core === true || r.is_main_core === "True") || {};
  el("st-kcore").textContent = kc.k ? `Main core (k = ${kc.k}): ${kc.n_nodes} faculty — ${LABS.map((l) => `${short(l)} ${kc[l] || 0}`).join(", ")}. The densest part of the network is a single lab.` : "";
  const g = R3.growth || [];
  plot("c-st-grow", [{ type: "scatter", mode: "lines+markers+text", x: g.map((r) => r.N), y: g.map((r) => r.E), text: g.map((r) => r.year), textposition: "top left", textfont: { size: 11, color: css("--muted") },
    line: { color: css("--lab-1"), width: 2.5 }, marker: { size: 8 }, hovertemplate: "%{text}: %{x} faculty, %{y} links<extra></extra>" }],
    { xaxis: { type: "log", title: "Connected faculty (cumulative)" }, yaxis: { type: "log", title: "Links (cumulative)" }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 50 },
      annotations: g.length ? [{ xref: "paper", yref: "paper", x: 0.02, y: 0.98, showarrow: false, align: "left", font: { size: 13, color: css("--ink-2") }, text: `E ∝ N<sup>${fmt(g[0].alpha_fit, 2)}</sup>` }] : [] });
  const pa = (R3.pref_attach || []).filter((r) => r.k > 0 && r.n_nodes >= 5);
  plot("c-st-pa", [{ type: "scatter", mode: "markers", x: pa.map((r) => r.k), y: pa.map((r) => r.rate), marker: { size: pa.map((r) => 5 + Math.sqrt(r.n_nodes)), color: css("--lab-3") },
    customdata: pa.map((r) => r.n_nodes), hovertemplate: "%{x} links: %{y:.2f} new links a year (%{customdata} faculty-years)<extra></extra>" }],
    { xaxis: { type: "log", title: "Links at the end of the previous year" }, yaxis: { type: "log", title: "New links in the year" }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 50 },
      annotations: [{ xref: "paper", yref: "paper", x: 0.02, y: 0.98, showarrow: false, font: { size: 13, color: css("--ink-2") }, text: `kernel ∝ k<sup>${fmt(((S.growth || {}).pa_gamma ?? (S.growth || {}).gamma), 2)}</sup> (1 = linear)` }] });
  const pm = (R3.position_model || []).filter((r) => /per SD/.test(r.term));
  plot("c-st-pos", ["log_papers_2021_26", ...new Set(pm.map((r) => r.outcome))].filter((v, i, a) => a.indexOf(v) === i).map((o, j) => { const rr = pm.filter((r) => r.outcome === o);
    return { type: "scatter", mode: "markers", name: o.includes("paper") ? "later papers" : "later normalised citations", y: rr.map((r) => r.term.replace(" (per SD)", "")), x: rr.map((r) => r.coef),
      error_x: { type: "data", symmetric: false, array: rr.map((r) => r.ci_hi - r.coef), arrayminus: rr.map((r) => r.coef - r.ci_lo), color: j ? css("--lab-3") : css("--lab-1") },
      marker: { size: 11, color: j ? css("--lab-3") : css("--lab-1") }, hovertemplate: "%{y}: %{x:+.2f} per SD<extra></extra>" }; }),
    { xaxis: { title: "Effect per standard deviation", zeroline: true, zerolinecolor: css("--muted") }, yaxis: { automargin: true }, margin: { l: 10, r: 10, t: 40, b: 50 } });
  const lp = (R3.link_prediction || []).slice().sort((a, b) => a.auc - b.auc);
  plot("c-st-lp", [{ type: "bar", orientation: "h", y: lp.map((r) => r.method.replace(/,? fit .*$/, "").replace("logistic (same lab + topic + log AA)", "logistic: lab + topic + Adamic-Adar")), x: lp.map((r) => r.auc),
    error_x: { type: "data", symmetric: false, array: lp.map((r) => r.auc_hi - r.auc), arrayminus: lp.map((r) => r.auc - r.auc_lo), color: css("--ink-2") },
    marker: { color: lp.map((r, i) => i === lp.length - 1 ? css("--lab-2") : css("--lab-4")) }, customdata: lp.map((r) => r.precision_at_50),
    hovertemplate: "%{y}: AUC %{x:.2f}<br>precision@50 %{customdata:.0%}<extra></extra>" }],
    { xaxis: { range: [0.4, 1], title: "AUC (0.5 = chance)" }, yaxis: { automargin: true }, showlegend: false, margin: { l: 10, r: 10, t: 10, b: 50 },
      shapes: [{ type: "line", x0: 0.5, x1: 0.5, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: css("--muted") } }] });
  table("t-st-frag", (R3.crosslab_fragility || []).map((r) => Object.assign({}, r)), [{ title: "Labs", field: "lab_pair", minWidth: 150 }, { title: "Cross links", field: "cross_links", hozAlign: "right" },
    { title: "On one paper only", field: "single_paper_share", hozAlign: "right", formatter: (c) => pct(c.getValue(), 0) },
    { title: "Left without top 10 papers", field: "links_left_without_top10_papers", hozAlign: "right" }, { title: "Min. node cut", field: "min_node_cut", hozAlign: "right", formatter: (c) => fmt(c.getValue()) }],
    { layout: "fitColumns", maxHeight: 320 });
  table("t-st-fragp", R3.crosslab_papers || [], [{ title: "Paper that links labs", field: "title", formatter: "textarea", widthGrow: 4 }, { title: "Year", field: "year" },
    { title: "Labs", field: "labs", widthGrow: 2 }, { title: "Cross-lab pairs", field: "cross_lab_pairs", hozAlign: "right" }, { title: "Only via this paper", field: "pairs_only_on_this_paper", hozAlign: "right" }],
    { layout: "fitColumns", maxHeight: 320 });
  const ct = R3.contagion || [];
  plot("c-st-cont", [{ type: "bar", orientation: "h", y: ct.map((r) => r.exposure.replace(/ \(.*\)/, "")), x: ct.map((r) => r.rr),
    error_x: { type: "data", symmetric: false, array: ct.map((r) => r.rr_hi - r.rr), arrayminus: ct.map((r) => r.rr - r.rr_lo), color: css("--ink-2") },
    marker: { color: ct.map((r) => /placebo/.test(r.exposure) ? css("--axis") : css("--lab-1")) }, hovertemplate: "%{y}: %{x:.1f}× more likely<extra></extra>" }],
    { xaxis: { title: "Relative risk of starting a new subfield" }, yaxis: { automargin: true, autorange: "reversed" }, showlegend: false, margin: { l: 10, r: 10, t: 10, b: 50 } });
  const tw = table("t-st-twins", (R3.twins || []).map((r) => Object.assign({}, r, { a_lab: short(r.a_lab), b_lab: short(r.b_lab) })), [
    { title: "Person A", field: "a_name", minWidth: 150 }, { title: "Lab", field: "a_lab" }, { title: "Person B", field: "b_name", minWidth: 150 }, { title: "Lab", field: "b_lab" },
    { title: "Similarity", field: "cosine", hozAlign: "right", formatter: (c) => fmt(c.getValue(), 3) }, { title: "Shared subfields", field: "shared_subfields", widthGrow: 2 }],
    { layout: "fitColumns", maxHeight: 420 });
  if (tw) tw.on("rowClick", (e, row) => { state.cmp = [row.getData().a_id, row.getData().b_id]; el("vs-kind").value = "people"; delete rendered.versus; show("versus"); });
  table("t-st-main", R3.main_path || [], [{ title: "#", field: "order", width: 50 }, { title: "Paper", field: "title", formatter: "textarea", widthGrow: 4 }, { title: "Year", field: "year" },
    { title: "Lab", field: "labs" }, { title: "Citations", field: "cited_by_count", hozAlign: "right" }], { layout: "fitColumns", maxHeight: 420 });
  const en = (R3.entropy || []).filter((r) => r.year < D.meta.partial_year);
  plot("c-st-ent", LABS.map((l) => { const rr = en.filter((r) => r.lab === l); return { type: "scatter", mode: "lines+markers", name: short(l), x: rr.map((r) => r.year), y: rr.map((r) => r.entropy_rarefied_n50),
    line: { color: labColor(l), width: 2.5 }, customdata: rr.map((r) => [r.top_subfield, r.effective_subfields]), hovertemplate: `${short(l)} %{x}: %{y:.2f} bits<br>top: %{customdata[0]}<extra></extra>` }; }),
    { yaxis: { title: "Subfield entropy (bits, 50-paper samples)", rangemode: "normal" }, margin: { l: 60, r: 10, t: 40, b: 40 } });
}
const fmtAuto = (v) => v === null || v === undefined ? "–" : Math.abs(v) < 1 && v !== 0 ? (v < 0.2 ? v.toFixed(3) : pct(v, 1)) : fmt(v, Number.isInteger(v) ? 0 : 1);
DYREG.structure = renderStructure;

function DYWIRE() {
  const upd = () => simReset();
  ["sim-b", "sim-m"].forEach((id) => el(id).addEventListener("input", upd));
  ["sim-model", "sim-seed", "sim-rng"].forEach((id) => el(id).addEventListener("change", upd));
  el("sim-reset").addEventListener("click", simReset);
  el("sim-step").addEventListener("click", () => { if (SIM.cy) simStep(); });
  el("sim-run").addEventListener("click", () => {
    if (!SIM.cy) return;
    if (SIM.timer) { clearInterval(SIM.timer); SIM.timer = null; el("sim-run").textContent = "▶ Run"; return; }
    if (!SIM.st.includes(1)) simReset();
    el("sim-run").textContent = "❚❚ Pause"; SIM.timer = setInterval(simStep, 140);
  });
  el("sim-many").addEventListener("click", () => { if (SIM.cy) simMany(); });
  el("ep-x").addEventListener("change", renderEpidemics);
}
