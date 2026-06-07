import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore, Correction
from app.main import create_app, Services


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        done = "done" in user_text
        return LlmReply(reply="Got it." if done else "Anything else?",
                        inline_correction="用了 me want" if "me want" in user_text else None,
                        goal_reached=done)
    def correct(self, text):
        return [Correction(type="grammar", original="me want", suggestion="I want",
                           explanation="主格用 I")] if "me want" in text else []
    def summarize_comment(self, overall, weak_points): return "继续加油"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav, ref_text="", dialect="en-us"):
        return Pronunciation(overall=82, accuracy=82, fluency=78,
                             words=[WordScore(word="latte", score=88)])


def test_full_session_flow(tmp_path):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "a"))
    client = TestClient(create_app(services=services))
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "me want a latte",
                      "audio_b64": base64.b64encode(b"x").decode(), "stt_ms": 120})
        m1 = ws.receive_json()
        assert m1["inline_correction"] is not None
        ws.send_json({"type": "turn", "text": "that is all, I am done",
                      "audio_b64": "", "stt_ms": 90})
        m2 = ws.receive_json()
        assert m2["goal_reached"] is True

    summary = client.post(f"/api/session/{sid}/finish").json()
    assert summary["timing_breakdown"]["samples"] == 2
    assert 0 <= summary["overall_score"] <= 100
    assert any(c["type"] in ("grammar", "inline") for c in summary["correction_list"])
    timing = client.get(f"/api/session/{sid}/timing").json()
    assert timing["stt_avg"] >= 0
