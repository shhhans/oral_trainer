import json
from app.models import LlmReply, Correction
from app.services.llm import LlmService, extract_json, CHAT_SYSTEM_SUFFIX

# 点餐专属词:出现在公共 suffix 里就会污染其它场景(hotel/doctor/interview...)
ORDERING_TERMS = ["点餐", "订单", "菜品", "顾客", "点错单", "下单"]


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


def test_chat_suffix_is_scenario_neutral():
    # 公共 suffix 只应规定 JSON 格式,不得含任何点餐专属语义
    for term in ORDERING_TERMS:
        assert term not in CHAT_SYSTEM_SUFFIX, f"suffix 含点餐专属词: {term}"


def test_chat_does_not_inject_ordering_into_other_scenarios():
    captured = {}

    def transport(messages, temperature):
        captured["messages"] = messages
        return json.dumps({"reply": "ok", "goal_reached": False})

    svc = LlmService(transport=transport)
    hotel_prompt = "You are a hotel receptionist. Help the guest check in."
    svc.chat(system_prompt=hotel_prompt, history=[], user_text="Hi")
    system_content = captured["messages"][0]["content"]
    for term in ORDERING_TERMS:
        assert term not in system_content, f"非点餐场景 system prompt 被注入: {term}"


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
