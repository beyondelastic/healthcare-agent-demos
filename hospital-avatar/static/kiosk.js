// Hospital welcome kiosk: talk to the Foundry voice agent "Nia" (avatar via WebRTC), see routes and check-in.
const SAMPLE_RATE = 24000;
const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";

const UI = {
  de: { busy: "Nia ist gleich wieder für Sie da – bitte in einer halben Minute erneut starten.", here: "Sie sind hier: Haupteingang", idle: "Tippen Sie auf das Mikrofon und sprechen Sie mich an – in Ihrer Sprache.", start: "Gespräch starten", stop: "Gespräch beenden",
        connecting: "Nia wird verbunden …", listening: "Ich höre zu.", ended: "Gespräch beendet.", noAvatar: "Avatar nicht verfügbar – Sprache läuft weiter.",
        demo: "Demo mit fiktiven Daten · Keine medizinische Beratung · Bei Notfällen wenden Sie sich an das Personal", ask: "Oder tippen …", send: "Senden",
        hello: "Wie kann ich Ihnen helfen?", tiles: [["🗓️", "Termin anmelden", "Ich habe heute einen Termin und möchte mich anmelden."], ["🧭", "Weg finden", "Wo ist die Radiologie?"],
        ["🕑", "Besuchszeiten", "Wann sind die Besuchszeiten?"], ["☕", "Cafeteria", "Wo ist die Cafeteria und wann hat sie geöffnet?"]],
        route: "Ihr Weg", floor: "Ebene", room: "Raum", walk: "ca. {m} Min. zu Fuß", stepFree: "Stufenlos", checkedIn: "Sie sind angemeldet", number: "Ihre Wartenummer",
        at: "Termin um", bring: "Bitte halten Sie bereit", notified: "Die Ambulanz weiß, dass Sie da sind.", early: "Sie sind früh dran – bitte nehmen Sie im Wartebereich Platz.",
        late: "Kein Problem – das Team weiß Bescheid.", staff: "Eine Kollegin der Information kommt zu Ihnen", staffText: "Bitte warten Sie hier am Kiosk.",
        alarm: "Hilfe ist unterwegs", alarmText: "Bitte bleiben Sie hier. Das Personal ist alarmiert.", notFound: "Kein Termin gefunden", notFoundText: "Bitte prüfen Sie die Angaben – oder ich rufe eine Kollegin.",
        you: "Sie" },
  en: { busy: "Nia will be back in a moment – please start again in half a minute.", here: "You are here: main entrance", idle: "Tap the microphone and talk to me – in your language.", start: "Start conversation", stop: "End conversation",
        connecting: "Connecting Nia …", listening: "I'm listening.", ended: "Conversation ended.", noAvatar: "Avatar unavailable – voice continues.",
        demo: "Demo with fictional data · No medical advice · In an emergency, contact staff", ask: "Or type …", send: "Send",
        hello: "How can I help you?", tiles: [["🗓️", "Check in", "I have an appointment today and would like to check in."], ["🧭", "Find my way", "Where is radiology?"],
        ["🕑", "Visiting hours", "What are the visiting hours?"], ["☕", "Cafeteria", "Where is the cafeteria and when is it open?"]],
        route: "Your way", floor: "Floor", room: "Room", walk: "about {m} min walk", stepFree: "Step-free", checkedIn: "You are checked in", number: "Your waiting number",
        at: "Appointment at", bring: "Please have ready", notified: "The clinic knows you are here.", early: "You are early – please take a seat in the waiting area.",
        late: "No problem – the team has been informed.", staff: "A colleague from the information desk is coming", staffText: "Please wait here at the kiosk.",
        alarm: "Help is on the way", alarmText: "Please stay here. Staff have been alerted.", notFound: "No appointment found", notFoundText: "Please check your details – or I can call a colleague.",
        you: "You" },
  tr: { busy: "Nia birazdan tekrar burada – lütfen yarım dakika sonra yeniden başlatın.", here: "Buradasınız: ana giriş", idle: "Mikrofona dokunun ve benimle kendi dilinizde konuşun.", start: "Konuşmayı başlat", stop: "Konuşmayı bitir",
        connecting: "Nia bağlanıyor …", listening: "Dinliyorum.", ended: "Konuşma sona erdi.", noAvatar: "Avatar kullanılamıyor – ses devam ediyor.",
        demo: "Kurgusal verilerle demo · Tıbbi danışmanlık değildir · Acil durumda personele başvurun", ask: "Veya yazın …", send: "Gönder",
        hello: "Size nasıl yardımcı olabilirim?", tiles: [["🗓️", "Randevu kaydı", "Bugün randevum var, kayıt olmak istiyorum."], ["🧭", "Yol bul", "Radyoloji nerede?"],
        ["🕑", "Ziyaret saatleri", "Ziyaret saatleri ne zaman?"], ["☕", "Kafeterya", "Kafeterya nerede ve ne zaman açık?"]],
        route: "Yolunuz", floor: "Kat", room: "Oda", walk: "yaklaşık {m} dk yürüme", stepFree: "Basamaksız", checkedIn: "Kaydınız yapıldı", number: "Sıra numaranız",
        at: "Randevu saati", bring: "Lütfen hazır bulundurun", notified: "Poliklinik geldiğinizi biliyor.", early: "Erken geldiniz – lütfen bekleme alanında oturun.",
        late: "Sorun değil – ekip bilgilendirildi.", staff: "Danışmadan bir çalışan geliyor", staffText: "Lütfen burada, kioskta bekleyin.",
        alarm: "Yardım geliyor", alarmText: "Lütfen burada kalın. Personel uyarıldı.", notFound: "Randevu bulunamadı", notFoundText: "Lütfen bilgilerinizi kontrol edin – ya da bir çalışanı çağırabilirim.",
        you: "Siz" },
  ar: { busy: "ستعود نيا بعد لحظات – يرجى البدء مجددًا بعد نصف دقيقة.", here: "أنت هنا: المدخل الرئيسي", idle: "المس الميكروفون وتحدث معي بلغتك.", start: "ابدأ المحادثة", stop: "إنهاء المحادثة",
        connecting: "جارٍ توصيل نيا …", listening: "أنا أستمع.", ended: "انتهت المحادثة.", noAvatar: "الصورة الرمزية غير متاحة – الصوت مستمر.",
        demo: "عرض توضيحي ببيانات خيالية · ليست استشارة طبية · في حالات الطوارئ توجه إلى الموظفين", ask: "أو اكتب …", send: "إرسال",
        hello: "كيف يمكنني مساعدتك؟", tiles: [["🗓️", "تسجيل الموعد", "لدي موعد اليوم وأريد التسجيل."], ["🧭", "إيجاد الطريق", "أين قسم الأشعة؟"],
        ["🕑", "مواعيد الزيارة", "ما هي مواعيد الزيارة؟"], ["☕", "الكافتيريا", "أين الكافتيريا ومتى تفتح؟"]],
        route: "طريقك", floor: "الطابق", room: "الغرفة", walk: "حوالي {m} دقائق سيرًا", stepFree: "بدون درج", checkedIn: "تم تسجيلك", number: "رقم الانتظار",
        at: "الموعد الساعة", bring: "يرجى تجهيز", notified: "العيادة تعلم بوصولك.", early: "وصلت مبكرًا – يرجى الجلوس في منطقة الانتظار.",
        late: "لا مشكلة – تم إبلاغ الفريق.", staff: "زميلة من الاستعلامات قادمة إليك", staffText: "يرجى الانتظار هنا عند الشاشة.",
        alarm: "المساعدة في الطريق", alarmText: "يرجى البقاء هنا. تم تنبيه الموظفين.", notFound: "لم يتم العثور على موعد", notFoundText: "يرجى التحقق من بياناتك – أو يمكنني استدعاء زميلة.",
        you: "أنت" },
  uk: { busy: "Нія зараз повернеться – будь ласка, почніть знову за пів хвилини.", here: "Ви тут: головний вхід", idle: "Торкніться мікрофона й говоріть зі мною своєю мовою.", start: "Почати розмову", stop: "Завершити розмову",
        connecting: "Підключення Ніи …", listening: "Я слухаю.", ended: "Розмову завершено.", noAvatar: "Аватар недоступний – голос працює.",
        demo: "Демо з вигаданими даними · Не є медичною консультацією · У разі надзвичайної ситуації зверніться до персоналу", ask: "Або введіть …", send: "Надіслати",
        hello: "Чим я можу допомогти?", tiles: [["🗓️", "Реєстрація", "У мене сьогодні прийом, я хочу зареєструватися."], ["🧭", "Знайти шлях", "Де радіологія?"],
        ["🕑", "Години відвідування", "Коли години відвідування?"], ["☕", "Кафетерій", "Де кафетерій і коли він відкритий?"]],
        route: "Ваш шлях", floor: "Поверх", room: "Кімната", walk: "близько {m} хв пішки", stepFree: "Без сходів", checkedIn: "Вас зареєстровано", number: "Ваш номер черги",
        at: "Прийом о", bring: "Будь ласка, підготуйте", notified: "Амбулаторія знає, що ви прийшли.", early: "Ви рано – будь ласка, зачекайте в зоні очікування.",
        late: "Нічого страшного – команду повідомлено.", staff: "До вас іде співробітниця інформаційної служби", staffText: "Будь ласка, зачекайте тут біля кіоску.",
        alarm: "Допомога вже йде", alarmText: "Будь ласка, залишайтеся тут. Персонал сповіщено.", notFound: "Прийом не знайдено", notFoundText: "Перевірте дані – або я покличу співробітницю.",
        you: "Ви" },
};
const NAMES = { de: "Deutsch", en: "English", tr: "Türkçe", ar: "العربية", uk: "Українська" };
const t = (key) => UI[lang][key];

