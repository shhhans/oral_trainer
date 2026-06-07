"""SpeechAce 发音测评封装。

使用 score_text (Basic tier) 端点，以浏览器 STT 转写文本作为参考，
对用户实际发音进行逐词评分。
dialect 参数支持 en-us / en-gb，默认从 SPEECHACE_DIALECT 环境变量读取。
score_speech (Premium) 已确认当前账户不可用；如升级可切换 endpoint。
"""
from typing import Callable
import httpx
from app.config import get_settings
from app.models import Pronunciation, WordScore

Transport = Callable[[bytes, str, str], dict]


def normalize_speechace(raw: dict) -> Pronunciation | None:
    if raw.get("status") != "success":
        return None
    ts = raw.get("text_score", {})
    overall = float(ts.get("speechace_score", {}).get("pronunciation", 0))
    # include_fluency requires Pro tier; gracefully default to 0 when absent
    fluency = float(
        ts.get("fluency", {}).get("overall_metrics", {}).get("fluency_score", 0)
    )
    words = [
        WordScore(word=w["word"], score=float(w.get("quality_score", 0)))
        for w in ts.get("word_score_list", [])
    ]
    return Pronunciation(overall=overall, accuracy=overall, fluency=fluency, words=words)


def _default_transport(wav_bytes: bytes, ref_text: str, dialect: str) -> dict:
    s = get_settings()
    resp = httpx.post(
        f"{s.speechace_base_url}/api/scoring/text/v9/json",
        params={"key": s.speechace_api_key, "dialect": dialect,
                "user_id": "oral-trainer"},
        files={"user_audio_file": ("audio.wav", wav_bytes, "audio/wav")},
        data={"text": ref_text},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


class PronService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def assess(self, wav_bytes: bytes, ref_text: str = "",
               dialect: str | None = None) -> Pronunciation | None:
        if not ref_text.strip():
            return None
        if dialect is None:
            dialect = get_settings().speechace_dialect
        try:
            raw = self.transport(wav_bytes, ref_text, dialect)
        except httpx.HTTPError:
            return None
        return normalize_speechace(raw)
