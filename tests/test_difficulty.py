import pytest
from app.scenarios.registry import SCENARIOS


def test_beginner_prompt_mentions_simple_vocabulary():
    p = SCENARIOS["ordering"].build_prompt("beginner")
    assert "simple" in p.lower() or "slowly" in p.lower() or "suggest" in p.lower()


def test_intermediate_prompt_is_different_from_beginner():
    beginner_p = SCENARIOS["ordering"].build_prompt("beginner")
    intermediate_p = SCENARIOS["ordering"].build_prompt("intermediate")
    assert beginner_p != intermediate_p


def test_advanced_prompt_mentions_vocabulary():
    p = SCENARIOS["ordering"].build_prompt("advanced")
    assert "advanced" in p.lower() or "restrictions" in p.lower() or "complaint" in p.lower()


def test_all_difficulties_include_menu():
    for d in ("beginner", "intermediate", "advanced"):
        p = SCENARIOS["ordering"].build_prompt(d)
        assert "Classic Burger" in p or "ordering" in p.lower() or "restaurant" in p.lower()


def test_unknown_difficulty_falls_back_to_beginner():
    p = SCENARIOS["ordering"].build_prompt("expert")
    beginner_p = SCENARIOS["ordering"].build_prompt("beginner")
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
        def assess(self, wav, ref_text="", dialect="en-us"): return None

    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    client = TestClient(create_app(services=services))

    r = client.post("/api/session?difficulty=advanced")
    assert r.status_code == 200
    assert r.json()["difficulty"] == "advanced"
    assert len(r.json()["menu_items"]) == 16
    assert len(r.json()["task_card"]["tasks"]) == 5
    assert {item["course"] for item in r.json()["menu_items"]} == {
        "appetizer", "main", "dessert", "beverage"}

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
        def assess(self, wav, ref_text="", dialect="en-us"): return None

    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    client = TestClient(create_app(services=services))
    r = client.post("/api/session")
    assert r.json()["difficulty"] == "beginner"
    assert len(r.json()["menu_items"]) == 8
    assert len(r.json()["task_card"]["tasks"]) == 3


def test_websocket_prompt_uses_sampled_menu_and_task(tmp_path):
    from fastapi.testclient import TestClient
    from app.models import LlmReply
    from app.main import create_app, Services

    class RecordingLlm:
        system_prompt = ""

        def chat(self, system_prompt, history, user_text):
            self.system_prompt = system_prompt
            return LlmReply(reply="ok", goal_reached=False)

        def correct(self, text): return []
        def summarize_comment(self, overall, weak_points): return ""

    class FakeTts:
        def synthesize(self, text, voice="x"): return b"AUDIO"

    class FakePron:
        def assess(self, wav, ref_text="", dialect="en-us"): return None

    llm = RecordingLlm()
    client = TestClient(create_app(services=Services(
        llm=llm, tts=FakeTts(), pron=FakePron(),
        db_path=str(tmp_path / "t.db"),
        audio_dir=str(tmp_path / "audio"))))
    session = client.post(
        "/api/session?scenario=ordering&difficulty=advanced").json()

    with client.websocket_connect(f"/ws/{session['id']}") as ws:
        ws.send_json({"type": "turn", "text": "What do you recommend?"})
        ws.receive_json()

    first_item = session["menu_items"][0]
    assert session["restaurant_name"] in llm.system_prompt
    assert first_item["name"] in llm.system_prompt
    assert session["task_card"]["goal"] in llm.system_prompt
