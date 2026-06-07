import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore
from app.main import create_app, Services


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        return LlmReply(reply="Sure, a latte!", inline_correction=None,
                        goal_reached="that's all" in user_text)
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return "做得不错"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav, ref_text="", dialect="en-us"):
        return Pronunciation(overall=85, accuracy=85, fluency=80,
                             words=[WordScore(word="latte", score=88)])


def make_client(tmp_path):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services))


def test_health_endpoint(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "keys_configured" in body
    assert "minimax" in body["keys_configured"]
    assert "speechace" in body["keys_configured"]


def test_list_sessions(tmp_path):
    client = make_client(tmp_path)
    # No sessions yet
    assert client.get("/api/sessions").json() == []
    # Create two sessions
    client.post("/api/session")
    client.post("/api/session")
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 2
    assert all("id" in s and "status" in s for s in sessions)
    # limit param
    assert len(client.get("/api/sessions?limit=1").json()) == 1


def test_create_session_and_menu(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/session")
    assert r.status_code == 200
    assert "id" in r.json()
    assert client.get("/api/menu").status_code == 200


def test_websocket_turn_returns_reply_and_audio(tmp_path):
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "I want a latte",
                      "audio_b64": base64.b64encode(b"wav").decode()})
        msg = ws.receive_json()
    assert msg["assistant_text"] == "Sure, a latte!"
    assert base64.b64decode(msg["audio_b64"]) == b"AUDIO"
    # tts_ms may be None on first turn if greeting cache was used
    assert msg["timings"]["total_ms"] is not None
    assert msg["goal_reached"] is False


def test_turns_endpoint_returns_turn_list(tmp_path):
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "I want a latte", "audio_b64": ""})
        ws.receive_json()
    turns = client.get(f"/api/session/{sid}/turns").json()
    assert isinstance(turns, list)
    assert len(turns) == 1
    assert turns[0]["user_transcript"] == "I want a latte"
    assert turns[0]["assistant_text"] == "Sure, a latte!"


def test_turns_endpoint_404_for_unknown_session(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/api/session/doesnotexist/turns")
    assert r.status_code == 404


def test_finish_returns_summary(tmp_path):
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "that's all", "audio_b64": ""})
        ws.receive_json()
    r = client.post(f"/api/session/{sid}/finish")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == sid
    assert 0 <= body["overall_score"] <= 100
    assert client.get(f"/api/session/{sid}/summary").json()["session_id"] == sid
    assert client.get(f"/api/session/{sid}/timing").status_code == 200
