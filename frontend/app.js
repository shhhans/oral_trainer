'use strict';

// ── Scenario definitions (client-side) ────────────────────────────────────────

const SCENARIO_DEFS = {
  ordering: {
    icon: '🍽️', title: 'Restaurant Ordering', subtitle: '餐厅点餐',
    desc: '向服务员点餐，练习菜单词汇和礼貌用语',
    badge: '基础', badgeClass: 'badge-green',
    tasks: [
      'Ask the waiter about a dish on the menu',
      'Order at least one food item',
      'Order a drink',
      'Confirm your complete order',
    ],
    renderGuide: () => '<div class="menu-section"><h3>📋 Menu</h3><div id="menu-items"><p style="color:#9ca3af;font-size:.85rem">Loading…</p></div></div>',
    afterRender: loadOrderingMenu,
  },

  hotel: {
    icon: '🏨', title: 'Hotel Check-in', subtitle: '酒店入住',
    desc: '办理入住，确认预订信息，搞清楚不明确的细节',
    badge: '基础', badgeClass: 'badge-green',
    tasks: [
      'Give your name to confirm the reservation',
      'Ask which floor your room is on',
      'Find out if breakfast is included',
      'Get the WiFi password',
      'Confirm standard check-in time',
    ],
    renderGuide: () => `
      <div class="mock-doc">
        <div class="doc-header booking-header">
          <span>🏨</span>
          <div>
            <div class="doc-brand">Grand Plaza Hotel</div>
            <div class="doc-ref">Booking Confirmation #GP-4721 &nbsp;✓</div>
          </div>
        </div>
        <div class="doc-body">
          <div class="doc-row"><span class="lbl">Guest Name</span><span class="val">Zhang Wei</span></div>
          <div class="doc-row"><span class="lbl">Check-in</span><span class="val">Jun 10, 2025</span></div>
          <div class="doc-row"><span class="lbl">Check-out</span><span class="val">Jun 12, 2025 (2 nights)</span></div>
          <div class="doc-row"><span class="lbl">Room Type</span><span class="val">Deluxe Room</span></div>
          <div class="doc-divider"></div>
          <div class="doc-row gap-row"><span class="lbl">Floor</span><span class="gap-val" data-gap="floor">???</span></div>
          <div class="doc-row gap-row"><span class="lbl">Breakfast</span><span class="gap-val" data-gap="breakfast">???</span></div>
          <div class="doc-row gap-row"><span class="lbl">WiFi Password</span><span class="gap-val" data-gap="wifi">???</span></div>
          <div class="doc-row gap-row"><span class="lbl">Check-in Opens</span><span class="gap-val" data-gap="checkin_time">???</span></div>
        </div>
        <div class="doc-tip">💡 Tap any <b>???</b> field to fill it in once you find out</div>
      </div>`,
  },

  doctor: {
    icon: '🏥', title: "Doctor's Appointment", subtitle: '看医生',
    desc: '描述症状，回答医生追问，听懂诊断和医嘱',
    badge: '基础', badgeClass: 'badge-green',
    tasks: [
      'Describe your main symptom in English',
      'Tell the doctor how long you have had it',
      'Answer questions about fever / other symptoms',
      'Confirm you have no known allergies',
      "Understand the doctor's diagnosis",
    ],
    renderGuide: () => `
      <div class="mock-doc">
        <div class="doc-header doctor-header">
          <span>🏥</span>
          <div>
            <div class="doc-brand">City Medical Clinic</div>
            <div class="doc-ref">Patient Intake Form</div>
          </div>
        </div>
        <div class="doc-body">
          <div class="doc-row"><span class="lbl">Patient Name</span><span class="val">Alex Chen</span></div>
          <div class="doc-row"><span class="lbl">Age</span><span class="val">28</span></div>
          <div class="doc-row"><span class="lbl">Visit Date</span><span class="val">Today</span></div>
          <div class="doc-divider"></div>
          <div class="situation-label">🗣 Your situation — say this in English:</div>
          <div class="situation-card">
            <div class="symptom-row"><span class="zh">喉咙痛</span><span class="arrow">→</span><span class="en-hint">sore throat… describe it!</span></div>
            <div class="symptom-row"><span class="zh">已经 3 天</span><span class="arrow">→</span><span class="en-hint">for three days</span></div>
            <div class="symptom-row"><span class="zh">发烧 38°C</span><span class="arrow">→</span><span class="en-hint">slight fever</span></div>
            <div class="symptom-row"><span class="zh">无药物过敏</span><span class="arrow">→</span><span class="en-hint">no known allergies</span></div>
          </div>
        </div>
      </div>`,
  },

  shopping: {
    icon: '🛍️', title: 'Clothes Shopping', subtitle: '购物',
    desc: '在服装店购物，问清楚库存、折扣和退换货政策',
    badge: '基础', badgeClass: 'badge-green',
    tasks: [
      'Describe the jacket you are looking for',
      'Ask if size M is in stock',
      'Find out if it is currently on sale',
      'Ask about the return policy',
      'Make a decision: buy or not',
    ],
    renderGuide: () => `
      <div class="shopping-guide">
        <div class="product-card">
          <div class="product-image">🧥</div>
          <div class="product-info">
            <div class="product-name">Classic Wool Blend Jacket</div>
            <div class="product-meta">Color: Navy Blue</div>
            <div class="product-price">$75.00</div>
            <div class="doc-divider"></div>
            <div class="doc-row gap-row"><span class="lbl">Size M in stock</span><span class="gap-val" data-gap="size_m">???</span></div>
            <div class="doc-row gap-row"><span class="lbl">On sale</span><span class="gap-val" data-gap="on_sale">???</span></div>
            <div class="doc-row gap-row"><span class="lbl">Return window</span><span class="gap-val" data-gap="returns">???</span></div>
          </div>
        </div>
        <div class="mission-card">
          <div class="mission-title">🛍️ Your budget: $80 max</div>
          <p style="margin:2px 0 0;color:#374151;font-size:.82rem">Find out the missing info, then decide whether to buy.</p>
        </div>
        <div class="doc-tip">💡 Tap any <b>???</b> field to fill it in once you find out</div>
      </div>`,
  },

  interview: {
    icon: '💼', title: 'Job Interview', subtitle: '求职面试',
    desc: '用英文自我介绍、回答行为问题、向面试官提问',
    badge: '基础', badgeClass: 'badge-green',
    tasks: [
      'Give a 1-minute self-introduction',
      'Answer a behavioral question with an example',
      'Explain the 2022 gap year naturally',
      'Ask the interviewer at least 2 questions',
    ],
    renderGuide: () => `
      <div class="interview-guide">
        <div class="profile-card">
          <div class="profile-avatar">👤</div>
          <div class="profile-name">Alex Chen</div>
          <div class="profile-role">Backend Developer · 3 years exp.</div>
          <div class="profile-skills">Python &nbsp;·&nbsp; SQL &nbsp;·&nbsp; REST APIs &nbsp;·&nbsp; Docker</div>
          <div class="doc-divider"></div>
          <div class="profile-warning">⚠️ 2022: gap year — prepare to explain this!</div>
        </div>
        <div class="jd-card">
          <div class="jd-title">💼 Backend Engineer</div>
          <div class="jd-company">TechStart Inc. · Series B · ~200 people</div>
          <div class="jd-salary">$80k – $120k + benefits</div>
          <div class="doc-divider"></div>
          <div class="jd-req">✓ &nbsp;3+ yrs Python experience</div>
          <div class="jd-req">✓ &nbsp;REST API design</div>
          <div class="jd-req">✓ &nbsp;Team player, self-directed</div>
          <div class="jd-req">✓ &nbsp;CS degree or equivalent</div>
        </div>
      </div>`,
  },

  directions: {
    icon: '🗺️', title: 'Asking for Directions', subtitle: '问路',
    desc: '向路人问路，用方位词确认路线，找到目的地',
    badge: '进阶', badgeClass: 'badge-blue',
    tasks: [
      'Politely ask for directions to the Art Museum',
      'Ask for clarification on one turn',
      'Confirm the total walking time',
      'Thank the person',
    ],
    renderGuide: renderDirectionsGuide,
  },

  phone: {
    icon: '📞', title: 'Phone Appointment', subtitle: '电话预约',
    desc: '打电话预约，无视觉线索，只靠听力完成预约',
    badge: '进阶', badgeClass: 'badge-blue',
    tasks: [
      'State your name and reason for calling',
      'Find a slot that fits your calendar',
      'Give your date of birth when asked',
      'Confirm and repeat the appointment details',
    ],
    renderGuide: renderPhoneGuide,
  },
};

