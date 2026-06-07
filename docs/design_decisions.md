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
