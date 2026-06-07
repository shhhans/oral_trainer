"""直接测试 MiniMax TTS API,不依赖应用框架。"""
import os
import sys
import httpx

API_KEY = os.environ.get("MINIMAX_API_KEY", "")
GROUP_ID = os.environ.get("MINIMAX_GROUP_ID", "")
TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-02-turbo")
VOICE = "male-qn-qingse"
TEXT = "Hello! Welcome to our restaurant. What would you like to order today?"

def test_tts():
    if not API_KEY or not GROUP_ID:
        print("ERROR: MINIMAX_API_KEY or MINIMAX_GROUP_ID not set")
        sys.exit(1)

    print(f"Model : {TTS_MODEL}")
    print(f"Voice : {VOICE}")
    print(f"Text  : {TEXT}")
    print(f"Group : {GROUP_ID}")
    print(f"Key   : {API_KEY[:12]}…")
    print()

    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": TTS_MODEL,
        "text": TEXT,
        "stream": False,
        "voice_setting": {"voice_id": VOICE, "speed": 1.0},
        "audio_setting": {"format": "mp3", "sample_rate": 24000},
    }

    print("Sending request to MiniMax TTS…")
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)
        print(f"HTTP status : {resp.status_code}")

        data = resp.json()
        # print full JSON for debugging (mask key)
        import json
        safe = json.dumps(data, ensure_ascii=False, indent=2)
        print("Response JSON:")
        print(safe[:2000])  # trim if huge

        resp.raise_for_status()

        audio_hex = data.get("data", {}).get("audio", "")
        if not audio_hex:
            print("\nERROR: 'data.audio' missing or empty in response")
            sys.exit(1)

        audio_bytes = bytes.fromhex(audio_hex)
        out_path = "/tmp/minimax_tts_test.mp3"
        with open(out_path, "wb") as f:
            f.write(audio_bytes)

        print(f"\nSUCCESS: {len(audio_bytes)} bytes written to {out_path}")

    except httpx.HTTPStatusError as e:
        print(f"\nHTTP error: {e.response.status_code}")
        print(e.response.text[:500])
        sys.exit(1)
    except Exception as e:
        print(f"\nException: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_tts()