// ── Guide render functions ─────────────────────────────────────────────────────

async function loadOrderingMenu() {
  try {
    const menu = await (await fetch('/api/menu')).json();
    document.getElementById('menu-items').innerHTML = menu.map(m => `
      <div class="menu-item">
        <div class="menu-item-top">
          <span class="menu-item-name">${m.name}</span>
          <span class="menu-item-price">${m.price}</span>
        </div>
        <div class="menu-item-desc">${m.desc}</div>
      </div>`).join('');
  } catch {
    document.getElementById('menu-items').textContent = 'Menu unavailable';
  }
}

function renderDirectionsGuide() {
  return `
    <div class="directions-guide">
      <div class="map-container">
        <svg viewBox="0 0 270 230" xmlns="http://www.w3.org/2000/svg" class="city-map">
          <!-- Background -->
          <rect width="270" height="230" fill="#e8ece6"/>
          <!-- Horizontal roads -->
          <rect x="0" y="50" width="270" height="16" fill="#d6d0c8"/>
          <rect x="0" y="115" width="270" height="16" fill="#d6d0c8"/>
          <rect x="0" y="180" width="270" height="16" fill="#d6d0c8"/>
          <!-- Vertical roads -->
          <rect x="50" y="0" width="16" height="230" fill="#d6d0c8"/>
          <rect x="125" y="0" width="16" height="230" fill="#d6d0c8"/>
          <rect x="200" y="0" width="16" height="230" fill="#d6d0c8"/>
          <!-- Road centre lines -->
          <line x1="0" y1="58" x2="270" y2="58" stroke="#e8e0c0" stroke-width="1" stroke-dasharray="8,6"/>
          <line x1="0" y1="123" x2="270" y2="123" stroke="#e8e0c0" stroke-width="1" stroke-dasharray="8,6"/>
          <line x1="58" y1="0" x2="58" y2="230" stroke="#e8e0c0" stroke-width="1" stroke-dasharray="8,6"/>
          <line x1="133" y1="0" x2="133" y2="230" stroke="#e8e0c0" stroke-width="1" stroke-dasharray="8,6"/>
          <line x1="208" y1="0" x2="208" y2="230" stroke="#e8e0c0" stroke-width="1" stroke-dasharray="8,6"/>
          <!-- City Hall block -->
          <rect x="68" y="68" width="50" height="40" fill="#b8c4b0" rx="2"/>
          <text x="93" y="84" text-anchor="middle" font-size="7" fill="#4a5240" font-weight="600">City</text>
          <text x="93" y="94" text-anchor="middle" font-size="7" fill="#4a5240" font-weight="600">Hall</text>
          <!-- Coffee shop -->
          <rect x="68" y="133" width="50" height="40" fill="#c8d4b8" rx="2"/>
          <text x="93" y="149" text-anchor="middle" font-size="7" fill="#3a4a2a">☕ Coffee</text>
          <text x="93" y="160" text-anchor="middle" font-size="7" fill="#3a4a2a">Shop</text>
          <!-- Post Office -->
          <rect x="143" y="133" width="50" height="40" fill="#b8c4b0" rx="2"/>
          <text x="168" y="149" text-anchor="middle" font-size="7" fill="#4a5240">Post</text>
          <text x="168" y="160" text-anchor="middle" font-size="7" fill="#4a5240">Office</text>
          <!-- Subway -->
          <circle cx="133" cy="58" r="9" fill="#2b5cff"/>
          <text x="133" y="62" text-anchor="middle" font-size="9" fill="white" font-weight="800">M</text>
          <text x="133" y="47" text-anchor="middle" font-size="7" fill="#2b5cff" font-weight="600">Subway</text>
          <!-- Art Museum (destination) -->
          <rect x="218" y="68" width="44" height="40" fill="#fbbf24" rx="2" opacity=".85"/>
          <text x="240" y="83" text-anchor="middle" font-size="7" fill="#451a03" font-weight="700">Art</text>
          <text x="240" y="93" text-anchor="middle" font-size="7" fill="#451a03" font-weight="700">Museum</text>
          <text x="240" y="62" text-anchor="middle" font-size="13">🎯</text>
          <!-- You are here -->
          <circle cx="58" cy="188" r="9" fill="#dc2626" opacity=".9"/>
          <text x="58" y="193" text-anchor="middle" font-size="10" fill="white">▲</text>
          <text x="58" y="208" text-anchor="middle" font-size="7" fill="#dc2626" font-weight="700">You</text>
          <!-- Street name hints -->
          <text x="133" y="112" text-anchor="middle" font-size="6" fill="#9ca3af">Main St</text>
          <text x="14" y="60" font-size="6" fill="#9ca3af">Oak Ave</text>
        </svg>
      </div>
      <div class="map-legend">
        <span>▲ You are here</span>
        <span>🎯 Art Museum (goal)</span>
      </div>
      <p class="map-note">The route is not shown — ask the local for directions!</p>
    </div>`;
}

