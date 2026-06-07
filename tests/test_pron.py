from app.models import Pronunciation
from app.services.pron import PronService, normalize_speechace


def test_normalize_speechace_extracts_word_scores():
    raw = {"status": "success", "text_score": {
        "speechace_score": {"pronunciation": 88},
        "fluency": {"overall_metrics": {"fluency_score": 82}},
        "word_score_list": [
            {"word": "coffee", "quality_score": 90},
            {"word": "please", "quality_score": 75}]}}
    pron = normalize_speechace(raw)
    assert isinstance(pron, Pronunciation)
    assert pron.overall == 88
    assert pron.fluency == 82
    assert {w.word for w in pron.words} == {"coffee", "please"}


def test_assess_uses_transport():
    raw = {"status": "success", "text_score": {
        "speechace_score": {"pronunciation": 70},
        "fluency": {"overall_metrics": {"fluency_score": 70}},
        "word_score_list": []}}
    svc = PronService(transport=lambda wav: raw)
    pron = svc.assess(b"wavbytes")
    assert pron.overall == 70


def test_assess_handles_failure_status():
    svc = PronService(transport=lambda wav: {"status": "error"})
    assert svc.assess(b"x") is None
