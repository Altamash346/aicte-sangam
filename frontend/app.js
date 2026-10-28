"use strict";
const $ = (s, e = document) => e.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const S = { me: null, meta: null, lang: localStorage.lang || "en", theme: localStorage.theme || "light" };
const T = {
  en: { dashboard: "Dashboard", cases: "Cases", overlaps: "Overlap Centre", institutions: "Institutions", register: "Register Complaint", import: "Bulk Ingestion", audit: "Audit Trail",
    search: "Search", total: "Total received", Pending: "Pending", "Under Process": "Under process", Transferred: "Transferred", Escalated: "Escalated", Disposed: "Disposed",
    overdue: "Beyond timeline", due7: "Due in 7 days", banner: "Potential Overlapping Cases - Coordination Required", workload: "Bureau/Cell workload (active)", ageing: "Pending case ageing (days)",
    inflow: "Monthly inflow", topinst: "Institutions with most active cases", logout: "Sign out", alerts: "Alerts", reports: "Reports", impact: "Impact estimate", demo: "Guided demo", signin: "Sign in", acknowledge: "Acknowledge", notrel: "Not related", lead: "Make lead", conflicts: "Conflicting actions", track: "Track Grievance" },
  hi: { dashboard: "डैशबोर्ड", cases: "शिकायतें", overlaps: "ओवरलैप केंद्र", institutions: "संस्थान", register: "शिकायत दर्ज करें", import: "थोक प्रविष्टि", audit: "ऑडिट ट्रेल",
    search: "खोजें", total: "कुल प्राप्त", Pending: "लंबित", "Under Process": "प्रक्रियाधीन", Transferred: "स्थानांतरित", Escalated: "उच्चस्तर पर भेजी गई", Disposed: "निस्तारित",
    overdue: "समय-सीमा पार", due7: "7 दिन में देय", banner: "संभावित ओवरलैपिंग मामले - समन्वय आवश्यक", workload: "ब्यूरो/सेल कार्यभार (सक्रिय)", ageing: "लंबित मामलों की आयु (दिन)",
    inflow: "मासिक प्राप्ति", topinst: "सर्वाधिक सक्रिय मामलों वाले संस्थान", logout: "साइन आउट", alerts: "अलर्ट", reports: "रिपोर्ट", impact: "प्रभाव अनुमान", demo: "गाइडेड डेमो", signin: "साइन इन", acknowledge: "देखा", notrel: "संबंधित नहीं", lead: "प्रमुख बनाएं", conflicts: "परस्पर विरोधी कार्रवाइयाँ", track: "शिकायत ट्रैक करें" },
};
const t = k => (T[S.lang] && T[S.lang][k]) || T.en[k] || k;
const badge = s => `<span class="b s-${esc(String(s).replace(/\s/g, ""))}">${esc(t(s))}</span>`;
const sev = s => `<span class="b v-${esc(s)}">${esc(s)}</span>`;
const toast = m => { const d = document.createElement("div"); d.textContent = m; $("#toast").append(d); setTimeout(() => d.remove(), 3500); };
async function api(u, o = {}) {
  const r = await fetch("/api" + u, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, method: o.method || (o.body ? "POST" : "GET"), body: o.body ? JSON.stringify(o.body) : undefined });
  if (r.status === 401 && !u.startsWith("/auth/")) { S.me = null; loginView(); throw new Error("Session expired - please sign in again"); }  // never re-enter boot(): /auth/me is expected to 401 when logged out
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Request failed");
  return j;
}
const qs = o => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== "" && v != null && v !== false)).toString();
const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  cases: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  overlaps: '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/>',
  institutions: '<line x1="3" y1="21" x2="21" y2="21"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M5 6l7-3 7 3"/><line x1="4" y1="10" x2="4" y2="21"/><line x1="20" y1="10" x2="20" y2="21"/><line x1="8" y1="14" x2="8" y2="18"/><line x1="12" y1="14" x2="12" y2="18"/><line x1="16" y1="14" x2="16" y2="18"/>',
  register: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>',
  plus: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>',
  import: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  alerts: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  reports: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  audit: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  globe: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  play: '<polygon points="5 3 19 12 5 21 5 3"/>',
  sun: '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
  moon: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  shieldCheck: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
  shieldAlert: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  alert: '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  checkCircle: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3L2 6"/><path d="M22 6l-3-3"/><path d="M10 2h4"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  arrowsTransfer: '<path d="M16 3l4 4-4 4"/><path d="M20 7H4"/><path d="M8 21l-4-4 4-4"/><path d="M4 17h16"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  file: '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  printer: '<polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
  scale: '<path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h18"/>',
  mapPin: '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
  lightning: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  govSeal: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v18"/><path d="M3 12h18"/><path d="M5.6 5.6l12.8 12.8"/><path d="M18.4 5.6L5.6 18.4"/>',
  arrowLeft: '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  arrowRight: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>'
};

