# Design Decisions

## DD-01 — SpeechAce Regional Endpoint (AP-SE Singapore)

**Branch**: fix/speechace-score-text  
**Decision**: Use `https://api2.speechace.com` (AP-SE Singapore) instead of the default `https://api.speechace.co` (US West).

**Rationale**: API key was provisioned for the AP-SE region. Requests to US West returned 401. Introduced `SPEECHACE_BASE_URL` env var (default `https://api2.speechace.com`) so the endpoint can be overridden without code changes.

---

## DD-02 — SpeechAce `score_text` (Basic Tier) vs `score_speech` (Premium)

**Branch**: fix/speechace-score-text  
**Decision**: Use `/api/scoring/text/v9/json` (score_text, Basic tier) with browser STT text as the reference.

**Rationale**: `score_speech` requires Premium and adds latency to the critical path. Browser Web Speech API gives zero-latency STT at no cost. Method A (Browser STT + SpeechAce score_text) is faster, cheaper, and sufficient for per-word pronunciation scoring. Benchmark confirmed ~500ms end-to-end vs ~1200ms for Method B.

---

## DD-03 — Natural Dialogue Flow: Flow-First Prompt Strategy

**Branch**: feat/natural-dialogue-flow  
**Decision**: The LLM system prompt explicitly prioritizes advancing the ordering scenario over immediate correction. `inline_correction` fires only for errors that would cause misunderstanding; minor grammar mistakes are deferred to end-of-session summary.

**Rationale**: Constant interruptions break immersion. Users practice fluency better when the waiter stays in character and completes the ordering flow. Heavy inline correction is reserved for the async side-chain analysis.

---

## DD-04 — Side-Chain Injection: Async Grammar Analysis → Next-Turn Hint

**Branch**: feat/side-chain-injection  
**Decision**: `_bg_analyze` writes a hint string to module-level `_pending_hints[session_id]` when it detects a serious grammar correction. `ws_turn` pops this hint before each turn and passes it as `inline_hint` to `dialogue.run_turn()`, injecting it into the system prompt.

**Rationale**: Grammar correction runs async (off the critical path). The hint is injected on the *next* user turn rather than the current one, so it never delays the reply. Dict is popped on consume, on WebSocket disconnect, and in `finish()` to avoid memory leaks.

---

## DD-05 — Dialect Selection: en-us / en-gb

**Branch**: feat/dialect-selection  
**Decision**: Sessions carry a `dialect` field (`en-us` | `en-gb`). TTS voice and SpeechAce scoring dialect both follow this field.

**Implementation**:
- `POST /api/session?dialect=en-gb` stores dialect in `Session`
- `get_voice_for_dialect(dialect)` maps dialect → MiniMax voice ID (configurable via `MINIMAX_VOICE_EN_US` / `MINIMAX_VOICE_EN_GB` env vars)
- `PronService.assess(..., dialect=None)` falls back to `SPEECHACE_DIALECT` env var when dialect not provided
- `analyze_turn(... dialect=)` and `_bg_analyze(... dialect=)` thread the dialect through the async path

**Rationale**: MiniMax doesn't expose an accent parameter; accent is encoded in voice_id. British voices exist but IDs are not publicly documented, so we expose `MINIMAX_VOICE_EN_GB` as a user-configurable env var (default `English_Graceful_Lady`). SpeechAce natively supports `en-us` / `en-gb` scoring dialects.

**Alternatives considered**: Auto-detect accent from audio — too complex and unreliable. Per-session override only — chosen approach. System-wide env var only — would prevent per-session switching.

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

**Alternatives considered**: Pre-generate every assistant turn speculatively — too wasteful and often wrong. Streaming TTS — larger refactor. Client-side caching — requires frontend change.

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
