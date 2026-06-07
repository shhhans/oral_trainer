from app.services.tts import TtsService


def test_synthesize_returns_bytes():
    svc = TtsService(transport=lambda text, voice: b"AUDIO")
    out = svc.synthesize("Hello", voice="male-qn-qingse")
    assert out == b"AUDIO"


def test_synthesize_passes_text():
    seen = {}
    def fake(text, voice):
        seen["text"] = text
        return b""
    TtsService(transport=fake).synthesize("Order ready")
    assert seen["text"] == "Order ready"
