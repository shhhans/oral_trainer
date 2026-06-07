# Design Decisions

## DD-01 — SpeechAce Regional Endpoint (AP-SE Singapore)

**Branch**: fix/speechace-score-text

**Decision**: Use `https://api2.speechace.com` (AP-SE Singapore) instead of the default `https://api.speechace.co` (US West).

---

## DD-02 — SpeechAce `score_text` (Basic Tier)

**Branch**: fix/speechace-score-text

**Decision**: Use `/api/scoring/text/v9/json` (score_text, Basic tier) with browser STT text as reference. Benchmark confirmed ~500ms vs ~1200ms for `score_speech`.

---

## DD-03 — Natural Dialogue Flow: Flow-First Prompt

**Branch**: feat/natural-dialogue-flow

**Decision**: `inline_correction` fires only for errors that would cause misunderstanding. Minor grammar mistakes deferred to end-of-session summary.

---

## DD-04 — Side-Chain Injection

**Branch**: feat/side-chain-injection

**Decision**: Async grammar correction writes to `_pending_hints[session_id]`; next turn injects it into the system prompt. Popped on consume, disconnect, and finish().

---

## DD-05 — Dialect Selection: en-us / en-gb

**Branch**: feat/dialect-selection

**Decision**: Session carries `dialect` field. TTS voice (`MINIMAX_VOICE_EN_US`/`MINIMAX_VOICE_EN_GB`) and SpeechAce scoring dialect both follow it.

---

## DD-06 — Opening Greeting Pre-generation

**Branch**: feat/opening-greeting

**Decision**: Session creation launches a background task to synthesize the fixed opening line; first WebSocket turn uses cached audio (skips TTS, `tts_ms=None`). Cache evicted on first use, finish(), and disconnect.

---

## DD-07 — Dialogue History Truncation

**Branch**: feat/history-truncation

**Decision**: `DialogueService._history()` keeps `turns[0]` + last `window-1` turns when session exceeds `DIALOGUE_HISTORY_WINDOW` (default 8). Prevents unbounded token growth.

---

## DD-08 — `/api/health` Endpoint

**Branch**: feat/health-endpoint

**Decision**: `GET /api/health` returns `{"status": "ok", "keys_configured": {"minimax": bool, "speechace": bool}}` for load balancers and CI.

---

## DD-09 — Startup API Key Warnings + Lazy `get_settings()`

**Branch**: feat/missing-key-warnings

**Decision**: (a) `warn_missing_keys()` logs WARNING for each missing required key. (b) `get_settings()` constructs `Settings` with explicit `os.getenv()` calls so `monkeypatch` works in tests.

---

## DD-10 — `GET /api/session/{id}/turns`

**Branch**: feat/turns-endpoint

**Decision**: REST endpoint returning all turns as JSON array, enabling frontend review mode and debugging (per-turn pronunciation, corrections, timings).

---

## DD-11 — Summary Scoring When Pronunciation Data Is Absent

**Branch**: fix/summary-missing-pronunciation

**Decision**: When no turns have pronunciation data, `overall = grammar` instead of `0.5*0 + 0.3*0 + 0.2*grammar`. Prevents unfair near-zero scores when audio unavailable.

---

## DD-12 — `GET /api/sessions` Session List Endpoint

**Branch**: feat/session-listing

**Decision**: `GET /api/sessions?limit=50` returns sessions ordered by `created_at DESC` with basic metadata. `Storage.list_sessions(limit)` queries sessions table directly (no turns loaded).

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
