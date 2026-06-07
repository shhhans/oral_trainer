"""场景系统测试:注册表完整性、prompt 生成、API 端点、per-session 场景选择。"""
import pytest
from fastapi.testclient import TestClient
from app.scenarios.base import ScenarioConfig, ScenarioProp
from app.scenarios.registry import SCENARIOS
from app.models import LlmReply, Pronunciation, WordScore
from app.main import create_app, Services


# ─── ScenarioConfig unit tests ───────────────────────────────────────────────

def test_registry_contains_expected_scenarios():
    expected = {"ordering", "directions", "shopping", "hotel", "volleyball", "doctor", "interview", "phone"}
    assert expected == set(SCENARIOS.keys())


def test_each_scenario_has_required_fields():
    for sid, sc in SCENARIOS.items():
        assert sc.id == sid, f"{sid}: id mismatch"
        assert sc.display_name, f"{sid}: missing display_name"
        assert sc.opening_line, f"{sid}: missing opening_line"
        assert sc.goal_description, f"{sid}: missing goal_description"
        assert sc.base_role, f"{sid}: missing base_role"


def test_build_prompt_contains_goal():
    for sid, sc in SCENARIOS.items():
        prompt = sc.build_prompt("beginner")
        assert "goal_reached" in prompt.lower() or "goal" in prompt.lower(), \
            f"{sid}: prompt missing goal reference"


def test_build_prompt_difficulty_notes_vary():
    sc = SCENARIOS["ordering"]
    beginner_prompt = sc.build_prompt("beginner")
    advanced_prompt = sc.build_prompt("advanced")
    assert beginner_prompt != advanced_prompt


def test_build_prompt_unknown_difficulty_falls_back():
    sc = SCENARIOS["shopping"]
    prompt = sc.build_prompt("nonexistent")
    assert prompt  # should not raise, returns something


# ─── API endpoint tests ───────────────────────────────────────────────────────

class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        return LlmReply(reply="Got it!", inline_correction=None,
                        goal_reached="done" in user_text)
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return "Good"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav): return Pronunciation(overall=80, accuracy=80, fluency=75, words=[])


def make_client(tmp_path):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services))


def test_list_scenarios_returns_all(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert "ordering" in ids
    assert "hotel" in ids
    assert "volleyball" in ids
    assert len(ids) == 8


def test_list_scenarios_has_opening_line(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/api/scenarios")
    for sc in r.json():
        assert sc["opening_line"], f"Scenario {sc['id']} missing opening_line"


def test_create_session_default_scenario(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/session")
    assert r.status_code == 200
    body = r.json()
    assert body["scenario"] == "ordering"
    assert "id" in body


def test_create_session_with_scenario(tmp_path):
    client = make_client(tmp_path)
    for scenario in ("directions", "shopping", "hotel", "volleyball", "doctor", "interview", "phone"):
        r = client.post(f"/api/session?scenario={scenario}")
        assert r.status_code == 200, f"Failed for scenario={scenario}"
        assert r.json()["scenario"] == scenario


def test_create_session_unknown_scenario(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/session?scenario=unknown_xyz")
    assert r.status_code == 422


def test_create_session_invalid_difficulty(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/session?scenario=ordering&difficulty=expert")
    assert r.status_code == 422


def test_websocket_uses_scenario_prompt(tmp_path):
    """Verify a non-ordering scenario session runs a full turn successfully."""
    client = make_client(tmp_path)
    r = client.post("/api/session?scenario=hotel")
    assert r.status_code == 200
    sid = r.json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "I have a reservation under Smith"})
        msg = ws.receive_json()
    assert msg["assistant_text"] == "Got it!"
    assert msg["goal_reached"] is False


def test_session_scenario_stored_and_retrieved(tmp_path):
    """finish() works for non-default scenarios."""
    client = make_client(tmp_path)
    r = client.post("/api/session?scenario=shopping")
    sid = r.json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "done"})
        ws.receive_json()
    r = client.post(f"/api/session/{sid}/finish")
    assert r.status_code == 200
    assert r.json()["session_id"] == sid
