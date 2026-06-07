import app.services.audio as audio_mod
from app.services.audio import to_wav_16k


def test_to_wav_16k_invokes_pydub(monkeypatch):
    calls = {}

    class FakeSeg:
        @staticmethod
        def from_file(buf, format=None):
            calls["in_format"] = format
            return FakeSeg()
        def set_frame_rate(self, rate):
            calls["rate"] = rate
            return self
        def set_channels(self, n):
            calls["channels"] = n
            return self
        def export(self, out, format=None):
            calls["out_format"] = format
            out.write(b"WAVDATA")

    monkeypatch.setattr(audio_mod, "AudioSegment", FakeSeg)
    out = to_wav_16k(b"rawwebm", input_format="webm")
    assert out == b"WAVDATA"
    assert calls["rate"] == 16000
    assert calls["channels"] == 1
    assert calls["out_format"] == "wav"
