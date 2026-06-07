"""主链路编排:组装对话历史 → MiniMax 结构化对话 → 计时 → 落盘。
inline_hint 是副链路可随时推入的"即时纠错指令",拼进 system prompt 让 LLM 自然轻点。
TTS 不在此处,由 main.py 调用以便单独计时与回传。"""
import uuid
from app.models import Session, Turn, Timings
from app.services.timing import StepTimer


class DialogueService:
    def __init__(self, llm, storage, system_prompt: str):
        self.llm = llm
        self.storage = storage
        self.system_prompt = system_prompt

    def _history(self, session: Session) -> list[dict]:
        history: list[dict] = []
        for t in session.turns:
            history.append({"role": "user", "content": t.user_transcript})
            history.append({"role": "assistant", "content": t.assistant_text})
        return history

    def run_turn(self, session: Session, user_text: str,
                 inline_hint: str | None = None,
                 system_prompt: str | None = None) -> Turn:
        system_prompt = system_prompt or self.system_prompt
        if inline_hint:
            system_prompt += f"\n\n[即时纠错提示] {inline_hint}"

        timer = StepTimer()
        with timer.measure("llm"):
            reply = self.llm.chat(system_prompt=system_prompt,
                                  history=self._history(session),
                                  user_text=user_text)

        turn = Turn(
            id=uuid.uuid4().hex[:12],
            session_id=session.id,
            index=len(session.turns),
            user_transcript=user_text,
            assistant_text=reply.reply,
            inline_correction=reply.inline_correction,
            goal_reached=reply.goal_reached,
            timings=Timings(llm_ms=timer.results.get("llm")),
        )
        self.storage.save_turn(turn)
        return turn
