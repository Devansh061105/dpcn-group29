/* "Ask the data": a chatbot that answers only from this dashboard's own numbers. It runs in the browser with no
   external service: it recognises people, labs, peer institutes, metrics, thresholds and definitions, and otherwise
   searches every finding, verdict, method, team note and page description (BM25). Each answer links to its evidence. */
const CHAT = { kb: null, idf: null, avg: 0 };
const GLOSS = {
  "h-index": "The largest h such that h of a person's papers have at least h citations each. Here it is counted on 2016–2026 papers; the Explorer recomputes it for any filter.",
  "impact factor": "A journal's average citations per recent paper (Clarivate JCR 2024 here, with Scimago or OpenAlex fallbacks). It describes the journal, not any single paper in it.",
  "fwci": "Field-weighted citation impact: a paper's citations divided by the world average for papers of the same field, year and type. 1 = world average.",
  "mncs": "Mean normalised citation score: the mean of each paper's citations ÷ the average of papers of the same field and year in our corpus. 1 = average.",
  "sis": "Susceptible–Infected–Susceptible: an epidemic model where infected people recover but can be infected again, like an idea that must be kept alive. Above a threshold λ = β/μ it becomes endemic.",
  "sir": "Susceptible–Infected–Recovered: infected people recover for good, so an outbreak spreads once and dies out. Its final size measures how far something can travel.",
  "epidemic threshold": "The transmission-to-recovery ratio λ = β/μ above which an SIS process survives. Mean-field theory predicts ⟨k⟩/⟨k²⟩ or 1/Λmax of the adjacency matrix.",
  "random walk": "A walker that moves from person to person along co-authorship links at random. How long it takes to reach another lab measures how separate the labs are.",
  "mean first passage time": "The expected number of random-walk steps to first reach a target (here: any person of another lab).",
  "k-shell": "The core number of a node: the deepest k-core it belongs to. Kitsak et al. (2010) found it predicts spreading power better than degree.",
  "pagerank": "A centrality where a paper is important if important papers cite it. Without self-citations it no longer rewards groups citing their own work.",
  "gini": "An inequality index from 0 (everyone equal) to 1 (one person has everything).",
  "effective papers": "(Σc)² ÷ Σc²: the number of equally cited papers that would give the same spread of citations. Low = a few papers carry the total.",
  "z-score": "How many standard deviations an observed value is from the mean of a random baseline. Beyond about ±2 is unusual.",
  "q-value": "A p-value adjusted for testing many things at once (Benjamini–Hochberg). q < 0.05 is significant after the correction.",
  "odds ratio": "How many times higher the odds of an event are in one group than another. 1 = no difference.",
  "null model": "A randomised version of the data that keeps some features (e.g. everyone's number of co-authors) and scrambles the one being tested, giving the 'chance' baseline.",
  "fractional counting": "Each paper's credit divided equally among its authors, so a 300-author paper gives each author 1/300 of its citations.",
  "rca": "Revealed comparative advantage: an institute's share of papers in a subfield ÷ India's share. Above 1 = a specialisation.",
  "modularity": "How much more densely connected the communities are inside than chance predicts (Louvain finds communities that maximise it).",
  "nmi": "Normalised mutual information: agreement between two groupings, from 0 (unrelated) to 1 (identical).",
  "disparity filter": "Keeps only network links that carry an unusually large share of a node's weight, revealing the backbone (Serrano et al. 2009).",
  "triadic closure": "Two people with a co-author in common becoming co-authors themselves.",
  "lotka": "Lotka's law: the number of authors with n papers falls roughly as 1/n².",
  "bradford": "Bradford's law: journals sorted by output fall into zones of equal papers whose sizes grow as 1 : n : n².",
  "matthew effect": "Advantage compounds: those already successful keep getting more (Merton 1968).",
  "q1": "A journal in the top quarter of its Scimago subject category in the publication year.",
  "wilson interval": "A 95% confidence interval for a proportion that behaves well for small samples.",
  "bootstrap": "Resampling the data many times to see how much a number could vary: the source of most confidence intervals here.",
  "laplace": "A peaked, heavy-tailed distribution. Zhang et al. (P1) found yearly changes in scientists' output follow it.",
};
const LAB_ALIAS = Object.fromEntries(LABS.map((l) => [short(l).toLowerCase(), l]));
const METRIC_WORDS = [[/fraction/, "citations_frac"], [/lifetime/, "h_lifetime"], [/normali[sz]ed|mncs|fwci/, "mean_ncs"], [/h[\s-]?index|\bh\b/, "h"],
  [/impact factor|\bif\b/, "median_if"], [/citation|cited|cites/, "citations"], [/paper|publication|output|productiv/, "papers"],
  [/co-?author|connected|degree|collaborat/, "degree"], [/partner|institution/, "collab_inst"]];
