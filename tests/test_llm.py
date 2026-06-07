import json
from app.models import LlmReply, Correction
from app.services.llm import LlmService, extract_json


def test_extract_json_from_fenced():
    raw = 'prefix ```json\n{"reply":"hi","goal_reached":false}\n``` suffix'
    assert extract_json(raw)["reply"] == "hi"


def test_chat_parses_structured_reply():
    payload = json.dumps({"reply": "Sure, what would you like?",
                          "inline_correction": None, "goal_reached": False})
    svc = LlmService(transport=lambda messages, temperature: payload)
    reply = svc.chat(system_prompt="sys", history=[], user_text="I want coffee")
    assert isinstance(reply, LlmReply)
    assert reply.reply.startswith("Sure")
    assert reply.goal_reached is False


def test_chat_falls_back_on_bad_json():
    # 模型没按 JSON 返回时,降级为纯 reply,不崩
    svc = LlmService(transport=lambda messages, temperature: "Hello there!")
    reply = svc.chat(system_prompt="sys", history=[], user_text="hi")
    assert reply.reply == "Hello there!"
    assert reply.inline_correction is None
    assert reply.goal_reached is False


def test_correct_returns_corrections():
    payload = json.dumps({"corrections": [
        {"type": "grammar", "original": "I no like", "suggestion": "I don't like",
         "explanation": "否定要用 don't"}]})
    svc = LlmService(transport=lambda messages, temperature: payload)
    out = svc.correct("I no like fish")
    assert len(out) == 1
    assert isinstance(out[0], Correction)
    assert out[0].suggestion == "I don't like"


def test_correct_empty_on_no_errors():
    svc = LlmService(transport=lambda messages, temperature: '{"corrections": []}')
    assert svc.correct("I would like a coffee, please.") == []


def test_summarize_comment_returns_text():
    svc = LlmService(transport=lambda messages, temperature: "你的发音不错,注意时态。")
    assert "发音" in svc.summarize_comment(overall=80, weak_points=["时态"])
