# Design Decisions

## DD-01 — SpeechAce Regional Endpoint (AP-SE Singapore)

**Branch**: fix/speechace-score-text

**Decision**: Use `https://api2.speechace.com` (AP-SE Singapore).

---

## DD-02 — SpeechAce `score_text` (Basic Tier)

**Branch**: fix/speechace-score-text

**Decision**: `score_text` + browser STT instead of `score_speech`. Faster and cheaper.

---

## DD-03 — Natural Dialogue Flow: Flow-First Prompt

**Branch**: feat/natural-dialogue-flow

**Decision**: `inline_correction` fires only for misunderstanding-causing errors.

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

**Decision**: Background task synthesizes fixed opening line at session creation; first turn uses cached audio.

---

## DD-07 — Dialogue History Truncation

**Branch**: feat/history-truncation

**Decision**: `_history()` keeps `turns[0]` + last `window-1` turns. `DIALOGUE_HISTORY_WINDOW` env var (default 8).

---

## DD-08 — `/api/health` Endpoint

**Branch**: feat/health-endpoint

**Decision**: `GET /api/health` returns status + `keys_configured` booleans.

---

## DD-09 — Startup API Key Warnings + Lazy `get_settings()`

**Branch**: feat/missing-key-warnings

**Decision**: `warn_missing_keys()` logs WARNING for missing keys. `get_settings()` reads env vars fresh (enables `monkeypatch`).

---

## DD-10 — `GET /api/session/{id}/turns`

**Branch**: feat/turns-endpoint

**Decision**: REST endpoint returning all turns with full per-turn data.

---

## DD-11 — Summary Scoring When Pronunciation Data Is Absent

**Branch**: fix/summary-missing-pronunciation

**Decision**: `overall = grammar` (not near-zero) when no pronunciation collected.

---

## DD-12 — `GET /api/sessions` Session List Endpoint

**Branch**: feat/session-listing

**Decision**: Returns sessions ordered by `created_at DESC`. Turns not loaded (avoids N+1).

---

## DD-13 — Scenario Difficulty Levels

**Branch**: feat/scenario-difficulty

**Decision**: Session `difficulty` (beginner/intermediate/advanced) adjusts LLM system prompt.

---

## DD-14 — `GET /api/session/{id}/weak-words`

**Branch**: feat/weak-words-endpoint

**Decision**: Returns N lowest-scoring words aggregated across turns (averaged, sorted ascending).

---

## DD-15 — `GET /api/session/{id}/status`

**Branch**: feat/session-status-endpoint

**Decision**: Lightweight status endpoint (no turn deserialization). Uses COUNT query.

---

## DD-16 — SQLite Schema Migration for `difficulty` Column

**Branch**: fix/db-schema-migration

**Decision**: `Storage._migrate()` applies additive `ALTER TABLE` statements at startup; each is wrapped in try/except to be idempotent. `get_session` falls back to "beginner" if the column is absent at read time (pre-migration row).

**Rationale**: `CREATE TABLE IF NOT EXISTS` only creates tables for new databases. Existing databases opened after a column is added would fail `save_session` (OperationalError: table has no column "difficulty"). The migration list in `_migrate()` is append-only — new columns go there, never to the `CREATE TABLE` statement.

**Pattern**: Future column additions should be added to `_migrate()`, not to `CREATE TABLE IF NOT EXISTS`. The table definition stays as the minimal baseline (id + immutable fields); `_migrate()` carries all history.
