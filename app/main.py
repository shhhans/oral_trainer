"""FastAPI 入口:WebSocket 跑主链路(对话+TTS),后台跑副链路(发音+纠错),REST 提供菜单/总结/延迟。
Services 容器集中持有依赖,测试可整体替换为 fake。"""
import asyncio
import base64
import json
import os
import queue
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
from app.scenarios.base import ScenarioProp
from app.services.dialogue import DialogueService
from app.services.analysis import analyze_turn, build_summary
from app.services.timing import StepTimer, aggregate_timings
from app.services.audio import to_wav_16k
from app.services.llm import LlmService
from app.services.tts import TtsService
from app.services.pron import PronService
from app.services.stt import DashscopeStreamingSession
from app.services.session_content import sample_menu, sample_task_card

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
DEFAULT_OPENING_AUDIO_URL = "/static/audio/ordering-opening-en-us.mp3"

# Per-session pending hints from side-chain analysis.
_pending_hints: dict[str, str] = {}
HEARTBEAT_FOLLOWUPS = (
    "Are you still there? Take your time.",
    "Would you like me to repeat the question?",
    "Whenever you're ready, what would you like to say?",
)


@dataclass
class Services:
    llm: object
    tts: object
    pron: object
    db_path: str
    audio_dir: str
    # ASR 识别器工厂:注入以便测试用 fake 替换真实 DashScope SDK。None = 用真实实现。
    asr_factory: object = None


def default_services() -> Services:
    s = get_settings()
    warn_missing_keys()
    return Services(llm=LlmService(), tts=TtsService(), pron=PronService(),
                    db_path=os.path.join(s.data_dir, "app.db"),
                    audio_dir=os.path.join(s.data_dir, "audio"))


