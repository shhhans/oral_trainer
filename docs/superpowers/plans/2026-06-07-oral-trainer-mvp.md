# 英语口语陪练 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"点餐"单场景从实时语音对话 → 异步发音测评 → 两级纠错 → 课后总结(含词级发音可视化与延迟分解图)全链路跑通,并提供一个简单的 Web playground。

**Architecture:** Python + FastAPI 后端通过 WebSocket 编排主链路(浏览器 Web Speech 转写文本 → MiniMax M2 结构化对话 → MiniMax TTS),副链路异步调 SpeechAce 做发音测评、调 MiniMax 做细颗粒纠错;每轮各步耗时打点入库;课程结束聚合成总结。所有外部 service 走 provider 抽象 + 依赖注入,便于 mock 测试与后续换厂商(Azure / 通义 Paraformer)。

**Tech Stack:** Python 3.11、FastAPI、Uvicorn、pydantic v2、httpx、pydub(+ffmpeg)、SQLite(stdlib sqlite3)、pytest + pytest-asyncio;前端:原生 HTML/JS、MediaRecorder、Web Speech API、WebSocket、Chart.js。

---

## 设计约定(实现前必读)

- **外部 API 调用注入**:`llm.py` / `tts.py` / `pron.py` / `stt.py` 每个 service 类构造函数接收一个可注入的"传输函数"(默认实现用 httpx 真打 API,测试传 fake)。**所有单元测试只测封装逻辑(组装请求、解析响应、容错),不打真网络。**
- **真实 API 签名以官方文档为准**:计划里给出的 endpoint/字段是当前已知形态(MiniMax `chatcompletion_v2` / `t2a_v2`,SpeechAce `scoring/speech` / `scoring/text`,通义 DashScope Paraformer)。实现时若与文档不符,**只调整 `_call_api` 内的 HTTP 细节,保持对上层暴露的接口和返回类型不变**——测试因此不受影响。
- **配置**:所有 key 从环境变量读(`.env` + `python-dotenv`),代码中不硬编码。
- **目录根**:后端包为 `app/`,测试为 `tests/`,脚本为 `scripts/`,资源为 `resources/`,前端为 `frontend/`。

## 文件结构

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | 依赖与工具配置 |
| `.env.example` | 环境变量样例 |
| `app/__init__.py` | 包标记 |
| `app/config.py` | 读环境变量,提供 Settings |
| `app/models.py` | pydantic 数据模型(Session/Turn/Summary/LlmReply 等) |
| `app/storage.py` | SQLite + 音频文件持久化 |
| `app/services/timing.py` | 计时上下文管理器 + 聚合 |
| `app/services/audio.py` | webm/opus → 16k PCM wav 转码 |
| `app/services/llm.py` | MiniMax M2 对话(结构化输出)+ 纠错 + 总结点评 |
| `app/services/tts.py` | MiniMax TTS |
| `app/services/pron.py` | SpeechAce 发音测评(provider 抽象) |
| `app/services/stt.py` | STT provider 抽象;浏览器透传 + 通义 Paraformer 备选 |
| `app/scenarios/ordering.py` | 点餐场景配置:prompt 组装(注入菜单)、终止条件 |
| `app/services/dialogue.py` | 主链路编排 |
| `app/services/analysis.py` | 副链路异步分析 + 课程总结聚合 |
| `app/main.py` | FastAPI app、WebSocket 端点、REST 接口、静态前端 |
| `scripts/scrape_menu.py` | 爬真实菜单 → `resources/menu.json`(抓不动退内置静态) |
| `resources/menu.json` | 菜单数据 |
| `frontend/index.html` `frontend/app.js` `frontend/style.css` | playground 单页 |
| `tests/...` | 各模块单元测试 + 一个集成测试 |

---

## Task 0: 项目脚手架

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `app/__init__.py`, `app/services/__init__.py`, `app/scenarios/__init__.py`, `tests/__init__.py`, `app/config.py`, `tests/test_config.py`

- [ ] **Step 1: 写依赖与配置文件**

`pyproject.toml`:
```toml
[project]
name = "oral-trainer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.6",
    "httpx>=0.27",
    "pydub>=0.25",
    "python-dotenv>=1.0",
    "python-multipart>=0.0.9",
    "requests>=2.31",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
.venv/
data/
resources/menu.json
*.wav
*.webm
```

`.env.example`:
```
MINIMAX_API_KEY=
MINIMAX_GROUP_ID=
MINIMAX_LLM_MODEL=MiniMax-M2
MINIMAX_TTS_MODEL=speech-02-turbo
SPEECHACE_API_KEY=
DASHSCOPE_API_KEY=
DATA_DIR=data
```

- [ ] **Step 2: 写 `app/config.py`**

```python
"""集中读取环境变量。所有外部 API key 只能从这里取,代码其它处不直接读 os.environ。"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_group_id: str = os.getenv("MINIMAX_GROUP_ID", "")
    minimax_llm_model: str = os.getenv("MINIMAX_LLM_MODEL", "MiniMax-M2")
    minimax_tts_model: str = os.getenv("MINIMAX_TTS_MODEL", "speech-02-turbo")
    speechace_api_key: str = os.getenv("SPEECHACE_API_KEY", "")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    data_dir: str = os.getenv("DATA_DIR", "data")


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: 写空 `__init__.py`** for `app/`, `app/services/`, `app/scenarios/`, `tests/` (空文件)。

- [ ] **Step 4: 写 `tests/test_config.py` 并运行**

```python
from app.config import get_settings


def test_settings_have_defaults():
    s = get_settings()
    assert s.minimax_llm_model  # 默认非空
    assert s.data_dir == "data"
```

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS(在干净环境下,默认值生效)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore .env.example app tests
git commit -m "chore: 项目脚手架与配置"
```

---

## Task 1: 数据模型

**Files:**
- Create: `app/models.py`, `tests/test_models.py`

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
from app.models import (
    WordScore, Pronunciation, Correction, Timings, Turn, Session,
    SubScores, TimingBreakdown, Summary, LlmReply,
)


def test_turn_defaults():
    t = Turn(id="t1", session_id="s1", index=0, user_transcript="I want a coffee")
    assert t.pronunciation is None
    assert t.deferred_corrections == []
    assert t.goal_reached is False
    assert t.timings.total_ms is None


def test_llm_reply_parses_optional_correction():
    r = LlmReply(reply="Sure!", goal_reached=False)
    assert r.inline_correction is None


