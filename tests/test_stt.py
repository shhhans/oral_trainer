from app.services.stt import BrowserStt, SttResult, DashscopeStreamingSession


def test_browser_stt_passthrough():
    stt = BrowserStt()
    res = stt.transcribe(audio=b"ignored", browser_text="I want a latte")
    assert isinstance(res, SttResult)
    assert res.text == "I want a latte"
    assert res.source == "browser"


def test_browser_stt_strips_whitespace():
    res = BrowserStt().transcribe(audio=None, browser_text="  hello  ")
    assert res.text == "hello"


# ── DashscopeStreamingSession (fake recognizer, no SDK/network) ──────────────────

class FakeRecognizer:
    """每 feed 一帧就吐出脚本里的下一个中间结果,模拟 Paraformer 渐进识别。"""
    def __init__(self, session, script):
        self.session = session
        self.script = list(script)
        self.frames = []
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def send_audio_frame(self, buf):
        self.frames.append(buf)
        if self.script:
            self.session._on_text(self.script.pop(0))

    def stop(self):
        self.stopped = True


def _factory(script):
    return lambda session: FakeRecognizer(session, script)


def test_streaming_session_emits_partials_and_final():
    partials = []
    sess = DashscopeStreamingSession(
        on_partial=partials.append,
        recognizer_factory=_factory(["I", "I want", "I want a latte"]),
    )
    for frame in (b"a", b"b", b"c"):
        sess.feed(frame)
    result = sess.final()

    assert partials == ["I", "I want", "I want a latte"]
    assert result.text == "I want a latte"
    assert result.source == "dashscope"


def test_streaming_session_starts_recognizer_on_construct():
    captured = {}

    def factory(session):
        rec = FakeRecognizer(session, [])
        captured["rec"] = rec
        return rec

    sess = DashscopeStreamingSession(on_partial=lambda t: None, recognizer_factory=factory)
    assert captured["rec"].started is True
    sess.final()
    assert captured["rec"].stopped is True


def test_streaming_session_ignores_blank_results():
    partials = []
    sess = DashscopeStreamingSession(
        on_partial=partials.append,
        recognizer_factory=_factory(["", "  ", "hello"]),
    )
    for _ in range(3):
        sess.feed(b"x")
    result = sess.final()
    # 空白中间结果不回传、不覆盖最终文本
    assert partials == ["hello"]
    assert result.text == "hello"


def test_streaming_session_final_is_idempotent():
    rec_holder = {}

    def factory(session):
        rec = FakeRecognizer(session, [])
        rec_holder["rec"] = rec
        return rec

    sess = DashscopeStreamingSession(on_partial=lambda t: None, recognizer_factory=factory)
    sess.final()
    sess.final()  # 第二次不应再次 stop / 报错
    assert rec_holder["rec"].stopped is True
