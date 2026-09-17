/* Mirror: company weather radar. Vanilla JS, no build step. */
(() => {
  const COND = {
    sunny:  { label: "Sunny",  color: "var(--sunny)",  desc: "growing and funded" },
    front:  { label: "Front",  color: "var(--front)",  desc: "something just changed" },
    cloudy: { label: "Cloudy", color: "var(--cloudy)", desc: "flat" },
    storm:  { label: "Storm",  color: "var(--storm)",  desc: "cooling and cutting" },
    fog:    { label: "Fog",    color: "var(--fog)",    desc: "no footprint" },
  };
  const SVG = "http://www.w3.org/2000/svg";
  const $ = (s, el = document) => el.querySelector(s);
  const el = (tag, attrs = {}, ns = false) => {
    const e = ns ? document.createElementNS(SVG, tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "text") e.textContent = v; else if (k === "html") e.innerHTML = v; else e.setAttribute(k, v);
    }
    return e;
  };

  const state = { data: null, month: 11, filters: new Set(Object.keys(COND)), query: "", selected: null, nodes: new Map(), playing: null, positions: [] };

  // ---------- layout ----------
  const CX = 500, CY = 500, R_MIN = 110, R_MAX = 415;
  function hash(s) { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; }

  function layout(month) {
    const cs = state.data.companies;
    const sectors = [...new Set(cs.map(c => c.sector))].sort();
    const arc = (2 * Math.PI) / sectors.length;
    const pos = cs.map((c, i) => {
      const s = c.snapshots[month];
      const si = sectors.indexOf(c.sector);
      const risk = (1 - s.momentum) / 2;             // 0 calm .. 1 severe
      const r = R_MIN + (R_MAX - R_MIN) * Math.pow(risk, 0.9);
      const jitter = (hash(c.id) - 0.5) * arc * 0.8;
      const a = -Math.PI / 2 + si * arc + arc / 2 + jitter;
      return { c, i, x: CX + r * Math.cos(a), y: CY + r * Math.sin(a), r, a, cond: s.condition };
    });
    // relax collisions, keeping radius (risk) honest and nudging along the arc
    for (let it = 0; it < 40; it++) {
      for (let i = 0; i < pos.length; i++) for (let j = i + 1; j < pos.length; j++) {
        const p = pos[i], q = pos[j];
        const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, min = 44;
        if (d < min) {
          const push = (min - d) / 2;
          const ax = Math.atan2(p.y - CY, p.x - CX), aq = Math.atan2(q.y - CY, q.x - CX);
          p.x = CX + p.r * Math.cos(ax - push / p.r); p.y = CY + p.r * Math.sin(ax - push / p.r);
          q.x = CX + q.r * Math.cos(aq + push / q.r); q.y = CY + q.r * Math.sin(aq + push / q.r);
        }
      }
    }
    return { pos, sectors, arc };
  }

  // ---------- radar chrome ----------
  function drawChrome(svg, sectors, arc) {
    const defs = el("defs", {}, true);
    defs.innerHTML = `<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#1a2a55" stop-opacity=".9"/><stop offset="100%" stop-color="#0b1020" stop-opacity="0"/></radialGradient>
      <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#38d8f0" stop-opacity="0"/><stop offset="1" stop-color="#38d8f0" stop-opacity=".25"/></linearGradient>`;
    svg.appendChild(defs);
    svg.appendChild(el("circle", { cx: CX, cy: CY, r: R_MAX + 40, fill: "url(#glow)" }, true));
    // sweep wedge
    const sw = el("path", { class: "sweep", d: `M${CX},${CY} L${CX + R_MAX + 30},${CY} A${R_MAX + 30},${R_MAX + 30} 0 0,0 ${CX + (R_MAX + 30) * Math.cos(-0.5)},${CY + (R_MAX + 30) * Math.sin(-0.5)} Z` }, true);
    svg.appendChild(sw);
    [[R_MIN + 60, "calm"], [(R_MIN + R_MAX) / 2 + 20, "unsettled"], [R_MAX + 30, "severe"]].forEach(([r, lab], i) => {
      svg.appendChild(el("circle", { class: "ring" + (i === 2 ? " outer" : ""), cx: CX, cy: CY, r }, true));
      svg.appendChild(el("text", { class: "ringlabel", x: CX + 6, y: CY - r + 14, text: lab }, true));
    });
    sectors.forEach((s, i) => {
      const a = -Math.PI / 2 + i * arc;
      svg.appendChild(el("line", { class: "spoke", x1: CX, y1: CY, x2: CX + (R_MAX + 30) * Math.cos(a), y2: CY + (R_MAX + 30) * Math.sin(a) }, true));
      const am = a + arc / 2, rl = R_MAX + 62;
      svg.appendChild(el("text", { class: "sectorlabel", x: CX + rl * Math.cos(am), y: CY + rl * Math.sin(am) + 4, text: s }, true));
    });
  }

  function glyph(cond) {
    const g = el("g", { class: "glyph " + cond }, true);
    if (cond === "sunny") {
      for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; g.appendChild(el("line", { class: "rays", x1: 13 * Math.cos(a), y1: 13 * Math.sin(a), x2: 18 * Math.cos(a), y2: 18 * Math.sin(a) }, true)); }
      g.appendChild(el("circle", { class: "sun", r: 9 }, true));
    } else if (cond === "front") {
      g.appendChild(el("path", { class: "frontg", d: "M-12,-10 L8,0 L-12,10 L-6,0 Z" }, true));
      g.appendChild(el("path", { class: "frontg", d: "M2,-10 L18,0 L2,10 L8,0 Z", opacity: ".55" }, true));
    } else if (cond === "fog") {
      g.appendChild(el("circle", { class: "fogc", r: 10 }, true));
      g.appendChild(el("circle", { class: "fogc", r: 5, opacity: ".5" }, true));
    } else {
      g.appendChild(el("path", { class: "cloud", d: "M-14,6 a7,7 0 0 1 3,-13 a9,9 0 0 1 17,-2 a7,7 0 0 1 8,11 a5,5 0 0 1 -2,4 Z" }, true));
      if (cond === "storm") g.appendChild(el("path", { class: "bolt", d: "M0,4 L-5,14 L1,12 L-2,22 L7,9 L1,11 L4,4 Z" }, true));
    }
    return g;
  }

  function render() {
    const svg = $("#radar");
    svg.innerHTML = "";
    state.nodes.clear();
    const { pos, sectors, arc } = layout(state.month);
    state.positions = pos;
    drawChrome(svg, sectors, arc);
    const layer = el("g", { id: "nodes" }, true);
    svg.appendChild(layer);
    for (const p of pos) {
      const n = el("g", { class: "node", "data-id": p.c.id, tabindex: 0, role: "button" }, true);
      n.style.transform = `translate(${p.x}px, ${p.y}px)`;
      n.appendChild(el("circle", { class: "halo", r: 24 }, true));
      n.appendChild(glyph(p.cond));
      n.appendChild(el("text", { class: "label", y: 30, text: p.c.name }, true));
      n.appendChild(el("title", { text: `${p.c.name}: ${COND[p.cond].label}, ${COND[p.cond].desc}` }, true));
      n.addEventListener("click", () => select(p.c.id));
      n.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.c.id); } });
      layer.appendChild(n);
      state.nodes.set(p.c.id, n);
    }
    applyFilters();
    if (state.selected) { state.nodes.get(state.selected)?.classList.add("sel"); renderPanel(state.selected); }
  }

  function update() {
    // move and re-glyph without rebuilding the chrome
    const { pos } = layout(state.month);
    for (const p of pos) {
      const n = state.nodes.get(p.c.id);
      if (!n) continue;
      n.style.transform = `translate(${p.x}px, ${p.y}px)`;
      const old = n.querySelector(".glyph");
      if (!old.classList.contains(p.cond)) n.replaceChild(glyph(p.cond), old);
      n.querySelector("title").textContent = `${p.c.name}: ${COND[p.cond].label}, ${COND[p.cond].desc}`;
    }
    applyFilters();
    if (state.selected) renderPanel(state.selected);
    $("#monthLabel").textContent = fmtMonth(state.data.meta.months[state.month]);
    renderLegend();
  }

  function applyFilters() {
    const q = state.query.trim().toLowerCase();
    for (const c of state.data.companies) {
      const n = state.nodes.get(c.id);
      const cond = c.snapshots[state.month].condition;
      const hit = (!q || c.name.toLowerCase().includes(q) || c.domain.includes(q)) && state.filters.has(cond);
      n.classList.toggle("dim", !hit);
    }
  }

  // ---------- legend, meter ----------
  function renderLegend() {
    const lg = $("#legend");
    lg.innerHTML = "";
    const counts = {};
    for (const c of state.data.companies) { const k = c.snapshots[state.month].condition; counts[k] = (counts[k] || 0) + 1; }
    for (const [k, v] of Object.entries(COND)) {
      const b = el("button", { class: state.filters.has(k) ? "on" : "", "aria-pressed": state.filters.has(k), title: v.desc });
      b.style.setProperty("--c", v.color);
      b.innerHTML = `<span class="dot"></span>${v.label} <span class="n">${counts[k] || 0}</span>`;
      b.addEventListener("click", () => { state.filters.has(k) ? state.filters.delete(k) : state.filters.add(k); if (!state.filters.size) Object.keys(COND).forEach(x => state.filters.add(x)); renderLegend(); applyFilters(); });
      lg.appendChild(b);
    }
  }
  function renderMeter() {
    const m = state.data.meta;
    $("#meter").innerHTML = `Glasser <b>$${Number(m.total_charge_usd).toFixed(2)}</b> · ${m.runs} runs`;
    $("#badge").hidden = !m.synthetic;
  }

  // ---------- panel ----------
  const fmt = {
    n: v => v == null ? "—" : v >= 1e9 ? (v / 1e9).toFixed(1) + "B" : v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "k" : String(Math.round(v)),
    usd: v => v == null ? "—" : "$" + fmt.n(v),
  };
  function fmtMonth(mk) { const [y, m] = mk.split("-"); return new Date(+y, +m - 1, 1).toLocaleString("en", { month: "short", year: "numeric" }); }

  function gauge(label, value, why, diverging) {
    const g = el("div", { class: "gauge" });
    const bar = el("div", { class: "bar" + (diverging ? " div" : "") });
    const i = el("i");
    if (value == null) { i.style.width = "0"; }
    else if (diverging) { const w = Math.abs(value) * 50; i.style.width = w + "%"; i.style.left = value >= 0 ? "50%" : (50 - w) + "%"; i.style.background = value >= 0 ? "var(--pos)" : "var(--neg)"; }
    else { i.style.left = "0"; i.style.width = (value * 100) + "%"; }
    bar.appendChild(i);
    g.appendChild(el("div", { class: "lab", text: label }));
    g.appendChild(bar);
    g.appendChild(el("div", { class: "why", text: why || (value == null ? "no data" : "") }));
    return g;
  }

  function renderPanel(id) {
    const c = state.data.companies.find(x => x.id === id);
    if (!c) return;
    const s = c.snapshots[state.month];
    const body = $("#panelBody");
    const prevTab = body.querySelector(".tabs .on")?.dataset.tab || "prosecution";
    body.innerHTML = "";
    body.appendChild($("#tplPanel").content.cloneNode(true));
    $("#panelEmpty").hidden = true; body.hidden = false;
    $(".name", body).textContent = c.name;
    $(".sector", body).textContent = c.sector; $(".city", body).textContent = c.city || "—"; $(".domain", body).textContent = c.domain;
    const chip = $(".chip", body); chip.textContent = COND[s.condition].label; chip.style.setProperty("--c", COND[s.condition].color);
    $(".forecast", body).textContent = state.month === 11 ? c.forecast : `${fmtMonth(s.month)}: ${COND[s.condition].label}, ${COND[s.condition].desc}. Momentum ${s.momentum >= 0 ? "+" : ""}${s.momentum.toFixed(2)}.`;
    const gs = $(".gauges", body);
    gs.appendChild(gauge("Temperature", s.temperature, s.temperature_why, true));
    gs.appendChild(gauge("Pressure", s.pressure, s.pressure_why, true));
    gs.appendChild(gauge("Precipitation", s.precipitation, s.precipitation_why, false));
    gs.appendChild(gauge("Wind", s.wind, s.wind_direction + (s.wind_events.length ? ": " + s.wind_events.slice(0, 2).join("; ") : ""), false));
    gs.appendChild(gauge("Visibility", s.visibility, s.visibility == null ? "no search data" : `domain rating ${c.signals.seo.domain_rating ?? "—"}, ${fmt.n(c.signals.seo.keywords)} keywords`, false));
    // sparkline
    const sp = $(".spark svg", body);
    sp.appendChild(el("line", { class: "zero", x1: 0, y1: 30, x2: 320, y2: 30 }, true));
    const pts = c.snapshots.map((ss, i) => [10 + i * (300 / 11), 30 - ss.momentum * 26]);
    sp.appendChild(el("polyline", { class: "line", points: pts.map(p => p.join(",")).join(" ") }, true));
    c.snapshots.forEach((ss, i) => { const d = el("circle", { class: "dotc", cx: pts[i][0], cy: pts[i][1], fill: COND[ss.condition].color, opacity: i === state.month ? 1 : .55 }, true); d.appendChild(el("title", { text: `${fmtMonth(ss.month)}: ${COND[ss.condition].label}` }, true)); sp.appendChild(d); });
    // glance
    const gl = $(".glance", body), g = c.glance;
    [["Visits / mo", fmt.n(g.monthly_visits)], ["Roles 90d", g.open_roles_90d ?? "—"], ["Headcount", g.headcount ?? "—"], ["Raised", fmt.usd(g.total_raised)], ["Last round", g.last_round ?? "—"], ["Domain rating", g.domain_rating == null ? "—" : Math.round(g.domain_rating)]]
      .forEach(([k, v]) => { const d = el("div"); d.appendChild(el("div", { class: "k", text: k })); d.appendChild(el("div", { class: "v", text: v })); gl.appendChild(d); });
    // tabs
    const claims = (list, sym) => list.map((cl, i) => {
      const d = el("div", { class: "claim" });
      d.appendChild(el("div", { class: "i", text: sym }));
      const t = el("div", { text: cl.text });
      const src = cl.source;
      t.appendChild(el("span", { class: "src", html: src ? `${src.signal} via ${src.provider}${src.run_url ? ` · <a href="${src.run_url}" target="_blank" rel="noopener">run</a>` : ""}` : "derived" }));
      d.appendChild(t); return d;
    });
    const pb = $('[data-body="prosecution"]', body); claims(c.argument.prosecution, "✕").forEach(x => pb.appendChild(x));
    const db = $('[data-body="defense"]', body); claims(c.argument.defense, "✓").forEach(x => db.appendChild(x));
    const sb = $('[data-body="sources"]', body);
    c.sources.forEach(src => { const r = el("div", { class: "srcrow" }); r.appendChild(el("div", { class: "s", text: src.signal })); r.appendChild(el("div", { text: `${src.provider} / ${src.endpoint} · ${src.status}` })); r.appendChild(el("div", { html: src.run_url ? `<a href="${src.run_url}" target="_blank" rel="noopener">$${src.charge}</a>` : `$${src.charge}` })); sb.appendChild(r); });
    $(".verdict", body).textContent = c.argument.verdict;
    $(".asof", body).textContent = fmtMonth(state.data.meta.asof.slice(0, 7));
    body.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(body, b.dataset.tab)));
    showTab(body, prevTab);
  }
  function showTab(body, name) {
    body.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === name));
    body.querySelectorAll(".tabbody").forEach(t => t.hidden = t.dataset.body !== name);
  }
  function select(id) {
    state.selected = id;
    state.nodes.forEach((n, k) => n.classList.toggle("sel", k === id));
    renderPanel(id);
    $("#panel").scrollTop = 0;
  }

  // ---------- search, live add ----------
  function toast(msg, ms = 4000) { const t = el("div", { class: "toast", text: msg }); document.body.appendChild(t); setTimeout(() => t.remove(), ms); }
  $("#search").addEventListener("input", e => { state.query = e.target.value; applyFilters(); });
  $("#searchForm").addEventListener("submit", async e => {
    e.preventDefault();
    const q = state.query.trim().toLowerCase();
    if (!q) return;
    const hit = state.data.companies.find(c => c.name.toLowerCase() === q || c.domain === q) || state.data.companies.find(c => c.name.toLowerCase().includes(q) || c.domain.includes(q));
    if (hit) { select(hit.id); return; }
    const domain = q.includes(".") ? q : q.replace(/\s+/g, "") + ".com";
    const btn = $("#addBtn"); btn.disabled = true; btn.textContent = "Fetching…";
    try {
      const r = await fetch("/api/company", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ domain }) });
      const j = await r.json();
      if (!r.ok || !j.company) throw new Error(j.error || "no result");
      await load(); state.query = ""; $("#search").value = ""; select(j.company.id);
      toast(`${j.company.name} added. Spend now $${Number(j.meta.total_charge_usd).toFixed(2)}.`);
    } catch (err) {
      toast(`Live add failed: ${err.message}. Run \`python -m mirror serve\` with resolved Glasser endpoints.`, 7000);
    } finally { btn.disabled = false; btn.textContent = "Add live"; }
  });

  // ---------- timeline ----------
  $("#time").addEventListener("input", e => { state.month = +e.target.value; update(); });
  $("#play").addEventListener("click", () => {
    if (state.playing) { clearInterval(state.playing); state.playing = null; $("#play").textContent = "▶"; return; }
    state.month = 0; $("#time").value = 0; update(); $("#play").textContent = "❚❚";
    state.playing = setInterval(() => { if (state.month >= 11) { clearInterval(state.playing); state.playing = null; $("#play").textContent = "▶"; return; } state.month++; $("#time").value = state.month; update(); }, 900);
  });

  // ---------- export ----------
  $("#exportBtn").addEventListener("click", () => {
    const m = state.data.meta, cs = state.data.companies, by = k => cs.filter(c => c.current.condition === k).sort((a, b) => Math.abs(b.current.momentum) - Math.abs(a.current.momentum));
    const L = [`# Weather briefing — ${m.asof}`, "", m.synthetic ? "_Synthetic demo data._\n" : "", `${cs.length} companies. Glasser spend $${m.total_charge_usd} across ${m.runs} runs.`, ""];
    for (const [title, k, n] of [["Fronts incoming (reach out now)", "front", 10], ["Storms (churn risk / poaching window)", "storm", 10], ["Sunny (buying, not cutting)", "sunny", 5]]) {
      const rows = by(k).slice(0, n); if (!rows.length) continue;
      L.push(`## ${title}`);
      for (const c of rows) {
        L.push(`- **${c.name}** (${c.sector}) — ${c.forecast}`);
        L.push(`  - ${c.current.temperature_why}; ${c.current.pressure_why}; ${c.current.precipitation_why}; wind ${c.current.wind_direction}.`);
        L.push(`  - Prosecution: ${c.argument.prosecution.map(x => x.text).join(" ")}`);
        L.push(`  - Defense: ${c.argument.defense.map(x => x.text).join(" ")}`);
        c.sources.filter(s => s.run_url).forEach(s => L.push(`  - source: ${s.signal} via ${s.provider} ${s.run_url}`));
      }
      L.push("");
    }
    const blob = new Blob([L.join("\n")], { type: "text/markdown" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `mirror-briefing-${m.asof}.md` }); document.body.appendChild(a); a.click(); a.remove();
  });

  // ---------- boot ----------
  async function load() {
    const r = await fetch("data.json?" + Date.now());
    state.data = await r.json();
    state.month = Math.min(state.month, state.data.meta.months.length - 1);
    $("#time").max = state.data.meta.months.length - 1;
    renderMeter(); renderLegend(); render();
    $("#monthLabel").textContent = fmtMonth(state.data.meta.months[state.month]);
  }
  load().catch(err => { $("#hint").textContent = "No data.json yet. Run: python -m mirror demo, then python -m mirror serve"; console.error(err); });
})();
