from app.models import (
    WordScore, Pronunciation, Correction, Timings, Turn, Session,
    SubScores, TimingBreakdown, Summary, LlmReply,
)


def test_turn_defaults():
    t = Turn(id="t1", session_id="s1", index=0, user_transcript="I want a coffee")
    assert t.pronunciation is None
    assert t.deferred_corrections == []
    assert t.goal_reached is False
    assert t.timings.total_ms is None
    assert t.timings.response_wait_ms is None


def test_llm_reply_parses_optional_correction():
    r = LlmReply(reply="Sure!", goal_reached=False)
    assert r.inline_correction is None


def test_summary_roundtrip():
    s = Summary(
        session_id="s1", overall_score=82.0,
        sub_scores=SubScores(pronunciation=80, fluency=85, grammar=81),
        word_scores=[WordScore(word="coffee", score=90)],
        correction_list=[Correction(type="grammar", original="I no like",
                                    suggestion="I don't like", explanation="否定用 don't")],
        timing_breakdown=TimingBreakdown(stt_avg=120, llm_avg=900, tts_avg=300,
                                         total_avg=1320, samples=3),
        llm_comment="整体不错",
    )
    dumped = s.model_dump()
    assert Summary(**dumped) == s