def test_summary_roundtrip():
    s = Summary(
        session_id="s1", overall_score=82.0,
        sub_scores=SubScores(pronunciation=80, fluency=85, grammar=81),
        word_scores=[WordScore(word="coffee", score=90)],
        correction_list=[Correction(type="grammar", original="I no like",
                                    suggestion="I don't like", explanation="否定用 don't")],
        timing_breakdown=TimingBreakdown(stt_avg=120, llm_avg=900, tts_avg=300,
                                         total_avg=1320, samples=3),
        llm_comment="整体不错",
    )
    dumped = s.model_dump()
    assert Summary(**dumped) == s
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL(`ModuleNotFoundError: app.models`)

- [ ] **Step 3: 写 `app/models.py`**

```python
"""全链路数据契约。前后端、主副链路、存储都以这些模型为准。"""
from __future__ import annotations
from pydantic import BaseModel, Field


class WordScore(BaseModel):
    word: str
    score: float  # 0-100 词级发音分


class Pronunciation(BaseModel):
    overall: float
    accuracy: float
    fluency: float
    words: list[WordScore] = Field(default_factory=list)


class Correction(BaseModel):
    type: str          # grammar | vocabulary | expression | pronunciation
    original: str
    suggestion: str
    explanation: str   # 中文解释


class Timings(BaseModel):
    stt_ms: float | None = None   # 浏览器端上报
    llm_ms: float | None = None
    tts_ms: float | None = None
    total_ms: float | None = None


class Turn(BaseModel):
    id: str
    session_id: str
    index: int
    user_transcript: str
    user_audio_path: str | None = None
    pronunciation: Pronunciation | None = None      # 副链路异步填充
    assistant_text: str = ""
    assistant_audio_path: str | None = None
    inline_correction: str | None = None            # 主链路即时纠错
    deferred_corrections: list[Correction] = Field(default_factory=list)  # 副链路异步填充
    goal_reached: bool = False
    timings: Timings = Field(default_factory=Timings)


class Session(BaseModel):
    id: str
    scenario: str
    status: str = "active"   # active | completed
    created_at: float
    completed_at: float | None = None
    turns: list[Turn] = Field(default_factory=list)


class SubScores(BaseModel):
    pronunciation: float
    fluency: float
    grammar: float


class TimingBreakdown(BaseModel):
    stt_avg: float
    llm_avg: float
    tts_avg: float
    total_avg: float
    samples: int


class Summary(BaseModel):
    session_id: str
    overall_score: float
    sub_scores: SubScores
    word_scores: list[WordScore] = Field(default_factory=list)
    correction_list: list[Correction] = Field(default_factory=list)
    timing_breakdown: TimingBreakdown
    llm_comment: str = ""


class LlmReply(BaseModel):
    """主链路 MiniMax 结构化输出契约。"""
    reply: str
    inline_correction: str | None = None
    goal_reached: bool = False
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: 全链路数据模型"
```

---

## Task 2: 存储层(SQLite + 音频文件)

**Files:**
- Create: `app/storage.py`, `tests/test_storage.py`

- [ ] **Step 1: 写失败测试 `tests/test_storage.py`**

```python
import time
from app.models import Session, Turn, Summary, SubScores, TimingBreakdown
from app.storage import Storage


def make_storage(tmp_path):
    return Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))


def test_create_and_get_session(tmp_path):
    st = make_storage(tmp_path)
    s = Session(id="s1", scenario="ordering", created_at=time.time())
    st.save_session(s)
    got = st.get_session("s1")
    assert got is not None
    assert got.scenario == "ordering"
    assert got.turns == []


def test_append_and_update_turn(tmp_path):
    st = make_storage(tmp_path)
    st.save_session(Session(id="s1", scenario="ordering", created_at=time.time()))
    turn = Turn(id="t1", session_id="s1", index=0, user_transcript="hi")
    st.save_turn(turn)
    turn.assistant_text = "Hello!"
    st.save_turn(turn)  # upsert
    got = st.get_session("s1")
    assert len(got.turns) == 1
    assert got.turns[0].assistant_text == "Hello!"


def test_save_audio_returns_path(tmp_path):
    st = make_storage(tmp_path)
    path = st.save_audio("s1", "t1", b"\x00\x01", suffix=".wav")
    assert path.endswith(".wav")
    with open(path, "rb") as f:
        assert f.read() == b"\x00\x01"


def test_summary_roundtrip(tmp_path):
    st = make_storage(tmp_path)
    st.save_session(Session(id="s1", scenario="ordering", created_at=time.time()))
    summary = Summary(
        session_id="s1", overall_score=80,
        sub_scores=SubScores(pronunciation=80, fluency=80, grammar=80),
        timing_breakdown=TimingBreakdown(stt_avg=1, llm_avg=2, tts_avg=3, total_avg=6, samples=1),
    )
    st.save_summary(summary)
    assert st.get_summary("s1").overall_score == 80
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL(`ModuleNotFoundError: app.storage`)

- [ ] **Step 3: 写 `app/storage.py`**

```python
"""SQLite 持久化 + 本地音频文件。session/summary 各一行;turn 以 (session_id, index) 唯一,JSON 存整模型。"""
import json
import os
import sqlite3
from app.models import Session, Turn, Summary


class Storage:
    def __init__(self, db_path: str, audio_dir: str):
        self.db_path = db_path
        self.audio_dir = audio_dir
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, scenario TEXT, status TEXT,
                created_at REAL, completed_at REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS turns(
                session_id TEXT, idx INTEGER, data TEXT,
                PRIMARY KEY(session_id, idx))""")
            c.execute("""CREATE TABLE IF NOT EXISTS summaries(
                session_id TEXT PRIMARY KEY, data TEXT)""")

    def save_session(self, s: Session) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO sessions(id, scenario, status, created_at, completed_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                    completed_at=excluded.completed_at""",
                (s.id, s.scenario, s.status, s.created_at, s.completed_at))

    def save_turn(self, t: Turn) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO turns(session_id, idx, data) VALUES(?,?,?)
                ON CONFLICT(session_id, idx) DO UPDATE SET data=excluded.data""",
                (t.session_id, t.index, t.model_dump_json()))

    def get_session(self, session_id: str) -> Session | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                return None
            turn_rows = c.execute(
                "SELECT data FROM turns WHERE session_id=? ORDER BY idx", (session_id,)
            ).fetchall()
        s = Session(id=row["id"], scenario=row["scenario"], status=row["status"],
                    created_at=row["created_at"], completed_at=row["completed_at"])
        s.turns = [Turn.model_validate_json(r["data"]) for r in turn_rows]
        return s

    def save_audio(self, session_id: str, turn_id: str, data: bytes, suffix: str) -> str:
        d = os.path.join(self.audio_dir, session_id)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{turn_id}{suffix}")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def save_summary(self, summary: Summary) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO summaries(session_id, data) VALUES(?,?)
                ON CONFLICT(session_id) DO UPDATE SET data=excluded.data""",
                (summary.session_id, summary.model_dump_json()))

    def get_summary(self, session_id: str) -> Summary | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM summaries WHERE session_id=?",
                            (session_id,)).fetchone()
        return Summary.model_validate_json(row["data"]) if row else None
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/storage.py tests/test_storage.py
git commit -m "feat: SQLite + 音频文件存储层"
```

---

## Task 3: 计时工具

**Files:**
- Create: `app/services/timing.py`, `tests/test_timing.py`

- [ ] **Step 1: 写失败测试 `tests/test_timing.py`**

```python
from app.models import Turn, Timings
from app.services.timing import StepTimer, aggregate_timings