function renderPhoneGuide() {
  return `
    <div class="phone-guide">
      <div class="caller-card">
        <div class="caller-title">📋 Your Details</div>
        <div class="doc-row"><span class="lbl">Name</span><span class="val">Alex Chen</span></div>
        <div class="doc-row"><span class="lbl">Date of Birth</span><span class="val">Jan 15, 1996</span></div>
        <div class="doc-row"><span class="lbl">Reason for call</span><span class="val">Routine checkup</span></div>
      </div>
      <div class="calendar-card">
        <div class="cal-title">📅 Your Week — Jun 9–13</div>
        <div class="cal-grid">
          <div class="cal-head">Mon</div><div class="cal-head">Tue</div><div class="cal-head">Wed</div><div class="cal-head">Thu</div><div class="cal-head">Fri</div>
          <div class="cal-cell busy">Busy<br>9–11am</div>
          <div class="cal-cell free">FREE</div>
          <div class="cal-cell busy">Busy<br>1–3pm</div>
          <div class="cal-cell free">FREE</div>
          <div class="cal-cell busy">Busy<br>all AM</div>
        </div>
        <div class="cal-note">Tuesday &amp; Thursday are free — find a slot that works!</div>
      </div>
    </div>`;
}

// ── State ──────────────────────────────────────────────────────────────────────

let sessionId = null, currentScenario = null, ws = null;
const storedDialect = localStorage.getItem('oral-trainer-dialect');
let selectedDialect = ['en-us', 'en-gb'].includes(storedDialect) ? storedDialect : 'en-us';
let mediaRecorder = null, chunks = [], recording = false;
let sttStart = 0, recognizing = '';
let micStream = null;  // 共享的 getUserMedia 流:MediaRecorder(发音评分)与 ASR 采集复用
// ASR-only 实验分支:转写仅使用服务端 DashScope,不启用浏览器 Web Speech。
let asrAvailable = false;
let asrWs = null, asrCtx = null, asrNode = null;
let asrFinalText = '', asrFinalResolve = null;

