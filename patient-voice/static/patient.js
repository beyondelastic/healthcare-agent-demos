// Patient page: talk (or type) to the discharge voice agent in the selected language.
// Audio handling adapted from beyondelastic/foundry-voice-agent (MIT).

const SAMPLE_RATE = 24000;
const $ = (id) => document.getElementById(id);

const UI = {
  de: { medTitle: "Ihr Medikationsplan – unverändert aus dem freigegebenen Brief", medCols: ["Medikament", "Stärke", "Einnahme", "Hinweis"], guard: "Antwort gestoppt", guardText: "Sie wich vom freigegebenen Brief ab. Es gilt der Medikationsplan oben. Das Team wurde informiert.", guardFinal: "Bitte halten Sie sich an Ihren Brief. Das Behandlungsteam ruft Sie zurück.", reconnecting: "Verbindung wird wiederhergestellt …", title: "Fragen zu Ihrem Entlassbrief", discharge: "Entlassung am", approved: "Ärztlich freigegeben",
        demo: "Demo: Zugang per QR-Code, Identitätsprüfung simuliert. Alle Daten sind fiktiv.",
        start: "Gespräch starten", stop: "Gespräch beenden", connecting: "Verbinde …", listening: "Ich höre zu. Sprechen Sie einfach.",
        ended: "Gespräch beendet.", ask: "Oder Frage eintippen …", send: "Senden",
        hint: "Fragen Sie in Ihrer Sprache, zum Beispiel:", examples: ["Welche Tabletten muss ich wann nehmen?", "Was bedeutet „1-0-0“ in meinem Brief?", "Wann ist mein nächster Termin?", "Worauf muss ich zu Hause achten?"],
        sos: "Notfall: 112", disclaimer: "Kein Ersatz für ärztliche Beratung.", letter: "Brief anzeigen",
        source: "Aus Ihrem Entlassbrief", callback: "Anfrage an das Behandlungsteam gesendet", callbackText: "Das Team meldet sich bei Ihnen. Dies ist kein Notdienst.",
        emergency: "Bitte rufen Sie jetzt den Notruf 112.", emergencyText: "Das Behandlungsteam wurde zusätzlich informiert.", micError: "Kein Mikrofon verfügbar. Sie können Ihre Frage eintippen." },
  en: { medTitle: "Your medication plan – unchanged from the approved letter", medCols: ["Medicine", "Strength", "How to take", "Note"], guard: "Answer stopped", guardText: "It did not match your approved letter. The medication plan above applies. Your care team has been informed.", guardFinal: "Please follow your letter. Your care team will call you back.", reconnecting: "Reconnecting …", title: "Questions about your discharge letter", discharge: "Discharged on", approved: "Approved by your doctor",
        demo: "Demo: access via QR code, identity check simulated. All data is fictional.",
        start: "Start conversation", stop: "End conversation", connecting: "Connecting …", listening: "I'm listening. Just speak.",
        ended: "Conversation ended.", ask: "Or type your question …", send: "Send",
        hint: "Ask in your language, for example:", examples: ["Which tablets do I take, and when?", "What does “1-0-0” mean in my letter?", "When is my next appointment?", "What should I watch out for at home?"],
        sos: "Emergency: 112", disclaimer: "Not a substitute for medical advice.", letter: "Show letter",
        source: "From your discharge letter", callback: "Request sent to your care team", callbackText: "The team will contact you. This is not an emergency service.",
        emergency: "Please call the emergency number 112 now.", emergencyText: "Your care team has also been informed.", micError: "No microphone available. You can type your question." },
  tr: { medTitle: "İlaç planınız – onaylı mektuptan değiştirilmeden", medCols: ["İlaç", "Doz", "Kullanım", "Not"], guard: "Yanıt durduruldu", guardText: "Onaylı mektubunuzla uyuşmadı. Yukarıdaki ilaç planı geçerlidir. Tedavi ekibi bilgilendirildi.", guardFinal: "Lütfen mektubunuza uyun. Tedavi ekibi sizi arayacak.", reconnecting: "Bağlantı yeniden kuruluyor …", title: "Taburcu mektubunuzla ilgili sorular", discharge: "Taburcu tarihi", approved: "Doktorunuz tarafından onaylandı",
        demo: "Demo: QR kod ile erişim, kimlik doğrulama simüle edildi. Tüm veriler kurgusaldır.",
        start: "Konuşmayı başlat", stop: "Konuşmayı bitir", connecting: "Bağlanıyor …", listening: "Dinliyorum. Konuşabilirsiniz.",
        ended: "Konuşma sona erdi.", ask: "Veya sorunuzu yazın …", send: "Gönder",
        hint: "Kendi dilinizde sorun, örneğin:", examples: ["Hangi ilaçları ne zaman almalıyım?", "Mektubumdaki „1-0-0“ ne anlama geliyor?", "Bir sonraki randevum ne zaman?", "Evde nelere dikkat etmeliyim?"],
        sos: "Acil: 112", disclaimer: "Tıbbi danışmanlığın yerini tutmaz.", letter: "Mektubu göster",
        source: "Taburcu mektubunuzdan", callback: "Tedavi ekibine talep gönderildi", callbackText: "Ekip sizinle iletişime geçecek. Bu bir acil servis değildir.",
        emergency: "Lütfen şimdi 112'yi arayın.", emergencyText: "Tedavi ekibi ayrıca bilgilendirildi.", micError: "Mikrofon yok. Sorunuzu yazabilirsiniz." },
  ar: { medTitle: "خطة أدويتك – كما وردت في الرسالة المعتمدة دون تغيير", medCols: ["الدواء", "الجرعة", "طريقة التناول", "ملاحظة"], guard: "تم إيقاف الإجابة", guardText: "لم تتطابق مع رسالتك المعتمدة. خطة الأدوية أعلاه هي المعتمدة. تم إبلاغ فريق العلاج.", guardFinal: "يرجى الالتزام برسالتك. سيتصل بك فريق العلاج.", reconnecting: "جارٍ إعادة الاتصال …", title: "أسئلة حول رسالة الخروج", discharge: "تاريخ الخروج", approved: "معتمدة من الطبيب",
        demo: "عرض توضيحي: الدخول عبر رمز QR، والتحقق من الهوية محاكى. جميع البيانات خيالية.",
        start: "ابدأ المحادثة", stop: "إنهاء المحادثة", connecting: "جارٍ الاتصال …", listening: "أنا أستمع. تحدث فقط.",
        ended: "انتهت المحادثة.", ask: "أو اكتب سؤالك …", send: "إرسال",
        hint: "اسأل بلغتك، مثلاً:", examples: ["ما الأدوية التي يجب أن أتناولها ومتى؟", "ماذا يعني „1-0-0“ في رسالتي؟", "متى موعدي القادم؟", "ما الذي يجب أن أنتبه إليه في المنزل؟"],
        sos: "طوارئ: 112", disclaimer: "لا يغني عن الاستشارة الطبية.", letter: "عرض الرسالة",
        source: "من رسالة الخروج", callback: "تم إرسال طلب إلى فريق العلاج", callbackText: "سيتواصل معك الفريق. هذه ليست خدمة طوارئ.",
        emergency: "يرجى الاتصال برقم الطوارئ 112 الآن.", emergencyText: "تم إبلاغ فريق العلاج أيضاً.", micError: "لا يوجد ميكروفون. يمكنك كتابة سؤالك." },
  uk: { medTitle: "Ваш план ліків – без змін із затвердженого листа", medCols: ["Ліки", "Доза", "Прийом", "Примітка"], guard: "Відповідь зупинено", guardText: "Вона не відповідала затвердженому листу. Діє план ліків вище. Команду лікування повідомлено.", guardFinal: "Будь ласка, дотримуйтеся листа. Команда лікування вам зателефонує.", reconnecting: "Відновлення з'єднання …", title: "Запитання щодо виписки", discharge: "Дата виписки", approved: "Затверджено лікарем",
        demo: "Демо: доступ через QR-код, перевірка особи змодельована. Усі дані вигадані.",
        start: "Почати розмову", stop: "Завершити розмову", connecting: "З'єднання …", listening: "Я слухаю. Просто говоріть.",
        ended: "Розмову завершено.", ask: "Або введіть запитання …", send: "Надіслати",
        hint: "Запитуйте своєю мовою, наприклад:", examples: ["Які ліки і коли мені приймати?", "Що означає „1-0-0“ у моєму листі?", "Коли мій наступний прийом?", "На що звернути увагу вдома?"],
        sos: "Екстрено: 112", disclaimer: "Не замінює консультацію лікаря.", letter: "Показати лист",
        source: "З вашої виписки", callback: "Запит надіслано команді лікування", callbackText: "Команда зв'яжеться з вами. Це не екстрена служба.",
        emergency: "Будь ласка, негайно телефонуйте 112.", emergencyText: "Команду лікування також повідомлено.", micError: "Мікрофон недоступний. Ви можете ввести запитання." },
};
const NAMES = { de: "Deutsch", en: "English", tr: "Türkçe", ar: "العربية", uk: "Українська" };