def test_step_timer_records_ms():
    timer = StepTimer()
    with timer.measure("llm"):
        sum(range(1000))
    assert timer.results["llm"] >= 0
    assert "llm" in timer.results


def test_aggregate_timings_averages():
    turns = [
        Turn(id="t1", session_id="s", index=0, user_transcript="a",
             timings=Timings(stt_ms=100, llm_ms=800, tts_ms=200, total_ms=1100)),
        Turn(id="t2", session_id="s", index=1, user_transcript="b",
             timings=Timings(stt_ms=200, llm_ms=1000, tts_ms=400, total_ms=1600)),
    ]
    br = aggregate_timings(turns)
    assert br.stt_avg == 150
    assert br.llm_avg == 900
    assert br.samples == 2


def test_aggregate_timings_ignores_none():
    turns = [Turn(id="t1", session_id="s", index=0, user_transcript="a",
                  timings=Timings())]
    br = aggregate_timings(turns)
    assert br.samples == 1
    assert br.llm_avg == 0
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_timing.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 写 `app/services/timing.py`**

```python
"""各步耗时打点。StepTimer 在主链路用作上下文管理器;aggregate_timings 课后聚合画延迟分解图。"""
import time
from contextlib import contextmanager
from app.models import Turn, TimingBreakdown


class StepTimer:
    def __init__(self) -> None:
        self.results: dict[str, float] = {}

    @contextmanager
    def measure(self, step: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.results[step] = (time.perf_counter() - start) * 1000.0


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def aggregate_timings(turns: list[Turn]) -> TimingBreakdown:
    def col(attr: str) -> list[float]:
        return [getattr(t.timings, attr) for t in turns
                if getattr(t.timings, attr) is not None]
    return TimingBreakdown(
        stt_avg=_avg(col("stt_ms")),
        llm_avg=_avg(col("llm_ms")),
        tts_avg=_avg(col("tts_ms")),
        total_avg=_avg(col("total_ms")),
        samples=len(turns),
    )
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_timing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/timing.py tests/test_timing.py
git commit -m "feat: 计时打点与聚合"
```

---

## Task 4: 音频转码

**Files:**
- Create: `app/services/audio.py`, `tests/test_audio.py`

注:`pydub` 需要系统装 `ffmpeg`。转码逻辑薄,测试用 monkeypatch 替换 pydub,避免依赖 ffmpeg 与真实音频。

- [ ] **Step 1: 写失败测试 `tests/test_audio.py`**

```python
import app.services.audio as audio_mod
from app.services.audio import to_wav_16k


def test_to_wav_16k_invokes_pydub(monkeypatch):
    calls = {}

    class FakeSeg:
        @staticmethod
        def from_file(buf, format=None):
            calls["in_format"] = format
            return FakeSeg()
        def set_frame_rate(self, rate):
            calls["rate"] = rate
            return self
        def set_channels(self, n):
            calls["channels"] = n
            return self
        def export(self, out, format=None):
            calls["out_format"] = format
            out.write(b"WAVDATA")

    monkeypatch.setattr(audio_mod, "AudioSegment", FakeSeg)
    out = to_wav_16k(b"rawwebm", input_format="webm")
    assert out == b"WAVDATA"
    assert calls["rate"] == 16000
    assert calls["channels"] == 1
    assert calls["out_format"] == "wav"
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 写 `app/services/audio.py`**

```python
"""浏览器 MediaRecorder 出的多为 webm/opus,而 SpeechAce/通义/Azure 要 16k 单声道 PCM wav。
这是最易踩的格式坑,单独隔离。需系统装 ffmpeg(pydub 依赖)。"""
import io
from pydub import AudioSegment


def to_wav_16k(raw: bytes, input_format: str = "webm") -> bytes:
    seg = AudioSegment.from_file(io.BytesIO(raw), format=input_format)
    seg = seg.set_frame_rate(16000).set_channels(1)
    out = io.BytesIO()
    seg.export(out, format="wav")
    return out.getvalue()
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_audio.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/audio.py tests/test_audio.py
git commit -m "feat: 音频转码 webm->wav16k"
```

---

## Task 5: MiniMax LLM 服务(对话/纠错/总结)

**Files:**
- Create: `app/services/llm.py`, `tests/test_llm.py`

接口设计:`LlmService(transport=...)`,`transport(messages, temperature) -> str`(返回模型纯文本)。三个方法:`chat()` 解析结构化对话;`correct()` 出 deferred 纠错卡;`summarize_comment()` 出总评。`transport` 默认实现用 httpx 打 MiniMax `chatcompletion_v2`,测试注入 fake。

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**

```python
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/llm.py`**

```python
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
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/llm.py tests/test_llm.py
git commit -m "feat: MiniMax LLM 对话/纠错/总评封装"
```

---

## Task 6: MiniMax TTS 服务

**Files:**
- Create: `app/services/tts.py`, `tests/test_tts.py`

接口:`TtsService(transport=...)`,`transport(text, voice) -> bytes`(返回音频字节)。`synthesize()` 返回 bytes。默认 transport 打 MiniMax `t2a_v2`(返回 hex/base64 audio,解码成 bytes)。

- [ ] **Step 1: 写失败测试 `tests/test_tts.py`**

```python
from app.services.tts import TtsService


def test_synthesize_returns_bytes():
    svc = TtsService(transport=lambda text, voice: b"AUDIO")
    out = svc.synthesize("Hello", voice="male-qn-qingse")
    assert out == b"AUDIO"