// 启动时探测后端是否配置了 DashScope。
async function probeAsrCapability() {
  try {
    const h = await (await fetch('/api/health')).json();
    asrAvailable = !!(h.keys_configured && h.keys_configured.dashscope);
  } catch { asrAvailable = false; }
}
probeAsrCapability();
// 复用同一个 audio 元素:回复音频在 WebSocket 异步回调里播放,已脱离用户手势栈,
// Chrome 自动播放策略可能拦截。startRec 时(用户手势内)先 prime 解锁该元素,
// 后续 play 才不会被静默拦截。lastAudioB64 留作"重播"回退用。
let audioPlayer = null, audioPrimePromise = null, lastAudioSource = null;
let idleTimer = null, idleStartedAt = null, responseWaitMs = 0;
let heartbeatSequence = 0, waitingForUser = false;
let historyRecords = [], historyChart = null;
// ── Scenario Picker ────────────────────────────────────────────────────────────

function initPicker() {
  const dialectInput = document.querySelector(
    `input[name="dialect"][value="${selectedDialect}"]`,
  );
  if (dialectInput) dialectInput.checked = true;
  document.querySelectorAll('input[name="dialect"]').forEach(input => {
    input.addEventListener('change', () => {
      if (!input.checked) return;
      selectedDialect = input.value;
      localStorage.setItem('oral-trainer-dialect', selectedDialect);
    });
  });

  const grid = document.getElementById('scenario-grid');
  grid.innerHTML = Object.entries(SCENARIO_DEFS).map(([id, sc]) => `
    <div class="scenario-card" data-id="${id}">
      <div class="sc-icon">${sc.icon}</div>
      <div class="sc-title">${sc.title}</div>
      <div class="sc-sub">${sc.subtitle}</div>
      <div class="sc-desc">${sc.desc}</div>
      <span class="sc-badge ${sc.badgeClass}">${sc.badge}</span>
    </div>`).join('');
  grid.querySelectorAll('.scenario-card').forEach(card => {
    card.addEventListener('click', () => startScenario(card.dataset.id));
  });
}

const HISTORY_DEMO = [
  { completed_at: Date.now() / 1000 - 35 * 86400, summary: { overall_score: 68, sub_scores: { pronunciation: 65, fluency: 62, grammar: 78, responsiveness: 72 } } },
  { completed_at: Date.now() / 1000 - 28 * 86400, summary: { overall_score: 72, sub_scores: { pronunciation: 70, fluency: 68, grammar: 80, responsiveness: 75 } } },
  { completed_at: Date.now() / 1000 - 21 * 86400, summary: { overall_score: 75, sub_scores: { pronunciation: 74, fluency: 71, grammar: 82, responsiveness: 78 } } },
  { completed_at: Date.now() / 1000 - 14 * 86400, summary: { overall_score: 79, sub_scores: { pronunciation: 78, fluency: 76, grammar: 84, responsiveness: 82 } } },
  { completed_at: Date.now() / 1000 - 7 * 86400, summary: { overall_score: 82, sub_scores: { pronunciation: 81, fluency: 80, grammar: 85, responsiveness: 84 } } },
  { completed_at: Date.now() / 1000, summary: { overall_score: 86, sub_scores: { pronunciation: 85, fluency: 84, grammar: 88, responsiveness: 87 } } },
];

function historyMetricValue(record, metric) {
  if (metric === 'overall') return record.summary.overall_score;
  return record.summary.sub_scores[metric] ?? 0;
}

function formatHistoryDate(timestamp, includeTime = false) {
  if (!timestamp) return '未记录';
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    ...(includeTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(new Date(timestamp * 1000));
}

function renderHistoryChart(records, isDemo) {
  const metric = document.getElementById('history-metric').value;
  const labels = {
    overall: '综合',
    pronunciation: '发音',
    fluency: '流利度',
    grammar: '语法',
    responsiveness: '反应速度',
  };
  const chronological = [...records].sort((a, b) => a.completed_at - b.completed_at);
  if (historyChart) historyChart.destroy();
  historyChart = new Chart(document.getElementById('history-chart'), {
    type: 'line',
    data: {
      labels: chronological.map(item => formatHistoryDate(item.completed_at)),
      datasets: [{
        label: labels[metric],
        data: chronological.map(item => historyMetricValue(item, metric)),
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37,99,235,.1)',
        pointBackgroundColor: '#fff',
        pointBorderColor: '#2563eb',
        pointBorderWidth: 2,
        pointRadius: 4,
        tension: .28,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: context => `${labels[metric]} ${context.parsed.y}` } },
      },
      scales: {
        y: { min: 0, max: 100, ticks: { stepSize: 20 }, grid: { color: '#eef0f2' } },
        x: { grid: { display: false } },
      },
    },
  });
  document.getElementById('history-demo-badge').classList.toggle('hidden', !isDemo);
}

