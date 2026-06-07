"""FastAPI 入口:WebSocket 跑主链路(对话+TTS),后台跑副链路(发音+纠错),REST 提供菜单/总结/延迟。
Services 容器集中持有依赖,测试可整体替换为 fake。"""
import asyncio
import base64
import os
import time
import uuid
from dataclasses import dataclass
from fastapi import FastAPI, Query, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings, warn_missing_keys
from app.models import Session
from app.storage import Storage
from app.scenarios.registry import SCENARIOS
from app.services.dialogue import DialogueService
from app.services.analysis import analyze_turn, build_summary
from app.services.timing import StepTimer, aggregate_timings
from app.services.audio import to_wav_16k
from app.services.llm import LlmService
from app.services.tts import TtsService
from app.services.pron import PronService

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Per-session pending hints from side-chain analysis.
_pending_hints: dict[str, str] = {}


@dataclass
class Services:
    llm: object
    tts: object
    pron: object
    db_path: str
    audio_dir: str


def default_services() -> Services:
    s = get_settings()
    warn_missing_keys()
    return Services(llm=LlmService(), tts=TtsService(), pron=PronService(),
                    db_path=os.path.join(s.data_dir, "app.db"),
                    audio_dir=os.path.join(s.data_dir, "audio"))


def create_app(services: Services | None = None) -> FastAPI:
    services = services or default_services()
    storage = Storage(db_path=services.db_path, audio_dir=services.audio_dir)
    # Pre-compute system prompts for all scenarios × all difficulty levels
    _prompts: dict[str, dict[str, str]] = {
        sid: {d: sc.build_prompt(d) for d in ("beginner", "intermediate", "advanced")}
        for sid, sc in SCENARIOS.items()
    }
    default_prompt = _prompts["ordering"]["beginner"]
    dialogue = DialogueService(llm=services.llm, storage=storage, system_prompt=default_prompt)

    app = FastAPI()
    if os.path.isdir(FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        idx = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(idx) if os.path.exists(idx) else JSONResponse({"ok": True})

    @app.get("/api/health")
    def health():
        s = get_settings()
        return {
            "status": "ok",
            "keys_configured": {
                "minimax": bool(s.minimax_api_key and s.minimax_group_id),
                "speechace": bool(s.speechace_api_key),
            },
        }

    @app.get("/api/scenarios")
    def list_scenarios():
        return [
            {"id": s.id, "name": s.display_name, "description": s.description,
             "opening_line": s.opening_line}
            for s in SCENARIOS.values()
        ]

    @app.get("/api/menu")
    def get_menu():
        from app.scenarios.ordering import DEFAULT_MENU
        return [{"name": m.name, "price": m.price, "desc": m.desc} for m in DEFAULT_MENU]

    @app.get("/api/sessions")
    def list_sessions(limit: int = 50):
        return storage.list_sessions(limit=limit)

    @app.post("/api/session")
    async def create_session(
        scenario: str = Query(default="ordering"),
        dialect: str = Query(default="en-us", pattern="^(en-us|en-gb)$"),
        difficulty: str = Query(default="beginner",
                                pattern="^(beginner|intermediate|advanced)$"),
    ):
        if scenario not in SCENARIOS:
            return JSONResponse({"error": f"Unknown scenario: {scenario}"}, status_code=422)
        sid = uuid.uuid4().hex[:12]
        storage.save_session(Session(id=sid, scenario=scenario,
                                     dialect=dialect, difficulty=difficulty,
                                     created_at=time.time()))
        return {"id": sid, "scenario": scenario, "dialect": dialect, "difficulty": difficulty,
                "opening_line": SCENARIOS[scenario].opening_line}

    @app.websocket("/ws/{session_id}")
    async def ws_turn(ws: WebSocket, session_id: str):
        await ws.accept()
        try:
            while True:
                data = await ws.receive_json()
                if data.get("type") != "turn":
                    continue
                session = storage.get_session(session_id)
                if session is None:
                    await ws.send_json({"error": "session not found"})
                    continue

                user_text = (data.get("text") or "").strip()
                inline_hint = _pending_hints.pop(session_id, None)
                timer = StepTimer()
                from app.services.tts import get_voice_for_dialect
                voice = get_voice_for_dialect(session.dialect)
                sp = _prompts.get(session.scenario, _prompts["ordering"]).get(
                    session.difficulty, default_prompt)
                with timer.measure("total"):
                    turn = await asyncio.to_thread(
                        dialogue.run_turn, session, user_text=user_text,
                        inline_hint=inline_hint, system_prompt=sp)
                    # 始终为本轮真实回复合成音频,确保音画一致
                    with timer.measure("tts"):
                        audio = await asyncio.to_thread(
                            services.tts.synthesize, turn.assistant_text, voice)

                turn.assistant_audio_path = storage.save_audio(
                    session_id, turn.id + "_tts", audio, suffix=".mp3")
                turn.timings.tts_ms = timer.results.get("tts")
                turn.timings.stt_ms = data.get("stt_ms")
                turn.timings.total_ms = timer.results.get("total")

                wav_bytes = None
                audio_b64_in = data.get("audio_b64")
                if audio_b64_in:
                    raw = base64.b64decode(audio_b64_in)
                    turn.user_audio_path = storage.save_audio(
                        session_id, turn.id + "_user", raw, suffix=".webm")
                    try:
                        wav_bytes = to_wav_16k(raw, "webm")
                    except Exception:  # noqa: BLE001
                        wav_bytes = None
                storage.save_turn(turn)

                asyncio.create_task(
                    _bg_analyze(turn, wav_bytes, services, storage,
                                dialect=session.dialect))

                await ws.send_json({
                    "assistant_text": turn.assistant_text,
                    "audio_b64": base64.b64encode(audio).decode(),
                    "inline_correction": turn.inline_correction,
                    "goal_reached": turn.goal_reached,
                    "timings": turn.timings.model_dump(),
                })
        except Exception:  # noqa: BLE001
            pass
        finally:
            _pending_hints.pop(session_id, None)

    @app.post("/api/session/{session_id}/finish")
    def finish(session_id: str):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        session.status = "completed"
        session.completed_at = time.time()
        storage.save_session(session)
        _pending_hints.pop(session_id, None)
        summary = build_summary(session, llm=services.llm)
        storage.save_summary(summary)
        return summary.model_dump()

    @app.get("/api/session/{session_id}/summary")
    def get_summary(session_id: str):
        summary = storage.get_summary(session_id)
        if summary is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return summary.model_dump()

    @app.get("/api/session/{session_id}/timing")
    def get_timing(session_id: str):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return aggregate_timings(session.turns).model_dump()

    @app.get("/api/session/{session_id}/turns")
    def get_turns(session_id: str):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return [t.model_dump() for t in session.turns]

    @app.get("/api/session/{session_id}/status")
    def get_session_status(session_id: str):
        status = storage.get_session_status(session_id)
        if status is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return status

    @app.get("/api/session/{session_id}/weak-words")
    def get_weak_words(session_id: str, n: int = 5):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        totals: dict[str, list[float]] = {}
        for turn in session.turns:
            if turn.pronunciation:
                for ws in turn.pronunciation.words:
                    totals.setdefault(ws.word.lower(), []).append(ws.score)
        averaged = [
            {"word": w, "avg_score": round(sum(scores) / len(scores), 1),
             "occurrences": len(scores)}
            for w, scores in totals.items()
        ]
        averaged.sort(key=lambda x: x["avg_score"])
        return averaged[:n]

    return app


async def _bg_analyze(turn, wav_bytes, services: Services, storage: Storage,
                      dialect: str = "en-us"):
    serious = await asyncio.to_thread(
        analyze_turn, turn, wav_bytes, services.pron, services.llm, storage,
        dialect=dialect)

    if serious:
        parts = [
            f'用户说了"{c.original}"，语法问题：{c.explanation}（建议改为"{c.suggestion}"）'
            for c in serious
        ]
        hint = "；".join(parts) + "。请在本轮回复中用自然方式轻轻点出，随后继续推进对话流程。"
        _pending_hints[turn.session_id] = hint


# 模块级导出,支持 `uvicorn app.main:app` 直接启动
app = create_app()
