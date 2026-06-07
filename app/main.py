"""FastAPI 入口:WebSocket 跑主链路(对话+TTS),后台跑副链路(发音+纠错),REST 提供菜单/总结/延迟。
Services 容器集中持有依赖,测试可整体替换为 fake。"""
import asyncio
import base64
import os
import time
import uuid
from dataclasses import dataclass
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.models import Session
from app.storage import Storage
from app.scenarios.ordering import load_menu, build_system_prompt
from app.services.dialogue import DialogueService
from app.services.analysis import analyze_turn, build_summary
from app.services.timing import StepTimer, aggregate_timings
from app.services.llm import LlmService
from app.services.tts import TtsService
from app.services.pron import PronService

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
MENU_PATH = os.path.join("resources", "menu.json")


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
    menu = load_menu(MENU_PATH) if os.path.exists(MENU_PATH) else []
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
    def create_session():
        sid = uuid.uuid4().hex[:12]
        storage.save_session(Session(id=sid, scenario="ordering", created_at=time.time()))
        return {"id": sid}

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
                timer = StepTimer()
                with timer.measure("total"):
                    turn = dialogue.run_turn(session, user_text=user_text)
                    with timer.measure("tts"):
                        audio = services.tts.synthesize(turn.assistant_text)

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
                    # 真实环境此处应先 audio.to_wav_16k(raw, "webm");测试用 fake pron 不解析内容,
                    # 故保留 raw 以免单测依赖 ffmpeg。接真 SpeechAce 时改为转码。
                    wav_bytes = raw
                storage.save_turn(turn)

                # 后台异步分析(发音 + 纠错),不阻塞回包
                asyncio.create_task(_bg_analyze(turn, wav_bytes, services, storage))

                await ws.send_json({
                    "assistant_text": turn.assistant_text,
                    "audio_b64": base64.b64encode(audio).decode(),
                    "inline_correction": turn.inline_correction,
                    "goal_reached": turn.goal_reached,
                    "timings": turn.timings.model_dump(),
                })
        except Exception:  # noqa: BLE001 — 客户端断开等,直接结束连接
            return

    @app.post("/api/session/{session_id}/finish")
    def finish(session_id: str):
        session = storage.get_session(session_id)
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        session.status = "completed"
        session.completed_at = time.time()
        storage.save_session(session)
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


async def _bg_analyze(turn, wav_bytes, services: Services, storage: Storage):
    analyze_turn(turn, wav_bytes, pron=services.pron, llm=services.llm, storage=storage)


app = create_app() if os.getenv("ORAL_TRAINER_BOOT") else None
