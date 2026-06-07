import time
from app.models import Session, LlmReply
from app.services.dialogue import DialogueService


class FakeLlm:
    def __init__(self, reply): self._reply = reply
    def chat(self, system_prompt, history, user_text):
        self.seen = dict(system_prompt=system_prompt, history=history, user_text=user_text)
        return self._reply


class MemStorage:
    def __init__(self): self.turns = []
    def save_turn(self, t): self.turns.append(t)


def make_session():
    return Session(id="s1", scenario="ordering", created_at=time.time())


def test_run_turn_builds_history_from_prior_turns():
    llm = FakeLlm(LlmReply(reply="Anything else?", goal_reached=False))
    storage = MemStorage()
    svc = DialogueService(llm=llm, storage=storage, system_prompt="SERVE")
    s = make_session()
    t1 = svc.run_turn(s, user_text="I want a latte")
    s.turns.append(t1)
    svc.run_turn(s, user_text="and a burger")
    # 第二轮 history 含第一轮 user+assistant
    assert llm.seen["history"] == [
        {"role": "user", "content": "I want a latte"},
        {"role": "assistant", "content": "Anything else?"},
    ]


def test_run_turn_records_llm_timing_and_persists():
    llm = FakeLlm(LlmReply(reply="Sure!", goal_reached=True))
    storage = MemStorage()
    svc = DialogueService(llm=llm, storage=storage, system_prompt="SERVE")
    s = make_session()
    turn = svc.run_turn(s, user_text="that's all")
    assert turn.assistant_text == "Sure!"
    assert turn.goal_reached is True
    assert turn.timings.llm_ms is not None
    assert storage.turns[-1].id == turn.id


def test_run_turn_injects_inline_hint_into_system_prompt():
    llm = FakeLlm(LlmReply(reply="ok", goal_reached=False))
    svc = DialogueService(llm=llm, storage=MemStorage(), system_prompt="SERVE")
    s = make_session()
    svc.run_turn(s, user_text="me want food", inline_hint="用户用了 me want,可轻点纠正")
    assert "me want" in llm.seen["system_prompt"]
