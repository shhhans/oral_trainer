import time
from app.models import (Session, Turn, Pronunciation, WordScore, Correction, Timings)
from app.services.analysis import (
    build_summary,
    grammar_score_from_corrections,
    responsiveness_score,
)


class FakeLlm:
    def summarize_comment(self, overall, weak_points): return "总评"


def make_session_with_turns():
    s = Session(id="s1", scenario="ordering", created_at=time.time())
    s.turns = [
        Turn(id="t1", session_id="s1", index=0, user_transcript="I want coffee",
             pronunciation=Pronunciation(overall=90, accuracy=90, fluency=80,
                                         words=[WordScore(word="coffee", score=90)]),
             deferred_corrections=[],
             timings=Timings(stt_ms=100, llm_ms=800, tts_ms=200, total_ms=1100)),
        Turn(id="t2", session_id="s1", index=1, user_transcript="me want burger",
             pronunciation=Pronunciation(overall=70, accuracy=70, fluency=60,
                                         words=[WordScore(word="burger", score=70)]),
             deferred_corrections=[Correction(type="grammar", original="me want",
                                              suggestion="I want", explanation="主格用 I")],
             timings=Timings(stt_ms=120, llm_ms=900, tts_ms=300, total_ms=1320)),
    ]
    return s


def test_grammar_score_decreases_with_errors():
    assert grammar_score_from_corrections(0) == 100
    assert grammar_score_from_corrections(2) < 100


def test_responsiveness_score_uses_average_wait():
    assert responsiveness_score([]) == 100
    assert responsiveness_score([5000, 15000]) == 50
    assert responsiveness_score([30000]) == 0


def test_build_summary_aggregates():
    s = make_session_with_turns()
    summary = build_summary(s, llm=FakeLlm())
    assert summary.session_id == "s1"
    assert summary.sub_scores.pronunciation == 80   # (90+70)/2
    assert summary.sub_scores.fluency == 70         # (80+60)/2
    assert summary.sub_scores.responsiveness == 100
    assert len(summary.word_scores) == 2
    assert len(summary.correction_list) == 1
    assert summary.timing_breakdown.samples == 2
    assert 0 <= summary.overall_score <= 100
    assert summary.llm_comment == "总评"


def test_build_summary_includes_response_wait_in_score():
    s = make_session_with_turns()
    s.turns[0].timings.response_wait_ms = 5000
    s.turns[1].timings.response_wait_ms = 15000

    summary = build_summary(s, llm=FakeLlm())

    assert summary.response_wait_total_ms == 20000
    assert summary.sub_scores.responsiveness == 50
    assert summary.overall_score < 80


def test_build_summary_no_pronunciation_uses_grammar_only():
    """When no pronunciation data exists overall score must equal grammar score."""
    s = Session(id="s2", scenario="ordering", created_at=time.time())
    s.turns = [
        Turn(id="t1", session_id="s2", index=0, user_transcript="I want coffee",
             pronunciation=None, deferred_corrections=[], timings=Timings()),
    ]
    summary = build_summary(s, llm=FakeLlm())
    assert summary.sub_scores.pronunciation == 0.0
    # No pronunciation → overall = grammar (no corrections → grammar=100)
    assert summary.overall_score == summary.sub_scores.grammar


def test_build_summary_no_pronunciation_does_not_penalize():
    """overall_score without pronunciation data should not be near-zero."""
    s = Session(id="s3", scenario="ordering", created_at=time.time())
    s.turns = [
        Turn(id="t1", session_id="s3", index=0, user_transcript="I want coffee",
             pronunciation=None, deferred_corrections=[], timings=Timings()),
    ]
    summary = build_summary(s, llm=FakeLlm())
    # Grammar with no corrections = 100 → overall should be high, not near-zero
    assert summary.overall_score >= 75