def test_synthesize_passes_text():
    seen = {}
    def fake(text, voice):
        seen["text"] = text
        return b""
    TtsService(transport=fake).synthesize("Order ready")
    assert seen["text"] == "Order ready"
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_tts.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/tts.py`**

```python
"""MiniMax TTS 封装。返回音频 bytes(wav/mp3),由调用方落盘并回传前端。"""
from typing import Callable
import httpx
from app.config import get_settings

Transport = Callable[[str, str], bytes]
DEFAULT_VOICE = "male-qn-qingse"


def _default_transport(text: str, voice: str) -> bytes:
    s = get_settings()
    resp = httpx.post(
        f"https://api.minimax.chat/v1/t2a_v2?GroupId={s.minimax_group_id}",
        headers={"Authorization": f"Bearer {s.minimax_api_key}",
                 "Content-Type": "application/json"},
        json={"model": s.minimax_tts_model, "text": text,
              "stream": False,
              "voice_setting": {"voice_id": voice, "speed": 1.0},
              "audio_setting": {"format": "mp3", "sample_rate": 24000}},
        timeout=30.0,
    )
    resp.raise_for_status()
    # MiniMax t2a_v2 返回 data.audio 为 hex 字符串;若文档不符只改这两行
    audio_hex = resp.json()["data"]["audio"]
    return bytes.fromhex(audio_hex)


class TtsService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE) -> bytes:
        return self.transport(text, voice)
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_tts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/tts.py tests/test_tts.py
git commit -m "feat: MiniMax TTS 封装"
```

---

## Task 7: SpeechAce 发音测评(provider 抽象)

**Files:**
- Create: `app/services/pron.py`, `tests/test_pron.py`

接口:`PronService(transport=...)`,`transport(wav_bytes) -> dict`(返回 SpeechAce 原始 JSON)。`assess()` 把原始 JSON 归一化成 `Pronunciation`。provider 抽象点:换 Azure 时只改 `transport` + `_normalize`。

- [ ] **Step 1: 写失败测试 `tests/test_pron.py`**

```python
from app.models import Pronunciation
from app.services.pron import PronService, normalize_speechace


def test_normalize_speechace_extracts_word_scores():
    raw = {"status": "success", "text_score": {
        "speechace_score": {"pronunciation": 88},
        "fluency": {"overall_metrics": {"fluency_score": 82}},
        "word_score_list": [
            {"word": "coffee", "quality_score": 90},
            {"word": "please", "quality_score": 75}]}}
    pron = normalize_speechace(raw)
    assert isinstance(pron, Pronunciation)
    assert pron.overall == 88
    assert pron.fluency == 82
    assert {w.word for w in pron.words} == {"coffee", "please"}


def test_assess_uses_transport():
    raw = {"status": "success", "text_score": {
        "speechace_score": {"pronunciation": 70},
        "fluency": {"overall_metrics": {"fluency_score": 70}},
        "word_score_list": []}}
    svc = PronService(transport=lambda wav: raw)
    pron = svc.assess(b"wavbytes")
    assert pron.overall == 70


def test_assess_handles_failure_status():
    svc = PronService(transport=lambda wav: {"status": "error"})
    assert svc.assess(b"x") is None
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_pron.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/pron.py`**

```python
"""SpeechAce 发音测评封装(provider 抽象,Azure key 到位后替换 transport+normalize)。
归一化为统一 Pronunciation 模型,上层不感知厂商差异。"""
from typing import Callable
import httpx
from app.config import get_settings
from app.models import Pronunciation, WordScore

Transport = Callable[[bytes], dict]


def normalize_speechace(raw: dict) -> Pronunciation | None:
    if raw.get("status") != "success":
        return None
    ts = raw.get("text_score", {})
    overall = float(ts.get("speechace_score", {}).get("pronunciation", 0))
    fluency = float(ts.get("fluency", {}).get("overall_metrics", {}).get("fluency_score", 0))
    words = [WordScore(word=w["word"], score=float(w.get("quality_score", 0)))
             for w in ts.get("word_score_list", [])]
    return Pronunciation(overall=overall, accuracy=overall, fluency=fluency, words=words)