function renderHistory(records) {
  const isDemo = records.length === 0;
  const trendRecords = isDemo ? HISTORY_DEMO : records;
  const scores = records.map(item => item.summary.overall_score);
  const average = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : '—';
  const best = scores.length ? Math.max(...scores) : '—';
  const latest = scores.length ? scores[0] : '—';
  const totalWait = records.reduce(
    (sum, item) => sum + (item.summary.response_wait_total_ms || 0), 0,
  );
  document.getElementById('history-stats').innerHTML = `
    <div class="history-stat"><div class="history-stat-label">已完成练习</div><div class="history-stat-value">${records.length}</div><div class="history-stat-note">累计课程</div></div>
    <div class="history-stat"><div class="history-stat-label">平均分</div><div class="history-stat-value">${average}</div><div class="history-stat-note">综合表现</div></div>
    <div class="history-stat"><div class="history-stat-label">最高分</div><div class="history-stat-value">${best}</div><div class="history-stat-note">个人最佳</div></div>
    <div class="history-stat"><div class="history-stat-label">最近成绩</div><div class="history-stat-value">${latest}</div><div class="history-stat-note">总等待 ${(totalWait / 1000).toFixed(0)} 秒</div></div>`;

  const list = document.getElementById('history-list');
  if (isDemo) {
    list.innerHTML = '<div class="history-empty">完成一次课程后，真实评分记录会显示在这里。</div>';
  } else {
    list.innerHTML = records.map(item => {
      const sc = SCENARIO_DEFS[item.scenario];
      const sub = item.summary.sub_scores;
      const accent = item.dialect === 'en-gb' ? '英式' : '美式';
      return `
        <div class="history-row">
          <div>
            <div class="history-session-name">${sc ? `${sc.icon} ${sc.subtitle}` : item.scenario}</div>
            <div class="history-meta">${accent} · ${item.difficulty}</div>
          </div>
          <div class="history-date">${formatHistoryDate(item.completed_at, true)}</div>
          <div class="history-scores">
            <span>发音 ${sub.pronunciation}</span>
            <span>流利 ${sub.fluency}</span>
            <span>语法 ${sub.grammar}</span>
            <span>反应 ${sub.responsiveness}</span>
          </div>
          <div class="history-overall">${item.summary.overall_score}</div>
        </div>`;
    }).join('');
  }
  renderHistoryChart(trendRecords, isDemo);
}

async function openHistory() {
  document.getElementById('picker').classList.add('hidden');
  document.getElementById('history-view').classList.remove('hidden');
  document.getElementById('history-list').innerHTML =
    '<div class="history-empty">正在加载评分记录...</div>';
  try {
    const response = await fetch('/api/history');
    if (!response.ok) throw new Error('history request failed');
    historyRecords = await response.json();
  } catch {
    historyRecords = [];
  }
  renderHistory(historyRecords);
}

async function startScenario(scenarioId) {
  primeAudio();
  resetIdleTracking();
  currentScenario = SCENARIO_DEFS[scenarioId];

  // Create session on server
  const params = new URLSearchParams({
    scenario: scenarioId,
    dialect: selectedDialect,
  });
  const res = await fetch(`/api/session?${params}`, { method: 'POST' });
  const data = await res.json();
  sessionId = data.id;

  // Render guide
  document.getElementById('guide-content').innerHTML = currentScenario.renderGuide();
  if (currentScenario.afterRender) await currentScenario.afterRender();
  enableGapFills();

  // Render task list
  renderTaskList(currentScenario.tasks);

  // Update header
  document.getElementById('session-title').textContent =
    `${currentScenario.icon} ${currentScenario.subtitle}`;
  const badge = document.getElementById('session-badge');
  badge.textContent = currentScenario.badge;
  badge.className = `sc-badge ${currentScenario.badgeClass}`;

  // Show opening line as first message
  const openingLine = data.opening_line || '';
  if (openingLine) addMessage(openingLine, 'opening');
  let openingPlayback = Promise.resolve();
  if (data.opening_audio_url) openingPlayback = playAudioSource(data.opening_audio_url);
  else if (data.opening_audio_b64) openingPlayback = playAudio(data.opening_audio_b64);
  openingPlayback.finally(scheduleIdleFollowup);

  // Switch views
  document.getElementById('picker').classList.add('hidden');
  document.getElementById('session-view').classList.remove('hidden');

  // WebSocket
  connectWs();
}

