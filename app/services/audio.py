"""浏览器 MediaRecorder 出的多为 webm/opus,而 SpeechAce/通义/Azure 要 16k 单声道 PCM wav。
这是最易踩的格式坑,单独隔离。需系统装 ffmpeg(pydub 依赖)。"""
import io
from pydub import AudioSegment


def to_wav_16k(raw: bytes, input_format: str = "webm") -> bytes:
    seg = AudioSegment.from_file(io.BytesIO(raw), format=input_format)
    seg = seg.set_frame_rate(16000).set_channels(1)
    out = io.BytesIO()
    seg.export(out, format="wav")
    return out.getvalue()
