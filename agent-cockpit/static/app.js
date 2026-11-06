// Klinik Cockpit: renders the real agent workflow state polled from /api/state.

const $ = (id) => document.getElementById(id);
const SYS = {
  KIS: "#0b6e8a", RIS: "#7052b8", LIS: "#c2410c", OP: "#0f766e", PFLEGE: "#be185d",
  PATHO: "#a16207", MED: "#15803d", TERMIN: "#475569",
};
const STATUS = { available: "gelesen", pending: "ausstehend", unreleased: "nicht freigegeben" };
const KIND = {
  unreleased: ["Nicht freigegeben", "amber"], pending: ["Ausstehend", "blue"],
  missing: ["Fehlt", "red"], conflict: ["Widerspruch", "red"],
};
const AGENT = { writer: "Dokumentations-Agent", reviewer: "Prüf-Agent", system: "System", human: "Ärztin" };

let state = null, timer = null, renderedEvents = 0, letterKey = "";

const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const clock = (ts) => new Date(ts * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

async function call(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Fehler");
  return data;
}

async function refresh() {
  try {
    state = await (await fetch("/api/state")).json();
    render();
  } finally {
    clearTimeout(timer);
    timer = setTimeout(refresh, state?.busy ? 500 : 2000);
  }
}

// ---------- Render ----------
function render() {
  const p = state.patient;
  $("patient").innerHTML = "";
  $("patient").append(el("strong", "", p.name), el("span", "", `${p.age} J. · ${p.case_id} · ${p.department}`),
    el("span", "pill", `Entlassung heute · ${p.discharge}`));
  $("model-writer").textContent = state.agents.writer;
  $("model-reviewer").textContent = state.agents.reviewer;
  if (!$("systems").childElementCount) {
    for (const [code, name] of Object.entries(state.systems)) {
      const chip = el("span", "system-chip"); const tag = el("span", "sys", code); tag.style.background = SYS[code];
      chip.append(tag, ` ${name}`); $("systems").appendChild(chip);
    }
  }
  renderAgents();
  renderStats();
  renderTimeline();
  renderLetter();
  renderOpenPoints();
  renderReview();
  renderControls();
}

function lastOf(agent) {
  return [...state.events].reverse().find((e) => e.agent === agent && ["start", "draft", "review", "error"].includes(e.kind));
}

function renderAgents() {
  for (const agent of ["writer", "reviewer"]) {
    const last = lastOf(agent);
    const working = state.busy && last && last.kind === "start";
    const label = working ? "arbeitet" : last?.kind === "draft" ? "fertig" : last?.kind === "review" ? (last.verdict === "freigabefähig" ? "freigabefähig" : "Befunde") : last?.kind === "error" ? "Fehler" : "bereit";
    $(`state-${agent}`).textContent = label;
    $(`state-${agent}`).className = `state ${working ? "busy" : last ? "done" : ""}`;
    $(`agent-${agent}`).classList.toggle("working", !!working);
  }
}

function renderStats() {
  const s = state.stats;
  $("stats").innerHTML = "";
  if (!s.model_calls) return;
  for (const [value, label] of [[s.sources_read, "Quellen"], [s.systems.length, "Systeme"], [s.model_calls, "KI-Aufrufe"], [s.tool_calls, "Tools"], [`${Math.round(s.seconds)} s`, "Laufzeit"]]) {
    const box = el("div", "stat"); box.append(el("b", "", value), el("span", "", label)); $("stats").appendChild(box);
  }
}

function renderTimeline() {
  const list = $("timeline");
  if (!state.events.length) { list.innerHTML = '<li class="empty">Noch keine Aktivität.</li>'; renderedEvents = 0; return; }
  if (renderedEvents > state.events.length || renderedEvents === 0) { list.innerHTML = ""; renderedEvents = 0; }
  if (renderedEvents === state.events.length) return;
  // Follow new entries only if the presenter hasn't scrolled up to show an earlier one.
  const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  for (const e of state.events.slice(renderedEvents)) {
    if (e.kind === "model") continue;
    const li = el("li", `ev ${e.agent} ev-${e.kind}`);
    const who = el("span", "who", AGENT[e.agent] || e.agent);
    const body = el("div", "what");
    if (e.kind === "read") {
      const tag = el("span", "sys", e.system); tag.style.background = SYS[e.system] || "#475569";
      body.append(tag, ` ${e.title} `, el("span", `status ${e.status}`, STATUS[e.status] || e.status));
    } else if (e.kind === "review") {
      body.append(e.title, " ", el("span", `verdict ${e.verdict === "freigabefähig" ? "ok" : "warn"}`, e.verdict));
    } else if (e.kind === "draft") {
      body.append(e.changed?.length ? `Aktualisiert: ${e.changed.join(", ")}. ` : "", e.title);
    } else if (e.kind === "validation") {
      body.append("Server-Prüfung: Zitat korrigieren lassen – ", (e.problems || []).join(" "));
    } else {
      body.append(e.title);
    }
    li.append(el("time", "", clock(e.at)), who, body);
    list.appendChild(li);
  }
  renderedEvents = state.events.length;
  if (atBottom) list.scrollTop = list.scrollHeight;
}

function renderLetter() {
  const draft = state.draft;
  $("start").hidden = !!draft || state.busy;
  $("letter").hidden = !draft && !state.busy;
  if (!draft) {
    letterKey = "";
    if (state.busy) { $("sections").innerHTML = '<div class="writing">Die Agenten sammeln Informationen aus den Klinik-Systemen …</div>'; $("version").textContent = "wird erstellt …"; $("version").className = "version busy"; $("letter-sub").textContent = ""; }
    return;
  }
  const p = state.patient;
  $("letter-sub").textContent = `${p.name}, geb. ${p.date_of_birth} · Aufenthalt ${p.admitted}–${p.discharge} · an die weiterbehandelnde Hausarztpraxis`;
  $("version").textContent = state.approval ? "Freigegeben" : state.busy ? `Entwurf v${draft.version} · wird bearbeitet …` : `Entwurf v${draft.version}`;
  $("version").className = `version ${state.approval ? "ok" : state.busy ? "busy" : ""}`;
  const banner = $("approved");
  banner.hidden = !state.approval;
  if (state.approval) banner.textContent = `✓ Freigegeben von ${state.approval.by} um ${clock(state.approval.at)} · bereit zum Versand`;
  // Rebuild sections only when the draft itself changed, so animations don't replay on every poll.
  const key = `${draft.version}|${state.approval ? "final" : "draft"}|${draft.sections.map((s) => s.text).join("|")}`;
  if (key === letterKey) return;
  const firstVersion = !letterKey;
  letterKey = key;
  const box = $("sections");
  box.innerHTML = "";
  $("letter").classList.toggle("final", !!state.approval);
  if (state.approval) { renderFinal(box); return; }
  for (const s of draft.sections) {
    const sec = el("section", `sec${s.changed ? " changed" : ""}${s.revised && !s.changed ? " revised" : ""}`);
    const head = el("div", "sec-head");
    head.appendChild(el("h3", "", s.title));
    if (s.changed) head.appendChild(el("span", "badge", "↻ nach Systemereignis aktualisiert"));
    if (s.revised) head.appendChild(el("span", "badge purple", "✓ nach Prüfung korrigiert"));
    sec.append(head, el("p", "", s.text));
    const before = s.changed ? s.previous_text : s.revised ? s.revised_from : null;
    if (before) {
      const prev = el("details", "prev"); prev.append(el("summary", "", "Vorherige Fassung"), el("p", "", before)); sec.appendChild(prev);
    }
    const chips = el("div", "chips");
    for (const id of s.source_ids) {
      const src = state.sources.find((x) => x.id === id);
      if (!src) continue;
      const chip = el("button", "chip"); chip.type = "button";
      const tag = el("span", "sys", src.system); tag.style.background = SYS[src.system];
      chip.append(tag, ` ${src.title}`);
      chip.onclick = () => openSource(id);
      chips.appendChild(chip);
    }
    if (!s.source_ids.length) chips.appendChild(el("span", "nochip", "keine freigegebene Quelle"));
    sec.appendChild(chips);
    box.appendChild(sec);
  }
  const highlight = box.querySelector(".sec.changed, .sec.revised");
  if (highlight && !firstVersion) highlight.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderFinal(box) {
  const L = state.letter, p = state.patient, a = state.approval;
  const date = new Date(a.at * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  const head = el("div", "lh");
  const org = el("div", "lh-org");
  org.append(el("strong", "", L.hospital), el("span", "", L.clinic), el("span", "", L.director), el("span", "", L.address));
  head.append(el("div", "lh-mark", "✚"), org);
  const addr = el("div", "lh-row");
  const to = el("div", "lh-to"); L.recipient.forEach((line) => to.appendChild(el("div", "", line)));
  const meta = el("div", "lh-meta");
  meta.append(el("div", "", `Musterstadt, ${date}`), el("div", "", `Unser Zeichen: ${p.case_id}`), el("div", "", L.phone));
  addr.append(to, meta);
  const subject = el("p", "subject", `Entlassbrief – ${p.name}, geb. ${p.date_of_birth} – stationärer Aufenthalt vom ${p.admitted} bis ${p.discharge}`);
  const intro = el("p", "", `Sehr geehrte Frau Kollegin, sehr geehrter Herr Kollege, wir berichten über Ihre Patientin Frau ${p.name}, geb. ${p.date_of_birth}, die sich vom ${p.admitted} bis ${p.discharge} in unserer stationären Behandlung befand.`);
  box.append(head, addr, subject, intro);
  for (const s of state.draft.sections) {
    const sec = el("section", "fsec");
    sec.append(el("h3", "", s.title), el("p", "", s.text));
    box.appendChild(sec);
  }
  const sign = el("div", "sign");
  sign.append(el("p", "", "Mit freundlichen kollegialen Grüßen"), el("strong", "", a.by), el("span", "", L.signer_role),
    el("span", "esign", `✓ elektronisch freigegeben am ${date} um ${clock(a.at)} Uhr`));
  const qr = el("div", "fqr");
  const img = el("img"); img.src = "/api/qr.svg"; img.alt = "QR-Code zum Entlass-Assistenten";
  const qt = el("div");
  qt.append(el("strong", "", "Für Sie als Patientin: Fragen zu diesem Brief?"),
    el("p", "", "Scannen Sie den Code. Der Entlass-Assistent erklärt Ihnen diesen ärztlich freigegebenen Brief in Ihrer Sprache – Deutsch, English, Türkçe, العربية, Українська."));
  qr.append(img, qt);
  box.append(sign, qr, el("p", "fiction", "Fiktiver Demo-Brief. Keine reale Person, keine reale Behandlung."));
}

function renderOpenPoints() {
  const box = $("open-points");
  if (!state.draft) return;
  box.innerHTML = "";
  if (!state.draft.open_points.length) { box.appendChild(el("p", "ok-line", "✓ Keine offenen Punkte")); return; }
  for (const point of state.draft.open_points) {
    const [label, color] = KIND[point.kind] || [point.kind, "blue"];
    const card = el("div", `point ${color}`);
    card.append(el("span", "kind", label), el("strong", "", point.title), el("p", "", point.detail));
    box.appendChild(card);
  }
}

function renderReview() {
  const box = $("review");
  const review = state.review;
  if (!review) { if (state.busy && state.draft) { box.innerHTML = '<p class="muted">Prüfung läuft …</p>'; } return; }
  box.innerHTML = "";
  const ok = review.verdict === "freigabefähig";
  box.append(el("span", `verdict big ${ok ? "ok" : "warn"}`, ok ? "✓ freigabefähig" : "⚠ überarbeiten"), el("p", "", review.summary));
  for (const f of review.findings) {
    const item = el("div", `finding ${f.severity}`);
    item.append(el("b", "", f.severity === "fehler" ? "Fehler" : "Hinweis"), ` ${f.issue}`);
    box.appendChild(item);
  }
  const corrected = (state.review_rounds || []).filter((r) => r.errors.length);
  for (const round of corrected) {
    const fixed = el("details", "rounds");
    fixed.open = true;
    fixed.appendChild(el("summary", "", `${round.errors.length} Fehler in Entwurf v${round.draft_version} gefunden → vom Dokumentations-Agenten korrigiert`));
    for (const f of round.errors) fixed.appendChild(el("div", "finding fixed", `✓ ${f.issue}`));
    box.appendChild(fixed);
  }
}

function renderControls() {
  const med = state.sources.find((s) => s.id === "med-entlassplan");
  const release = $("release");
  release.disabled = state.busy || med.status !== "unreleased" || !!state.approval || !state.draft;
  release.textContent = med.status === "unreleased" ? "⚡ Demo-Ereignis: Stationsapotheke gibt Medikationsplan frei" : "✓ Medikationsplan freigegeben";
  release.classList.toggle("done", med.status !== "unreleased");
  const ready = state.phase === "ready" && !state.busy && !state.approval && state.review;
  $("approve").disabled = !ready;
  $("approve").hidden = !!state.approval;
  $("dispatch").hidden = !state.approval;
  $("approve-title").textContent = state.approval ? "Versand" : "Ärztliche Freigabe";
  $("approve-hint").textContent = state.approval ? "Freigegeben. Versandwege (Simulation):" : state.busy ? "Wartet auf die Agenten …" : "Einzige menschliche Entscheidung im Ablauf.";
  for (const btn of document.querySelectorAll("#dispatch button")) {
    const sent = state.dispatch?.[btn.dataset.channel];
    btn.classList.toggle("sent", !!sent);
    btn.querySelector(".done-at").textContent = sent ? `✓ ${clock(sent)}` : "";
  }
  $("prepare").disabled = state.busy;
  $("reset").disabled = state.busy;
  if (state.phase === "failed" && state.error) {
    $("approve-hint").textContent = `Fehler: ${state.error}`;
  }
}

// ---------- Actions ----------
$("prepare").onclick = async () => { $("prepare").disabled = true; try { state = await call("/api/prepare"); render(); } catch (e) { alert(e.message); } refresh(); };
$("release").onclick = async () => { $("release").disabled = true; try { state = await call("/api/events/medication-released"); render(); } catch (e) { alert(e.message); } refresh(); };
$("reset").onclick = async () => { if (!confirm("Demo zurücksetzen? Entwurf und Protokoll werden gelöscht.")) return; try { await call("/api/reset"); } catch (e) { alert(e.message); } renderedEvents = 0; refresh(); };
document.querySelectorAll("#dispatch button").forEach((btn) => {
  btn.onclick = async () => {
    try { state = await call(`/api/dispatch/${btn.dataset.channel}`); render(); } catch (e) { alert(e.message); return; }
    if (btn.dataset.channel === "print") window.print();
  };
});

$("approve").onclick = () => {
  const box = $("approve-summary");
  box.innerHTML = "";
  const points = state.draft.open_points;
  box.append(el("p", "", `Entwurf v${state.draft.version} · Prüf-Agent: ${state.review.verdict}.`));
  if (points.length) {
    box.append(el("p", "", "Im Brief dokumentierte offene Punkte:"));
    const ul = el("ul"); points.forEach((pt) => ul.appendChild(el("li", "", pt.title))); box.appendChild(ul);
  }
  $("confirm").checked = false;
  $("approve-submit").disabled = true;
  $("approve-error").textContent = "";
  $("approve-dialog").showModal();
};
$("confirm").onchange = () => { $("approve-submit").disabled = !$("confirm").checked; };
$("approve-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    state = await call("/api/approve", { physician: $("physician").value, confirmed: $("confirm").checked });
    $("approve-dialog").close();
    render();
  } catch (err) { $("approve-error").textContent = err.message; }
};

async function openSource(id) {
  const s = await (await fetch(`/api/sources/${id}`)).json();
  $("source-system").textContent = s.system; $("source-system").style.background = SYS[s.system];
  $("source-title").textContent = ` ${s.title}`;
  $("source-meta").textContent = `${state.systems[s.system]} · ${s.date} · ${STATUS[s.status] || s.status}`;
  $("source-text").textContent = s.text || "Inhalt nicht freigegeben.";
  $("source-dialog").showModal();
}
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => b.closest("dialog").close()));

refresh();