// 建立(或重建)主链路 WebSocket。会话状态由服务端 SQLite 持久化,
// 同一 session_id 重连后可无缝继续,故断线时按需重连是安全的。
function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/${sessionId}`);
  ws.onmessage = onServerMessage;
  // 服务重启(如 dev --reload)、网络抖动都会触发 close;不在此重连,
  // 留待下次发送时 ensureWsOpen 重连,避免会话结束后无谓重连。
  ws.onclose = e => console.warn('WS closed', e.code, e.reason);
  ws.onerror = () => console.warn('WS error');
}

// 确保 ws 处于 OPEN:已断开则重连并等待握手完成,超时/失败则 reject。
function ensureWsOpen(timeoutMs = 4000) {
  return new Promise((resolve, reject) => {
    if (!sessionId) return reject(new Error('no active session'));
    if (ws && ws.readyState === WebSocket.OPEN) return resolve();
    // CLOSED/CLOSING/无连接 → 重建;CONNECTING → 复用,仅等待其 open
    if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
      connectWs();
    }
    const timer = setTimeout(() => reject(new Error('ws connect timeout')), timeoutMs);
    ws.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
    ws.addEventListener('error', () => { clearTimeout(timer); reject(new Error('ws error')); }, { once: true });
  });
}

function clearIdleTimer(addElapsed = false) {
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = null;
  if (addElapsed && idleStartedAt !== null) {
    responseWaitMs += performance.now() - idleStartedAt;
  }
  idleStartedAt = null;
}

function resetIdleTracking() {
  clearIdleTimer();
  responseWaitMs = 0;
  heartbeatSequence = 0;
  waitingForUser = false;
}

function scheduleIdleFollowup() {
  clearIdleTimer();
  if (!sessionId || recording) return;
  waitingForUser = true;
  idleStartedAt = performance.now();
  idleTimer = setTimeout(sendIdleFollowup, 5000);
}

async function sendIdleFollowup() {
  clearIdleTimer(true);
  if (!waitingForUser || !sessionId) return;
  try {
    await ensureWsOpen();
    if (!waitingForUser) return;
    ws.send(JSON.stringify({ type: 'heartbeat', sequence: heartbeatSequence }));
  } catch {
    if (waitingForUser) scheduleIdleFollowup();
  }
}

// ── Gap-fill interaction ────────────────────────────────────────────────────────

function enableGapFills() {
  document.querySelectorAll('.gap-val').forEach(el => {
    el.addEventListener('click', () => {
      if (el.classList.contains('filled') || el.querySelector('input')) return;
      el.innerHTML = '<input type="text" placeholder="type answer…" />';
      const inp = el.querySelector('input');
      inp.focus();
      function commit() {
        const v = inp.value.trim();
        el.textContent = v || '???';
        if (v) el.classList.add('filled');
      }
      inp.addEventListener('blur', commit);
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } });
    });
  });
}

// ── Task checklist ─────────────────────────────────────────────────────────────

function renderTaskList(tasks) {
  const div = document.getElementById('task-list');
  div.innerHTML = '<h3>Your Tasks</h3>' +
    tasks.map((t, i) => `
      <div class="task-item" id="task-${i}">
        <input type="checkbox" id="tc-${i}">
        <label for="tc-${i}">${t}</label>
      </div>`).join('');
  div.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => {
      cb.closest('.task-item').classList.toggle('done', cb.checked);
    });
  });
}

function checkLastTask() {
  const items = document.querySelectorAll('.task-item');
  if (!items.length) return;
  const last = items[items.length - 1];
  const cb = last.querySelector('input');
  if (cb && !cb.checked) { cb.checked = true; last.classList.add('done'); }
}

// ── Chat ───────────────────────────────────────────────────────────────────────

function addMessage(text, who) {
  const div = document.createElement('div');
  div.className = `msg ${who}`;
  div.textContent = text;
  document.getElementById('messages').appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function addCorrection(text) {
  const empty = document.querySelector('.empty-hint');
  if (empty) empty.remove();
  const div = document.createElement('div');
  div.className = 'card';
  div.textContent = text;
  document.getElementById('corrections').prepend(div);
}

// ── Recording ──────────────────────────────────────────────────────────────────

const recBtn = document.getElementById('record-btn');
recBtn.addEventListener('mousedown', startRec);
recBtn.addEventListener('mouseup', stopRec);
recBtn.addEventListener('touchstart', e => { e.preventDefault(); startRec(); });
recBtn.addEventListener('touchend', e => { e.preventDefault(); stopRec(); });

document.addEventListener('keydown', e => {
  if (e.code === 'Space' && !e.repeat && e.target === document.body && !recording) {
    e.preventDefault(); startRec();
  }
});
document.addEventListener('keyup', e => {
  if (e.code === 'Space' && recording) { e.preventDefault(); stopRec(); }
});

async function startRec() {
  if (recording || !ws || !sessionId) return;
  clearIdleTimer(true);
  waitingForUser = false;
  recording = true;
  recBtn.classList.add('recording');
  recBtn.textContent = '🔴 Recording…';
  setStatus('');
  primeAudio();  // 在用户手势内解锁音频,确保稍后异步回复能正常播放
  recognizing = ''; chunks = []; sttStart = performance.now();
  if (!asrAvailable) {
    recording = false;
    recBtn.classList.remove('recording');
    recBtn.textContent = '🎤 按住说话';
    setStatus('服务端 ASR 不可用，请检查 DashScope 配置');
    scheduleIdleFollowup();
    return;
  }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(micStream);  // webm:供后端发音评分,与转写无关
    mediaRecorder.ondataavailable = e => chunks.push(e.data);
    mediaRecorder.start();
  } catch {
    setStatus('麦克风权限被拒绝'); recording = false; recBtn.classList.remove('recording');
    recBtn.textContent = '🎤 按住说话';
    scheduleIdleFollowup();
    return;
  }
  try {
    await startAsrStream();
  } catch {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try { mediaRecorder.stop(); } catch {}
    }
    stopMic();
    recording = false;
    recBtn.classList.remove('recording');
    recBtn.textContent = '🎤 按住说话';
    setStatus('服务端 ASR 启动失败，请检查连接后重试');
    scheduleIdleFollowup();
  }
}

async function stopRec() {
  if (!recording) return;
  recording = false;
  recBtn.classList.remove('recording');
  recBtn.textContent = '🎤 按住说话';
  if (mediaRecorder) mediaRecorder.stop();

  const text = (await stopAsrStream()).trim();
  stopMic();
  const sttMs = performance.now() - sttStart;
  const blob = new Blob(chunks, { type: 'audio/webm' });
  const audioB64 = await blobToB64(blob);
  if (!text) {
    setStatus('没听清，请重试');
    scheduleIdleFollowup();
    return;
  }
  addMessage(text, 'user');
  setStatus('等待回复…');
  // 连接可能在录音期间断开(服务重启/网络抖动),发送前保活并重连
  try {
    await ensureWsOpen();
    ws.send(JSON.stringify({
      type: 'turn',
      text,
      audio_b64: audioB64,
      stt_ms: sttMs,
      response_wait_ms: Math.round(responseWaitMs),
    }));
    responseWaitMs = 0;
    heartbeatSequence = 0;
  } catch {
    setStatus('⚠️ 连接已断开,正在重连,请再说一次');
  }
}

function stopMic() {
  if (micStream) { try { micStream.getTracks().forEach(t => t.stop()); } catch {} micStream = null; }
}

// 开启服务端实时 ASR:建 /ws/asr 链路 + AudioWorklet 采集 16k PCM 流式上传,实时回显 partial。
async function startAsrStream() {
  asrFinalText = ''; recognizing = '';
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  asrWs = new WebSocket(`${proto}//${location.host}/ws/asr/${sessionId}`);
  asrWs.binaryType = 'arraybuffer';
  await new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      callback(value);
    };
    const fail = message => finish(reject, new Error(message));
    const timer = setTimeout(() => fail('asr ready timeout'), 3000);

    asrWs.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.type === 'ready') finish(resolve);
      else if (m.type === 'partial') { recognizing = m.text; setStatus('🎙️ ' + m.text); }
      else if (m.type === 'final') { asrFinalText = m.text; if (asrFinalResolve) asrFinalResolve(m.text); }
      else if (m.type === 'unavailable' || m.type === 'error') {
        if (m.type === 'unavailable') asrAvailable = false;
        fail(`asr ${m.type}`);
      }
    };
    asrWs.onerror = () => fail('asr ws error');
    asrWs.onclose = () => fail('asr ws closed before ready');
  }).catch(error => {
    try { asrWs && asrWs.close(); } catch {}
    asrWs = null;
    throw error;
  });
  // 以 16k 创建 context,源被重采样到 16k,Worklet 直接吐 16k PCM(无需手动降采样)
  asrCtx = new AudioContext({ sampleRate: 16000 });
  await asrCtx.audioWorklet.addModule('/static/pcm-worklet.js');
  const src = asrCtx.createMediaStreamSource(micStream);
  asrNode = new AudioWorkletNode(asrCtx, 'pcm-worklet');
  asrNode.port.onmessage = e => {
    if (asrWs && asrWs.readyState === WebSocket.OPEN) asrWs.send(e.data);
  };
  // 经零增益连到 destination 以确保 Worklet 被调度,同时不产生回放
  const mute = asrCtx.createGain(); mute.gain.value = 0;
  src.connect(asrNode); asrNode.connect(mute); mute.connect(asrCtx.destination);
}

