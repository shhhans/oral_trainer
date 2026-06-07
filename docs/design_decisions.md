# 设计决策记录

本文记录项目各关键设计决策及被否决的备选方案，供以后审查。

---

## DD-01: SpeechAce 端点选择（score_text vs score_speech）

**决策时间**: 2026-06-07  
**相关 PR**: `fix/speechace-score-text`

### 背景

SpeechAce 提供两个核心评分端点：

| 端点 | 功能 | 所需方案 | 费用 |
|------|------|----------|------|
| `score_text/v9` | 有参考文本的发音评分 | Basic ($40/月) | 基础 |
| `score_speech/v9` | 自由说转写 + 发音/流利/语法评分 | Premium ($125/月) | 高 |

原代码使用 `score_speech`，实测报 `error_feature_unavailable`，导致发音副链路**静默失败**。

### 选项

**A. 切换到 score_text（采用）**  
- 以浏览器 STT 文本作为参考，调用 score_text 评分
- 优点：当前账户可用，无需升级，延迟 897-1583ms（异步，不影响主链路）
- 缺点：fluency 评分需 Pro 方案（`include_fluency=1`），当前默认为 0
- 限制：需要有效的参考文本；浏览器 STT 失败则跳过评分

**B. 保留 score_speech，升级到 Premium**  
- 优点：一次调用得到 STT + 发音 + 流利度 + 语法 + 语义相关性
- 缺点：$125/月，超出当前预算；即使可用，响应约 500-1500ms，若放主链路会增加首音延迟
- 结论：暂不采用，未来升级后可作为副链路增强（不需要改动主链路架构）

**C. 放弃发音评分，纯用浏览器 STT**  
- 最低成本，但失去逐词发音反馈
- 结论：弃用，发音评分是产品核心特性

### 结论

选 A。`SPEECHACE_BASE_URL` 已外化为环境变量，升级 Premium 后只需切换端点无需改代码结构。

---

## DD-02: STT 方案选择（浏览器 vs SpeechAce vs MiniMax/DashScope）

**决策时间**: 2026-06-07  
**相关文件**: `app/services/stt.py`, `docs/benchmark_stt_report.md`

### 背景

用户音频转文字有三条路径：

| 方案 | STT 延迟（后端视角）| 质量 | 成本 |
|------|---------------------|------|------|
| 浏览器 Web Speech API | ~0ms（前端完成）| 依赖浏览器/网络 | 免费 |
| SpeechAce score_speech | ~500-1500ms（主链路阻塞）| SpeechAce ASR | Premium 必需 |
| DashScope Paraformer | 需实测 | 高（阿里通义）| 按量付费 |

### 选项

**A. 浏览器 Web Speech API（现行，保留）**  
- 主链路首音延迟 ≈ 2800-6400ms（LLM + TTS，STT 不在关键路径）
- 优点：零后端延迟，零成本，前端即时反馈
- 缺点：质量依赖 Chrome 版本和网络；移动端体验可能差异大

**B. SpeechAce score_speech 兼做 STT**  
- 主链路首音延迟增加 ~500ms+，因为 SpeechAce 进入关键路径
- 优点：一次调用 = STT + 发音 + 流利度；减少 API 数量
- 缺点：需 Premium，且延迟更高；基准测试已确认比方案 A 慢
- 结论：**不采用**

**C. 后端 DashScope Paraformer**  
- 可提供更稳定的企业级 ASR
- 适用场景：移动端/无法用 Web Speech 的环境
- 结论：留作备选，接口已预留（`DashscopeStt`），需要时注入

### 结论

保留浏览器 STT 作为主路径，速度最快且免费。DashScope 备选接口保留但不激活。

---

## DD-03: 副链路错误注入时机与方式

**决策时间**: 2026-06-07  
**相关 PR**: `feat/side-chain-injection`

### 背景

副链路（`analyze_turn`）异步分析发音和语法，结果通常在用户下一句话之前就绪。
当检测到严重语法错误时，如何让助手在下一轮自然地点出？

### 选项

**A. 注入下一轮 system prompt（采用）**  
- 将 serious 错误格式化为 coaching hint，拼入下一轮的 system prompt
- 助手自行决定如何"自然地点出"，不强制措辞
- 优点：不打断当前轮次，不增加主链路延迟，措辞自然
- 缺点：hint 可能在下一轮被"埋没"；如果用户等待时间过长，上下文可能淡化

**B. 直接在当前轮次回包中加 inline_correction 字段**  
- 前端立即显示纠错 UI
- 优点：即时反馈
- 缺点：副链路是异步的，当前轮已经回包了，无法回填

**C. 推送独立 WebSocket 消息（前端补丁）**  
- 副链路完成后，向前端推送一条 `{type: "correction"}` 消息
- 优点：真正即时，不依赖下一轮
- 缺点：需要前端处理新消息类型；可能在用户正在说话时打断
- 结论：留作未来增强，目前 MVP 不引入

**D. 仅在总结中展示，不注入主链路**  
- 最简单，零风险
- 缺点：用户在课中无法得到任何即时语法指导，影响学习效果

### 结论

