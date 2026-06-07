"""MiniMax TTS 封装。返回音频 bytes(wav/mp3),由调用方落盘并回传前端。"""
from typing import Callable
import httpx
from app.config import get_settings

Transport = Callable[[str, str], bytes]
DEFAULT_VOICE = "male-qn-qingse"


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
    # MiniMax t2a_v2 返回 data.audio 为 hex 字符串;若文档不符只改这两行
    audio_hex = resp.json()["data"]["audio"]
    return bytes.fromhex(audio_hex)


class TtsService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE) -> bytes:
        return self.transport(text, voice)