let lang = "de", letter = null, ws = null, ctx = null, mic = null, micSource = null, micMeter = null, voiceMeter = null;
let emergencyShown = false, medicationCardShown = false;
let voiceBus = null, playTime = 0, playing = [], muted = false, pendingSources = [], readySources = [], queuedText = null, withMic = false;

const t = (key) => UI[lang][key];

// ---------- Static content ----------
fetch("/api/letter").then((r) => r.json()).then((data) => { letter = data; renderStatic(); });
renderLanguages();
renderStatic();

function renderLanguages() {
  $("languages").innerHTML = "";
  for (const [code, name] of Object.entries(NAMES)) {
    const button = document.createElement("button");
    button.textContent = name;
    button.className = code === lang ? "active" : "";
    button.onclick = () => setLanguage(code);
    $("languages").appendChild(button);
  }
}

function setLanguage(code) {
  if (code === lang) return;
  lang = code;
  renderLanguages();
  renderStatic();
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "language", code }));
}

function renderStatic() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  $("title").textContent = t("title");
  $("demo-note").textContent = t("demo");
  $("mic-label").textContent = ws ? t("stop") : t("start");
  $("question").placeholder = t("ask");
  $("send").textContent = t("send");
  $("sos").textContent = t("sos");
  $("disclaimer").textContent = t("disclaimer");
  $("show-letter").textContent = t("letter");
  if ($("hint")) {
    $("hint").innerHTML = "";
    $("hint").append(t("hint"));
    const list = document.createElement("ul");
    t("examples").forEach((example) => { const li = document.createElement("li"); li.textContent = example; list.appendChild(li); });
    $("hint").appendChild(list);
  }
  if (!letter) return;
  $("hospital").textContent = letter.hospital;
  $("patient-name").textContent = letter.patient.name;
  $("discharge").textContent = `${t("discharge")} ${letter.discharge_date}`;
  $("approved").textContent = `${t("approved")} · ${letter.approval.approved_at}`;
}

