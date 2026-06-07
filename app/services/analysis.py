"""副链路:单轮异步分析(发音+纠错回填)+ 课程总结聚合。
analyze_turn 在 main.py 里以后台任务调度,不阻塞主链路对话。"""
from app.models import (Session, Turn, Summary, SubScores, WordScore, Correction)
from app.services.timing import aggregate_timings


def grammar_score_from_corrections(avg_corrections: float) -> float:
    """纠错越多语法分越低。每条均值扣 8 分,下限 0。"""
    return max(0.0, 100.0 - 8.0 * avg_corrections)


def responsiveness_score(wait_ms: list[float]) -> float:
    """平均每等待 1 秒扣 5 分。无等待数据时不扣分。"""
    if not wait_ms:
        return 100.0
    average_seconds = sum(wait_ms) / len(wait_ms) / 1000
    return round(max(0.0, 100.0 - average_seconds * 5.0), 1)


def analyze_turn(turn: Turn, wav_bytes: bytes | None, pron, llm, storage,
                 dialect: str = "en-us") -> list:
    """异步:发音测评 + 纠错，回填并存回。返回 serious_corrections 供主链路注入。

    serious_corrections: 仅含 type=="grammar" 且有具体建议的项，上限 2 条。
    调用方（main.py）将其格式化为 inline_hint，注入下一轮的 system prompt。
    """
    if wav_bytes is not None:
        turn.pronunciation = pron.assess(wav_bytes, ref_text=turn.user_transcript,
                                         dialect=dialect)
    corrections = llm.correct(turn.user_transcript)
    turn.deferred_corrections = corrections
    storage.save_turn(turn)

    serious = [c for c in corrections if c.type == "grammar" and c.suggestion.strip()]
    return serious[:2]


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
    response_wait = [
        t.timings.response_wait_ms
        for t in turns
        if t.timings.response_wait_ms is not None
    ]
    responsiveness = responsiveness_score(response_wait)
    response_wait_total_ms = round(sum(response_wait), 1)

    word_scores: list[WordScore] = []
    for t in turns:
        if t.pronunciation:
            word_scores.extend(t.pronunciation.words)

    # If no pronunciation data was collected, exclude pron/fluency from overall
    # to avoid unfairly zeroing the score (e.g. browser STT unavailable).
    has_pron = any(t.pronunciation for t in turns)
    if has_pron:
        overall = round(
            0.45 * pron_overall
            + 0.25 * fluency
            + 0.2 * grammar
            + 0.1 * responsiveness,
            1,
        )
    else:
        overall = round(0.8 * grammar + 0.2 * responsiveness, 1)

    weak = []
    if has_pron and pron_overall < 75: weak.append("发音")
    if has_pron and fluency < 75: weak.append("流利度")
    if grammar < 75: weak.append("语法")
    if responsiveness < 75: weak.append("反应速度")
    comment = llm.summarize_comment(overall=overall, weak_points=weak)

    return Summary(
        session_id=session.id,
        overall_score=overall,
        sub_scores=SubScores(
            pronunciation=pron_overall,
            fluency=fluency,
            grammar=grammar,
            responsiveness=responsiveness,
        ),
        word_scores=word_scores,
        correction_list=corrections,
        timing_breakdown=aggregate_timings(turns),
        response_wait_total_ms=response_wait_total_ms,
        llm_comment=comment,
    )
