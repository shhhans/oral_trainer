import base64
import pytest
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore
from app.main import create_app, Services, _greeting_cache, OPENING_LINE


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        return LlmReply(reply="Sure!", inline_correction=None, goal_reached=False)
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return "ok"


class CountingTts:
    def __init__(self):
        self.calls: list[str] = []

    def synthesize(self, text, voice="x"):
        self.calls.append(text)
        return b"AUDIO_" + text.encode()[:4]


class FakePron:
    def assess(self, wav):
        return Pronunciation(overall=85, accuracy=85, fluency=80,
                             words=[WordScore(word="hi", score=80)])


def make_client(tmp_path, tts=None):
    tts = tts or CountingTts()
    services = Services(llm=FakeLlm(), tts=tts, pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services)), services.tts


def test_greeting_cache_populated_after_session_create(tmp_path):
    client, tts = make_client(tmp_path)
    _greeting_cache.clear()
    sid = client.post("/api/session").json()["id"]
    # Background task runs synchronously in TestClient before response is returned.
    assert sid in _greeting_cache
    assert _greeting_cache[sid] == b"AUDIO_" + OPENING_LINE.encode()[:4]
    _greeting_cache.clear()


def test_first_turn_uses_cache_skips_tts(tmp_path):
    client, tts = make_client(tmp_path)
    _greeting_cache.clear()
    sid = client.post("/api/session").json()["id"]
    assert sid in _greeting_cache  # pre-generated

    pre_calls = list(tts.calls)
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "hello", "audio_b64": ""})
        msg = ws.receive_json()

    # TTS should NOT have been called for first turn (greeting cache used)
    assert tts.calls == pre_calls
    # tts_ms is None because we skipped TTS
    assert msg["timings"]["tts_ms"] is None
    # Cache entry consumed
    assert sid not in _greeting_cache
    _greeting_cache.clear()


def test_second_turn_calls_tts(tmp_path):
    client, tts = make_client(tmp_path)
    _greeting_cache.clear()
    sid = client.post("/api/session").json()["id"]

    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "first turn", "audio_b64": ""})
        ws.receive_json()
        calls_after_first = list(tts.calls)

        ws.send_json({"type": "turn", "text": "second turn", "audio_b64": ""})
        msg = ws.receive_json()

    # TTS called for second turn
    assert len(tts.calls) > len(calls_after_first)
    assert msg["timings"]["tts_ms"] is not None
    _greeting_cache.clear()


def test_finish_clears_greeting_cache(tmp_path):
    client, tts = make_client(tmp_path)
    _greeting_cache.clear()
    sid = client.post("/api/session").json()["id"]
    assert sid in _greeting_cache

    client.post(f"/api/session/{sid}/finish")
    assert sid not in _greeting_cache


def test_disconnect_clears_greeting_cache(tmp_path):
    client, tts = make_client(tmp_path)
    _greeting_cache.clear()
    sid = client.post("/api/session").json()["id"]

    # Don't consume the greeting; disconnect immediately
    with client.websocket_connect(f"/ws/{sid}"):
        pass  # close without sending

    assert sid not in _greeting_cache
    _greeting_cache.clear()