// 停止采集并向后端请求最终文本;超时则回退已收到的最后一段 partial。
async function stopAsrStream() {
  try { asrNode && asrNode.disconnect(); } catch {}
  try { asrCtx && (await asrCtx.close()); } catch {}
  asrCtx = null; asrNode = null;
  const finalText = await new Promise(res => {
    asrFinalResolve = res;
    if (asrWs && asrWs.readyState === WebSocket.OPEN) asrWs.send(JSON.stringify({ type: 'stop' }));
    setTimeout(() => res(asrFinalText || recognizing), 3000);
  });
  asrFinalResolve = null;
  try { asrWs && asrWs.close(); } catch {}
  asrWs = null;
  return finalText;
}

// ── Audio playback ───────────────────────────────────────────────────────────

// 在用户手势内"解锁"播放元素:静音播一下再暂停,使后续异步 play 不被自动播放策略拦截。
function primeAudio() {
  if (!audioPlayer) audioPlayer = new Audio();
  if (audioPrimePromise) return audioPrimePromise;
  const sampleRate = 8000;
  const samples = new Uint8Array(sampleRate / 10).fill(128);
  const wav = new ArrayBuffer(44 + samples.length);
  const view = new DataView(wav);
  const write = (offset, text) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, 'RIFF'); view.setUint32(4, 36 + samples.length, true);
  write(8, 'WAVEfmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate, true);
  view.setUint16(32, 1, true); view.setUint16(34, 8, true);
  write(36, 'data'); view.setUint32(40, samples.length, true);
  new Uint8Array(wav, 44).set(samples);

  audioPlayer.muted = true;
  const unlockUrl = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }));
  audioPlayer.src = unlockUrl;
  audioPrimePromise = audioPlayer.play().then(() => {
    audioPlayer.pause();
    audioPlayer.currentTime = 0;
    audioPlayer.muted = false;
  }).catch(() => {
    audioPlayer.muted = false;
  }).finally(() => {
    URL.revokeObjectURL(unlockUrl);
  });
  return audioPrimePromise;
}

function playAudio(b64) {
  return playAudioSource('data:audio/mp3;base64,' + b64);
}

function playAudioSource(source) {
  lastAudioSource = source;
  if (!audioPlayer) audioPlayer = new Audio();
  const ready = audioPrimePromise || Promise.resolve();
  return new Promise(resolve => {
    ready.finally(() => {
      audioPlayer.muted = false;
      audioPlayer.src = source;
      audioPlayer.onended = resolve;
      audioPlayer.onerror = resolve;
      audioPlayer.play().then(() => hideReplay()).catch(() => {
        // 自动播放被拦截:不静默失败,显式提示并给出手动重播。
        setStatus('🔇 浏览器拦截了自动播放');
        showReplay();
        resolve();
      });
    });
  });
}

