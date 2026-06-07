"""/ws/asr 实时 ASR 端点测试。用 fake 识别器,不触 dashscope SDK / 网络。"""
from fastapi.testclient import TestClient
from app.main import create_app, Services


class FakeLlm:
    def chat(self, system_prompt, history, user_text): ...
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return ""


class FakeTts:
    def synthesize(self, text, voice="x"): return b""


class FakePron:
    def assess(self, wav, ref_text="", dialect="en-us"): return None


class FakeRecognizer:
    """每喂一帧就吐脚本里的下一句中间结果。"""
    def __init__(self, session, script):
        self.session = session
        self.script = list(script)

    def start(self): ...

    def send_audio_frame(self, buf):
        if self.script:
            self.session._on_text(self.script.pop(0))

    def stop(self): ...


def make_client(tmp_path, asr_factory=None):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"),
                        asr_factory=asr_factory)
    return TestClient(create_app(services=services))


def test_health_reports_dashscope_capability(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k")
    client = make_client(tmp_path)
    body = client.get("/api/health").json()
    assert body["keys_configured"]["dashscope"] is True


def test_ws_asr_unavailable_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/asr/{sid}") as ws:
        msg = ws.receive_json()
    assert msg == {"type": "unavailable"}


def test_ws_asr_streams_partials_then_final(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k")
    script = ["I", "I want", "I want tea"]
    factory = lambda session: FakeRecognizer(session, script)
    client = make_client(tmp_path, asr_factory=factory)
    sid = client.post("/api/session").json()["id"]

    received = []
    with client.websocket_connect(f"/ws/asr/{sid}") as ws:
        for _ in range(3):
            ws.send_bytes(b"\x00\x01")
            received.append(ws.receive_json())
        ws.send_json({"type": "stop"})
        final = ws.receive_json()

    assert [m["text"] for m in received] == ["I", "I want", "I want tea"]
    assert all(m["type"] == "partial" for m in received)
    assert final == {"type": "final", "text": "I want tea"}