let lang = "de", campus = null, ws = null, ctx = null, mic = null, micSource = null, pc = null;
let avatarLive = false, avatarFailed = false, avatarTimer = null, playTime = 0, playing = [];
let current = { kind: "welcome" };

fetch("/api/campus").then((r) => r.json()).then((data) => { campus = data; renderStatic(); renderStage(); });
renderLanguages();
renderStatic();
renderStage();
setInterval(renderClock, 30000);

// ---------- Static UI ----------
function renderLanguages() {
  $("languages").innerHTML = "";
  for (const [code, name] of Object.entries(NAMES)) {
    const b = document.createElement("button");
    b.textContent = name;
    b.className = code === lang ? "active" : "";
    b.onclick = () => setLanguage(code);
    $("languages").appendChild(b);
  }
}

function setLanguage(code) {
  if (code === lang) return;
  lang = code;
  renderLanguages();
  renderStatic();
  renderStage();
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "language", code }));
}

function renderStatic() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  $("here-label").textContent = t("here");
  $("idle-text").textContent = t("idle");
  $("mic-label").textContent = ws ? t("stop") : t("start");
  $("demo-note").textContent = t("demo");
  $("question").placeholder = t("ask");
  $("send").textContent = t("send");
  if (avatarLive && ws) setStatus(mic ? t("listening") : "");
  renderClock();
}

