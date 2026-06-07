# Design Decisions

## DD-01 — SpeechAce Regional Endpoint (AP-SE Singapore)

**Branch**: fix/speechace-score-text

**Decision**: Use `https://api2.speechace.com` (AP-SE Singapore) instead of the default `https://api.speechace.co` (US West).

---

## DD-02 — SpeechAce `score_text` (Basic Tier)

**Branch**: fix/speechace-score-text

**Decision**: Use `/api/scoring/text/v9/json` (score_text, Basic tier) with browser STT text as reference.

---

## DD-03 — Natural Dialogue Flow: Flow-First Prompt

**Branch**: feat/natural-dialogue-flow

**Decision**: `inline_correction` fires only for errors causing misunderstanding; minor issues deferred to end-of-session summary.

---

## DD-04 — Side-Chain Injection

**Branch**: feat/side-chain-injection

**Decision**: Async grammar correction → `_pending_hints[session_id]` → injected into next turn's system prompt.

---

## DD-05 — Dialect Selection: en-us / en-gb

**Branch**: feat/dialect-selection

**Decision**: Session `dialect` field controls TTS voice and SpeechAce scoring dialect.

---

## DD-06 — Opening Greeting Pre-generation

**Branch**: feat/opening-greeting

**Decision**: Background task synthesizes fixed opening line at session creation; first turn uses cached audio (skips TTS).

---

## DD-07 — Dialogue History Truncation

**Branch**: feat/history-truncation

**Decision**: `_history()` keeps `turns[0]` + last `window-1` turns. Cap via `DIALOGUE_HISTORY_WINDOW` env var (default 8).

---

## DD-08 — `/api/health` Endpoint

**Branch**: feat/health-endpoint

**Decision**: `GET /api/health` returns status + `keys_configured` booleans.

---

## DD-09 — Startup API Key Warnings + Lazy `get_settings()`

**Branch**: feat/missing-key-warnings

**Decision**: `warn_missing_keys()` logs WARNING for missing keys. `get_settings()` reads env vars lazily (enables `monkeypatch`).

---

## DD-10 — `GET /api/session/{id}/turns`

**Branch**: feat/turns-endpoint

**Decision**: REST endpoint returning all turns as JSON for per-turn debugging and review.

---

## DD-11 — Summary Scoring When Pronunciation Data Is Absent

**Branch**: fix/summary-missing-pronunciation

**Decision**: `overall = grammar` (not `0.5*0 + 0.3*0 + 0.2*grammar`) when no pronunciation collected.

---

## DD-12 — `GET /api/sessions` Session List Endpoint

**Branch**: feat/session-listing

**Decision**: Returns sessions ordered by `created_at DESC` with basic metadata. No turns loaded (avoids N+1).

---

## DD-13 — Scenario Difficulty Levels

**Branch**: feat/scenario-difficulty

**Decision**: `Session.difficulty` (beginner/intermediate/advanced) adjusts LLM system prompt behavior. Pre-computed at app startup.

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
