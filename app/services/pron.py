"""SpeechAce 发音测评封装(provider 抽象,Azure key 到位后替换 transport+normalize)。
归一化为统一 Pronunciation 模型,上层不感知厂商差异。"""
from typing import Callable
import httpx
from app.config import get_settings
from app.models import Pronunciation, WordScore

Transport = Callable[[bytes], dict]


def normalize_speechace(raw: dict) -> Pronunciation | None:
    if raw.get("status") != "success":
        return None
    ts = raw.get("text_score", {})
    overall = float(ts.get("speechace_score", {}).get("pronunciation", 0))
    fluency = float(ts.get("fluency", {}).get("overall_metrics", {}).get("fluency_score", 0))
    words = [WordScore(word=w["word"], score=float(w.get("quality_score", 0)))
             for w in ts.get("word_score_list", [])]
    return Pronunciation(overall=overall, accuracy=overall, fluency=fluency, words=words)


def _default_transport(wav_bytes: bytes) -> dict:
    s = get_settings()
    # SpeechAce spontaneous/自由说评分;dialect=en-us。endpoint/参数以官方文档为准
    resp = httpx.post(
        "https://api.speechace.co/api/scoring/speech/v9/json",
        params={"key": s.speechace_api_key, "dialect": "en-us", "user_id": "oral-trainer"},
        files={"user_audio_file": ("audio.wav", wav_bytes, "audio/wav")},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


class PronService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def assess(self, wav_bytes: bytes) -> Pronunciation | None:
        try:
            raw = self.transport(wav_bytes)
        except httpx.HTTPError:
            return None
        return normalize_speechace(raw)
