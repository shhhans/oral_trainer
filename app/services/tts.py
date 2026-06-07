"""MiniMax TTS 封装。返回音频 bytes(mp3),由调用方落盘并回传前端。

dialect 参数控制英式/美式发音（通过 voice_id 实现；MiniMax 没有独立 accent 参数）。
实际可用的 British voice ID 需通过 MINIMAX_VOICE_EN_GB 环境变量配置。
"""
from typing import Callable
import httpx
from app.config import get_settings

Transport = Callable[[str, str], bytes]


def get_voice_for_dialect(dialect: str) -> str:
    """根据方言返回对应的 MiniMax voice_id。"""
    s = get_settings()
    if dialect == "en-gb":
        return s.minimax_voice_en_gb
    return s.minimax_voice_en_us


def _default_transport(text: str, voice: str) -> bytes:
    s = get_settings()
    resp = httpx.post(
        f"https://api.minimax.chat/v1/t2a_v2?GroupId={s.minimax_group_id}",
        headers={"Authorization": f"Bearer {s.minimax_api_key}",
                 "Content-Type": "application/json"},
        json={"model": s.minimax_tts_model, "text": text,
              "stream": False,
              "voice_setting": {"voice_id": voice, "speed": 1.0},
              "audio_setting": {"format": "mp3", "sample_rate": 24000}},
        timeout=30.0,
    )
    resp.raise_for_status()
    return bytes.fromhex(resp.json()["data"]["audio"])


class TtsService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        if voice is None:
            voice = get_voice_for_dialect("en-us")
        return self.transport(text, voice)
