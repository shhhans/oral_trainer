"""
测试副链路（side-chain）语法错误注入主链路的完整流程。

覆盖场景：
1. _bg_analyze 检测到严重语法错误时，将 hint 写入 _pending_hints
2. 下一轮 ws_turn 正确消费 hint（作为 inline_hint 传入 run_turn）
3. hint 被消费后清除（不重复注入）
4. 无严重错误时不写入 hint
"""
import asyncio
import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore, Correction
from app.main import create_app, Services, _pending_hints, _bg_analyze


# ── Fakes ─────────────────────────────────────────────────────────────

class GrammarLlm:
    """第一次 correct() 返回语法错误，之后返回空。"""
    def __init__(self):
        self._calls = 0

    def chat(self, system_prompt, history, user_text):
        # 记录传入的 system_prompt 以便断言 inline_hint 是否注入
        self.last_system_prompt = system_prompt
        return LlmReply(reply="Sure!", inline_correction=None, goal_reached=False)

    def correct(self, text):
        self._calls += 1
        if self._calls == 1:
            return [Correction(type="grammar", original="me want",
                               suggestion="I want", explanation="主格用 I")]
        return []

    def summarize_comment(self, overall, weak_points): return "ok"


class VocabLlm:
    """correct() 只返回 vocabulary 错误（不应触发注入）。"""
    def chat(self, system_prompt, history, user_text):
        self.last_system_prompt = system_prompt
        return LlmReply(reply="Got it!", inline_correction=None, goal_reached=False)

    def correct(self, text):
        return [Correction(type="vocabulary", original="burger",
                           suggestion="sandwich", explanation="用词更精准")]

    def summarize_comment(self, overall, weak_points): return "ok"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav, ref_text=""): return None


# ── Helper ─────────────────────────────────────────────────────────────

def make_client(llm, tmp_path):
    services = Services(llm=llm, tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services)), services


# ── Tests ──────────────────────────────────────────────────────────────

def test_bg_analyze_stores_hint_for_grammar_error(tmp_path):
    """_bg_analyze 遇到 grammar 错误时写入 _pending_hints。"""
    from app.models import Turn, Timings
    from app.storage import Storage

    llm = GrammarLlm()
    pron = FakePron()
    storage = Storage(db_path=str(tmp_path / "t.db"),
                      audio_dir=str(tmp_path / "audio"))

    turn = Turn(id="t1", session_id="sess1", index=0,
                user_transcript="me want a burger",
                timings=Timings())

    _pending_hints.pop("sess1", None)  # 清空初始状态

    asyncio.run(_bg_analyze(turn, None,
                            type("S", (), {"pron": pron, "llm": llm})(),
                            storage))

    assert "sess1" in _pending_hints
    hint = _pending_hints["sess1"]
    assert "me want" in hint
    assert "I want" in hint

    _pending_hints.pop("sess1", None)  # 清理


def test_bg_analyze_no_hint_for_vocabulary_only(tmp_path):
    """vocabulary 类纠错不触发注入。"""
    from app.models import Turn, Timings
    from app.storage import Storage

    llm = VocabLlm()
    pron = FakePron()
    storage = Storage(db_path=str(tmp_path / "t.db"),
                      audio_dir=str(tmp_path / "audio"))

    turn = Turn(id="t2", session_id="sess2", index=0,
                user_transcript="I want a burger",
                timings=Timings())

    _pending_hints.pop("sess2", None)

    asyncio.run(_bg_analyze(turn, None,
                            type("S", (), {"pron": pron, "llm": llm})(),
                            storage))

    assert "sess2" not in _pending_hints


def test_hint_consumed_on_next_turn(tmp_path):
    """_pending_hints 中预置 hint 后，下一轮 ws_turn LLM 的 system_prompt 包含该 hint。"""
    llm = GrammarLlm()
    client, _ = make_client(llm, tmp_path)

    sid = client.post("/api/session").json()["id"]

    # 预置 hint，模拟副链路已检测到错误
    hint_text = "用户说了\"me want\"，语法问题：主格用 I（建议改为\"I want\"）。请自然点出。"
    _pending_hints[sid] = hint_text

    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "something else", "stt_ms": 100})
        ws.receive_json()

    # hint 应已被消费（不再存在）
    assert sid not in _pending_hints
    # LLM 收到的 system_prompt 应包含 hint
    assert hint_text in llm.last_system_prompt


def test_hint_consumed_only_once(tmp_path):
    """hint 消费后不重复注入第二轮。"""
    llm = GrammarLlm()
    client, _ = make_client(llm, tmp_path)

    sid = client.post("/api/session").json()["id"]
    _pending_hints[sid] = "TEST HINT"

    with client.websocket_connect(f"/ws/{sid}") as ws:
        # 第一轮：消费 hint
        ws.send_json({"type": "turn", "text": "turn one", "stt_ms": 100})
        ws.receive_json()
        assert sid not in _pending_hints

        # 第二轮：hint 不再存在，system_prompt 不含 TEST HINT
        ws.send_json({"type": "turn", "text": "turn two", "stt_ms": 100})
        ws.receive_json()

    assert "TEST HINT" not in llm.last_system_prompt
