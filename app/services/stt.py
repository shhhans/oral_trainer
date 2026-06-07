"""STT provider 抽象。
MVP:BrowserStt —— 浏览器 Web Speech 已在前端转写,后端透传文本(零网络往返、延迟最低)。
备选:DashscopeStt(通义 Paraformer)—— 需要后端可控/更高质量时启用,接口一致。"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SttResult:
    text: str
    source: str  # browser | dashscope


class Stt(Protocol):
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult: ...


class BrowserStt:
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult:
        return SttResult(text=(browser_text or "").strip(), source="browser")


# 通义 Paraformer 备选实现(MVP 默认不启用)。启用时注入 transport,接口与 BrowserStt 一致。
# class DashscopeStt:
#     def transcribe(self, audio, browser_text=None) -> SttResult:
#         text = self._recognize(audio)  # 调 DashScope Paraformer 实时识别
#         return SttResult(text=text, source="dashscope")
