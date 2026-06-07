"""各步耗时打点。StepTimer 在主链路用作上下文管理器;aggregate_timings 课后聚合画延迟分解图。"""
import time
from contextlib import contextmanager
from app.models import Turn, TimingBreakdown


class StepTimer:
    def __init__(self) -> None:
        self.results: dict[str, float] = {}

    @contextmanager
    def measure(self, step: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.results[step] = (time.perf_counter() - start) * 1000.0


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def aggregate_timings(turns: list[Turn]) -> TimingBreakdown:
    def col(attr: str) -> list[float]:
        return [getattr(t.timings, attr) for t in turns
                if getattr(t.timings, attr) is not None]
    return TimingBreakdown(
        stt_avg=_avg(col("stt_ms")),
        llm_avg=_avg(col("llm_ms")),
        tts_avg=_avg(col("tts_ms")),
        total_avg=_avg(col("total_ms")),
        samples=len(turns),
    )
