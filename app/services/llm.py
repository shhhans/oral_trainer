"""MiniMax M2 封装。主链路对话用结构化输出;副链路出纠错卡与总评。
transport 抽象出 HTTP,默认打 MiniMax chatcompletion_v2,测试注入 fake。"""
import json
import re
from typing import Callable
import httpx
from app.config import get_settings
from app.models import LlmReply, Correction

Transport = Callable[[list[dict], float], str]

CHAT_SYSTEM_SUFFIX = (
    "\n\n严格只输出 JSON,格式:"
    '{"reply": "<你的英文对话回复>", '
    '"inline_correction": "<仅当用户犯了严重/影响理解的错误时,给一句中文即时纠正提示,否则 null>", '
    '"goal_reached": <用户是否已完成本场景目标,true/false>}'
)

CORRECT_PROMPT = (
    "你是英语口语老师。分析下面这句学习者的英文,找出语法/用词/表达问题。"
    "只输出 JSON:{\"corrections\":[{\"type\":\"grammar|vocabulary|expression\","
    "\"original\":\"原文片段\",\"suggestion\":\"建议改法\",\"explanation\":\"中文解释\"}]}。"
    "没有问题就返回 {\"corrections\":[]}。句子:"
)


def extract_json(raw: str) -> dict:
    """容错解析:优先 ```json``` 代码块,其次第一个 {...},失败抛 ValueError。"""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        candidate = brace.group(0) if brace else None
    if candidate is None:
        raise ValueError("no json found")
    return json.loads(candidate)


def _default_transport(messages: list[dict], temperature: float) -> str:
    s = get_settings()
    resp = httpx.post(
        "https://api.minimax.chat/v1/text/chatcompletion_v2",
        headers={"Authorization": f"Bearer {s.minimax_api_key}",
                 "Content-Type": "application/json"},
        json={"model": s.minimax_llm_model, "messages": messages,
              "temperature": temperature},
        timeout=30.0,
    )
    resp.raise_for_status()
    # MiniMax 兼容 OpenAI 格式;若文档不符只改这一行解析
    return resp.json()["choices"][0]["message"]["content"]


class LlmService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def chat(self, system_prompt: str, history: list[dict], user_text: str) -> LlmReply:
        messages = [{"role": "system", "content": system_prompt + CHAT_SYSTEM_SUFFIX}]
        messages += history
        messages.append({"role": "user", "content": user_text})
        raw = self.transport(messages, 0.7)
        try:
            data = extract_json(raw)
            return LlmReply(**data)
        except (ValueError, json.JSONDecodeError, TypeError):
            # 模型没给合法 JSON:降级为纯对话回复,保证主链路不崩
            return LlmReply(reply=raw.strip())

    def correct(self, user_text: str) -> list[Correction]:
        messages = [{"role": "user", "content": CORRECT_PROMPT + user_text}]
        raw = self.transport(messages, 0.0)
        try:
            data = extract_json(raw)
            return [Correction(**c) for c in data.get("corrections", [])]
        except (ValueError, json.JSONDecodeError, TypeError):
            return []

    def summarize_comment(self, overall: float, weak_points: list[str]) -> str:
        prompt = (f"学习者本次口语综合分 {overall:.0f}/100,薄弱点:{', '.join(weak_points) or '无'}。"
                  "用 2-3 句中文给鼓励性总评和一条改进建议。")
        return self.transport([{"role": "user", "content": prompt}], 0.6).strip()
