"""STT provider 抽象。
BrowserStt —— 浏览器 Web Speech 已在前端转写,后端透传文本(回退路径,零网络往返)。
DashscopeStreamingSession —— 通义 Paraformer 实时识别:后端流式接收 PCM,边收边回 partial。

recognizer 通过 factory 注入,使会话逻辑可在不依赖 dashscope SDK / 网络的情况下单测,
与 llm.py 的 transport 注入同构。"""
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class SttResult:
    text: str
    source: str  # browser | dashscope


class Stt(Protocol):
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult: ...


class BrowserStt:
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult:
        return SttResult(text=(browser_text or "").strip(), source="browser")


# 一帧 PCM 推进识别器后,识别器通过其 callback 调回 session._on_text。
# factory 接收 session(而非裸 callback),由它自行构造并接线 callback,
# 这样真实实现可子类化 dashscope 的 RecognitionCallback,fake 则直接回调 session。
class Recognizer(Protocol):
    def start(self) -> None: ...
    def send_audio_frame(self, buffer: bytes) -> None: ...
    def stop(self) -> None: ...


PartialCallback = Callable[[str], None]
RecognizerFactory = Callable[["DashscopeStreamingSession"], Recognizer]


class DashscopeStreamingSession:
    """一次流式识别会话。聚合中间结果,结束时返回最终文本。

    on_partial:每次收到非空中间结果时回调(用于实时回传前端)。
    recognizer_factory:注入识别器构造逻辑;缺省构造真实 DashScope Paraformer。
    """

    def __init__(self, on_partial: PartialCallback,
                 recognizer_factory: RecognizerFactory | None = None,
                 language_hints: list[str] | None = None):
        self.on_partial = on_partial
        self._finalized: list[str] = []
        self._current = ""
        self._stopped = False
        factory = recognizer_factory or _default_recognizer_factory(language_hints or ["en"])
        self._recognizer = factory(self)
        self._recognizer.start()

    def feed(self, pcm: bytes) -> None:
        """推一帧 PCM16/16k 音频。"""
        self._recognizer.send_audio_frame(pcm)

    def _aggregate(self) -> str:
        parts = [*self._finalized]
        if self._current:
            parts.append(self._current)
        return " ".join(parts).strip()

    def _on_text(self, text: str, sentence_end: bool = False) -> None:
        """识别器回调:更新当前句,并在句末归档后回传完整聚合文本。"""
        text = (text or "").strip()
        if text:
            self._current = text
        if sentence_end and self._current:
            self._finalized.append(self._current)
            self._current = ""
        if text or sentence_end:
            aggregate = self._aggregate()
            if aggregate:
                self.on_partial(aggregate)

    def final(self) -> SttResult:
        """停止识别并返回最终聚合文本。可重复调用(幂等)。"""
        if not self._stopped:
            self._stopped = True
            try:
                self._recognizer.stop()
            except Exception:  # noqa: BLE001
                pass
        return SttResult(text=self._aggregate(), source="dashscope")


def _default_recognizer_factory(language_hints: list[str]) -> RecognizerFactory:
    """缺省工厂:构造真实 DashScope Paraformer 实时识别器。

    dashscope SDK 仅在此处 import,未安装/未配 key 时不影响其余代码与测试。
    """
    def factory(session: "DashscopeStreamingSession") -> Recognizer:
        import dashscope
        from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
        from app.config import get_settings

        dashscope.api_key = get_settings().dashscope_api_key

        class _Callback(RecognitionCallback):
            # on_event 在 SDK 线程被调用;只做文本提取并回调 session,不做 IO。
            def on_event(self, result) -> None:  # noqa: ANN001
                sentence = result.get_sentence()
                if sentence and sentence.get("text"):
                    session._on_text(
                        sentence["text"],
                        RecognitionResult.is_sentence_end(sentence),
                    )

        return Recognition(
            model="paraformer-realtime-v2", format="pcm",
            sample_rate=16000, language_hints=language_hints,
            callback=_Callback(),
        )

    return factory