function renderClock() {
  if (!campus) return;
  const now = campus.demo_now;
  const weekday = { de: now.weekday, en: "Tuesday", tr: "Salı", ar: "الثلاثاء", uk: "Вівторок" }[lang];
  $("clock").textContent = `${weekday}, ${now.date} · ${now.time}`;
}

// ---------- Session ----------
$("mic").onclick = () => (ws ? stopSession() : startSession());
$("ask").onsubmit = (e) => { e.preventDefault(); const text = $("question").value.trim(); if (text) { $("question").value = ""; sendText(text); } };

function sendText(text) {
  const now = Date.now();
  if (text === lastText.text && now - lastText.at < 1500) return;  // ignore double taps
  lastText = { text, at: now };
  showLine("visitor", text);
  if (ws?.readyState === WebSocket.OPEN && (avatarLive || avatarFailed)) ws.send(JSON.stringify({ type: "text", text }));
  else { pendingText = text; if (!ws && !starting) startSession(); }
}
let pendingText = null, lastText = { text: "", at: 0 }, starting = false;

async function startSession() {
  if (ws || starting) return;
  starting = true;
  clearTimeout(idleTimer);
  ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
  try {
    await ctx.audioWorklet.addModule("/static/mic-worklet.js");
    mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    micSource = ctx.createMediaStreamSource(mic);
  } catch { mic = null; }
  avatarLive = avatarFailed = false;
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?lang=${lang}`);
  ws = socket;
  starting = false;
  socket.binaryType = "arraybuffer";
  socket.onmessage = (e) => (typeof e.data === "string" ? onEvent(JSON.parse(e.data)) : playAudio(e.data));
  socket.onclose = () => { if (ws === socket) stopSession(); };
  $("mic").classList.add("active");
  $("mic").textContent = "■";
  $("mic-label").textContent = t("stop");
  setStatus(t("connecting"));
  // If the avatar video doesn't start, continue with voice only.
  avatarTimer = setTimeout(() => { if (!avatarLive) fallBackToVoice(); }, 15000);
}

function stopSession() {
  if (!ws) return;
  const socket = ws;
  ws = null;
  socket.close();
  clearTimeout(avatarTimer);
  pc?.close(); pc = null;
  mic?.getTracks().forEach((track) => track.stop());
  ctx?.close();
  ctx = mic = micSource = null;
  avatarLive = false;
  stopPlayback();
  $("avatar-video").srcObject = null;
  $("avatar-frame").classList.remove("live");
  $("mic").classList.remove("active");
  $("mic").textContent = "🎙️";
  $("mic-label").textContent = t("start");
  setStatus(t("ended"));
  clearTimeout(idleTimer);
  idleTimer = setTimeout(goHome, 45000);  // privacy: the next visitor doesn't see the previous check-in
}

let idleTimer = null;
function goHome() {
  if (ws) return;
  current = { kind: "welcome" };
  $("subtitle").innerHTML = "";
  setStatus("");
  renderStage();
}
document.querySelector(".logo").onclick = goHome;

function startCapture() {
  if (!micSource || !ctx) return;
  const node = new AudioWorkletNode(ctx, "mic-capture", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1, channelCountMode: "explicit" });
  node.port.onmessage = (e) => ws?.readyState === WebSocket.OPEN && ws.send(e.data);
  micSource.connect(node);
}

function onEvent(msg) {
  switch (msg.type) {
    case "config": startCapture(); break;
    case "ice_servers": connectAvatar(msg.servers); break;
    case "avatar_answer": acceptAnswer(msg.sdp); break;
    case "status": if (msg.text === "ended") setStatus(t("ended")); break;
    case "transcript": showLine(msg.role, msg.text); break;
    case "tool": onTool(msg); break;
    case "rule_alarm": current = { kind: "alarm" }; renderStage(); break;
    case "interrupt": stopPlayback(); break;
    case "error": setStatus(/rate.limit/i.test(msg.text) ? t("busy") : msg.text, true); break;
  }
}

// ---------- Avatar (WebRTC) ----------
async function connectAvatar(servers) {
  try {
    pc = new RTCPeerConnection({ iceServers: servers });
    pc.ontrack = (event) => {
      if (event.track.kind === "video") {
        const video = $("avatar-video");
        video.srcObject = new MediaStream([event.track]);
        video.onplaying = () => onAvatarLive();
      } else {
        $("avatar-audio").srcObject = new MediaStream([event.track]);
      }
    };
    pc.addTransceiver("video", { direction: "sendrecv" });
    pc.addTransceiver("audio", { direction: "sendrecv" });
    let sent = false;
    const send = () => {
      if (sent || !ws) return;
      sent = true;
      ws.send(JSON.stringify({ type: "avatar_offer", sdp: btoa(JSON.stringify(pc.localDescription)) }));
    };
    pc.onicecandidate = (event) => { if (!event.candidate) send(); };
    await pc.setLocalDescription(await pc.createOffer());
    setTimeout(send, 2000);
  } catch (err) {
    console.error(err);
    fallBackToVoice();
  }
}

async function acceptAnswer(sdp) {
  try { await pc.setRemoteDescription(new RTCSessionDescription(JSON.parse(atob(sdp)))); }
  catch (err) { console.error(err); fallBackToVoice(); }
}

function onAvatarLive() {
  if (avatarLive) return;
  avatarLive = true;
  clearTimeout(avatarTimer);
  $("avatar-frame").classList.add("live");
  setStatus(mic ? t("listening") : "");
  ws?.send(JSON.stringify({ type: "avatar_ready", greet: !pendingText }));
  if (pendingText) { ws.send(JSON.stringify({ type: "text", text: pendingText })); pendingText = null; }
}

function fallBackToVoice() {
  if (avatarLive || avatarFailed || !ws) return;
  avatarFailed = true;
  setStatus(t("noAvatar"), true);
  ws.send(JSON.stringify({ type: "no_avatar", greet: !pendingText }));
  if (pendingText) { ws.send(JSON.stringify({ type: "text", text: pendingText })); pendingText = null; }
}

// Voice-only fallback: play PCM audio from the relay (with the avatar, voice comes over WebRTC).
function playAudio(data) {
  if (!avatarFailed || !ctx) return;
  const pcm = new Int16Array(data);
  const buffer = ctx.createBuffer(1, pcm.length, SAMPLE_RATE);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) samples[i] = pcm[i] / 0x8000;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  playTime = Math.max(playTime, ctx.currentTime);
  source.start(playTime);
  playTime += buffer.duration;
  playing.push(source);
  source.onended = () => { playing = playing.filter((s) => s !== source); };
}

function stopPlayback() {
  playing.forEach((s) => { try { s.stop(); } catch {} });
  playing = [];
  playTime = 0;
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

function showLine(role, text) {
  if (!text) return;
  const line = document.createElement("div");
  line.className = `line ${role}`;
  line.textContent = role === "visitor" ? `${t("you")}: ${text}` : text;
  const box = $("subtitle");
  box.appendChild(line);
  while (box.children.length > 3) box.firstChild.remove();
}

// ---------- Stage (right side) ----------
function onTool(msg) {
  const r = msg.result;
  // The screen follows the language the visitor speaks (set by the agent in each tool call).
  if (msg.args.language && UI[msg.args.language] && msg.args.language !== lang) {
    lang = msg.args.language; renderLanguages(); renderStatic();
  }
  if (msg.name === "find_location" && r.ok) current = { kind: "route", route: r.route };
  else if (msg.name === "check_in_appointment") current = r.ok ? { kind: "checkin", checkin: r } : { kind: "notfound" };
  else if (msg.name === "get_visitor_information" && r.ok) current = { kind: "info", info: r };
  else if (msg.name === "call_staff" && r.ok) current = current.kind === "alarm" || r.urgency === "urgent" && msg.args.need === "unwell" ? { kind: "alarm" } : { kind: "staff" };
  else return;
  renderStage();
}

function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

function renderStage() {
  const stage = $("stage");
  stage.innerHTML = "";
  stage.className = `stage ${current.kind}`;
  if (current.kind === "welcome") {
    stage.appendChild(el("h1", "", t("hello")));
    const grid = el("div", "tiles");
    for (const [icon, label, text] of t("tiles")) {
      const tile = el("button", "tile");
      tile.append(el("span", "icon", icon), el("span", "", label));
      tile.onclick = () => sendText(text);
      grid.appendChild(tile);
    }
    stage.appendChild(grid);
  } else if (current.kind === "route") {
    stage.append(routeCard(current.route));
  } else if (current.kind === "checkin") {
    const c = current.checkin;
    const ticket = el("div", "ticket");
    const head = el("div", "ticket-head");
    head.append(el("div", "ok", `✓ ${t("checkedIn")}`), el("div", "time", `${t("at")} ${c.appointment_time}`));
    const number = el("div", "number");
    number.append(el("small", "", t("number")), el("strong", "", c.waiting_number));
    const where = el("div", "where", `${c.route.name} · ${c.route.building.split("·")[0].trim()} · ${t("floor")} ${c.route.floor} · ${c.route.room}`);
    const bring = el("div", "bring");
    bring.append(el("small", "", t("bring")), el("span", "", c.bring.join(" · ")));
    const hint = el("div", "hint", `${t("notified")} ${c.arrival === "early" ? t("early") : c.arrival === "late" ? t("late") : ""}`);
    ticket.append(head, number, where, bring, hint);
    stage.append(ticket, routeCard(c.route, true));
  } else if (current.kind === "info") {
    const card = el("div", "info-card");
    card.append(el("h2", "", current.info.title), el("p", "", current.info.text));
    stage.appendChild(card);
  } else if (current.kind === "staff" || current.kind === "alarm" || current.kind === "notfound") {
    const kind = current.kind;
    const card = el("div", `notice-card ${kind}`);
    const [title, text, icon] = kind === "alarm" ? [t("alarm"), t("alarmText"), "🚨"] : kind === "staff" ? [t("staff"), t("staffText"), "🙋"] : [t("notFound"), t("notFoundText"), "🔎"];
    card.append(el("div", "big-icon", icon), el("h2", "", title), el("p", "", text));
    stage.appendChild(card);
  }
}

function routeCard(route, compact = false) {
  const card = el("div", `route-card${compact ? " compact" : ""}`);
  const head = el("div", "route-head");
  const title = el("div", "");
  title.append(el("small", "", t("route")), el("h2", "", route.name));
  const badges = el("div", "badges");
  badges.append(el("span", "badge floor", `${t("floor")} ${route.floor}`), el("span", "badge", route.room), el("span", "badge", t("walk").replace("{m}", route.walk_minutes)));
  if (route.barrier_free) badges.append(el("span", "badge step-free", `♿ ${t("stepFree")}`));
  head.append(title, badges);
  card.append(head, campusMap(route.id));
  if (!compact) {
    const steps = el("ol", "steps");
    route.steps.forEach((s) => steps.appendChild(el("li", "", s)));
    if (route.barrier_free) steps.appendChild(el("li", "step-free-note", route.barrier_free));
    card.appendChild(steps);
  }
  return card;
}

function campusMap(locationId) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 1000 620");
  svg.classList.add("map");
  if (!campus) return svg;
  const add = (tag, attrs, text) => { const n = document.createElementNS(SVG, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; svg.appendChild(n); return n; };
  const target = campus.locations.find((l) => l.id === locationId);
  for (const s of campus.streets) {
    add("line", { x1: s.line[0][0], y1: s.line[0][1], x2: s.line[1][0], y2: s.line[1][1], class: "street" });
    add("text", { x: 60, y: 512, class: "street-label" }, s.name);
  }
  add("line", { x1: 130, y1: 360, x2: 930, y2: 360, class: "corridor" });
  add("text", { x: 655, y: 352, class: "corridor-label" }, "Magistrale");
  for (const b of campus.buildings) {
    const [x, y, w, h] = b.rect;
    const active = target && target.building === b.id;
    add("rect", { x, y, width: w, height: h, rx: 14, class: `building${active ? " active" : ""}${b.id === "D" ? " emergency" : ""}` });
    add("text", { x: x + 14, y: y + 26, class: "building-id" }, b.id.length === 1 && "ABCD".includes(b.id) ? b.id : "");
    add("text", { x: x + (("ABCD".includes(b.id)) ? 40 : 12), y: y + 26, class: "building-name" }, b.name.replace(/^Gebäude [A-D] · /, ""));
  }
  if (target) {
    const points = target.path.map((p) => p.join(",")).join(" ");
    add("polyline", { points, class: "path-shadow" });
    const path = add("polyline", { points, class: "path" });
    const length = target.path.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - target.path[i][0], p[1] - target.path[i][1]), 0);
    path.style.strokeDasharray = length;
    path.style.strokeDashoffset = length;
    const [px, py] = target.pin;
    add("circle", { cx: px, cy: py, r: 16, class: "pin" });
    add("text", { x: px, y: py + 5, class: "pin-label", "text-anchor": "middle" }, String(target.floor));
  }
  const [kx, ky] = campus.kiosk.point;
  add("circle", { cx: kx, cy: ky, r: 20, class: "here-pulse" });
  add("circle", { cx: kx, cy: ky, r: 9, class: "here" });
  return svg;
}
