"""
基准测试：比较两种 STT/评分方案

Method A: 浏览器 Web Speech API (前端 STT, ~0ms 后端) + SpeechAce score_text 评分（副链路异步）
Method B: SpeechAce score_speech (STT + 发音评分 单次调用) — 需 Premium 方案

测试流程:
  1. 用 MiniMax TTS 生成 3 条英文测试音频，音频缓存到 /tmp
  2. 对每段音频分别测量:
     - SpeechAce score_text 延迟（目前可用方案）
     - SpeechAce score_speech 延迟（仅诊断可用性）
  3. 模拟 Method A 完整链路延迟: LLM + TTS（主链路可控部分）
  4. 输出 /tmp/bench_results.json 供报告脚本读取

API 调用预算: MiniMax TTS ×3 + SpeechAce score_text ×3 + score_speech probe ×1 = 7 次
"""
import os
import sys
import time
import json
import httpx
import urllib.parse
from pathlib import Path

# ── 凭证 ──────────────────────────────────────────────────────────────
MINIMAX_API_KEY   = os.environ["MINIMAX_API_KEY"]
MINIMAX_GROUP_ID  = os.environ["MINIMAX_GROUP_ID"]
MINIMAX_TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-02-turbo")
SPEECHACE_KEY     = urllib.parse.unquote(os.environ["SPEECHACE_API_KEY"])
SPEECHACE_BASE    = "https://api2.speechace.com"   # AP-SE Singapore (key region)

TEST_CASES = [
    {"id": "short",  "text": "I'd like a burger, please.",
     "label": "短句 5 词"},
    {"id": "medium", "text": "Can I have the grilled chicken sandwich with a side of fries and a large Coke?",
     "label": "中句 17 词"},
    {"id": "long",   "text": ("Actually, I'm not sure what to get. "
                               "Could you tell me more about your daily specials? "
                               "I'm looking for something light but filling."),
     "label": "长句 27 词"},
]

CACHE_DIR = Path("/tmp/bench_audio")
CACHE_DIR.mkdir(exist_ok=True)


# ── MiniMax TTS ────────────────────────────────────────────────────────
def tts_to_mp3(text: str, cache_path: Path) -> tuple[bytes, float]:
    if cache_path.exists():
        print("    (使用缓存)", end=" ")
        return cache_path.read_bytes(), 0.0
    t0 = time.perf_counter()
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={MINIMAX_GROUP_ID}"
    r = httpx.post(url,
        headers={"Authorization": f"Bearer {MINIMAX_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": MINIMAX_TTS_MODEL, "text": text, "stream": False,
              "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0},
              "audio_setting": {"format": "mp3", "sample_rate": 24000}},
        timeout=30.0)
    r.raise_for_status()
    mp3 = bytes.fromhex(r.json()["data"]["audio"])
    cache_path.write_bytes(mp3)
    return mp3, (time.perf_counter() - t0) * 1000


# ── SpeechAce score_text ────────────────────────────────────────────────
def speechace_score_text(mp3: bytes, ref_text: str) -> tuple[float, dict]:
    t0 = time.perf_counter()
    r = httpx.post(f"{SPEECHACE_BASE}/api/scoring/text/v9/json",
        params={"key": SPEECHACE_KEY, "dialect": "en-us", "user_id": "bench"},
        files={"user_audio_file": ("a.mp3", mp3, "audio/mpeg")},
        data={"text": ref_text},
        timeout=60.0)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    r.raise_for_status()
    return elapsed_ms, r.json()


# ── SpeechAce score_speech probe (1 次，仅探测可用性) ──────────────────
def speechace_score_speech_probe(mp3: bytes) -> tuple[float, str]:
    t0 = time.perf_counter()
    r = httpx.post(f"{SPEECHACE_BASE}/api/scoring/speech/v9/json",
        params={"key": SPEECHACE_KEY, "dialect": "en-us", "user_id": "bench"},
        files={"user_audio_file": ("a.mp3", mp3, "audio/mpeg")},
        data={"relevance_context": "ordering food at a restaurant"},
        timeout=60.0)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    d = r.json()
    return elapsed_ms, d.get("status", "?"), d.get("short_message", "")


# ── 主流程 ─────────────────────────────────────────────────────────────
def main():
    results = []
    probe_done = False

    for case in TEST_CASES:
        print(f"\n{'='*60}")
        print(f"  {case['label']} — \"{case['text'][:60]}\"")

        cache = CACHE_DIR / f"{case['id']}.mp3"
        mp3, tts_ms = tts_to_mp3(case["text"], cache)
        if tts_ms:
            print(f"  TTS:       {tts_ms:.0f}ms  ({len(mp3)} bytes)")
        else:
            print(f"  TTS:       (cached, {len(mp3)} bytes)")

        # --- score_text ---
        print("  score_text:", end=" ", flush=True)
        st_ms, st_raw = speechace_score_text(mp3, case["text"])
        st_ok   = st_raw.get("status") == "success"
        quota   = st_raw.get("quota_remaining", "?")
        ts      = st_raw.get("text_score", {})
        scores  = ts.get("speechace_score", {})
        words   = ts.get("word_score_list", [])
        print(f"{st_ms:.0f}ms  ok={st_ok}  quota={quota}  words={len(words)}  "
              f"scores={json.dumps(scores, ensure_ascii=False)}")

        # --- score_speech probe (只做一次) ---
        ss_ms = ss_status = ss_msg = None
        if not probe_done:
            print("  score_speech (probe):", end=" ", flush=True)
            ss_ms, ss_status, ss_msg = speechace_score_speech_probe(mp3)
            print(f"{ss_ms:.0f}ms  status={ss_status}  msg={ss_msg}")
            probe_done = True

        results.append({
            "id": case["id"],
            "label": case["label"],
            "text": case["text"],
            "word_count": len(case["text"].split()),
            "audio_bytes": len(mp3),
            "tts_ms": round(tts_ms) if tts_ms else 0,
            "score_text_ms": round(st_ms),
            "score_text_ok": st_ok,
            "quota_remaining": quota,
            "speechace_scores": scores,
            "word_scores": [{"word": w["word"], "q": w.get("quality_score")}
                            for w in words],
            "score_speech_probe_ms": round(ss_ms) if ss_ms else None,
            "score_speech_available": (ss_status == "success") if ss_ms else None,
            "score_speech_msg": ss_msg,
        })

    # 写结果
    out = Path("/tmp/bench_results.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n结果已写入 {out}")

    # 打印摘要
    print(f"\n{'='*60}")
    print("摘要")
    print(f"{'ID':<8} {'score_text':>12} {'words':>6} {'score_speech_avail':>20}")
    print("-"*50)
    for r in results:
        ss = r.get("score_speech_available")
        ss_str = str(ss) if ss is not None else "(未测)"
        print(f"{r['id']:<8} {r['score_text_ms']:>10}ms {r['word_count']:>6}  {ss_str:>20}")


if __name__ == "__main__":
    main()
