"""DashScope 实时 ASR 可达性自检。
生成 1 秒 16k 正弦 PCM 喂给 Paraformer 实时识别,验证鉴权/连接/事件回传是否通畅。
非测试用例,仅供手动运行:python scripts/check_asr.py"""
import math
import os
import struct
import sys
import time

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback


def make_pcm(seconds=1.0, rate=16000, freq=440.0):
    """生成正弦波 PCM16/16k(纯音不含语音,主要验证链路可达,识别结果可能为空)。"""
    frames = []
    for i in range(int(seconds * rate)):
        v = int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / rate))
        frames.append(struct.pack("<h", v))
    return b"".join(frames)


class Probe(RecognitionCallback):
    def __init__(self):
        self.events, self.opened, self.completed, self.error = [], False, False, None

    def on_open(self):
        self.opened = True

    def on_event(self, result):
        s = result.get_sentence()
        if s:
            self.events.append(s.get("text", ""))

    def on_complete(self):
        self.completed = True

    def on_error(self, result):
        self.error = str(result)


def main():
    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key:
        print("FAIL: DASHSCOPE_API_KEY 未配置")
        return 1
    dashscope.api_key = key
    print(f"key 已读取 (len={len(key)})，发起实时识别…")

    cb = Probe()
    rec = Recognition(model="paraformer-realtime-v2", format="pcm",
                      sample_rate=16000, language_hints=["en"], callback=cb)
    t0 = time.time()
    rec.start()
    pcm = make_pcm()
    frame = 3200  # ~100ms / 帧
    for i in range(0, len(pcm), frame):
        rec.send_audio_frame(pcm[i:i + frame])
        time.sleep(0.1)
    rec.stop()
    dt = (time.time() - t0) * 1000

    print(f"opened={cb.opened} completed={cb.completed} events={cb.events!r} "
          f"error={cb.error} elapsed={dt:.0f}ms")
    if cb.error:
        print("FAIL: 识别返回错误(可能鉴权失败或参数不符)")
        return 1
    print("OK: DashScope 实时 ASR 链路可达(连接+鉴权+事件回传正常)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