// ---------- Session ----------
$("mic").onclick = () => (ws ? stopSession() : startSession(true));
$("ask").onsubmit = (e) => {
  e.preventDefault();
  const text = $("question").value.trim();
  if (!text) return;
  $("question").value = "";
  addBubble("patient", text);
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "text", text }));
  else { queuedText = text; if (!ws) startSession(false); }
};

async function startSession(useMic) {
  withMic = useMic;
  ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
  voiceBus = ctx.createGain();
  voiceBus.connect(ctx.destination);
  voiceMeter = meter(voiceBus);
  if (useMic) {
    try {
      await ctx.audioWorklet.addModule("/static/mic-worklet.js");
      mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      micSource = ctx.createMediaStreamSource(mic);
      micMeter = meter(micSource);
    } catch (err) {
      setStatus(t("micError"), true);
      withMic = false;
    }
  }
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?lang=${lang}&greet=${queuedText ? 0 : 1}`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (e) => (typeof e.data === "string" ? onEvent(JSON.parse(e.data)) : playAudio(e.data));
  ws.onclose = () => stopSession();
  $("mic").classList.add("active");
  $("mic").textContent = "■";
  $("mic-label").textContent = t("stop");
  setStatus(t("connecting"));
  animate();
}

function startCapture() {
  if (!withMic || !micSource) return;
  const capture = new AudioWorkletNode(ctx, "mic-capture", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1, channelCountMode: "explicit" });
  capture.port.onmessage = (e) => ws?.readyState === WebSocket.OPEN && ws.send(e.data);
  micSource.connect(capture);
}

function stopSession() {
  if (!ws) return;
  const socket = ws;
  ws = null;
  socket.close();
  stopPlayback();
  mic?.getTracks().forEach((track) => track.stop());
  ctx?.close();
  ctx = mic = micSource = micMeter = null;
  $("mic").classList.remove("active", "speaking");
  $("mic").textContent = "🎙️";
  $("mic-label").textContent = t("start");
  setStatus(t("ended"));
}

function onEvent(msg) {
  switch (msg.type) {
    case "config": startCapture(); break;
    case "status":
      if (msg.text === "connected" || msg.text === "reconnected") {
        setStatus(withMic ? t("listening") : "");
        if (queuedText) { ws.send(JSON.stringify({ type: "text", text: queuedText })); queuedText = null; }
      }
      if (msg.text === "reconnecting") { stopPlayback(); setStatus(t("reconnecting")); }
      break;
    case "transcript":
      if (msg.role === "patient") addBubble("patient", msg.text);
      else { addBubble("assistant", msg.text, msg.stopped ? [] : readySources, msg.stopped); if (!msg.stopped) readySources = []; }
      break;
    case "tool": onTool(msg); break;
    case "medication_card": showMedicationCard(msg); break;
    case "guard": stopPlayback(); muted = true; notice("guard", t("guard"), t("guardText")); break;
    case "guard_final": notice("guard", t("guard"), t("guardFinal")); break;
    case "rule_emergency": if (!emergencyShown) { emergencyShown = true; notice("emergency", t("emergency"), t("emergencyText")); } break;
    case "interrupt": stopPlayback(); muted = true; break;
    // Sources belong to the reply that follows the tool call, not to the "let me check" preamble.
    case "response_started": muted = false; if (pendingSources.length) { readySources = pendingSources; pendingSources = []; } break;
    case "error": setStatus(msg.text, true); break;
  }
}

function onTool(msg) {
  if (!msg.result.ok) return;
  if (msg.name === "get_discharge_information") {
    for (const section of msg.result.sections) if (!pendingSources.includes(section.title)) pendingSources.push(section.title);
  }
  if (msg.name === "request_staff_callback") {
    const urgency = msg.args.urgency;
    if (urgency === "emergency") {
      if (!emergencyShown) { emergencyShown = true; notice("emergency", t("emergency"), t("emergencyText")); }
    } else notice(urgency === "urgent" ? "urgent" : "callback", t("callback"), t("callbackText"));
  }
}

function notice(kind, titleText, text) {
  const box = document.createElement("div");
  box.className = `notice ${kind}`;
  const title = document.createElement("strong");
  title.textContent = titleText;
  box.append(title, text);
  appendToConversation(box);
}

// The plan is rendered from the approved letter (sent by the server), never from the model's words.
function showMedicationCard(msg) {
  if (medicationCardShown) return;
  medicationCardShown = true;
  const card = document.createElement("div");
  card.className = "med-card";
  const title = document.createElement("strong");
  title.textContent = `💊 ${t("medTitle")}`;
  const table = document.createElement("table");
  const head = table.insertRow();
  t("medCols").forEach((label) => { const th = document.createElement("th"); th.textContent = label; head.appendChild(th); });
  for (const m of msg.plan) {
    const row = table.insertRow();
    [`${m.name}`, `${m.strength} · ${m.form}`, m.schedule, m.note].forEach((v, i) => { const td = row.insertCell(); td.textContent = v; if (i === 0) td.className = "drug"; });
  }
  const foot = document.createElement("small");
  foot.textContent = `${msg.source} · ${msg.approved_at}`;
  card.append(title, table, foot);
  appendToConversation(card);
}

// ---------- Conversation ----------
function addBubble(role, text, sources = [], stopped = false) {
  if (!text) return;
  $("hint")?.remove();
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}${stopped ? " stopped" : ""}`;
  bubble.textContent = text;
  if (sources.length) {
    const chips = document.createElement("div");
    chips.className = "sources";
    for (const title of sources) { const chip = document.createElement("span"); chip.textContent = `📄 ${t("source")}: ${title}`; chips.appendChild(chip); }
    bubble.appendChild(chips);
  }
  appendToConversation(bubble);
}

