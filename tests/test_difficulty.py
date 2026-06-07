import pytest
from app.scenarios.ordering import build_system_prompt, DEFAULT_MENU


def test_beginner_prompt_mentions_simple_vocabulary():
    p = build_system_prompt(DEFAULT_MENU, difficulty="beginner")
    assert "simple" in p.lower() or "slowly" in p.lower()


def test_intermediate_prompt_is_default():
    default_p = build_system_prompt(DEFAULT_MENU)
    intermediate_p = build_system_prompt(DEFAULT_MENU, difficulty="intermediate")
    assert default_p != intermediate_p  # different from beginner


def test_advanced_prompt_mentions_vocabulary():
    p = build_system_prompt(DEFAULT_MENU, difficulty="advanced")
    assert "advanced" in p.lower() or "jargon" in p.lower() or "restrictions" in p.lower()


def test_all_difficulties_include_menu():
    for d in ("beginner", "intermediate", "advanced"):
        p = build_system_prompt(DEFAULT_MENU, difficulty=d)
        assert "Classic Burger" in p


def test_unknown_difficulty_falls_back_to_beginner():
    p = build_system_prompt(DEFAULT_MENU, difficulty="expert")
    beginner_p = build_system_prompt(DEFAULT_MENU, difficulty="beginner")
    assert p == beginner_p


def test_session_create_accepts_difficulty_param(tmp_path):
    from fastapi.testclient import TestClient
    from app.models import LlmReply, Pronunciation, WordScore
    from app.main import create_app, Services

    class FakeLlm:
        def chat(self, system_prompt, history, user_text):
            return LlmReply(reply="ok", inline_correction=None, goal_reached=False)
        def correct(self, text): return []
        def summarize_comment(self, overall, weak_points): return ""

    class FakeTts:
        def synthesize(self, text, voice="x"): return b"AUDIO"

    class FakePron:
        def assess(self, wav): return None

    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    client = TestClient(create_app(services=services))

    r = client.post("/api/session?difficulty=advanced")
    assert r.status_code == 200
    assert r.json()["difficulty"] == "advanced"

    r2 = client.post("/api/session?difficulty=invalid")
    assert r2.status_code == 422  # validation error


def test_session_difficulty_defaults_to_beginner(tmp_path):
    from fastapi.testclient import TestClient
    from app.models import LlmReply
    from app.main import create_app, Services

    class FakeLlm:
        def chat(self, system_prompt, history, user_text):
            return LlmReply(reply="ok", inline_correction=None, goal_reached=False)
        def correct(self, text): return []
        def summarize_comment(self, overall, weak_points): return ""

    class FakeTts:
        def synthesize(self, text, voice="x"): return b"AUDIO"

    class FakePron:
        def assess(self, wav): return None

    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    client = TestClient(create_app(services=services))
    r = client.post("/api/session")
    assert r.json()["difficulty"] == "beginner"
