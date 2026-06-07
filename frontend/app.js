// playground 主逻辑:Web Speech 本地转写 + MediaRecorder 录音 → WebSocket 主链路 → 渲染。
let sessionId = null, ws = null, mediaRecorder = null, chunks = [], recognizing = "";
let sttStart = 0;

async function init() {
  const menu = await (await fetch("/api/menu")).json();
  document.getElementById("menu-list").innerHTML =
    menu.map(m => `<li><b>${m.name}</b> <span>${m.price}</span><br><small>${m.desc}</small></li>`).join("");
  sessionId = (await (await fetch("/api/session", { method: "POST" })).json()).id;
  // HTTPS 页面必须用 wss,否则浏览器按混合内容拦截 ws://
  const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${wsProto}//${location.host}/ws/${sessionId}`);
  ws.onmessage = onServerMessage;
}

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  document.getElementById("messages").appendChild(div);
  div.scrollIntoView();
}

function addCorrection(text) {
  const div = document.createElement("div");
  div.className = "card";
  div.textContent = text;
  document.getElementById("corrections").prepend(div);
}

// 录音:Web Speech 转写 + MediaRecorder 抓音频,松手时一并发送
const recBtn = document.getElementById("record-btn");
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SR ? new SR() : null;
if (recognition) { recognition.lang = "en-US"; recognition.interimResults = false; }

recBtn.addEventListener("mousedown", startRec);
recBtn.addEventListener("mouseup", stopRec);

async function startRec() {
  recBtn.classList.add("recording");
  recognizing = ""; chunks = []; sttStart = performance.now();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  mediaRecorder.start();
  if (recognition) {
    recognition.onresult = e => { recognizing = e.results[0][0].transcript; };
    recognition.start();
  }
}

async function stopRec() {
  recBtn.classList.remove("recording");
  if (recognition) recognition.stop();
  if (mediaRecorder) mediaRecorder.stop();
  await new Promise(r => setTimeout(r, 300)); // 等转写与音频收尾
  const sttMs = performance.now() - sttStart;
  const blob = new Blob(chunks, { type: "audio/webm" });
  const audioB64 = await blobToB64(blob);
  const text = recognizing.trim();
  if (!text) { document.getElementById("status").textContent = "没听清,重试"; return; }
  addMessage(text, "user");
  ws.send(JSON.stringify({ type: "turn", text, audio_b64: audioB64, stt_ms: sttMs }));
}

function blobToB64(blob) {
  return new Promise(res => {
    const r = new FileReader();
    r.onloadend = () => res(r.result.split(",")[1]);
    r.readAsDataURL(blob);
  });
}

function onServerMessage(ev) {
  const m = JSON.parse(ev.data);
  if (m.error) return;
  addMessage(m.assistant_text, "assistant");
  if (m.inline_correction) addCorrection("即时:" + m.inline_correction);
  if (m.audio_b64) new Audio("data:audio/mp3;base64," + m.audio_b64).play();
  if (m.goal_reached) document.getElementById("status").textContent = "🎉 点餐完成,可结束课程";
}

document.getElementById("finish-btn").addEventListener("click", finish);

async function finish() {
  const s = await (await fetch(`/api/session/${sessionId}/finish`, { method: "POST" })).json();
  document.getElementById("summary-panel").classList.remove("hidden");
  document.getElementById("scores").innerHTML =
    `综合 <b>${s.overall_score}</b> | 发音 ${s.sub_scores.pronunciation} | ` +
    `流利 ${s.sub_scores.fluency} | 语法 ${s.sub_scores.grammar}`;
  document.getElementById("word-scores").innerHTML = s.word_scores.map(w => {
    const hue = Math.round(w.score * 1.2); // 0→红 120→绿
    return `<span class="word" style="background:hsl(${hue},70%,45%)">${w.word} ${w.score}</span>`;
  }).join("");
  document.getElementById("comment").textContent = s.llm_comment;
  const t = s.timing_breakdown;
  new Chart(document.getElementById("timing-chart"), {
    type: "bar",
    data: { labels: ["STT", "LLM", "TTS", "总计"],
      datasets: [{ label: "平均耗时 (ms)",
        data: [t.stt_avg, t.llm_avg, t.tts_avg, t.total_avg],
        backgroundColor: ["#5b9", "#2b5cff", "#e8a13a", "#888"] }] },
    options: { plugins: { title: { display: true, text: "延迟分解(流畅性)" } } },
  });
}

init();
