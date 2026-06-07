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