def create_app(services: Services | None = None) -> FastAPI:
    services = services or default_services()
    storage = Storage(db_path=services.db_path, audio_dir=services.audio_dir)
    # DialogueService keeps a fallback; each turn supplies session-specific context.
    default_prompt = SCENARIOS["ordering"].build_prompt("beginner")
    dialogue = DialogueService(llm=services.llm, storage=storage, system_prompt=default_prompt)

    def prompt_for_session(session: Session) -> str:
        scenario = SCENARIOS.get(session.scenario, SCENARIOS["ordering"])
        props = scenario.props
        if session.menu_items:
            menu = "\n".join(
                f"{item.course}: {item.name} ({item.price}) - {item.description}"
                for item in session.menu_items
            )
            props = [
                ScenarioProp("Restaurant", session.restaurant_name or "Restaurant"),
                ScenarioProp("Available menu", menu),
            ]
        goal = scenario.goal_description
        if session.task_card:
            goal = f"{goal}\nSession mission: {session.task_card.goal}"
        return scenario.build_prompt(
            session.difficulty, props=props, goal_description=goal)

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
                # 前端据此决定走服务端实时 ASR 还是回退浏览器 Web Speech
                "dashscope": bool(s.dashscope_api_key),
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
    def get_menu(session_id: str | None = None):
        if session_id:
            session = storage.get_session(session_id)
            if session is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            if session.menu_items:
                return [
                    {**item.model_dump(), "desc": item.description}
                    for item in session.menu_items
                ]
        from app.scenarios.ordering import DEFAULT_MENU
        return [{"name": m.name, "price": m.price, "desc": m.desc} for m in DEFAULT_MENU]

    @app.get("/api/sessions")
    def list_sessions(limit: int = 50):
        return storage.list_sessions(limit=limit)

    @app.get("/api/history")
    def list_history(limit: int = Query(default=50, ge=1, le=200)):
        return storage.list_history(limit=limit)

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
        task_card = sample_task_card(scenario, difficulty, sid)
        restaurant_name = None
        menu_items = []
        if scenario == "ordering":
            restaurant_name, menu_items = sample_menu(difficulty, sid)
        from app.services.tts import get_voice_for_dialect
        opening_line = SCENARIOS[scenario].opening_line
        opening_audio_b64 = None
        opening_audio_url = None
        if scenario == "ordering" and dialect == "en-us":
            opening_audio_url = DEFAULT_OPENING_AUDIO_URL
        else:
            opening_audio = await asyncio.to_thread(
                services.tts.synthesize,
                opening_line,
                get_voice_for_dialect(dialect),
            )
            opening_audio_b64 = base64.b64encode(opening_audio).decode()
        storage.save_session(Session(
            id=sid, scenario=scenario, dialect=dialect, difficulty=difficulty,
            created_at=time.time(), restaurant_name=restaurant_name,
            menu_items=menu_items, task_card=task_card))
        return {"id": sid, "scenario": scenario, "dialect": dialect, "difficulty": difficulty,
                "opening_line": opening_line,
                "opening_audio_b64": opening_audio_b64,
                "opening_audio_url": opening_audio_url,
                "restaurant_name": restaurant_name,
                "menu_items": [item.model_dump() for item in menu_items],
                "task_card": task_card.model_dump()}

    @app.websocket("/ws/{session_id}")
    async def ws_turn(ws: WebSocket, session_id: str):
        await ws.accept()
        try:
            while True:
                data = await ws.receive_json()
                message_type = data.get("type")
                if message_type not in {"turn", "heartbeat"}:
                    continue
                session = storage.get_session(session_id)
                if session is None:
                    await ws.send_json({"error": "session not found"})
                    continue

                from app.services.tts import get_voice_for_dialect
                voice = get_voice_for_dialect(session.dialect)
                if message_type == "heartbeat":
                    raw_sequence = data.get("sequence")
                    followup_index = raw_sequence if isinstance(raw_sequence, int) else 0
                    followup = HEARTBEAT_FOLLOWUPS[
                        followup_index % len(HEARTBEAT_FOLLOWUPS)
                    ]
                    try:
                        audio = await asyncio.to_thread(
                            services.tts.synthesize, followup, voice)
                    except Exception:  # noqa: BLE001
                        audio = b""
                    await ws.send_json({
                        "type": "heartbeat",
                        "assistant_text": followup,
                        "audio_b64": base64.b64encode(audio).decode() if audio else "",
                    })
                    continue

                user_text = (data.get("text") or "").strip()
                inline_hint = _pending_hints.pop(session_id, None)
                timer = StepTimer()
                sp = prompt_for_session(session)
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
                raw_wait_ms = data.get("response_wait_ms")
                if isinstance(raw_wait_ms, (int, float)) and not isinstance(raw_wait_ms, bool):
                    turn.timings.response_wait_ms = min(
                        max(float(raw_wait_ms), 0.0),
                        3_600_000.0,
                    )
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

    @app.websocket("/ws/asr/{session_id}")
    async def ws_asr(ws: WebSocket, session_id: str):
        """实时 ASR 链路:浏览器流式上传 PCM16/16k,后端喂给 DashScope,回传 partial/final。
        未配 DASHSCOPE_API_KEY 时回 unavailable,前端据此回退浏览器 Web Speech。"""
        await ws.accept()
        if not get_settings().dashscope_api_key:
            await ws.send_json({"type": "unavailable"})
            await ws.close()
            return

        # partial 在 SDK 线程产生,放进线程安全队列,由 async 侧统一回传,避免跨线程 asyncio 调度。
        partials: queue.Queue = queue.Queue()
        try:
            sess = await asyncio.to_thread(
                DashscopeStreamingSession,
                partials.put,
                services.asr_factory,
            )
        except Exception:  # noqa: BLE001
            await ws.send_json({"type": "error"})
            await ws.close()
            return
        await ws.send_json({"type": "ready"})

        async def drain_partials():
            while not partials.empty():
                await ws.send_json({"type": "partial", "text": partials.get()})

        try:
            while True:
                msg = await ws.receive()
                if msg.get("bytes") is not None:
                    await asyncio.to_thread(sess.feed, msg["bytes"])
                    await drain_partials()
                elif msg.get("text"):
                    data = json.loads(msg["text"])
                    if data.get("type") == "stop":
                        result = await asyncio.to_thread(sess.final)
                        await drain_partials()
                        await ws.send_json({"type": "final", "text": result.text})
                        break
        except Exception:  # noqa: BLE001
            # 客户端断开或识别异常:静默结束本次会话,前端按需回退/重试
            pass
        finally:
            await asyncio.to_thread(sess.final)  # 幂等,确保识别器释放
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

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
