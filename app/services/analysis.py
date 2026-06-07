"""副链路:单轮异步分析(发音+纠错回填)+ 课程总结聚合。
analyze_turn 在 main.py 里以后台任务调度,不阻塞主链路对话。"""
from app.models import (Session, Turn, Summary, SubScores, WordScore, Correction)
from app.services.timing import aggregate_timings


def grammar_score_from_corrections(avg_corrections: float) -> float:
    """纠错越多语法分越低。每条均值扣 8 分,下限 0。"""
    return max(0.0, 100.0 - 8.0 * avg_corrections)


def analyze_turn(turn: Turn, wav_bytes: bytes | None, pron, llm, storage,
                 dialect: str = "en-us") -> Turn:
    """异步:发音测评 + 细颗粒纠错,回填并存回。pron/llm 为 service 实例。"""
    if wav_bytes is not None:
        turn.pronunciation = pron.assess(wav_bytes, ref_text=turn.user_transcript,
                                         dialect=dialect)
    turn.deferred_corrections = llm.correct(turn.user_transcript)
    storage.save_turn(turn)
    return turn


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def build_summary(session: Session, llm) -> Summary:
    turns = session.turns
    pron_overall = _avg([t.pronunciation.overall for t in turns if t.pronunciation])
    fluency = _avg([t.pronunciation.fluency for t in turns if t.pronunciation])

    corrections: list[Correction] = []
    for t in turns:
        corrections.extend(t.deferred_corrections)
        if t.inline_correction:
            corrections.append(Correction(type="inline", original=t.user_transcript,
                                          suggestion="", explanation=t.inline_correction))
    avg_corr = len(corrections) / len(turns) if turns else 0.0
    grammar = grammar_score_from_corrections(avg_corr)

    word_scores: list[WordScore] = []
    for t in turns:
        if t.pronunciation:
            word_scores.extend(t.pronunciation.words)

    overall = round(0.5 * pron_overall + 0.3 * fluency + 0.2 * grammar, 1)

    weak = []
    if pron_overall < 75: weak.append("发音")
    if fluency < 75: weak.append("流利度")
    if grammar < 75: weak.append("语法")
    comment = llm.summarize_comment(overall=overall, weak_points=weak)

    return Summary(
        session_id=session.id,
        overall_score=overall,
        sub_scores=SubScores(pronunciation=pron_overall, fluency=fluency, grammar=grammar),
        word_scores=word_scores,
        correction_list=corrections,
        timing_breakdown=aggregate_timings(turns),
        llm_comment=comment,
    )
