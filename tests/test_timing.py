from app.models import Turn, Timings
from app.services.timing import StepTimer, aggregate_timings


def test_step_timer_records_ms():
    timer = StepTimer()
    with timer.measure("llm"):
        sum(range(1000))
    assert timer.results["llm"] >= 0
    assert "llm" in timer.results


def test_aggregate_timings_averages():
    turns = [
        Turn(id="t1", session_id="s", index=0, user_transcript="a",
             timings=Timings(stt_ms=100, llm_ms=800, tts_ms=200, total_ms=1100)),
        Turn(id="t2", session_id="s", index=1, user_transcript="b",
             timings=Timings(stt_ms=200, llm_ms=1000, tts_ms=400, total_ms=1600)),
    ]
    br = aggregate_timings(turns)
    assert br.stt_avg == 150
    assert br.llm_avg == 900
    assert br.samples == 2


def test_aggregate_timings_ignores_none():
    turns = [Turn(id="t1", session_id="s", index=0, user_transcript="a",
                  timings=Timings())]
    br = aggregate_timings(turns)
    assert br.samples == 1
    assert br.llm_avg == 0