function appendToConversation(node) {
  $("conversation").appendChild(node);
  $("conversation").scrollTop = $("conversation").scrollHeight;
  node.scrollIntoView({ block: "end", behavior: "smooth" });
}

// ---------- Audio ----------
function playAudio(data) {
  if (muted || !ctx) return;
  const pcm = new Int16Array(data);
  const buffer = ctx.createBuffer(1, pcm.length, SAMPLE_RATE);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) samples[i] = pcm[i] / 0x8000;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(voiceBus);
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

function meter(node) {
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  node.connect(analyser);
  const data = new Float32Array(analyser.fftSize);
  return () => { analyser.getFloatTimeDomainData(data); return Math.sqrt(data.reduce((s, v) => s + v * v, 0) / data.length); };
}

function animate() {
  if (!ctx) return document.documentElement.style.setProperty("--level", 0);
  const speaking = playing.length > 0;
  const level = Math.min(1, ((speaking ? voiceMeter?.() : micMeter?.()) || 0) * 6);
  $("mic").classList.toggle("speaking", speaking);
  document.documentElement.style.setProperty("--level", level.toFixed(2));
  requestAnimationFrame(animate);
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

// ---------- Letter dialog ----------
$("show-letter").onclick = () => {
  if (!letter) return;
  $("letter-title").textContent = `${letter.patient.name} · ${letter.discharge_date}`;
  $("letter-body").innerHTML = "";
  for (const section of letter.sections) {
    const h = document.createElement("h3"); h.textContent = section.title;
    const p = document.createElement("p"); p.textContent = section.text;
    $("letter-body").append(h, p);
  }
  $("letter").showModal();
};
$("close-letter").onclick = () => $("letter").close();
