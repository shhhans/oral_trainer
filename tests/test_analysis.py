import time
from app.models import (Session, Turn, Pronunciation, WordScore, Correction, Timings)
from app.services.analysis import build_summary, grammar_score_from_corrections


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


def test_build_summary_aggregates():
    s = make_session_with_turns()
    summary = build_summary(s, llm=FakeLlm())
    assert summary.session_id == "s1"
    assert summary.sub_scores.pronunciation == 80   # (90+70)/2
    assert summary.sub_scores.fluency == 70         # (80+60)/2
    assert len(summary.word_scores) == 2
    assert len(summary.correction_list) == 1
    assert summary.timing_breakdown.samples == 2
    assert 0 <= summary.overall_score <= 100
    assert summary.llm_comment == "总评"
