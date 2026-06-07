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
    seen = {}
    def transport(wav, text, dialect):
        seen["dialect"] = dialect
        return raw
    svc = PronService(transport=transport)
    pron = svc.assess(b"wavbytes", ref_text="hello world", dialect="en-gb")
    assert pron.overall == 70
    assert seen["dialect"] == "en-gb"


def test_assess_returns_none_without_ref_text():
    svc = PronService(transport=lambda wav, text, d: {})
    assert svc.assess(b"wavbytes", ref_text="") is None


def test_assess_handles_failure_status():
    svc = PronService(transport=lambda wav, text, d: {"status": "error"})
    assert svc.assess(b"x", ref_text="hi") is None


def test_assess_uses_en_gb_dialect():
    """dialect 参数正确传递给 transport。"""
    seen = {}
    def transport(wav, text, dialect):
        seen["dialect"] = dialect
        return {"status": "success", "text_score": {
            "speechace_score": {"pronunciation": 90},
            "fluency": {}, "word_score_list": []}}
    PronService(transport=transport).assess(b"x", ref_text="hello", dialect="en-gb")
    assert seen["dialect"] == "en-gb"
