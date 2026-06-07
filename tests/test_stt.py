from app.services.stt import BrowserStt, SttResult


def test_browser_stt_passthrough():
    stt = BrowserStt()
    res = stt.transcribe(audio=b"ignored", browser_text="I want a latte")
    assert isinstance(res, SttResult)
    assert res.text == "I want a latte"
    assert res.source == "browser"


def test_browser_stt_strips_whitespace():
    res = BrowserStt().transcribe(audio=None, browser_text="  hello  ")
    assert res.text == "hello"
