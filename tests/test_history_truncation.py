import os
import pytest
from app.models import Session, Turn, Timings
from app.services.dialogue import DialogueService


class CaptureLlm:
    def __init__(self):
        self.last_history: list[dict] = []

    def chat(self, system_prompt, history, user_text):
        self.last_history = history
        from app.models import LlmReply
        return LlmReply(reply="ok", inline_correction=None, goal_reached=False)


class FakeStorage:
    def save_turn(self, turn): pass


def _make_session(n_turns: int) -> Session:
    session = Session(id="test", scenario="ordering", created_at=0.0)
    for i in range(n_turns):
        session.turns.append(Turn(
            id=f"t{i}", session_id="test", index=i,
            user_transcript=f"user{i}", assistant_text=f"asst{i}",
            timings=Timings(),
        ))
    return session


def _make_service() -> tuple[DialogueService, CaptureLlm]:
    llm = CaptureLlm()
    svc = DialogueService(llm=llm, storage=FakeStorage(), system_prompt="sys")
    return svc, llm


def test_short_session_history_unchanged():
    svc, llm = _make_service()
    session = _make_session(4)
    svc.run_turn(session, user_text="hi")
    assert len(llm.last_history) == 8  # 4 turns × 2 messages


def test_long_session_history_capped_at_window():
    svc, llm = _make_service()
    session = _make_session(12)
    svc.run_turn(session, user_text="hi")
    # window=8: turn[0] + last 7 = 8 turns → 16 messages
    assert len(llm.last_history) <= 8 * 2


def test_long_session_includes_first_turn():
    svc, llm = _make_service()
    session = _make_session(12)
    svc.run_turn(session, user_text="hi")
    assert llm.last_history[0]["content"] == "user0"
    assert llm.last_history[1]["content"] == "asst0"


def test_long_session_includes_most_recent_turns():
    svc, llm = _make_service()
    session = _make_session(12)
    svc.run_turn(session, user_text="hi")
    # Last message pair should be from turn 11 (index 11)
    assert llm.last_history[-2]["content"] == "user11"
    assert llm.last_history[-1]["content"] == "asst11"


def test_exact_window_size_no_truncation():
    svc, llm = _make_service()
    session = _make_session(8)
    svc.run_turn(session, user_text="hi")
    # Exactly 8 turns = window; no truncation
    assert len(llm.last_history) == 16


def test_window_env_var_respected(monkeypatch):
    monkeypatch.setenv("DIALOGUE_HISTORY_WINDOW", "4")
    # Reload settings for each call
    from app import config as cfg_mod
    import importlib
    importlib.reload(cfg_mod)
    from app.services import dialogue as dlg_mod
    importlib.reload(dlg_mod)

    llm = CaptureLlm()
    svc = dlg_mod.DialogueService(llm=llm, storage=FakeStorage(), system_prompt="sys")
    session = _make_session(10)
    svc.run_turn(session, user_text="hi")
    assert len(llm.last_history) <= 4 * 2

    # Restore
    importlib.reload(cfg_mod)
    importlib.reload(dlg_mod)
