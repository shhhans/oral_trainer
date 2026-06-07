# Design Decisions

## DD-17 — Multi-Scenario Architecture

**Branch:** `feat/multi-scenario`

### Problem
The original codebase had a single hardcoded "ordering" scenario. The system prompt was built once at app startup from a static menu file, applied identically to all sessions with no way to practice different real-life English situations.

### Decision
Introduce a `ScenarioConfig` abstraction with a central registry, giving each scenario:
- A unique `id`, `display_name`, `description`, `opening_line`
- `props` (context facts given to the LLM)
- `base_role` and `difficulty_notes` (beginner / intermediate / advanced)
- A `build_prompt(difficulty)` method

System prompts are pre-computed at app startup for all scenario × difficulty combinations and cached in `_prompts`. Per-session, `ws_turn` looks up the right prompt from `session.scenario`.

### Scenarios added (8 total)

| ID | Display Name | Pain Point |
|----|--------------|------------|
| `ordering` | Restaurant Ordering | Menu vocabulary, polite requests |
| `directions` | Asking for Directions | Spatial prepositions, landmark references |
| `shopping` | Clothes Shopping | Size/color/price vocabulary, retail interactions |
| `hotel` | Hotel Check-in | Reservation vocabulary, service requests |
| `volleyball` | Volleyball Team Communication | Sports calls, team coordination, no-think speed |
| `doctor` | Doctor's Appointment | Symptom vocabulary, medical instructions — survival English |
| `interview` | Job Interview | Professional English, self-intro, STAR method — highest demand |
| `phone` | Phone Appointment | No visual cues — technically hardest for Chinese learners |

### API changes
- `GET /api/scenarios` — list all available scenarios
- `POST /api/session?scenario=hotel&difficulty=intermediate` — creates session with chosen scenario
- Session `scenario` field is stored in DB and used for prompt resolution on every turn

### Trade-offs
- Keeping `difficulty` as a query param (not stored in Session) keeps the DB schema unchanged on this branch; difficulty can be stored in a future PR when the Session model is extended.
- `ordering.py` still exports the old `build_system_prompt` function for backward compatibility with any external tooling.