采用 A（注入下一轮 system prompt），兼顾自然性和实现简单性。  
`_pending_hints` 用 `pop` 保证一条 hint 只消费一次，避免重复提示。  
C 方案（WebSocket push）已在设计上预留，未来可作为增强。

### 触发阈值

仅 `type == "grammar"` 且 `suggestion` 非空的纠错触发注入，上限 2 条/轮。  
`vocabulary`/`expression` 类纠错不触发注入，留给总结。

---

## DD-04: 对话流中断策略（流程优先 vs 纠错优先）

**决策时间**: 2026-06-07  
**相关 PR**: `feat/natural-dialogue-flow`

### 背景

原 system prompt 对 `inline_correction` 触发条件不够明确，LLM 倾向于
对轻微语法错误（如 "me want" 代替 "I want"）立即给出提示，中断点餐流程。

### 选项

**A. 流程优先：只在真实误解时打断（采用）**  
- 明确定义"真实误解" = 服务员在现实中完全不知道客人想要什么
- 轻微语法、时态、冠词错误 → 不打断
- 菜单项名称完全错误 / 自相矛盾的要求 → 打断
- 优点：对话流畅，接近真实餐厅体验，语言学习者更有信心
- 缺点：小错误可能积累，用户需等到总结才知道

**B. 及时纠错：每次错误都提示**  
- 所有 grammar/vocabulary 错误即时提示
- 缺点：频繁打断体验差，学习者容易沮丧，不符合"口语练习"定位

**C. 用户可配置阈值**  
- 提供"严格/标准/宽松"三个纠错模式
- 优点：灵活
- 缺点：实现复杂，MVP 阶段过早

### 结论

采用 A，在 system prompt 中明确用自然语言定义触发条件，并通过 `CHAT_SYSTEM_SUFFIX`
约束 `inline_correction` 的输出条件。C 方案留作 v2 增强。

---

## DD-05: 方言选择（en-us / en-gb）

**相关 PR**: `feat/dialect-selection`

Session 携带 `dialect` 字段，TTS voice 和 SpeechAce 评分方言均随之切换。
- `POST /api/session?dialect=en-gb` 存入 Session
- `get_voice_for_dialect()` 映射 dialect → MiniMax voice_id（可通过环境变量配置）
- `PronService.assess(..., dialect=None)` 无指定时回退到 `SPEECHACE_DIALECT` 环境变量
---

## DD-06 — Opening Greeting Pre-generation

**Branch**: feat/opening-greeting  
**Decision**: Pre-generate the opening TTS audio ("Welcome! What can I get for you today?") in a background task immediately after session creation, storing bytes in `_greeting_cache[session_id]`. On the first WebSocket turn, use the cached audio instead of calling TTS.

**Implementation**:
- `POST /api/session` uses FastAPI `BackgroundTasks` to launch `_pregenerate_greeting(sid, services)`
- `_pregenerate_greeting` runs `asyncio.to_thread(tts.synthesize, OPENING_LINE)` and stores result in `_greeting_cache`
- `ws_turn` checks `len(session.turns) == 0 and session_id in _greeting_cache`; if true, pops cache entry and skips TTS call (first-turn `tts_ms` is None)
- Cache entries are evicted on: first use (pop), `finish()` REST call, and WebSocket disconnect (finally block)

**Rationale**: TTS synthesis adds ~500ms latency to every turn. The opening line is fixed and predictable, so it can be synthesized speculatively during the time the user opens their microphone. The cache pop on first use ensures the pre-generated audio is never replayed accidentally on subsequent turns.

**Alternatives considered**: Pre-generate every assistant turn speculatively — too wasteful and often wrong. Streaming TTS — larger refactor; see DD-07 aspirations. Client-side caching — requires frontend change.

---

## DD-07 — Dialogue History Truncation

**Branch**: feat/history-truncation  
**Decision**: Cap the history sent to the LLM at `DIALOGUE_HISTORY_WINDOW` turns (default 8). For sessions exceeding the window, always include `turns[0]` (opening context that sets the scenario) plus the last `window-1` turns.

**Implementation**:
- `DIALOGUE_HISTORY_WINDOW` env var added to `config.py` (default `8`)
- `DialogueService._history()` applies truncation: `[turns[0]] + turns[-(window-1):]` when `len(turns) > window`
- Result: at most `window * 2` messages passed to the LLM

