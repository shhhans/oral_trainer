"""三条链路可达性测试:MiniMax LLM / MiniMax TTS / SpeechAce 评分。
运行: python scripts/test_connectivity.py
"""
import os
import struct
import sys
import urllib.parse
import httpx

# ── 读取配置 ──────────────────────────────────────────────────────────────────
MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_LLM_MODEL = os.getenv("MINIMAX_LLM_MODEL", "MiniMax-M2")
MINIMAX_TTS_MODEL = os.getenv("MINIMAX_TTS_MODEL", "speech-02-turbo")
SPEECHACE_API_KEY = urllib.parse.unquote(os.getenv("SPEECHACE_API_KEY", ""))

PASS = "\033[32m✓ PASS\033[0m"
FAIL = "\033[31m✗ FAIL\033[0m"


def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print('─'*60)


# ── 1. MiniMax LLM ────────────────────────────────────────────────────────────
def test_llm():
    section("1. MiniMax LLM  (国内站 chatcompletion_v2)")
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    payload = {
        "model": MINIMAX_LLM_MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "temperature": 0.0,
        "max_tokens": 16,
    }
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=20.0,
        )
        print(f"  HTTP {r.status_code}")
        r.raise_for_status()
        body = r.json()
        content = body["choices"][0]["message"]["content"]
        print(f"  模型回复: {content!r}")
        print(f"  {PASS}")
        return True
    except Exception as e:
        print(f"  错误: {e}")
        print(f"  {FAIL}")
        return False


# ── 2. MiniMax TTS ────────────────────────────────────────────────────────────
def test_tts():
    section("2. MiniMax TTS  (国内站 t2a_v2)")
    if not MINIMAX_GROUP_ID:
        print("  ⚠  MINIMAX_GROUP_ID 未配置,跳过 TTS 测试")
        return None
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={MINIMAX_GROUP_ID}"
    payload = {
        "model": MINIMAX_TTS_MODEL,
        "text": "Hello.",
        "stream": False,
        "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0},
        "audio_setting": {"format": "mp3", "sample_rate": 24000},
    }
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        print(f"  HTTP {r.status_code}")
        r.raise_for_status()
        body = r.json()
        audio_hex = body.get("data", {}).get("audio", "")
        audio_bytes = bytes.fromhex(audio_hex)
        print(f"  音频大小: {len(audio_bytes)} bytes")
        if len(audio_bytes) > 0:
            print(f"  {PASS}")
            return True
        else:
            print(f"  返回音频为空  {FAIL}")
            return False
    except Exception as e:
        print(f"  错误: {e}")
        print(f"  {FAIL}")
        return False


# ── 3. SpeechAce 评分 ─────────────────────────────────────────────────────────
def _make_silent_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """生成最小 PCM WAV 静音音频,用于 API 连通性测试。"""
    num_samples = int(sample_rate * duration_s)
    pcm = b'\x00\x00' * num_samples  # 16-bit silence
    data_size = len(pcm)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size,
    )
    return header + pcm


def test_speechace():
    section("3. SpeechAce 发音评分  (AP Southeast Singapore api2.speechace.com)")
    # 用户指定的 Singapore endpoint
    url = "https://api2.speechace.com/api/scoring/speech/v9/json"
    wav_bytes = _make_silent_wav()
    print(f"  测试 WAV: {len(wav_bytes)} bytes (静音)")
    print(f"  Endpoint: {url}")
    print(f"  API Key (前20字符): {SPEECHACE_API_KEY[:20]}…")
    try:
        r = httpx.post(
            url,
            params={"key": SPEECHACE_API_KEY, "dialect": "en-us", "user_id": "oral-trainer-test"},
            files={"user_audio_file": ("audio.wav", wav_bytes, "audio/wav")},
            timeout=30.0,
        )
        print(f"  HTTP {r.status_code}")
        body = r.json()
        print(f"  响应 status: {body.get('status')!r}")
        # 静音音频预期返回 success 或特定 error,只要 HTTP 200 且有 JSON 即为可达
        if r.status_code == 200:
            print(f"  {PASS}  (端点可达,JSON 响应正常)")
            if body.get("status") != "success":
                print(f"  ℹ  静音音频评分结果: {body.get('status')} — 属正常(无有效语音)")
            return True
        else:
            print(f"  {FAIL}")
            return False
    except Exception as e:
        print(f"  错误: {e}")
        print(f"  {FAIL}")
        return False


# ── 汇总 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    results = {
        "MiniMax LLM":  test_llm(),
        "MiniMax TTS":  test_tts(),
        "SpeechAce":    test_speechace(),
    }

    section("汇总")
    all_ok = True
    for name, ok in results.items():
        if ok is None:
            tag = "\033[33m⚠ SKIP\033[0m"
        elif ok:
            tag = PASS
        else:
            tag = FAIL
            all_ok = False
        print(f"  {tag}  {name}")

    print()
    sys.exit(0 if all_ok else 1)