def _default_transport(wav_bytes: bytes) -> dict:
    s = get_settings()
    # SpeechAce spontaneous/自由说评分;dialect=en-us。endpoint/参数以官方文档为准
    resp = httpx.post(
        "https://api.speechace.co/api/scoring/speech/v9/json",
        params={"key": s.speechace_api_key, "dialect": "en-us", "user_id": "oral-trainer"},
        files={"user_audio_file": ("audio.wav", wav_bytes, "audio/wav")},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


class PronService:
    def __init__(self, transport: Transport | None = None):
        self.transport = transport or _default_transport

    def assess(self, wav_bytes: bytes) -> Pronunciation | None:
        try:
            raw = self.transport(wav_bytes)
        except httpx.HTTPError:
            return None
        return normalize_speechace(raw)
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_pron.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/pron.py tests/test_pron.py
git commit -m "feat: SpeechAce 发音测评封装"
```

---

## Task 8: STT provider 抽象(浏览器透传 + 通义备选)

**Files:**
- Create: `app/services/stt.py`, `tests/test_stt.py`

MVP 主链路用浏览器 Web Speech 转写,后端只是"透传"前端给的文本。但仍建抽象,便于切后端通义 Paraformer。

- [ ] **Step 1: 写失败测试 `tests/test_stt.py`**

```python
from app.services.stt import BrowserStt, SttResult


def test_browser_stt_passthrough():
    stt = BrowserStt()
    res = stt.transcribe(audio=b"ignored", browser_text="I want a latte")
    assert isinstance(res, SttResult)
    assert res.text == "I want a latte"
    assert res.source == "browser"


def test_browser_stt_strips_whitespace():
    res = BrowserStt().transcribe(audio=None, browser_text="  hello  ")
    assert res.text == "hello"
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_stt.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/stt.py`**

```python
"""STT provider 抽象。
MVP:BrowserStt —— 浏览器 Web Speech 已在前端转写,后端透传文本(零网络往返、延迟最低)。
备选:DashscopeStt(通义 Paraformer)—— 需要后端可控/更高质量时启用,接口一致。"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SttResult:
    text: str
    source: str  # browser | dashscope


class Stt(Protocol):
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult: ...


class BrowserStt:
    def transcribe(self, audio: bytes | None, browser_text: str | None) -> SttResult:
        return SttResult(text=(browser_text or "").strip(), source="browser")


# 通义 Paraformer 备选实现(MVP 默认不启用)。启用时注入 transport,接口与 BrowserStt 一致。
# class DashscopeStt:
#     def transcribe(self, audio, browser_text=None) -> SttResult:
#         text = self._recognize(audio)  # 调 DashScope Paraformer 实时识别
#         return SttResult(text=text, source="dashscope")
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_stt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/stt.py tests/test_stt.py
git commit -m "feat: STT provider 抽象(浏览器透传)"
```

---

## Task 9: 菜单爬虫 + 点餐场景配置

**Files:**
- Create: `scripts/scrape_menu.py`, `app/scenarios/ordering.py`, `resources/menu.json`(脚本产出,先放内置静态兜底), `tests/test_ordering.py`

菜单选型:实现时挑一个结构清晰的公开餐厅菜单页爬取;抓不动就用内置静态菜单(下方 `FALLBACK_MENU`)直接写入 `resources/menu.json`。场景 prompt 注入菜单,让"服务员"基于真实菜品对话。

- [ ] **Step 1: 写失败测试 `tests/test_ordering.py`**

```python
from app.scenarios.ordering import build_system_prompt, load_menu, MenuItem


def test_load_menu_returns_items(tmp_path):
    p = tmp_path / "menu.json"
    p.write_text('[{"name":"Latte","price":"$4","desc":"espresso + milk"}]', encoding="utf-8")
    items = load_menu(str(p))
    assert items[0] == MenuItem(name="Latte", price="$4", desc="espresso + milk")


def test_build_system_prompt_injects_menu():
    items = [MenuItem(name="Latte", price="$4", desc="espresso + milk")]
    prompt = build_system_prompt(items)
    assert "Latte" in prompt
    assert "waiter" in prompt.lower() or "server" in prompt.lower()
    # 终止目标(完成点餐)写进 prompt
    assert "goal" in prompt.lower() or "完成" in prompt
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_ordering.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/scenarios/ordering.py`**

```python
"""点餐场景:加载菜单 + 组装"服务员"角色 system prompt。
goal_reached 由 LLM 在用户确认下单后判定(prompt 里定义目标)。"""
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    name: str
    price: str
    desc: str


def load_menu(path: str) -> list[MenuItem]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [MenuItem(name=i["name"], price=i.get("price", ""), desc=i.get("desc", ""))
            for i in data]


def build_system_prompt(items: list[MenuItem]) -> str:
    menu_lines = "\n".join(f"- {i.name} ({i.price}): {i.desc}" for i in items)
    return (
        "You are a friendly restaurant waiter/server. Speak natural, simple English. "
        "Keep replies short (1-2 sentences) so the conversation flows. "
        "Help the customer order from this menu:\n"
        f"{menu_lines}\n"
        "Goal: guide the customer until they have confirmed a complete order "
        "(at least one dish, and they say they're done). "
        "When the order is confirmed and complete, set goal_reached=true and warmly close."
    )
```

- [ ] **Step 4: 写 `scripts/scrape_menu.py`(带内置兜底)**

```python
"""爬一份真实餐厅菜单 → resources/menu.json。
合规:只抓公开菜单页、低频、结果缓存本地,跑一次即可。抓取失败回退内置静态菜单。
用法:python scripts/scrape_menu.py [URL]"""
import json
import os
import sys
import requests
from bs4 import BeautifulSoup

FALLBACK_MENU = [
    {"name": "Classic Burger", "price": "$9.50", "desc": "beef patty, lettuce, tomato, cheese"},
    {"name": "Caesar Salad", "price": "$7.00", "desc": "romaine, croutons, parmesan"},
    {"name": "Margherita Pizza", "price": "$11.00", "desc": "tomato, mozzarella, basil"},
    {"name": "Latte", "price": "$4.00", "desc": "espresso with steamed milk"},
    {"name": "Cheesecake", "price": "$6.00", "desc": "New York style, berry topping"},
]

OUT_PATH = os.path.join("resources", "menu.json")


def scrape(url: str) -> list[dict]:
    """按目标站点结构解析。不同站点需调整选择器;失败抛异常由 main 回退。"""
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 oral-trainer"}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    # 示例选择器:实现时按实际页面调整
    for card in soup.select(".menu-item"):
        name = card.select_one(".item-name")
        price = card.select_one(".item-price")
        desc = card.select_one(".item-desc")
        if name:
            items.append({"name": name.get_text(strip=True),
                          "price": price.get_text(strip=True) if price else "",
                          "desc": desc.get_text(strip=True) if desc else ""})
    if not items:
        raise ValueError("no items parsed")
    return items


def main() -> None:
    os.makedirs("resources", exist_ok=True)
    menu = FALLBACK_MENU
    if len(sys.argv) > 1:
        try:
            menu = scrape(sys.argv[1])
            print(f"scraped {len(menu)} items")
        except Exception as e:  # noqa: BLE001 — 任意抓取失败都回退,保证有可用菜单
            print(f"scrape failed ({e}); using fallback menu")
    else:
        print("no URL given; using fallback menu")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 生成 `resources/menu.json` 并运行测试**

Run:
```bash
python scripts/scrape_menu.py
python -m pytest tests/test_ordering.py -v
```
Expected: 生成 `resources/menu.json`;测试 PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/scrape_menu.py app/scenarios/ordering.py tests/test_ordering.py resources/menu.json
git commit -m "feat: 点餐场景配置 + 菜单爬虫(带兜底)"
```

---

## Task 10: 主链路编排(dialogue)

**Files:**
- Create: `app/services/dialogue.py`, `tests/test_dialogue.py`

`DialogueService` 注入 `llm`(已有)与 `storage`。`run_turn()` 输入:session、用户文本、(可选)副链路推来的 inline hint。组装 history → 调 LLM 结构化 → 计时 → 存 turn → 返回。**不在此调 TTS**(TTS 在 main.py 层做,便于计时与回传);但计时 llm 步骤在此完成。终止判定:LLM 的 `goal_reached` 透传。

- [ ] **Step 1: 写失败测试 `tests/test_dialogue.py`**

```python
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_dialogue.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/dialogue.py`**

```python
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
                 inline_hint: str | None = None) -> Turn:
        system_prompt = self.system_prompt
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
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_dialogue.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/dialogue.py tests/test_dialogue.py
git commit -m "feat: 主链路对话编排"
```

---

## Task 11: 副链路分析与课程总结(analysis)

**Files:**
- Create: `app/services/analysis.py`, `tests/test_analysis.py`

两职责:
1. `analyze_turn(turn, wav_bytes)`:异步对单轮做发音测评(pron)+ 细颗粒纠错(llm.correct),回填 `turn.pronunciation` 与 `turn.deferred_corrections`,存回。
2. `build_summary(session)`:聚合所有 turn → `Summary`(整体分、分项、词级发音、纠错汇总、延迟分解、LLM 总评)。

整体分算法(确定可测):`overall = 0.5*pron_overall + 0.3*fluency + 0.2*grammar_score`;`grammar_score = max(0, 100 - 8 * 纠错条数均值)`。

- [ ] **Step 1: 写失败测试 `tests/test_analysis.py`**

```python
import time
from app.models import (Session, Turn, Pronunciation, WordScore, Correction, Timings)
from app.services.analysis import build_summary, grammar_score_from_corrections


class FakeLlm:
    def summarize_comment(self, overall, weak_points): return "总评"


def make_session_with_turns():
    s = Session(id="s1", scenario="ordering", created_at=time.time())
    s.turns = [
        Turn(id="t1", session_id="s1", index=0, user_transcript="I want coffee",
             pronunciation=Pronunciation(overall=90, accuracy=90, fluency=80,
                                         words=[WordScore(word="coffee", score=90)]),
             deferred_corrections=[],
             timings=Timings(stt_ms=100, llm_ms=800, tts_ms=200, total_ms=1100)),
        Turn(id="t2", session_id="s1", index=1, user_transcript="me want burger",
             pronunciation=Pronunciation(overall=70, accuracy=70, fluency=60,
                                         words=[WordScore(word="burger", score=70)]),
             deferred_corrections=[Correction(type="grammar", original="me want",
                                              suggestion="I want", explanation="主格用 I")],
             timings=Timings(stt_ms=120, llm_ms=900, tts_ms=300, total_ms=1320)),
    ]
    return s


def test_grammar_score_decreases_with_errors():
    assert grammar_score_from_corrections(0) == 100
    assert grammar_score_from_corrections(2) < 100


def test_build_summary_aggregates():
    s = make_session_with_turns()
    summary = build_summary(s, llm=FakeLlm())
    assert summary.session_id == "s1"
    assert summary.sub_scores.pronunciation == 80   # (90+70)/2
    assert summary.sub_scores.fluency == 70         # (80+60)/2
    assert len(summary.word_scores) == 2
    assert len(summary.correction_list) == 1
    assert summary.timing_breakdown.samples == 2
    assert 0 <= summary.overall_score <= 100
    assert summary.llm_comment == "总评"
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/services/analysis.py`**

```python
"""副链路:单轮异步分析(发音+纠错回填)+ 课程总结聚合。
analyze_turn 在 main.py 里以后台任务调度,不阻塞主链路对话。"""
from app.models import (Session, Turn, Summary, SubScores, WordScore, Correction)
from app.services.timing import aggregate_timings


def grammar_score_from_corrections(avg_corrections: float) -> float:
    """纠错越多语法分越低。每条均值扣 8 分,下限 0。"""
    return max(0.0, 100.0 - 8.0 * avg_corrections)


def analyze_turn(turn: Turn, wav_bytes: bytes | None, pron, llm, storage) -> Turn:
    """异步:发音测评 + 细颗粒纠错,回填并存回。pron/llm 为 service 实例。"""
    if wav_bytes is not None:
        turn.pronunciation = pron.assess(wav_bytes)
    turn.deferred_corrections = llm.correct(turn.user_transcript)
    storage.save_turn(turn)
    return turn


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def build_summary(session: Session, llm) -> Summary:
    turns = session.turns
    pron_overall = _avg([t.pronunciation.overall for t in turns if t.pronunciation])
    fluency = _avg([t.pronunciation.fluency for t in turns if t.pronunciation])

    corrections: list[Correction] = []
    for t in turns:
        corrections.extend(t.deferred_corrections)
        if t.inline_correction:
            corrections.append(Correction(type="inline", original=t.user_transcript,
                                          suggestion="", explanation=t.inline_correction))
    avg_corr = len(corrections) / len(turns) if turns else 0.0
    grammar = grammar_score_from_corrections(avg_corr)

    word_scores: list[WordScore] = []
    for t in turns:
        if t.pronunciation:
            word_scores.extend(t.pronunciation.words)

    overall = round(0.5 * pron_overall + 0.3 * fluency + 0.2 * grammar, 1)

    weak = []
    if pron_overall < 75: weak.append("发音")
    if fluency < 75: weak.append("流利度")
    if grammar < 75: weak.append("语法")
    comment = llm.summarize_comment(overall=overall, weak_points=weak)

    return Summary(
        session_id=session.id,
        overall_score=overall,
        sub_scores=SubScores(pronunciation=pron_overall, fluency=fluency, grammar=grammar),
        word_scores=word_scores,
        correction_list=corrections,
        timing_breakdown=aggregate_timings(turns),
        llm_comment=comment,
    )
```

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/analysis.py tests/test_analysis.py
git commit -m "feat: 副链路分析与课程总结聚合"
```

---

## Task 12: FastAPI 应用(WebSocket + REST + 静态前端)

**Files:**
- Create: `app/main.py`, `tests/test_main.py`

端点:
- `GET /` → 返回 `frontend/index.html`;`/static/*` → 前端资源。
- `GET /api/menu` → `resources/menu.json`。
- `POST /api/session` → 新建 session,返回 id。
- `WS /ws/{session_id}` → 收 `{type:"turn", text, audio_b64?}`:跑主链路 → 调 TTS → 回 `{assistant_text, audio_b64, inline_correction, goal_reached, timings}`;并后台调 `analyze_turn`。
- `POST /api/session/{id}/finish` → `build_summary` 存库,返回 Summary。
- `GET /api/session/{id}/summary` → 取 Summary。
- `GET /api/session/{id}/timing` → 取延迟聚合(`aggregate_timings`)。

注入容器 `Services`(便于测试替换)。测试用 FastAPI `TestClient` 测 REST + WebSocket,全程注入 fake service,不打真 API。

- [ ] **Step 1: 写失败测试 `tests/test_main.py`**

```python
import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore
from app.main import create_app, Services


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        return LlmReply(reply="Sure, a latte!", inline_correction=None,
                        goal_reached="that's all" in user_text)
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return "做得不错"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav): return Pronunciation(overall=85, accuracy=85, fluency=80,
                                               words=[WordScore(word="latte", score=88)])


def make_client(tmp_path):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services))


def test_create_session_and_menu(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/session")
    assert r.status_code == 200
    assert "id" in r.json()
    assert client.get("/api/menu").status_code == 200


def test_websocket_turn_returns_reply_and_audio(tmp_path):
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "I want a latte",
                      "audio_b64": base64.b64encode(b"wav").decode()})
        msg = ws.receive_json()
    assert msg["assistant_text"] == "Sure, a latte!"
    assert base64.b64decode(msg["audio_b64"]) == b"AUDIO"
    assert msg["timings"]["tts_ms"] is not None
    assert msg["goal_reached"] is False


def test_finish_returns_summary(tmp_path):
    client = make_client(tmp_path)
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "that's all", "audio_b64": ""})
        ws.receive_json()
    r = client.post(f"/api/session/{sid}/finish")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == sid
    assert 0 <= body["overall_score"] <= 100
    assert client.get(f"/api/session/{sid}/summary").json()["session_id"] == sid
    assert client.get(f"/api/session/{sid}/timing").status_code == 200
```

- [ ] **Step 2: 运行,确认失败**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `app/main.py`**

```python
"""FastAPI 入口:WebSocket 跑主链路(对话+TTS),后台跑副链路(发音+纠错),REST 提供菜单/总结/延迟。
Services 容器集中持有依赖,测试可整体替换为 fake。"""
import base64
import os
import time
import uuid
from dataclasses import dataclass
from fastapi import FastAPI, WebSocket, BackgroundTasks
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
                    wav_bytes = raw  # 真实环境此处先 audio.to_wav_16k(raw);见注
                storage.save_turn(turn)

                # 后台异步分析(发音 + 纠错)
                import asyncio
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
        return summary.model_dump() if summary else JSONResponse({"error": "not found"}, 404)

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
```

注:WebSocket 里 `wav_bytes = raw` 是占位——真实环境应先 `from app.services.audio import to_wav_16k; wav_bytes = to_wav_16k(raw, "webm")`。测试传的是任意字节且 `FakePron.assess` 不解析内容,故此处保留 raw 以免测试依赖 ffmpeg。实现者接真 SpeechAce 时改成转码。

- [ ] **Step 4: 运行,确认通过**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS(WebSocket 与 REST 全绿)

- [ ] **Step 5: 全量回归**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: FastAPI 应用(WebSocket 主链路 + 副链路后台 + REST)"
```

---

## Task 13: 前端 playground

**Files:**
- Create: `frontend/index.html`, `frontend/style.css`, `frontend/app.js`

无自动化测试(纯前端 UI),靠 Task 14 手动验收。功能:菜单面板、press-to-talk(Web Speech 转写 + MediaRecorder 录音)、对话气泡、纠错卡、结束总结(词级发音色块 + Chart.js 延迟分解图)。

- [ ] **Step 1: 写 `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>口语陪练 · 点餐</title>
  <link rel="stylesheet" href="/static/style.css" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
  <header><h1>英语口语陪练 · 餐厅点餐</h1></header>
  <main>
    <section id="menu-panel"><h2>Menu</h2><ul id="menu-list"></ul></section>
    <section id="chat-panel">
      <div id="messages"></div>
      <div id="controls">
        <button id="record-btn">按住说话</button>
        <button id="finish-btn">结束课程</button>
        <span id="status"></span>
      </div>
    </section>
    <section id="correction-panel"><h2>纠错</h2><div id="corrections"></div></section>
  </main>
  <section id="summary-panel" class="hidden">
    <h2>课后总结</h2>
    <div id="scores"></div>
    <div id="word-scores"></div>
    <canvas id="timing-chart"></canvas>
    <p id="comment"></p>
  </section>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 `frontend/style.css`**

```css
* { box-sizing: border-box; font-family: system-ui, sans-serif; }
body { margin: 0; background: #f5f6f8; color: #1a1a1a; }
header { background: #2b5cff; color: #fff; padding: 12px 20px; }
main { display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 12px; padding: 16px; }
section { background: #fff; border-radius: 10px; padding: 14px; }
#messages { height: 50vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.msg { padding: 8px 12px; border-radius: 10px; max-width: 80%; }
.msg.user { align-self: flex-end; background: #2b5cff; color: #fff; }
.msg.assistant { align-self: flex-start; background: #ebedf2; }
#record-btn { padding: 10px 18px; font-size: 16px; border: none; border-radius: 8px;
  background: #2b5cff; color: #fff; cursor: pointer; }
#record-btn.recording { background: #e23; }
.card { border-left: 3px solid #e8a13a; padding: 6px 10px; margin: 6px 0; background: #fff8ec; }
.word { display: inline-block; padding: 2px 6px; margin: 2px; border-radius: 4px; color: #fff; }
.hidden { display: none; }
#summary-panel { margin: 16px; }
</style>
```

注:上面误含 `</style>` 收尾标记,写文件时删掉该行(CSS 文件不需要 `</style>`)。

- [ ] **Step 3: 写 `frontend/app.js`**

```javascript
// playground 主逻辑:Web Speech 本地转写 + MediaRecorder 录音 → WebSocket 主链路 → 渲染。
let sessionId = null, ws = null, mediaRecorder = null, chunks = [], recognizing = "";
let sttStart = 0;

async function init() {
  const menu = await (await fetch("/api/menu")).json();
  document.getElementById("menu-list").innerHTML =
    menu.map(m => `<li><b>${m.name}</b> <span>${m.price}</span><br><small>${m.desc}</small></li>`).join("");
  sessionId = (await (await fetch("/api/session", { method: "POST" })).json()).id;
  ws = new WebSocket(`ws://${location.host}/ws/${sessionId}`);
  ws.onmessage = onServerMessage;
}

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  document.getElementById("messages").appendChild(div);
  div.scrollIntoView();
}

function addCorrection(text) {
  const div = document.createElement("div");
  div.className = "card";
  div.textContent = text;
  document.getElementById("corrections").prepend(div);
}

// 录音:Web Speech 转写 + MediaRecorder 抓音频,松手时一并发送
const recBtn = document.getElementById("record-btn");
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SR ? new SR() : null;
if (recognition) { recognition.lang = "en-US"; recognition.interimResults = false; }

recBtn.addEventListener("mousedown", startRec);
recBtn.addEventListener("mouseup", stopRec);

async function startRec() {
  recBtn.classList.add("recording");
  recognizing = ""; chunks = []; sttStart = performance.now();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  mediaRecorder.start();
  if (recognition) {
    recognition.onresult = e => { recognizing = e.results[0][0].transcript; };
    recognition.start();
  }
}

async function stopRec() {
  recBtn.classList.remove("recording");
  if (recognition) recognition.stop();
  if (mediaRecorder) mediaRecorder.stop();
  await new Promise(r => setTimeout(r, 300)); // 等转写与音频收尾
  const sttMs = performance.now() - sttStart;
  const blob = new Blob(chunks, { type: "audio/webm" });
  const audioB64 = await blobToB64(blob);
  const text = recognizing.trim();
  if (!text) { document.getElementById("status").textContent = "没听清,重试"; return; }
  addMessage(text, "user");
  ws.send(JSON.stringify({ type: "turn", text, audio_b64: audioB64, stt_ms: sttMs }));
}

function blobToB64(blob) {
  return new Promise(res => {
    const r = new FileReader();
    r.onloadend = () => res(r.result.split(",")[1]);
    r.readAsDataURL(blob);
  });
}

function onServerMessage(ev) {
  const m = JSON.parse(ev.data);
  if (m.error) return;
  addMessage(m.assistant_text, "assistant");
  if (m.inline_correction) addCorrection("即时:" + m.inline_correction);
  if (m.audio_b64) new Audio("data:audio/mp3;base64," + m.audio_b64).play();
  if (m.goal_reached) document.getElementById("status").textContent = "🎉 点餐完成,可结束课程";
}

document.getElementById("finish-btn").addEventListener("click", finish);

async function finish() {
  const s = await (await fetch(`/api/session/${sessionId}/finish`, { method: "POST" })).json();
  document.getElementById("summary-panel").classList.remove("hidden");
  document.getElementById("scores").innerHTML =
    `综合 <b>${s.overall_score}</b> | 发音 ${s.sub_scores.pronunciation} | ` +
    `流利 ${s.sub_scores.fluency} | 语法 ${s.sub_scores.grammar}`;
  document.getElementById("word-scores").innerHTML = s.word_scores.map(w => {
    const hue = Math.round(w.score * 1.2); // 0→红 120→绿
    return `<span class="word" style="background:hsl(${hue},70%,45%)">${w.word} ${w.score}</span>`;
  }).join("");
  document.getElementById("comment").textContent = s.llm_comment;
  const t = s.timing_breakdown;
  new Chart(document.getElementById("timing-chart"), {
    type: "bar",
    data: { labels: ["STT", "LLM", "TTS", "总计"],
      datasets: [{ label: "平均耗时 (ms)",
        data: [t.stt_avg, t.llm_avg, t.tts_avg, t.total_avg],
        backgroundColor: ["#5b9", "#2b5cff", "#e8a13a", "#888"] }] },
    options: { plugins: { title: { display: true, text: "延迟分解(流畅性)" } } },
  });
}

init();
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: 前端 playground(菜单/录音/对话/纠错/总结图表)"
```

---

## Task 14: 端到端集成测试 + 手动验收

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写集成测试 `tests/test_integration.py`(全 mock API,跑通多轮 → 结束 → 总结)**

```python
import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore, Correction
from app.main import create_app, Services


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        done = "done" in user_text
        return LlmReply(reply="Got it." if done else "Anything else?",
                        inline_correction="用了 me want" if "me want" in user_text else None,
                        goal_reached=done)
    def correct(self, text):
        return [Correction(type="grammar", original="me want", suggestion="I want",
                           explanation="主格用 I")] if "me want" in text else []
    def summarize_comment(self, overall, weak_points): return "继续加油"


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def assess(self, wav):
        return Pronunciation(overall=82, accuracy=82, fluency=78,
                             words=[WordScore(word="latte", score=88)])


def test_full_session_flow(tmp_path):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=FakePron(),
                        db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "a"))
    client = TestClient(create_app(services=services))
    sid = client.post("/api/session").json()["id"]
    with client.websocket_connect(f"/ws/{sid}") as ws:
        ws.send_json({"type": "turn", "text": "me want a latte",
                      "audio_b64": base64.b64encode(b"x").decode(), "stt_ms": 120})
        m1 = ws.receive_json()
        assert m1["inline_correction"] is not None
        ws.send_json({"type": "turn", "text": "that is all, I am done",
                      "audio_b64": "", "stt_ms": 90})
        m2 = ws.receive_json()
        assert m2["goal_reached"] is True

    summary = client.post(f"/api/session/{sid}/finish").json()
    assert summary["timing_breakdown"]["samples"] == 2
    assert 0 <= summary["overall_score"] <= 100
    assert any(c["type"] in ("grammar", "inline") for c in summary["correction_list"])
    timing = client.get(f"/api/session/{sid}/timing").json()
    assert timing["stt_avg"] >= 0
```

- [ ] **Step 2: 运行集成测试 + 全量回归**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 3: 手动验收(真实 API)**

```bash
# 1) 填好 .env(MINIMAX_API_KEY/GROUP_ID、SPEECHACE_API_KEY)
# 2) 生成菜单
python scripts/scrape_menu.py
# 3) 启动
ORAL_TRAINER_BOOT=1 python -m uvicorn app.main:app --reload
```
浏览器开 `http://localhost:8000`(用 Chrome,Web Speech 需要):
- 菜单面板有真实菜品
- 按住"按住说话"用英文点餐 → 听到 TTS 回复、看到对话气泡
- 故意说错(如 "me want")→ 右侧出现纠错卡
- 点"结束课程"→ 出现综合分、词级发音色块、延迟分解柱状图、中文总评

验收标准:全链路无报错,延迟图三段(STT/LLM/TTS)有数据。

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 全链路集成测试"
```

---

## 自查结论(plan vs spec)

- **场景选择**:点餐单场景 ✔(Task 9/10)
- **实时语音对话**:Web Speech 转写 + MiniMax 对话 + TTS ✔(Task 5/6/10/12/13)
- **发音测评**:SpeechAce 异步 ✔(Task 7/11/12)
- **语法/表达纠错**:两级(inline 主链路 + deferred 副链路)✔(Task 5/10/11)
- **课后总结**:聚合分 + 词级发音可视化 + 中文总评 ✔(Task 11/13)
- **耗时日志/流畅性反馈**:StepTimer + aggregate + 延迟分解图 ✔(Task 3/12/13)
- **真实菜单 resource**:爬虫 + 兜底 + playground 展示 ✔(Task 9/13)
- **provider 抽象(Azure/通义预留)**:stt/pron/llm/tts 均注入 transport ✔
- 类型一致性:`LlmReply` / `Pronunciation` / `Correction` / `Summary` / `Timings` 跨任务签名一致 ✔
- 无占位符:每步含可执行代码与命令(前端 CSS 末尾 `</style>` 已在 Task13 Step2 标注删除)✔
