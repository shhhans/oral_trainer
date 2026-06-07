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
from app.config import get_settings
from app.models import Session
from app.storage import Storage
from app.scenarios.ordering import load_menu_or_default, build_system_prompt
from app.services.dialogue import DialogueService
from app.services.analysis import analyze_turn, build_summary
from app.services.timing import StepTimer, aggregate_timings
from app.services.audio import to_wav_16k
from app.services.llm import LlmService
from app.services.tts import TtsService
from app.services.pron import PronService

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
MENU_PATH = os.path.join("resources", "menu.json")

# Per-session pending hints from side-chain analysis.
# Populated by _bg_analyze when a serious grammar error is detected;
# consumed (and cleared) at the start of the next user turn.
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
    return Services(llm=LlmService(), tts=TtsService(), pron=PronService(),
                    db_path=os.path.join(s.data_dir, "app.db"),
                    audio_dir=os.path.join(s.data_dir, "audio"))


def create_app(services: Services | None = None) -> FastAPI:
    services = services or default_services()
    storage = Storage(db_path=services.db_path, audio_dir=services.audio_dir)
    menu = load_menu_or_default(MENU_PATH)  # 文件缺失时回退内置菜单,新检出也能用
    system_prompt = build_system_prompt(menu)
    dialogue = DialogueService(llm=services.llm, storage=storage, system_prompt=system_prompt)

    app = FastAPI()
    if os.path.isdir(FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        idx = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(idx) if os.path.exists(idx) else JSONResponse({"ok": True})

    @app.get("/api/menu")
    def get_menu():
        return [m.__dict__ for m in menu]

    @app.post("/api/session")
    def create_session(dialect: str = Query(default="en-us",
                                            pattern="^(en-us|en-gb)$")):
        sid = uuid.uuid4().hex[:12]
        storage.save_session(Session(id=sid, scenario="ordering",
                                     dialect=dialect, created_at=time.time()))
        return {"id": sid, "dialect": dialect}

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
                # Consume any pending hint injected by the previous turn's side-chain analysis.
                inline_hint = _pending_hints.pop(session_id, None)
                timer = StepTimer()
                # LLM/TTS 是同步 HTTP 调用(30-60s 超时),必须丢到 worker 线程,
                # 否则会阻塞 event loop,卡住其它 WebSocket / 请求。
                from app.services.tts import get_voice_for_dialect
                voice = get_voice_for_dialect(session.dialect)
                with timer.measure("total"):
                    turn = await asyncio.to_thread(
                        dialogue.run_turn, session, user_text=user_text,
                        inline_hint=inline_hint)
                    with timer.measure("tts"):
                        audio = await asyncio.to_thread(
                            services.tts.synthesize, turn.assistant_text, voice)

                # 落盘音频 + 计时回填
                turn.assistant_audio_path = storage.save_audio(
                    session_id, turn.id + "_tts", audio, suffix=".mp3")
                turn.timings.tts_ms = timer.results.get("tts")
                turn.timings.stt_ms = data.get("stt_ms")  # 浏览器上报
                turn.timings.total_ms = timer.results.get("total")

                # 用户音频落盘 + 后台副链路分析(不阻塞回包)
                wav_bytes = None
                audio_b64_in = data.get("audio_b64")
                if audio_b64_in:
                    raw = base64.b64decode(audio_b64_in)
                    turn.user_audio_path = storage.save_audio(
                        session_id, turn.id + "_user", raw, suffix=".webm")
                    # 浏览器 MediaRecorder 出的是 webm/opus,SpeechAce 要 16k wav,必须转码。
                    # 转码失败(空/损坏音频,如测试桩)则跳过本轮发音测评。
                    try:
                        wav_bytes = to_wav_16k(raw, "webm")
                    except Exception:  # noqa: BLE001
                        wav_bytes = None
                storage.save_turn(turn)

                # 后台异步分析(发音 + 纠错),不阻塞回包
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
        except Exception:  # noqa: BLE001 — 客户端断开等,直接结束连接
            pass
        finally:
            _pending_hints.pop(session_id, None)  # 断线时清理，防止内存泄漏

    @app.post("/api/session/{session_id}/finish")
    def finish(session_id: str):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        session.status = "completed"
        session.completed_at = time.time()
        storage.save_session(session)
        _pending_hints.pop(session_id, None)  # 会话正常结束时清理
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

    return app


async def _bg_analyze(turn, wav_bytes, services: Services, storage: Storage,
                      dialect: str = "en-us"):
    # analyze_turn 内含同步发音/纠错 HTTP 调用,丢到 worker 线程避免阻塞 event loop
    serious = await asyncio.to_thread(
        analyze_turn, turn, wav_bytes, services.pron, services.llm, storage,
        dialect=dialect)

    if serious:
        # Build a coaching hint for the LLM (instructs the assistant, not the user directly).
        parts = [
            f'用户说了"{c.original}"，语法问题：{c.explanation}（建议改为"{c.suggestion}"）'
            for c in serious
        ]
        hint = "；".join(parts) + "。请在本轮回复中用自然方式轻轻点出，随后继续推进点餐流程。"
        _pending_hints[turn.session_id] = hint


# 模块级导出,支持 `uvicorn app.main:app` 直接启动
app = create_app()