**Rationale**: Full history grows linearly with session length, wasting tokens and increasing latency for long sessions. Keeping `turns[0]` preserves the scenario opening (e.g. the user's initial order context), while the recent window maintains conversational coherence. 8 turns covers typical ordering sessions end-to-end.

**Alternatives considered**: Summarize old turns — adds LLM call overhead. Rolling window without anchor — risks losing scenario context. Fixed 8-turn limit — chosen; configurable via env var.

---

## DD-08 — `/api/health` Endpoint

**Branch**: feat/health-endpoint  
**Decision**: Add `GET /api/health` returning `{"status": "ok", "keys_configured": {"minimax": bool, "speechace": bool}}`.

**Rationale**: Without a health endpoint, load balancers and CI pipelines have no way to verify the app is running and configured. The `keys_configured` field distinguishes a running-but-broken deploy (keys missing) from a healthy one without exposing key values.


---

## DD-09 — Startup API Key Warnings + Lazy env var reading in `get_settings()`

**Branch**: feat/missing-key-warnings  
**Decision**: (a) `warn_missing_keys()` in `config.py` logs `WARNING`-level messages for each missing required key at startup. (b) `get_settings()` now constructs `Settings` with explicit `os.getenv()` calls instead of relying on class-level default values.

**Rationale for (a)**: Silent failures when keys are absent produce cryptic HTTP 401/500 errors deep in a request. Warning at startup makes misconfiguration immediately visible in logs.

**Rationale for (b)**: Python dataclass field defaults are evaluated at class-definition time (module import), so the original `str = os.getenv(...)` pattern captured env var values once and never updated them. Moving reads into `get_settings()` makes the function truly reflect the current environment, which also enables `pytest`'s `monkeypatch.setenv/delenv` to work correctly without module reloads.



---

## DD-10 — `GET /api/session/{id}/turns` Endpoint

**Branch**: feat/turns-endpoint  
**Decision**: Add a REST endpoint that returns all turns for a session as a JSON array, including user transcript, assistant text, pronunciation scores, corrections, and timings.

**Rationale**: The existing `GET /api/session/{id}/summary` aggregates scores but discards per-turn detail. A frontend "review mode" or debugging workflow needs turn-by-turn data (e.g., which specific utterance had the low pronunciation score, what the assistant said at each step). The `Turn.model_dump()` serialization is already complete and includes all fields.

---

## DD-11 — Summary Scoring When Pronunciation Data Is Absent

**Branch**: fix/summary-missing-pronunciation

**Decision**: When no turns have pronunciation data (e.g., browser STT unavailable, audio not recorded), `build_summary` sets `overall = grammar` instead of `0.5*0 + 0.3*0 + 0.2*grammar`.

**Rationale**: The original formula zeroed 80% of the overall score when pronunciation was simply uncollected — unfairly penalizing users. The fix distinguishes "no pronunciation data" (skip pron/fluency from weighting) from "pronunciation scored zero" (include in weighting). Sub-scores still report 0.0 for transparency.

---

## DD-12 — `GET /api/sessions` Session List Endpoint

**Branch**: feat/session-listing

**Decision**: `GET /api/sessions?limit=50` returns all sessions ordered by `created_at DESC` with basic metadata (id, scenario, status, created_at, completed_at). Turns are not included (avoiding N+1 load). `Storage.list_sessions(limit)` queries the sessions table directly.

**Rationale**: Any real history UI needs to enumerate past sessions. Without this, clients would need to guess session IDs. The limit parameter prevents accidentally loading very large databases.

---

## DD-13 — Scenario Difficulty Levels

**Branch**: feat/scenario-difficulty

**Decision**: Sessions carry a `difficulty` field (`beginner` | `intermediate` | `advanced`). The LLM system prompt adjusts language complexity and waiter behavior per level.

**Implementation**:
- `Session.difficulty: str = "beginner"` — stored in DB
- `POST /api/session?difficulty=advanced` with regex pattern validation
- `build_system_prompt(items, difficulty="beginner")` — `_DIFFICULTY_NOTES` dict maps each level to behavioral instructions
- `DialogueService.run_turn(..., system_prompt=None)` — accepts optional override; `main.py` pre-computes all 3 prompts at startup and passes the right one per turn
- Unknown difficulty silently falls back to "beginner"

**Level behaviors**:
- beginner: speak slowly, simple vocabulary, repeat order back, rephrase if confused
- intermediate: natural pace, follow-up questions (size, drink, sides)
- advanced: restaurant jargon, allergies/substitutions, upselling, brisk pace

**Alternatives considered**: Per-session system_prompt stored in DB — too flexible and untestable. Single prompt with difficulty variable injection — complex prompt, less predictable behavior.

---

## DD-14 — `GET /api/session/{id}/weak-words`

**Branch**: feat/weak-words-endpoint

**Decision**: Returns the N lowest-scoring words aggregated across all turns (averaged by word, sorted ascending by score, with occurrence count). Default N=5.

**Implementation**:
- Collects `WordScore` objects from all turns with pronunciation data
- Groups by `word.lower()` to handle capitalisation
- Averages scores for repeated words, records occurrence count
- Sorts ascending and returns first N entries

**Rationale**: The summary already returns all word scores, but unsorted and without deduplication. A focused "weakest words" view lets students see exactly what to practice without parsing a large array. Useful for spaced-repetition flashcard integration.

---

## DD-15 — `GET /api/session/{id}/status`

**Branch**: feat/session-status-endpoint

**Decision**: Lightweight status endpoint that returns session metadata and `turn_count` without deserializing any turn JSON. Uses a COUNT query instead of loading all turns.

**Rationale**: `GET /api/session/{id}/summary` and `GET /api/session/{id}/turns` both load all turn data. Polling for session completion (e.g., waiting for finish()) doesn't need turn data — just `status` and `turn_count`. The lightweight query avoids O(turns) JSON deserialization on every poll.