const MNAME = { h: "h-index", citations: "citations", papers: "papers", median_if: "median journal impact factor", degree: "faculty co-authors", citations_frac: "fractional citations",
  mean_ncs: "mean normalised citations", h_lifetime: "lifetime h-index (OpenAlex)", collab_inst: "partner institutions", h_lt100: "h-index without 100+ author papers" };
const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9.%<>=+\- ]/g, " ");
const toks = (s) => norm(s).split(/\s+/).filter((w) => w.length > 1 && !STOP.has(w));
const STOP = new Set("the a an of in on to and or is are was were be by for with what which who whom how why does do did at as it its this that these those from than then there their our we you me my about tell show give find list any all can i".split(" "));

function chatKB() {
  if (CHAT.kb) return CHAT.kb;
  const kb = [], add = (text, tab, kind) => { if (text) kb.push({ text, tab, kind, t: toks(text) }); };
  (P3API.verdicts ? P3API.verdicts() : []).forEach((v) => add(`${v.q} Verdict: ${({ yes: "supported", no: "not supported", partly: "partly" })[v.v] || v.v}. ${v.num}. ${v.why || ""} (Test: ${v.test})`, v.tab, "verdict"));
  [["extras", "extras"], ["dynamics", "epidemics"], ["structure", "structure"], ["benchmark", "benchmark"]].forEach(([k, tab]) => {
    ((RJ[k] || {}).findings || []).forEach((s) => add(s, /walk|passage|spectral/i.test(s) ? "walks" : tab, "finding"));
    Object.entries((RJ[k] || {}).methods || {}).forEach(([m, s]) => add(`Method (${m}): ${s}`, tab, "method"));
    ((RJ[k] || {}).caveats || []).forEach((s) => add(`Caveat: ${s}`, tab, "caveat")); });
  const noteTab = { overview: "overview", research: "findings", faculty: "compare", networks: "instnet", hyperauthorship: "flags", citers: "flags" };
  Object.entries((D.p2 || {}).notes || {}).forEach(([k, s]) => { if (typeof s === "string" && s.length > 20) s.split(/\n+/).forEach((p) => add(`Team interpretation: ${p}`, noteTab[k] || "findings", "note")); });
  (SCI.items || []).forEach((it) => add(`${it.claim} Source: ${it.source}`, "science", "science"));
  (R3.laws || []).forEach((r) => add(`${r.law}: ${r.statement}. Expected ${r.expected}; our data: ${r.observed}.`, "extras", "law"));
  Object.entries(SECTX).forEach(([k, m]) => add(`The ${m[0]} page: ${m[1]}. ${m[2]}`, k, "page"));
  Object.entries(GLOSS).forEach(([k, s]) => add(`${k}: ${s}`, null, "glossary"));
  (D.summary || []).forEach((s) => add(`${s.scope === "ALL" ? "All four labs" : s.scope}: ${fmt(s.papers)} papers, ${fmt(s.citations)} citations, ${fmt(s.faculty_with_papers)} faculty with papers of ${fmt(s.roster_faculty)} on the roster, ${pct(s.q1_fraction, 0)} in Q1 journals, median ${fmt(s.median_citations)} citations per paper.`, "overview", "lab"));
  (R3.lab_credit || []).forEach((r) => add(`${r.scope}: normalised impact MNCS ${fmt(r.mncs, 2)} (${fmt(r.mncs_lo, 2)}–${fmt(r.mncs_hi, 2)}), top-10% share ${pct(r.top10_share, 1)}, effective papers ${fmt(r.effective_papers, 0)}, Gini across faculty ${fmt(r.gini_faculty_citations, 2)}.`, "findings", "lab"));
  (Array.isArray(R3.benchmark) ? R3.benchmark : []).forEach((r) => add(`${r.short} (${r.name}, ${r.city}): ${fmt(r.papers)} papers 2016–2026, mean FWCI ${fmt(r.mean_fwci, 2)} (rank ${r.rank_mean_fwci}), top-10% share ${pct(r.top10_share, 1)}, ${fmt(r.citations_per_paper, 1)} citations per paper, international ${pct(r.intl_share, 0)}, open access ${pct(r.oa_share, 0)}, growth ${pct(r.cagr, 1)} a year.`, "benchmark", "peer"));
  (R3.rca_india || []).filter((r) => r.rca > 1).sort((a, b) => b.rca - a.rca).slice(0, 80).forEach((r) => add(`${r.short} specialises in ${r.subfield}: RCA ${fmt(r.rca, 1)} against India (${fmt(r.papers)} papers).`, "benchmark", "peer"));
  (R3.twins || []).slice(0, 25).forEach((r) => add(`Collaboration opportunity: ${r.a_name} (${short(r.a_lab)}) and ${r.b_name} (${short(r.b_lab)}) work on similar topics (cosine ${fmt(r.cosine, 2)}) but have never written together.`, "structure", "twin"));
  const N = kb.length, df = {};
  kb.forEach((d) => new Set(d.t).forEach((w) => { df[w] = (df[w] || 0) + 1; }));
  CHAT.idf = Object.fromEntries(Object.entries(df).map(([w, n]) => [w, Math.log(1 + (N - n + 0.5) / (n + 0.5))]));
  CHAT.avg = kb.reduce((a, d) => a + d.t.length, 0) / Math.max(1, N);
  CHAT.kb = kb; return kb;
}
const SECTX = {};
function bm25(q) {
  const kb = chatKB(), qt = toks(q), k1 = 1.4, b = 0.7;
  return kb.map((d) => { const tf = {}; d.t.forEach((w) => { tf[w] = (tf[w] || 0) + 1; });
    let s = 0; qt.forEach((w) => { const f = tf[w] || (w.length > 4 ? Object.keys(tf).filter((x) => x.startsWith(w.slice(0, -1))).reduce((a, x) => a + tf[x], 0) * 0.6 : 0);
      if (f) s += (CHAT.idf[w] || 0.6) * f * (k1 + 1) / (f + k1 * (1 - b + b * d.t.length / CHAT.avg)); });
    return [s, d]; }).filter(([s]) => s > 0).sort((a, b2) => b2[0] - a[0]);
}
function findPeople(q) {
  if (!XF.length) return [];
  const n = ` ${norm(q)} `;
  const full = XF.filter((p) => n.includes(` ${norm(p.name)} `));
  if (full.length) return full;
  const words = toks(q).filter((w) => w.length > 3 && !LAB_ALIAS[w] && !/index|citation|paper|impact|factor|compare|versus|profile|faculty|between/.test(w));
  const hits = XF.filter((p) => { const parts = norm(p.name).split(/\s+/).filter((x) => x.length > 3); return words.some((w) => parts.includes(w)); });
  return hits.length <= 6 ? hits : [];
}
function findLabs(q) { const n = norm(q); return Object.entries(LAB_ALIAS).filter(([a]) => new RegExp(`\\b${a}\\b`).test(n)).map(([, l]) => l); }
function findPeers(q) {
  const B = Array.isArray(R3.benchmark) ? R3.benchmark : [], n = norm(q);
  return B.filter((r) => r.group !== "ours" && (new RegExp(`\\b${norm(r.short.replace("CSIR-", ""))}\\b`).test(n) || n.includes(norm(r.name))));
}
const metricOf = (q) => { const n = norm(q); if (/without|excluding|under 100|<\s*100|small team/.test(n) && /h[\s-]?index/.test(n)) return "h_lt100"; const m = METRIC_WORDS.find(([re]) => re.test(n)); return m ? m[1] : null; };
const pval = (p, k) => k === "mean_ncs" ? fmt(p[k] ?? p.mncs, 2) : k === "median_if" ? fmt(p[k], 1) : k === "citations_frac" ? fmt(p[k], 0) : fmt(p[k]);
function personAnswer(p, k) {
  const fc = (R3.faculty_credit || []).find((r) => r.faculty_id === p.id) || {};
  if (k) return `${p.name} (${short(p.lab)}): ${MNAME[k]} ${pval(p, k)}${k === "citations" && fc.rank_citations ? ` (rank ${fc.rank_citations} of ${XF.length}; ${fmt(fc.rank_citations_frac)} under fractional counting)` : ""}${k === "h" ? `; ${fmt(p.h_lt100)} without papers of 100+ authors` : ""}.`;
  return `${p.name} — ${[p.designation, p.dept, short(p.lab)].filter(Boolean).join(", ")}. ${fmt(p.papers)} papers (2016–2026), ${fmt(p.citations)} citations, h-index ${fmt(p.h)} (${fmt(p.h_lt100)} without 100+ author papers), lifetime h-index ${fmt(p.h_lifetime)}. ${pct(p.led_share, 0)} of papers lab-led; median journal IF ${fmt(p.median_if, 1)}; ${fmt(p.degree)} faculty co-authors; ${fmt(p.collab_inst)} partner institutions.${p.flag ? ` Flag: ${p.flag}.` : ""}`;
}
function labLine(l, k) {
  const a = labAgg(l), s = (D.summary || []).find((r) => r.scope === l) || {}, bm = (Array.isArray(R3.benchmark) ? R3.benchmark : []).find((r) => r.short === l) || {};
  const lc = (R3.lab_credit || []).find((r) => r.scope === l) || {};
  if (k && a[k] !== undefined) return `${short(l)}: ${MNAME[k] || k} ${["mean_ncs", "degree", "collab_inst", "median_if"].includes(k) ? fmt(a[k], 2) : fmt(a[k])}${["degree", "collab_inst"].includes(k) ? " (mean per faculty member)" : ""}.`;
  return `${short(l)} (${D.meta.lab_names[l]}): ${fmt(s.papers ?? a.papers)} papers, ${fmt(s.citations ?? a.citations)} citations, ${fmt(a.faculty)} faculty with papers, h-index of the lab ${fmt(a.h)}, MNCS ${fmt(lc.mncs, 2)}, ${pct(s.q1_fraction, 0)} in Q1.${bm.mean_fwci ? ` Whole-institute mean FWCI ${fmt(bm.mean_fwci, 2)}, rank ${bm.rank_mean_fwci} of 17 Indian biology institutes.` : ""}`;
}
function topList(q) {
  const n = norm(q), m = n.match(/\b(top|best|most|highest|leading|largest)\b\s*(\d+)?/); if (!m) return null;
  const k = metricOf(q) || "citations", N = Math.min(20, +(m[2] || (n.match(/\b(\d+)\b/) || [])[1]) || 10), labs = findLabs(q);
  if (/spread/.test(n) && R3.epi_spreaders) return { text: `Top ${N} spreaders (SIR outbreak size when they are the first case): ` + R3.epi_spreaders.slice().sort((a, b) => a.rank_influence - b.rank_influence).filter((r) => !labs.length || labs.includes(r.lab)).slice(0, N).map((r, i) => `${i + 1}. ${r.name} (${short(r.lab)}, ${fmt(r.sir_size_mean, 1)})`).join("; "), tab: "epidemics" };
  const pool = XF.filter((p) => !labs.length || labs.includes(p.lab)).filter((p) => k !== "mean_ncs" || p.papers >= 10);
  const s = pool.slice().sort((a, b) => (b[k] ?? -1) - (a[k] ?? -1)).slice(0, N);
  return { text: `Top ${N} faculty${labs.length ? ` in ${labs.map(short).join(", ")}` : ""} by ${MNAME[k] || k}${k === "mean_ncs" ? " (at least 10 papers)" : ""}: ` + s.map((p, i) => `${i + 1}. ${p.name} (${short(p.lab)}, ${pval(p, k)})`).join("; ") + ".", tab: "explorer", people: s.slice(0, 3) };
}
function thresholdQuery(q) {
  const n = norm(q).replace(/greater than|more than|above|over|exceeding/g, ">").replace(/less than|fewer than|below|under/g, "<");
  const h = n.match(/h[\s-]?index\s*(?:of\s*)?(>|>=|=)?\s*(\d+)/), iff = n.match(/(?:impact factor|\bif\b)\s*(>|>=)?\s*(\d+(?:\.\d+)?)/), au = n.match(/(\d+)\s*authors|authors\s*(<|<=)?\s*(\d+)/);
  const cit = n.match(/citations?\s*(>|>=)\s*(\d+)/);
  if (!h && !iff && !(au && (h || iff || cit)) && !cit) return null;
  const F = Object.assign({}, EXDEF, { na: 5000 });
  if (h) F.h = +h[2]; if (iff) F.if = +iff[2] + 0.0001; if (cit) F.c = +cit[2] + 1;
  if (au) F.na = +(au[1] || au[3]); else if (h || iff) F.na = /all papers|including/.test(n) ? 5000 : 100;
  return F;
}
function runFilters(F) {
  const save = state.lab, labs = []; void labs;
  const pass = XP.map((p) => paperPass(Object.assign({}, p), Object.assign({}, F, { t: "" })) );
  void save;
  const people = XF.map((pr) => { const mine = byPerson[pr.i].filter(([k]) => pass[k]).map(([k]) => XP[k]); return { p: pr, h: hIndex(mine.map((x) => x.c)), n: mine.length }; }).filter((x) => x.n && x.h > F.h);
  return { people: people.sort((a, b) => b.h - a.h), papers: pass.filter(Boolean).length };
}
function answer(q) {
  const n = norm(q).trim();
  if (!n) return null;
  if (/^(hi|hello|hey|help)\b/.test(n)) return { text: "Ask me about any scientist, lab, peer institute, finding or method. For example: “h-index of Thangaraj”, “compare CCMB and IGIB”, “top 5 by fractional citations in CDRI”, “faculty with h-index above 10 and fewer than 100 authors”, “what is SIS?”, “do lab walls slow spreading?”." };
  const def = n.match(/^(what is|what are|what's|define|meaning of|explain)\s+(an? |the )?(.+?)\??$/);
  if (def) { const key = Object.keys(GLOSS).find((g) => def[3].includes(g) || g.includes(def[3].trim())); if (key) return { text: `${key}: ${GLOSS[key]}` }; }
  if (/who cites|citing institution|citers?\b|cite (us|the labs|our)/.test(n)) {
    const C = (R3.citers_collab || []).slice().sort((a, b) => b.cites_in - a.cites_in).slice(0, 8);
    if (C.length) return { text: `Indian institutions citing the labs most (external citations, our own labs excluded): ${C.map((r, i) => `${i + 1}. ${r.partner_inst} (${fmt(r.cites_in)}; ${fmt(r.shared_papers)} joint papers)`).join("; ")}. Big institutions cite more simply because they publish more; the Flags tab divides by each institution's output.`, tab: "flags" };
  }
  const F = thresholdQuery(q);
  if (F && X) { const r = runFilters(F);
    const cond = [`fewer than ${F.na} authors`, F.if > 0 ? `journal impact factor above ${Math.floor(F.if)}` : null, F.c > 0 ? `at least ${F.c} citations` : null].filter(Boolean).join(", ");
    if (F.h > 0) return { text: `${fmt(r.people.length)} faculty have an h-index above ${F.h} counting only papers with ${cond}${state.lab !== "ALL" ? ` (${short(state.lab)} only)` : ""}. Highest: ${r.people.slice(0, 8).map((x) => `${x.p.name} (${short(x.p.lab)}, h ${x.h})`).join("; ")}.`, tab: "explorer", filters: F };
    const top = XP.filter((p) => paperPass(p, Object.assign({}, F, { t: "" }))).sort((a, b) => b.c - a.c).slice(0, 5);
    return { text: `${fmt(r.papers)} papers have ${cond}${state.lab !== "ALL" ? ` (${short(state.lab)} only)` : ""}, by ${fmt(r.people.length)} faculty. Most cited: ${top.map((p) => `“${p.title.slice(0, 80)}” (${p.year}, ${fmt(p.c)} citations, IF ${fmt(p.if, 1)})`).join("; ")}.`, tab: "explorer", filters: F }; }
  const ppl = findPeople(q), labs = findLabs(q), peers = findPeers(q), k = metricOf(q);
  const cmp = /compare|versus|\bvs\b|against|difference between/.test(n);
  if (cmp && ppl.length >= 2) return { text: ppl.slice(0, 4).map((p) => personAnswer(p, k)).join(" "), tab: "versus", compare: ppl.slice(0, 6).map((p) => p.id) };
  if (ppl.length === 1) return { text: personAnswer(ppl[0], k), person: ppl[0].id };
  if (ppl.length > 1 && ppl.length <= 6 && !labs.length) return { text: `Several people match: ${ppl.map((p) => `${p.name} (${short(p.lab)})`).join(", ")}. Add a first name or initials.`, people: ppl.slice(0, 4) };
  const tl = topList(q); if (tl) return tl;
  if (labs.length || peers.length) {
    const lines = labs.map((l) => labLine(l, cmp ? null : k)).concat(peers.map((r) => `${r.short} (${r.name}): ${fmt(r.papers)} papers, mean FWCI ${fmt(r.mean_fwci, 2)} (rank ${r.rank_mean_fwci} of 17), top-10% share ${pct(r.top10_share, 1)}, international ${pct(r.intl_share, 0)}, open access ${pct(r.oa_share, 0)}.`));
    if (!/spread|walk|cite|citing|collab|wall|threshold|why|how|does|did|is |are /.test(n) || cmp) return { text: lines.join(" "), tab: peers.length ? "benchmark" : cmp ? "versus" : "overview", labs: !!labs.length && cmp };
  }
  const hits = bm25(q);
  if (!hits.length || hits[0][0] < 1.2) return { text: "I couldn't find that in the dashboard's data. Try a name, a lab (CCMB, IGIB, IMTECH, CDRI), a peer institute (NCBS, NII, IICB…), a measure (h-index, citations, impact factor, FWCI) or a topic (self-citation, lab walls, COVID-19, epidemic threshold, random walk, journals)." };
  const top = hits.slice(0, 3).filter(([s]) => s >= hits[0][0] * 0.55).map(([, d]) => d);
  return { text: top.map((d) => d.text).join("\n\n"), tab: top[0].tab, more: top.slice(1).map((d) => d.tab).filter(Boolean) };
}
function chatSay(who, text, a) {
  const log = el("chat-log"), m = mk("div", null, `msg ${who}`);
  text.split("\n\n").forEach((p) => m.append(mk("p", p)));
  if (a) {
    const acts = mk("div", null, "msg-acts");
    const btn = (label, fn) => { const b = mk("button", label, "chip-btn"); b.type = "button"; b.addEventListener("click", fn); acts.append(b); };
    if (a.person) { btn("Open profile", () => P3API.openPerson(a.person)); btn("Add to compare", () => P3API.addCompare(a.person)); }
    (a.people || []).forEach((p) => btn(p.name, () => P3API.openPerson(p.id)));
    if (a.compare) btn("Compare them", () => { state.cmp = a.compare; el("vs-kind").value = "people"; delete rendered.versus; show("versus"); });
    if (a.labs) btn("Compare the labs", () => { el("vs-kind").value = "labs"; delete rendered.versus; show("versus"); });
    if (a.filters) btn("Open in Filter & find", () => { exSet(a.filters); document.querySelectorAll("#ex-presets .preset").forEach((x) => x.classList.remove("on")); delete rendered.explorer; show("explorer"); });
    if (a.tab && !a.filters) btn(`Go to ${(SECTX[a.tab] || [a.tab])[0]} →`, () => { show(a.tab); window.scrollTo(0, 0); });
    if (acts.childNodes.length) m.append(acts);
  }
  log.append(m); log.scrollTop = log.scrollHeight;
}
function CHATWIRE() {
  Object.assign(SECTX, SECT);
  const open = el("chat-open"), box = el("chat"), sugg = el("chat-sugg");
  const toggle = (v) => { box.hidden = !v; open.classList.toggle("on", v); if (v) { el("chat-in").focus(); if (!el("chat-log").childNodes.length) chatSay("bot", "Hello! I answer from this dashboard's numbers only. Ask about any scientist, lab, peer institute, finding or method."); } };
  open.addEventListener("click", () => toggle(box.hidden));
  el("chat-close").addEventListener("click", () => toggle(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !box.hidden) toggle(false); });
  ["h-index of Thangaraj", "compare CCMB and IGIB", "faculty with h-index above 10 and fewer than 100 authors", "top 5 spreaders", "what is SIS?", "do lab walls slow spreading?", "how does NCBS compare?", "did the labs move to weaker journals?"]
    .forEach((s) => { const b = mk("button", s, "chip-btn"); b.type = "button"; b.addEventListener("click", () => { el("chat-in").value = s; el("chat-form").requestSubmit(); }); sugg.append(b); });
  el("chat-form").addEventListener("submit", (e) => {
    e.preventDefault(); const q = el("chat-in").value.trim(); if (!q) return;
    chatSay("me", q); el("chat-in").value = "";
    let a; try { a = answer(q); } catch (err) { a = { text: "Something went wrong answering that; try rephrasing." }; console.error(err); }
    if (a) chatSay("bot", a.text, a);
  });
}