function showReplay() {
  let btn = document.getElementById('replay-btn');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'replay-btn';
    btn.textContent = '▶ 重播';
    btn.addEventListener('click', () => {
      if (lastAudioSource) playAudioSource(lastAudioSource);
    });
    document.getElementById('controls').appendChild(btn);
  }
  btn.classList.remove('hidden');
}

function hideReplay() {
  const btn = document.getElementById('replay-btn');
  if (btn) btn.classList.add('hidden');
}

function blobToB64(blob) {
  return new Promise(res => {
    const r = new FileReader();
    r.onloadend = () => res(r.result.split(',')[1]);
    r.readAsDataURL(blob);
  });
}

// ── Server messages ────────────────────────────────────────────────────────────

function onServerMessage(ev) {
  const m = JSON.parse(ev.data);
  if (m.error) { setStatus('错误: ' + m.error); return; }
  if (m.type === 'heartbeat') {
    if (!waitingForUser) return;
    setStatus('');
    heartbeatSequence += 1;
    addMessage(m.assistant_text, 'assistant');
    const playback = m.audio_b64 ? playAudio(m.audio_b64) : Promise.resolve();
    playback.finally(() => {
      if (waitingForUser) scheduleIdleFollowup();
    });
    return;
  }
  setStatus('');
  addMessage(m.assistant_text, 'assistant');
  if (m.inline_correction) addCorrection('即时: ' + m.inline_correction);
  const playback = m.audio_b64 ? playAudio(m.audio_b64) : Promise.resolve();
  playback.finally(() => {
    if (!m.goal_reached) scheduleIdleFollowup();
  });
  if (m.goal_reached) {
    waitingForUser = false;
    setStatus('🎉 场景完成！可以结束课程了');
    checkLastTask();
  }
}

// ── Back button ────────────────────────────────────────────────────────────────

document.getElementById('back-btn').addEventListener('click', () => {
  resetIdleTracking();
  if (ws) { try { ws.close(); } catch {} ws = null; }
  sessionId = null; currentScenario = null;
  document.getElementById('messages').innerHTML = '';
  document.getElementById('corrections').innerHTML = '<p class="empty-hint">对话后显示纠错建议</p>';
  document.getElementById('summary-panel').classList.add('hidden');
  document.getElementById('session-view').classList.add('hidden');
  document.getElementById('picker').classList.remove('hidden');
});

document.getElementById('history-btn').addEventListener('click', openHistory);
document.getElementById('history-back-btn').addEventListener('click', () => {
  document.getElementById('history-view').classList.add('hidden');
  document.getElementById('picker').classList.remove('hidden');
});
document.getElementById('history-metric').addEventListener('change', () => {
  renderHistoryChart(historyRecords.length ? historyRecords : HISTORY_DEMO, !historyRecords.length);
});

// ── Finish / Summary ───────────────────────────────────────────────────────────

document.getElementById('finish-btn').addEventListener('click', async () => {
  resetIdleTracking();
  if (!sessionId) return;
  document.getElementById('finish-btn').disabled = true;
  setStatus('生成总结中…');
  try {
    const s = await (await fetch(`/api/session/${sessionId}/finish`, { method: 'POST' })).json();
    renderSummary(s);
  } catch {
    setStatus('总结生成失败');
  } finally {
    document.getElementById('finish-btn').disabled = false;
    setStatus('');
  }
});

function renderSummary(s) {
  document.getElementById('summary-panel').classList.remove('hidden');
  document.getElementById('scores').innerHTML =
    `综合 <b>${s.overall_score}</b> &nbsp;|&nbsp; ` +
    `发音 ${s.sub_scores.pronunciation} &nbsp;|&nbsp; ` +
    `流利 ${s.sub_scores.fluency} &nbsp;|&nbsp; ` +
    `语法 ${s.sub_scores.grammar} &nbsp;|&nbsp; ` +
    `反应 ${s.sub_scores.responsiveness} &nbsp;|&nbsp; ` +
    `等待 ${(s.response_wait_total_ms / 1000).toFixed(1)} 秒`;
  document.getElementById('word-scores').innerHTML = s.word_scores.map(w => {
    const hue = Math.round(w.score * 1.2);
    return `<span class="word" style="background:hsl(${hue},65%,42%)">${w.word} ${w.score}</span>`;
  }).join('');
  document.getElementById('comment').textContent = s.llm_comment;
  document.getElementById('summary-panel').scrollIntoView({ behavior: 'smooth' });
  const t = s.timing_breakdown;
  new Chart(document.getElementById('timing-chart'), {
    type: 'bar',
    data: {
      labels: ['STT', 'LLM', 'TTS', '总计'],
      datasets: [{ label: '平均耗时 (ms)',
        data: [t.stt_avg, t.llm_avg, t.tts_avg, t.total_avg],
        backgroundColor: ['#5b9', '#2b5cff', '#e8a13a', '#888'] }],
    },
    options: { plugins: { title: { display: true, text: '延迟分解 (ms)' } }, scales: { y: { beginAtZero: true } } },
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

// ── Boot ───────────────────────────────────────────────────────────────────────

initPicker();