function icon(name, size = 16, cls = "") {
  const p = ICONS[name] || "";
  if (!p) return "";
  return `<svg class="ico ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
}

const NAV = [["dashboard", ""], ["cases", ""], ["overlaps", ""], ["institutions", ""], ["register", ""], ["import", ""], ["alerts", ""], ["reports", ""]];
const route = () => { const h = location.hash.slice(1) || "/dashboard"; const [p, q] = h.split("?"); return { parts: p.split("/").filter(Boolean), q: Object.fromEntries(new URLSearchParams(q || "")) }; };

function shell(inner) {
  const adm = S.me.role === "ADMIN", cur = route().parts[0];
  const nav = NAV.concat(adm ? [["audit", ""]] : []);
  const href = k => ({ dashboard: "dashboard", cases: "cases", overlaps: "overlaps", institutions: "institutions", register: "new", import: "import", alerts: "alerts", reports: "reports", audit: "audit", track: "track" }[k]);
  return `<div class="shell"><aside>
    <div class="brand">
      <div class="brand-title"><span class="brand-logo">${icon("govSeal", 20)}</span> AICTE Samvad <span class="badge">PRO</span></div>
      <small>Integrated Grievance Cockpit</small>
    </div>
    <nav>${nav.map(([k]) =>
      `<a href="#/${href(k)}" class="${cur === href(k) || (k === "cases" && cur === "case") ? "on" : ""}"><span class="nav-ico">${icon(k, 16)}</span><span class="nav-label">${esc(t(k))}</span></a>`).join("")}</nav>
  </aside>
  <div>
    <div class="top">
      <div class="live-pill" title="Deterministic Cross-Bureau Correlation Engine Active"><span class="live-dot"></span> LIVE ENGINE</div>
      <button class="search-btn" id="sbtn" title="Search cases, institutions, bureaus (Ctrl+K)">${icon("search", 14)} <span>${esc(t("search"))}</span> <kbd>Ctrl K</kbd></button>
      <span class="sp"></span>
      <a href="#/track" class="btn sm alt" style="text-decoration:none;display:inline-flex;align-items:center;gap:6px" title="Public Citizen Tracking">${icon("globe", 14)} <span>Citizen Portal</span></a>
      <button id="demo" class="btn sm" style="display:inline-flex;align-items:center;gap:6px">${icon("play", 13)} <span>Guided Demo</span></button>
      <button id="lang" class="btn sm alt" title="Language">${S.lang === "en" ? "हिं" : "EN"}</button>
      <button id="theme" class="btn sm alt" style="display:inline-flex;align-items:center;gap:6px" title="Theme">${icon(S.theme === "dark" ? "sun" : "moon", 14)} <span>${S.theme === "dark" ? "Light" : "Dark"}</span></button>
      <span class="mut" style="font-weight:600;font-size:13px">${esc(S.me.name)} <span class="b v-Info">${esc(S.me.role)}</span></span>
      <button id="out" class="btn sm alt" style="display:inline-flex;align-items:center;gap:6px">${icon("lock", 13)} <span>${esc(t("logout"))}</span></button>
    </div>
    <main id="view"></main>
  </div></div>`;
}
function bindShell() {
  $("#sbtn").onclick = openPal; $("#demo").onclick = () => startTour(); $("#lang").onclick = () => { S.lang = S.lang === "en" ? "hi" : "en"; localStorage.lang = S.lang; render(); };
  $("#theme").onclick = () => {
    S.theme = S.theme === "dark" ? "light" : "dark";
    localStorage.theme = S.theme;
    document.documentElement.dataset.theme = S.theme;
    $("#theme").innerHTML = `${icon(S.theme === "dark" ? "sun" : "moon", 14)} <span>${S.theme === "dark" ? "Light" : "Dark"}</span>`;
  };
  $("#out").onclick = async () => { try { await api("/auth/logout", { method: "POST", body: {} }); } catch (e) { } S.me = null; loginView(); };
}
async function render() {
  const r = route(), p = r.parts;
  if (p[0] === "track") {
    $("#app").innerHTML = shell(); bindShell();
    const v = $("#view");
    v.innerHTML = await vTrack(p[1]); (vTrack.after || (() => {}))();
    return;
  }
  $("#app").innerHTML = shell(); bindShell(); const v = $("#view");
  try {
    const fn = { dashboard: vDash, cases: vCases, case: vCase, overlaps: vOverlaps, institutions: vInsts, institution: vInst, new: vNew, import: vImport, track: vTrack, audit: vAudit, alerts: vAlerts, reports: vReports }[p[0] || "dashboard"] || vDash;
    v.innerHTML = '<p class="mut">Loading...</p>'; v.innerHTML = await fn(p[1], r.q); (fn.after || (() => { }))(p[1], r.q);
  } catch (e) { v.innerHTML = `<div class="card">[Alert] ${esc(e.message)}</div>`; }
}

/* ---------- dashboard ---------- */
const bars = (rows, max, cls = "") => rows.map(([n, v, c]) => `<div class="bar"><span>${esc(n)}</span><i class="${c || cls}" style="width:${Math.round(220 * v / (max || 1))}px"></i><b>${v}</b></div>`).join("");
async function vDash() {
  const [d, ov, cf, im] = await Promise.all([api("/dashboard"), api("/overlaps?min_severity=Medium"), api("/conflicts"), api("/impact")]);
  const k = (n, label, href, cls = "", ico = "cases") => `<a class="card kpi ${cls}" href="#/cases${href}">
    <div class="kpi-head">
      <span class="kpi-icon">${icon(ico, 17)}</span>
      <span class="b ${cls === 'red' ? 'red' : cls === 'amb' ? 'v-Medium' : 'v-Info'}">${esc(label)}</span>
    </div>
    <div class="kpi-body">
      <b>${n}</b>
      <span class="kpi-sub">Total cases</span>
    </div>
  </a>`;
  const s = d.by_status;
  const wl = Object.entries(d.bureau_workload), mx = Math.max(1, ...wl.map(([, v]) => v.active)), mo = d.monthly_inflow.slice(-8), mm = Math.max(1, ...mo.map(m => m.received));
  const pts = mo.map((m, i) => `${20 + i * (320 / Math.max(1, mo.length - 1))},${110 - 90 * m.received / mm}`).join(" ");
  return `<h1>${esc(t("dashboard"))}</h1>
  ${ov.length || cf.length ? `<a class="banner" href="#/overlaps"><span class="banner-ico">${icon("alert", 16)}</span> <b>[Alert]</b> ${esc(t("banner"))} - ${ov.length} ${S.lang === "en" ? "institutions with overlapping matters" : "संस्थान"}${cf.length ? `, ${cf.length} ${esc(t("conflicts")).toLowerCase()}` : ""} &rarr;</a>` : ""}
  <div class="card" id="impact">
    <div class="row" style="margin-bottom:12px">
      <h2 style="margin:0;display:flex;align-items:center;gap:8px">${icon("shieldCheck", 20)} Cross-Bureau Coordination & Duplicate Prevention Impact</h2>
      <span class="sp"></span>
      <span class="live-pill"><span class="live-dot"></span> LIVE AUDIT</span>
    </div>
    <div class="facts">
      <div><small>Multi-Bureau Institutions</small><b style="font-size:26px;color:var(--pri)">${im.institutions_with_overlap}</b></div>
      <div><small>Duplicate-Matter Pairs Caught</small><b style="font-size:26px;color:var(--saffron)">${im.cross_bureau_pairs}</b></div>
      <div><small>Contradictory Orders Intercepted</small><b style="font-size:26px;color:var(--red)">${im.conflicts_caught}</b></div>
      <div><small>Estimated Officer-Hours Saved</small><b style="font-size:26px;color:var(--grn)">~${im.est_hours_saved} hrs</b></div>
    </div>
    <p class="mut" style="margin:10px 0 0;font-size:12px">${esc(im.assumption)}</p>
  </div>
  <div class="grid g4">
    ${k(d.total, t("total"), "", "", "inbox")}
    ${k(s.Pending, t("Pending"), "?status=Pending", "", "clock")}
    ${k(s["Under Process"], t("Under Process"), "?status=Under Process", "", "activity")}
    ${k(s.Disposed, t("Disposed"), "?status=Disposed", "", "checkCircle")}
    ${k(s.Transferred, t("Transferred"), "?status=Transferred", "", "arrowsTransfer")}
    ${k(s.Escalated, t("Escalated"), "?status=Escalated", "", "shieldAlert")}
    ${k(d.overdue, t("overdue"), "?overdue=true", "red", "alert")}
    ${k(d.due_in_7_days, t("due7"), "", "amb", "timer")}
  </div>
  <div class="grid g2">
    <div class="card"><h2>${esc(t("workload"))}</h2>${bars(wl.map(([b, v]) => [b, v.active]), mx)}<p class="mut" style="margin-top:12px">${esc(S.meta.bureaus.RB)} · ${esc(S.meta.bureaus.PGRC)}</p></div>
    <div class="card"><h2>${esc(t("ageing"))}</h2>${bars(Object.entries(d.ageing).map(([k2, v]) => [k2, v, k2 === "60+" ? "r" : ""]), Math.max(1, ...Object.values(d.ageing)))}<p style="margin-top:12px">Overall Disposal Rate: <b style="color:var(--grn)">${d.disposal_rate}%</b></p></div>
    <div class="card"><h2>${esc(t("inflow"))}</h2><svg viewBox="0 0 360 130" width="100%"><polyline fill="none" stroke="var(--pri)" stroke-width="3" points="${pts}"/>${mo.map((m, i) => `<text x="${20 + i * (320 / Math.max(1, mo.length - 1))}" y="126" font-size="9" text-anchor="middle" fill="var(--mut)">${esc(m.month.slice(5))}</text>`).join("")}</svg></div>
    <div class="card"><h2>${esc(t("topinst"))}</h2>${bars(d.top_institutions.map(i => [i.name.slice(0, 22), i.active]), Math.max(1, ...d.top_institutions.map(i => i.active)))}</div>
  </div>`;
}

/* ---------- cases ---------- */
const sel = (id, label, opts, cur) => `<select id="${id}" aria-label="${esc(label)}"><option value="">${esc(label)}</option>${opts.map(o => `<option value="${esc(o[0])}" ${o[0] === cur ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
async function vCases(_, q) {
  const page = +q.page || 1, d = await api("/cases?" + qs({ ...q, size: 20, page })), m = S.meta;
  vCases.after = () => {
    const go = extra => location.hash = "#/cases?" + qs({ q: $("#fq").value, bureau: $("#fb").value, region: $("#fr").value, category: $("#fc").value, status: $("#fs").value, date_from: $("#fd").value, date_to: $("#ft").value, overdue: q.overdue, ...extra });
    $("#fa").onclick = () => go({ page: 1 }); $("#fq").onkeydown = e => e.key === "Enter" && go({ page: 1 }); $("#fx").onclick = () => location.hash = "#/cases";
    const pv = $("#pv"), nx = $("#nx"); if (pv) pv.onclick = () => go({ page: page - 1 }); if (nx) nx.onclick = () => go({ page: page + 1 });
  };
  return `<h1>${esc(t("cases"))} <span class="mut">(${d.total})</span></h1><div class="filters"><input id="fq" placeholder="Institution / AICTE ID / Case no." value="${esc(q.q || "")}">
  ${sel("fb", "Bureau/Cell", Object.entries(m.bureaus).map(([k, v]) => [k, k + " - " + v]), q.bureau)}${sel("fr", "Region", m.regions.map(r => [r, r]), q.region)}
  ${sel("fc", "Category", Object.entries(m.categories).map(([k, v]) => [k, v.label]), q.category)}${sel("fs", "Status", m.statuses.map(s => [s, t(s)]), q.status)}
  <input type="date" id="fd" value="${esc(q.date_from || "")}" title="From"><input type="date" id="ft" value="${esc(q.date_to || "")}" title="To">
  <button class="btn" id="fa">Apply</button><button id="fx">Reset</button>${q.overdue ? '<span class="b red">Overdue only</span>' : ""}</div>
  <div class="card tw"><table><thead><tr><th>Case no.</th><th>Institution</th><th>Category</th><th>Bureau/Cell</th><th>Officer</th><th>Status</th><th>Due</th></tr></thead><tbody>
  ${d.items.map(c => `<tr><td><a href="#/case/${c.id}">${esc(c.case_no)}</a>${c.sealed ? ` <span class="b red">${icon("lock", 11)} Sealed</span>` : ""}</td><td>${esc(c.institution ? c.institution.name : c.institution_ref + " (unresolved)")}</td><td>${esc(c.category_label)}</td><td>${esc(c.bureau)}</td><td>${esc(c.officer || "-")}</td><td>${badge(c.status)}</td>
  <td>${esc(c.due_on)} ${c.overdue ? '<span class="b red">Overdue</span>' : ""}</td></tr>`).join("") || '<tr><td colspan="7" class="mut">No cases match.</td></tr>'}</tbody></table>
  <div class="row" style="margin-top:10px">${page > 1 ? `<button id="pv">${icon("arrowLeft", 12)} Prev</button>` : ""}<span class="mut">Page ${page} / ${Math.max(1, Math.ceil(d.total / 20))}</span>${page * 20 < d.total ? `<button id="nx">Next ${icon("arrowRight", 12)}</button>` : ""}</div></div>`;
}

/* ---------- case detail ---------- */
async function vCase(id) {
  const [d, ov] = await Promise.all([api("/cases/" + id), api(`/cases/${id}/overlaps`)]), c = d.case, m = S.meta;
  vCase.after = () => {
    const f = $("#af"); if (!f) return; const upd = () => $("#to").parentElement.style.display = $("#act").value === "transfer" ? "" : "none"; $("#act").onchange = upd; upd();
    f.onsubmit = async e => {
      e.preventDefault();
      try {
        const fi = $("#afile") && $("#afile").files[0];
        let docName = "";
        if (fi) {
          const fd = new FormData();
          fd.append("file", fi);
          fd.append("remarks", $("#rem").value || `Attached: ${fi.name}`);
          const res = await fetch(`/api/cases/${id}/documents`, { method: "POST", body: fd });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Document upload failed");
          }
          const dj = await res.json();
          docName = dj.filename;
        }
        await api(`/cases/${id}/actions`, {
          body: {
            action: $("#act").value,
            kind: $("#kind").value,
            remarks: $("#rem").value,
            next_action: $("#nxt").value,
            to_bureau: $("#act").value === "transfer" ? $("#to").value : null,
            doc: docName
          }
        });
        toast("Action recorded" + (docName ? " with document" : ""));
        render();
      } catch (x) {
        toast(x.message);
      }
    };
  };
  const other = (p) => (p.id_a == id ? [p.case_b, p.id_b, p.bureau_b] : [p.case_a, p.id_a, p.bureau_a]);
  return `<p><a href="#/cases">${icon("arrowLeft", 12)} ${esc(t("cases"))}</a></p><div class="row"><h1 style="margin:0">${esc(c.case_no)}</h1>${badge(c.status)}${c.sealed ? `<span class="b red">${icon("lock", 12)} Sealed</span>` : ""}${c.overdue ? '<span class="b red">Overdue</span>' : ""}</div><br>
  ${ov.banner ? `<div class="banner"><span class="banner-ico">${icon("alert", 16)}</span> <b>[Alert]</b> ${esc(ov.banner)}<br><small>Also active at: ${esc(ov.bureaus_active.join(", "))}</small></div>` : ""}
  ${ov.conflicts.map(x => `<div class="banner"><span class="banner-ico">${icon("shieldAlert", 16)}</span> <b>[Conflict]</b> ${esc(x.message)}<br><small>${esc(x.case_a)} (${esc(x.bureau_a)}: ${esc(x.kind_a)}) vs ${esc(x.case_b)} (${esc(x.bureau_b)}: ${esc(x.kind_b)})</small></div>`).join("")}
  <div class="card"><div class="facts"><div><small>Institution</small>${c.institution ? `<a href="#/institution/${c.institution.id}">${esc(c.institution.name)}</a><br><span class="mut">${esc(c.institution.aicte_id)} · ${esc(c.institution.region)}</span>` : `${esc(c.institution_ref)} <span class="b v-Medium">unresolved</span>`}</div>
  <div><small>Category</small>${esc(c.category_label)}</div><div><small>Bureau/Cell</small><b>${esc(c.bureau)}</b></div><div><small>Officer</small>${esc(c.officer || "-")}</div><div><small>Received</small>${esc(c.received_on)}</div>
  <div><small>Expected disposal</small>${esc(c.due_on)} ${c.days_to_due != null ? `<span class="mut">(${c.days_to_due} d)</span>` : ""}</div><div><small>Last action</small>${esc(c.last_action)}<br><span class="mut">${esc(c.last_action_on)}</span></div><div><small>Next action</small>${esc(c.next_action)}</div></div>
  <p><b>${esc(c.subject)}</b><br>${esc(c.description)}</p></div>
  ${ov.pairs.length ? `<div class="card"><h2>Related cases (why flagged)</h2>${ov.pairs.map(p => { const o = other(p); return `<div class="pair"><div class="row"><a href="#/case/${o[1]}">${esc(o[0])}</a> <span class="b">${esc(o[2])}</span>${sev(p.severity)}<span class="mut">score ${p.score}</span></div><p class="mut" style="margin:6px 0 0">${esc(p.explanation)}</p></div>`; }).join("")}</div>` : ""}
  <div class="card"><h2>Workflow & action history</h2><div class="tl">${d.history.map(h => `<div><b>${esc(h.action)}</b> · ${esc(h.bureau)} · ${esc(h.actor)}<br><small>${esc(h.ts.replace("T", " "))} ${h.kind !== "note" ? "· " + esc(h.kind) : ""}</small>${h.remarks ? `<br>${esc(h.remarks)}` : ""}${h.doc ? `<br><a href="/api/documents/${esc(h.doc)}" target="_blank" class="doc-pill">${icon("file", 13)} View Document</a>` : ""}</div>`).join("")}</div></div>
  ${d.can_act && c.status !== "Disposed" ? `<div class="card"><h2>Take action</h2><form id="af" class="form"><div><label>Action</label><select id="act"><option value="update">Update / progress</option>${c.status === "Transferred" ? '<option value="accept">Accept transfer</option>' : ""}<option value="transfer">Transfer</option><option value="escalate">Escalate</option><option value="dispose">Dispose</option></select></div>
  <div><label>Type of step</label><select id="kind">${m.action_kinds.map(k => `<option>${esc(k)}</option>`).join("")}</select></div><div><label>Transfer to</label><select id="to">${Object.keys(m.bureaus).filter(b => b !== c.bureau).map(b => `<option>${esc(b)}</option>`).join("")}</select></div>
  <div><label>Next action required</label><input id="nxt"></div><div class="full"><label>Remarks</label><textarea id="rem"></textarea></div>
  <div class="full"><label>Attach Supporting Document (PDF / Image / DOCX)</label><input type="file" id="afile" accept=".pdf,.png,.jpg,.jpeg,.docx,.txt"></div>
  <div class="full"><button class="btn">Record action</button></div></form></div>` : ""}`;
}

/* ---------- overlaps ---------- */
async function vOverlaps() {
  const [g, cf] = await Promise.all([api("/overlaps"), api("/conflicts")]), canRev = S.me.role !== "REGIONAL";
  vOverlaps.after = () => document.querySelectorAll("[data-rv]").forEach(b => b.onclick = async () => {
    const [a, c, dec, lead] = b.dataset.rv.split("|"); try { await api("/overlaps/review", { body: { case_a: +a, case_b: +c, decision: dec, lead_bureau: lead || null, note: "" } }); toast("Decision recorded in both case histories"); render(); } catch (x) { toast(x.message); }
  });
  return `<h1>${esc(t("overlaps"))}</h1>${cf.length ? `<div class="card"><h2 style="display:flex;align-items:center;gap:8px">${icon("shieldAlert", 18)} ${esc(t("conflicts"))} (${cf.length})</h2>${cf.map(x => `<div class="pair"><div class="row">${sev(x.severity)}<b>${esc(x.institution)}</b></div><p style="margin:6px 0">${esc(x.message)}</p>
  <small class="mut">${esc(x.case_a)} · ${esc(x.bureau_a)}: ${esc(x.kind_a)} &nbsp;vs&nbsp; ${esc(x.case_b)} · ${esc(x.bureau_b)}: ${esc(x.kind_b)}</small></div>`).join("")}</div>` : ""}
  ${g.map(x => `<div class="card"><div class="row"><h2 style="margin:0"><a href="#/institution/${x.institution_id}">${esc(x.institution)}</a></h2>${sev(x.severity)}<span class="mut">${esc(x.bureaus.join(" + "))}</span></div>
  <p class="${x.severity === "Info" ? "mut" : ""}" style="font-weight:600">${esc(x.message)}</p>
  ${x.pairs.map(p => `<div class="pair"><div class="vs"><div><a href="#/case/${p.id_a}">${esc(p.case_a)}</a> <span class="b">${esc(p.bureau_a)}</span></div><div><a href="#/case/${p.id_b}">${esc(p.case_b)}</a> <span class="b">${esc(p.bureau_b)}</span></div></div>
  <div class="row" style="margin:8px 0">${sev(p.severity)}<span class="mut">match ${Math.round(p.score * 100)}%</span>${p.review ? `<span class="b s-UnderProcess">${esc(p.review.status)}${p.review.lead_bureau ? " · lead " + esc(p.review.lead_bureau) : ""}</span>` : ""}</div>
  <p class="mut" style="margin:0 0 8px">${esc(p.explanation)}</p>${canRev ? `<div class="row"><button class="btn sm alt" data-rv="${p.id_a}|${p.id_b}|acknowledge|">${esc(t("acknowledge"))}</button>
  ${[...new Set([p.bureau_a, p.bureau_b])].map(b => `<button class="btn sm" data-rv="${p.id_a}|${p.id_b}|designate_lead|${esc(b)}">${esc(t("lead"))}: ${esc(b)}</button>`).join("")}<button class="btn sm alt" data-rv="${p.id_a}|${p.id_b}|not_related|">${esc(t("notrel"))}</button></div>` : ""}</div>`).join("")}
  <div class="mut">${x.cases.map(c => `${esc(c.bureau)}: ${esc(c.case_no)}`).join(" · ")}</div></div>`).join("") || '<div class="card">No overlaps detected.</div>'}`;
}

/* ---------- institutions ---------- */
async function vInsts(_, q) {
  const l = await api("/institutions?" + qs({ q: q.q || "" }));
  vInsts.after = () => { const i = $("#iq"); i.onkeydown = e => e.key === "Enter" && (location.hash = "#/institutions?" + qs({ q: i.value })); };
  return `<h1>${esc(t("institutions"))}</h1><div class="filters"><input id="iq" placeholder="Name, AICTE ID or city - press Enter" value="${esc(q.q || "")}"></div><div class="card tw"><table><thead><tr><th>Institution</th><th>AICTE ID</th><th>City</th><th>Region</th><th>Active cases</th></tr></thead><tbody>
  ${l.map(i => `<tr><td><a href="#/institution/${i.id}">${esc(i.name)}</a></td><td>${esc(i.aicte_id)}</td><td>${esc(i.city)}</td><td>${esc(i.region)}</td><td>${i.active_cases}</td></tr>`).join("")}</tbody></table></div>`;
}
async function vInst(id) {
  const d = await api("/institutions/" + id), i = d.institution, lanes = {};
  d.cases.forEach(c => (lanes[c.bureau] = lanes[c.bureau] || []).push(c));
  return `<p><a href="#/institutions">${icon("arrowLeft", 12)} ${esc(t("institutions"))}</a></p><h1>${esc(i.name)}</h1><p class="mut">AICTE Permanent ID <b>${esc(i.aicte_id)}</b> · ${esc(i.address)}, ${esc(i.state)} · ${esc(i.region)} region</p>
  ${d.bureaus_active.length > 1 ? `<div class="banner"><span class="banner-ico">${icon("alert", 16)}</span> <b>[Alert]</b> ${esc(t("banner"))}<br><small>Active at: ${esc(d.bureaus_active.join(", "))}</small></div>` : ""}
  <div class="card"><h2>Case family - who is handling what</h2><div class="lanes">${Object.entries(lanes).map(([b, cs]) => `<div class="lane"><h3>${esc(b)} · ${esc(S.meta.bureaus[b])}</h3>${cs.map(c => `<a href="#/case/${c.id}">${esc(c.case_no)}<br><span class="mut">${esc(c.category_label)}</span> ${badge(c.status)}</a>`).join("")}</div>`).join("") || "No cases."}</div></div>`;
}

/* ---------- register complaint with live pre-check ---------- */
async function vNew() {
  const insts = await api("/institutions");
  vNew.after = () => {
    let timer, cur = null;
    const run = async () => {
      const desc = $("#nd").value; if (desc.length < 15) return $("#pre").innerHTML = '<p class="mut">Type the complaint (English / Hinglish / हिन्दी) - the system checks who else is already acting on this institution.</p>';
      const hit = insts.find(i => i.name.toLowerCase() === $("#ni").value.trim().toLowerCase() || i.aicte_id === $("#ni").value.trim());
      try {
        const r = cur = await api("/intake/analyze", { body: { institution_ref: $("#ni").value, institution_id: hit ? hit.id : null, description: desc, subject: $("#ns").value } });
        const im = r.institution, nm = im.institution_id ? (insts.find(i => i.id === im.institution_id) || {}).name : null;
        $("#pre").innerHTML = `${r.banner ? `<div class="banner"><span class="banner-ico">${icon("alert", 16)}</span> <b>[Alert]</b> ${esc(r.banner)}</div>` : ""}<p><b>Institution:</b> ${nm ? esc(nm) + ` <span class="b v-${im.band === "auto" ? "Info" : "Medium"}">${esc(im.band)} · ${Math.round(im.score * 100)}%</span>` : '<span class="b v-Medium">not matched - pick from list</span>'}<br><span class="mut">${esc(im.reason)}</span></p>
        <p><b>Suggested:</b> ${r.suggested_category ? `${esc(S.meta.categories[r.suggested_category].label)} &rarr; ${esc(r.suggested_bureau)} <button type="button" class="btn sm alt" id="use">Use</button><br><span class="mut">detected: ${esc(r.triggering_concepts.join(", "))}</span>` : "no category detected"}</p>${r.flags.map(f => `<p class="mut" style="display:flex;align-items:center;gap:6px">${icon("bell", 13)} ${esc(f)}</p>`).join("")}
        ${r.similar_cases.slice(0, 4).map(s => `<div class="pair"><a href="#/case/${s.case.id}">${esc(s.case.case_no)}</a> <span class="b">${esc(s.case.bureau)}</span> ${s.likely_duplicate ? '<span class="b red">likely duplicate</span>' : ""}<br><small class="mut">${esc(s.explanation)}</small></div>`).join("")}`;
        const u = $("#use"); if (u) u.onclick = () => { $("#nc").value = r.suggested_category; $("#nb").value = r.suggested_bureau; };
      } catch (x) { $("#pre").innerHTML = `<p class="mut">${esc(x.message)}</p>`; }
    };
    ["ni", "nd", "ns"].forEach(i => $("#" + i).oninput = () => { clearTimeout(timer); timer = setTimeout(run, 500); });
    $("#nf").onsubmit = async e => {
      e.preventDefault(); const hit = insts.find(i => i.name.toLowerCase() === $("#ni").value.trim().toLowerCase() || i.aicte_id === $("#ni").value.trim()); const im = cur && cur.institution;
      const iid = hit ? hit.id : (im && im.band === "auto" ? im.institution_id : null);
      try { const c = await api("/cases", { body: { subject: $("#ns").value, description: $("#nd").value, category: $("#nc").value, bureau: $("#nb").value || null, institution_id: iid, institution_ref: $("#ni").value } }); toast("Registered " + c.case_no); location.hash = "#/case/" + c.id; } catch (x) { toast(x.message); }
    };
  };
  const m = S.meta;
  return `<h1>${esc(t("register"))}</h1><div class="grid g2"><form id="nf" class="card form"><div class="full"><label>Institution (name, AICTE ID, or free text)</label><input id="ni" list="il" style="width:100%" required><datalist id="il">${insts.map(i => `<option value="${esc(i.name)}">`).join("")}</datalist></div>
  <div class="full"><label>Subject</label><input id="ns" style="width:100%" required minlength="5"></div><div class="full"><label>Description</label><textarea id="nd" required minlength="10"></textarea></div>
  <div><label>Category</label><select id="nc">${Object.entries(m.categories).map(([k, v]) => `<option value="${esc(k)}">${esc(v.label)}</option>`).join("")}</select></div><div><label>Bureau/Cell (blank = default)</label><select id="nb"><option value="">Default</option>${Object.keys(m.bureaus).map(b => `<option>${esc(b)}</option>`).join("")}</select></div>
  <div class="full"><button class="btn">Register complaint</button></div></form><div class="card"><h2>Live pre-check</h2><div id="pre"><p class="mut">Type the complaint (English / Hinglish / हिन्दी) - the system checks who else is already acting on this institution.</p></div></div></div>`;
}

/* ---------- bulk CSV import ---------- */
async function vImport() {
  let previewData = null;
  vImport.after = () => {
    const fi = $("#csvf");
    if (!fi) return;
    fi.onchange = async () => {
      const file = fi.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      $("#prevbox").innerHTML = '<p class="mut">Parsing CSV and matching institutions with AICTE directory...</p>';
      try {
        const res = await fetch("/api/cases/import/preview", { method: "POST", body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Failed to preview CSV");
        }
        previewData = await res.json();
        renderPreview();
      } catch (err) {
        $("#prevbox").innerHTML = `<div class="card" style="border-color:var(--red);color:var(--red)">[Error] ${esc(err.message)}</div>`;
      }
    };

    function renderPreview() {
      if (!previewData) return;
      const d = previewData;
      $("#prevbox").innerHTML = `
        <div class="row" style="margin-bottom:12px">
          <b>Summary:</b>
          <span class="b v-Info">${d.total_rows} total rows</span>
          <span class="b s-Disposed">${d.valid_rows} valid to import</span>
          ${d.total_rows - d.valid_rows > 0 ? `<span class="b red">${d.total_rows - d.valid_rows} with errors</span>` : ""}
          <span class="sp"></span>
          ${d.valid_rows > 0 ? `<button class="btn" id="commitbtn">Confirm & Import ${d.valid_rows} Cases</button>` : ""}
        </div>
        <div class="tw"><table>
          <thead>
            <tr><th>Row</th><th>Institution Reference</th><th>Matched AICTE Institution</th><th>Category</th><th>Bureau</th><th>Priority</th><th>Overlap Risk</th><th>Status</th></tr>
          </thead>
          <tbody>
            ${d.items.map(it => `
              <tr style="${it.valid ? "" : "background:var(--redB)"}">
                <td>${it.row}</td>
                <td><b>${esc(it.institution_ref)}</b><br><small class="mut">${esc(it.subject)}</small></td>
                <td>${it.institution_matched ? `${esc(it.institution_matched)} <span class="b v-${it.match_band === 'auto' ? 'Info' : 'Medium'}">${esc(it.match_band)} (${Math.round(it.match_score * 100)}%)</span>` : '<span class="b v-Medium">unmatched</span>'}</td>
                <td>${esc(it.category_label)}</td>
                <td><b>${esc(it.bureau)}</b></td>
                <td>${esc(it.priority)}</td>
                <td>${it.overlap_warning ? `<span class="b red" title="${esc(it.overlap_warning)}">${icon("alert", 12)} Overlap</span>` : '<span class="mut">-</span>'}</td>
                <td>${it.valid ? '<span class="b s-Disposed">Ready</span>' : `<span class="b red">${esc(it.errors.join(", "))}</span>`}</td>
              </tr>
            `).join("")}
          </tbody>
        </table></div>
      `;
      const cb = $("#commitbtn");
      if (cb) {
        cb.onclick = async () => {
          cb.disabled = true;
          cb.textContent = "Importing...";
          try {
            const validItems = d.items.filter(x => x.valid);
            const res = await api("/cases/import/commit", { method: "POST", body: { items: validItems } });
            toast(`Successfully imported ${res.imported} cases`);
            location.hash = "#/cases";
          } catch (err) {
            toast(err.message);
            cb.disabled = false;
            cb.textContent = "Retry Import";
          }
        };
      }
    }
  };

  return `
    <div class="row">
      <h1 style="margin:0">${esc(t("import"))}</h1>
      <span class="sp"></span>
      <a href="/api/cases/import/template" class="btn sm alt" download>${icon("download", 14)} Download CSV Template</a>
    </div>
    <p class="mut">Upload incoming complaints spreadsheet from regional offices or web portals. The system pre-resolves institutions, checks categories, and flags overlaps before inserting.</p>
    <div class="card upload-zone" id="dropz">
      <input type="file" id="csvf" accept=".csv" style="display:none">
      <p style="font-size:16px;font-weight:600;margin:0 0 6px">Select Complaints CSV File</p>
      <p class="mut" style="margin:0 0 12px">Supports .csv format with UTF-8 encoding</p>
      <button type="button" class="btn sm" onclick="$('#csvf').click()">Choose CSV File</button>
    </div>
    <div class="card" id="prevbox">
      <p class="mut">No file chosen yet. Download the template above for the standard AICTE ingestion schema.</p>
    </div>
  `;
}

/* ---------- public citizen grievance tracking ---------- */
async function vTrack(caseNoParam) {
  vTrack.after = () => {
    const f = $("#tf");
    if (!f) return;
    f.onsubmit = e => {
      e.preventDefault();
      const num = $("#tno").value.trim();
      if (num) location.hash = "#/track/" + encodeURIComponent(num);
    };
  };

  let trackingResult = null, searchError = null;
  const targetNo = caseNoParam ? decodeURIComponent(caseNoParam) : "";
  if (targetNo) {
    try {
      const res = await fetch("/api/public/track/" + encodeURIComponent(targetNo));
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Grievance reference number not found");
      }
      trackingResult = await res.json();
    } catch (err) {
      searchError = err.message;
    }
  }

  return `
    <div class="track-card card">
      <div style="text-align:center;margin-bottom:20px">
        <h1 style="margin:0 0 6px">AICTE Grievance Status Tracker</h1>
        <p class="mut" style="margin:0">Public citizen & student single-window complaint tracking portal</p>
      </div>
      <form id="tf" class="row" style="margin-bottom:20px">
        <input id="tno" placeholder="Enter AICTE Case No (e.g. AICTE/PGRC/2026/00001)" value="${esc(targetNo)}" style="flex:1" required>
        <button class="btn">Track Status</button>
      </form>
      ${searchError ? `<div class="banner">${esc(searchError)}</div>` : ""}
      ${trackingResult ? renderTrackDetails(trackingResult) : !targetNo ? '<p class="mut" style="text-align:center">Enter your complaint case number above to see the official redressal status and milestones.</p>' : ""}
    </div>
  `;
}

function renderTrackDetails(k) {
  return `
    <div style="border-top:1px solid var(--line);padding-top:16px">
      <div class="row">
        <div>
          <span class="mut" style="font-size:12px">CASE NUMBER</span>
          <h2 style="margin:2px 0 0">${esc(k.case_no)}</h2>
        </div>
        <span class="sp"></span>
        ${badge(k.status)}
      </div>

      <div class="stepper">
        ${k.milestones.map((m, idx) => `
          <div class="step ${m.done ? 'done' : idx === k.milestones.findIndex(x => !x.done) ? 'active' : ''}">
            <div class="bubble">${m.done ? icon('check', 17) : idx + 1}</div>
            <div class="stitle">${esc(m.title)}</div>
            <div class="sdate">${esc(m.date || 'Pending')}</div>
          </div>
        `).join("")}
      </div>

      <div class="facts" style="margin-top:18px">
        <div><small>Target Institution</small><b>${esc(k.institution_name)}</b>${k.city ? `<br><span class="mut">${esc(k.city)}, ${esc(k.state)}</span>` : ""}</div>
        <div><small>Grievance Category</small>${esc(k.category_label)}</div>
        <div><small>Handling Bureau / Cell</small><b>${esc(k.bureau_label || k.bureau)}</b></div>
        <div><small>Received Date</small>${esc(k.received_on)}</div>
        <div><small>Expected Disposal (SLA)</small>${esc(k.expected_disposal)}${k.status !== 'Disposed' ? `<br><span class="mut">${k.days_remaining} day(s) left</span>` : ""}</div>
        <div><small>Latest Official Action</small>${esc(k.last_action)}<br><span class="mut">${esc(k.last_action_date)}</span></div>
      </div>
    </div>
  `;
}

async function renderPublicTrack(caseNoParam) {
  const content = await vTrack(caseNoParam);
  $("#app").innerHTML = `
    <div style="min-height:100vh;background:var(--bg);background-image:var(--bg-mesh);padding:32px 16px">
      <div style="max-width:760px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div class="brand" style="border:none;padding:0;margin:0">
          <div class="brand-title"><span class="brand-logo">${icon("govSeal", 22)}</span> AICTE Samvad <span class="badge">CITIZEN PORTAL</span></div>
          <small>National Institution Grievance Status Service</small>
        </div>
        <a href="#/dashboard" class="btn sm alt" style="text-decoration:none">${icon("lock", 13)} Staff Sign In &rarr;</a>
      </div>
      ${content}
    </div>
  `;
  (vTrack.after || (() => {}))();
}

/* ---------- audit ---------- */
async function vAudit() {
  const [rows, v] = await Promise.all([api("/audit?limit=60"), api("/audit/verify")]);
  return `<h1>${esc(t("audit"))}</h1><div class="banner ${v.valid ? "amb" : ""}">${v.valid ? `<span style="color:var(--grn);display:inline-flex;align-items:center;gap:6px;font-weight:700">${icon("shieldCheck", 17)} Hash chain intact</span>` : `<span style="color:var(--red);display:inline-flex;align-items:center;gap:6px;font-weight:700">${icon("shieldAlert", 17)} TAMPERING DETECTED at entry ` + v.broken_at + `</span>`} - ${v.entries} entries verified</div><div class="card tw"><table><thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Detail</th><th>Hash</th></tr></thead><tbody>
  ${rows.map(r => `<tr><td>${r.id}</td><td>${esc(r.ts.replace("T", " "))}</td><td>${esc(r.actor)}</td><td>${esc(r.action)}</td><td>${esc(r.entity)} ${esc(r.entity_id)}</td><td>${esc(r.detail)}</td><td class="mut">${esc(r.hash)}</td></tr>`).join("")}</tbody></table></div>`;
}

/* ---------- alerts ---------- */
const LV = { high: "red", medium: "v-Medium", low: "v-Info" };
async function vAlerts(_, q) {
  const mine = q.mine === "1", a = await api("/alerts" + (mine ? "?mine=true" : "")), f = q.type || "";
  const types = [...new Set(a.items.map(x => x.type))], items = a.items.filter(x => !f || x.type === f);
  vAlerts.after = () => { $("#am").onclick = () => location.hash = "#/alerts?" + qs({ mine: mine ? "" : "1", type: f }); $("#at").onchange = e => location.hash = "#/alerts?" + qs({ mine: mine ? "1" : "", type: e.target.value }); };
  return `<h1>${esc(t("alerts"))} <span class="b red">${a.counts.high} high</span> <span class="b v-Medium">${a.counts.medium} medium</span> <span class="b v-Info">${a.counts.low} low</span></h1>
  <div class="filters"><button id="am" class="btn ${mine ? "" : "alt"}">${mine ? "Showing: my cases" : "Show only my cases"}</button><select id="at"><option value="">All alert types</option>${types.map(x => `<option ${x === f ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>
  <div class="card tw"><table><thead><tr><th>Level</th><th>Alert</th><th>Case / reference</th><th>Institution</th><th>Bureau/Cell</th><th>Detail</th><th>Suggested step</th></tr></thead><tbody>
  ${items.map(x => `<tr><td><span class="b ${LV[x.level]}">${esc(x.level)}</span></td><td>${esc(x.type)}</td><td><a href="${esc(x.href)}">${esc(x.case_no)}</a></td><td>${esc(x.institution)}</td><td>${esc(x.bureau)}</td><td>${esc(x.detail)}</td><td class="mut">${esc(x.suggested)}</td></tr>`).join("") || '<tr><td colspan="7" class="mut">No alerts.</td></tr>'}</tbody></table></div>`;
}

/* ---------- reports ---------- */
const RK = [["bureau", "Bureau/Cell-wise"], ["region", "Region-wise"], ["institution", "Institution-wise"], ["category", "Category-wise"], ["status", "Status-wise"], ["ageing", "Pending ageing"], ["monthly", "Monthly"], ["quarterly", "Quarterly"], ["overlaps", "Overlapping cases"]];
async function vReports(kind) {
  kind = kind || "bureau"; const r = await api("/reports/" + kind);
  vReports.after = () => { $("#pr").onclick = () => window.print(); };
  return `<h1>${esc(t("reports"))}</h1><div class="filters">${RK.map(([k, l]) => `<a class="btn sm ${k === kind ? "" : "alt"}" href="#/reports/${k}" style="text-decoration:none">${esc(l)}</a>`).join("")}</div>
  <div class="card tw"><div class="row"><h2 style="margin:0">${esc(RK.find(x => x[0] === kind)[1])} report</h2><span class="sp"></span><a class="btn sm alt" href="/api/reports/${esc(kind)}?format=csv" style="text-decoration:none">${icon("download", 14)} CSV (Excel)</a><button class="btn sm alt" id="pr">${icon("printer", 14)} Print / Save as PDF</button></div>
  <p class="mut">Generated ${esc(r.generated)} · scope: ${esc(S.me.role)}${S.me.region ? " " + esc(S.me.region) : ""}${S.me.bureau ? " · " + esc(S.me.bureau) : ""}</p>
  <table><thead><tr>${r.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${r.rows.map(x => `<tr>${x.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

/* ---------- guided demo tour ---------- */
const TOUR = [
  { h: "#/dashboard", title: "1. One screen for every Bureau/Cell", text: "Totals, pending, transferred, escalated and overdue cases - with the red banner that warns when different Bureaus are acting on the same institution." },
  { h: "#/overlaps", title: "2. Overlap Centre", text: "Each flagged institution shows both cases side by side with a plain-language reason. The engine works across English, Hinglish and Hindi, so differently worded complaints still match." },
  { h: "#/overlaps", title: "3. Conflicting actions", text: "Beyond duplicate work, the system flags contradictory outcomes - e.g. RB withdrawing approval while PGRC finds the institution compliant - before conflicting orders go out." },
  { h: "#/new", title: "4. Intake pre-check", text: "Press 'Fill demo complaint': a Hinglish fee-refund complaint with a misspelt institution name. The system finds the institution, suggests the Bureau, and shows who is already acting.", fill: true },
  { h: "#/overlaps", title: "5. Humans decide", text: "An officer designates a lead Bureau (or marks the pair unrelated). The decision is written into both case histories and the audit log. Nothing is auto-merged." },
  { h: "#/alerts", title: "6. SLA and escalation alerts", text: "Overdue, approaching-deadline, idle and escalated cases, plus overlap and conflict alerts - filterable to 'my cases'." },
  { h: "#/reports/bureau", title: "7. Reports", text: "Bureau, region, institution, ageing, monthly and quarterly reports - exportable to CSV or print to PDF." },
  { h: "#/audit", title: "8. Tamper-evident audit trail", text: "Every action is hash-chained. Any edit or deletion of history is detected (Competent Authority view)." },
];
let tourI = -1;
function startTour() { tourI = 0; showTour(); }
function endTour() { tourI = -1; const d = $("#tour"); if (d) d.remove(); }
async function showTour() {
  const st = TOUR[tourI]; location.hash = st.h; let d = $("#tour");
  if (!d) { d = document.createElement("div"); d.id = "tour"; d.className = "tour"; document.body.append(d); }
  d.innerHTML = `<b>${esc(st.title)}</b><p>${esc(st.text)}</p><div class="row">${st.fill ? '<button class="btn sm" id="tf">Fill demo complaint</button>' : ""}<span class="sp"></span>${tourI ? '<button class="btn sm alt" id="tp">Back</button>' : ""}<button class="btn sm" id="tn">${tourI < TOUR.length - 1 ? "Next" : "Finish"}</button><button class="btn sm alt" id="tx">Exit</button></div><small class="mut">${tourI + 1} / ${TOUR.length}</small>`;
  $("#tn").onclick = () => { tourI++; tourI >= TOUR.length ? endTour() : showTour(); }; $("#tx").onclick = endTour; if ($("#tp")) $("#tp").onclick = () => { tourI--; showTour(); };
  if ($("#tf")) $("#tf").onclick = async () => {
    const g = (await api("/overlaps?min_severity=Medium")).find(x => x.cases.some(c => c.category === "fee_refund")) || (await api("/overlaps"))[0]; if (!g) return;
    const w = g.institution.split(" "); w[0] = w[0].length > 4 ? w[0].slice(0, -2) + w[0].slice(-1) + w[0].slice(-2, -1) : w[0];  // deliberate typo
    const set = (id, v) => { const e = $("#" + id); if (e) { e.value = v; e.dispatchEvent(new Event("input")); } };
    set("ni", w.join(" ").replace("Institute", "Instt.").replace("Engineering", "Engg")); set("ns", "Fee refund nahi mila"); set("nd", "Admission cancel karne ke baad bhi college Rs 35000 fee wapas nahi kar raha hai.");
  };
}

/* ---------- command palette ---------- */
function openPal() {
  const m = $("#pal"), i = $("input", m); m.hidden = false; i.value = ""; i.focus(); let tm;
  const pages = [["Dashboard", "#/dashboard"], ["Cases", "#/cases"], ["Overlap Centre", "#/overlaps"], ["Institutions", "#/institutions"], ["Register complaint", "#/new"], ["Bulk CSV Import", "#/import"], ["Track Grievance", "#/track"], ["Overdue cases", "#/cases?overdue=true"], ["Alerts", "#/alerts"], ["Reports", "#/reports/bureau"], ["Guided demo", "#/dashboard"]];
  const show = items => { $(".pallist", m).innerHTML = items.map(([l, h], n) => `<a href="${h}" class="${n ? "" : "on"}" style="display:flex;align-items:center;gap:8px">${icon(h.includes("institution") ? "institutions" : h.includes("case") ? "cases" : "dashboard", 14)} <span>${esc(l)}</span></a>`).join("") || '<p class="mut">No results</p>'; };
  const upd = async () => {
    const q = i.value.trim().toLowerCase(); let items = pages.filter(p => p[0].toLowerCase().includes(q));
    if (q.length >= 2) { try { const [c, n] = await Promise.all([api("/cases?" + qs({ q: i.value, size: 5 })), api("/institutions?" + qs({ q: i.value }))]);
      items = items.concat(c.items.map(x => [`${x.case_no} · ${x.category_label}`, `#/case/${x.id}`]), n.slice(0, 5).map(x => [`${x.name}`, `#/institution/${x.id}`])); } catch (e) { } }
    show(items);
  };
  i.oninput = () => { clearTimeout(tm); tm = setTimeout(upd, 200); }; show(pages);
  i.onkeydown = e => { if (e.key === "Escape") m.hidden = true; if (e.key === "Enter") { const a = $(".pallist a", m); if (a) { location.hash = a.getAttribute("href"); m.hidden = true; } } };
  m.onclick = e => { if (e.target === m || e.target.closest("a")) m.hidden = true; };
}
addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && S.me) { e.preventDefault(); openPal(); } });
addEventListener("hashchange", () => {
  const r = route();
  if (r.parts[0] === "track" && !S.me) {
    return renderPublicTrack(r.parts[1]);
  }
  if (S.me) render();
});

/* ---------- login / boot ---------- */
function loginView() {
  const demo = [
    ["chairman", "Competent Authority", "ADMIN", "shield"],
    ["rb.head", "Regulation Bureau Head", "HEAD", "scale"],
    ["pgrc.head", "Public Grievance Head", "HEAD", "shieldCheck"],
    ["rb.officer1", "Regulation Officer", "OFFICER", "file"],
    ["arc.head", "Anti-Ragging Cell", "HEAD", "lock"],
    ["ro.western", "Regional Officer (West)", "REGIONAL", "mapPin"]
  ];
  $("#app").innerHTML = `
    <div class="login" style="max-width:480px">
      <div class="card" style="box-shadow:var(--shadow-lg);border-color:var(--line-strong)">
        <div style="text-align:center;padding:10px 0 16px;border-bottom:1px solid var(--line);margin-bottom:18px">
          <div style="display:inline-flex;align-items:center;gap:8px;font-size:11px;font-weight:800;letter-spacing:0.08em;color:var(--mut);text-transform:uppercase;margin-bottom:6px">
            <span class="brand-logo" style="width:18px;height:18px">${icon("govSeal", 16)}</span> Government of India · AICTE
          </div>
          <h1 style="justify-content:center;margin:0 0 4px;font-size:26px">AICTE Samvad</h1>
          <p class="mut" style="margin:0;font-size:12.5px;font-weight:600">Integrated Institution Complaint Monitoring Cockpit</p>
        </div>

        <form id="lf" class="form">
          <div class="full">
            <label style="font-weight:700">Official Username</label>
            <input id="lu" style="width:100%" autocomplete="username" placeholder="e.g. chairman or rb.head" required>
          </div>
          <div class="full">
            <label style="font-weight:700">Password</label>
            <input id="lp" type="password" style="width:100%" autocomplete="current-password" placeholder="••••••••" required>
          </div>
          <div class="full">
            <button class="btn" style="width:100%;padding:12px;font-size:14px;box-shadow:var(--shadow-glow)">${esc(t("signin"))} &rarr;</button>
          </div>
        </form>

        <div style="margin-top:16px;padding:12px;background:var(--pri-bg);border-radius:10px;text-align:center;border:1px solid rgba(37,99,235,0.2)">
          <a href="#/track" style="font-weight:700;font-size:13px;color:var(--pri);text-decoration:none;display:inline-flex;align-items:center;gap:6px">${icon("search", 14)} Citizen Portal — Track Complaint Status &rarr;</a>
        </div>

        <div style="margin-top:20px;border-top:1px solid var(--line);padding-top:14px">
          <div class="row" style="margin-bottom:8px">
            <span class="mut" style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;display:inline-flex;align-items:center;gap:6px">${icon("lightning", 13)} Instant Demo Sign-In (Password: Aicte@2026)</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            ${demo.map(d => `
              <button type="button" data-u="${d[0]}" class="btn alt sm" style="text-align:left;display:flex;align-items:center;gap:8px;padding:8px 10px;font-size:12px;border-radius:8px">
                <span class="kpi-icon" style="width:28px;height:28px;border-radius:6px;flex-shrink:0">${icon(d[3], 15)}</span>
                <div style="overflow:hidden">
                  <b style="display:block;white-space:nowrap;text-overflow:ellipsis">${esc(d[1])}</b>
                  <span class="mut" style="font-size:10px">${esc(d[2])}</span>
                </div>
              </button>
            `).join("")}
          </div>
        </div>
      </div>
    </div>
  `;
  document.querySelectorAll("[data-u]").forEach(b => b.onclick = () => { $("#lu").value = b.dataset.u; $("#lp").value = "Aicte@2026"; });
  $("#lf").onsubmit = async e => { e.preventDefault(); try { S.me = await api("/auth/login", { body: { username: $("#lu").value, password: $("#lp").value } }); boot(); } catch (x) { toast(x.message); } };
}
async function boot() {
  document.documentElement.dataset.theme = S.theme;
  const r = route();
  if (r.parts[0] === "track" && !S.me) {
    return renderPublicTrack(r.parts[1]);
  }
  if (!S.me) { try { S.me = await api("/auth/me"); } catch (e) { return loginView(); } }
  if (!S.meta) S.meta = await api("/meta");
  render();
}
boot();
