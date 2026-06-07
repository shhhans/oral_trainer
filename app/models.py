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
    type: str          # grammar | vocabulary | expression | pronunciation | inline
    original: str
    suggestion: str
    explanation: str   # 中文解释


class Timings(BaseModel):
    stt_ms: float | None = None   # 浏览器端上报
    response_wait_ms: float | None = None
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


class SessionMenuItem(BaseModel):
    restaurant: str
    section: str
    name: str
    description: str
    price: str
    course: str


class TaskCard(BaseModel):
    id: str
    title: str
    tasks: list[str] = Field(default_factory=list)
    goal: str


class Session(BaseModel):
    id: str
    scenario: str
    dialect: str = "en-us"        # en-us | en-gb
    difficulty: str = "beginner"   # beginner | intermediate | advanced
    status: str = "active"         # active | completed
    created_at: float
    completed_at: float | None = None
    restaurant_name: str | None = None
    menu_items: list[SessionMenuItem] = Field(default_factory=list)
    task_card: TaskCard | None = None
    turns: list[Turn] = Field(default_factory=list)


class SubScores(BaseModel):
    pronunciation: float
    fluency: float
    grammar: float
    responsiveness: float = 100.0


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
    response_wait_total_ms: float = 0.0
    llm_comment: str = ""


class LlmReply(BaseModel):
    """主链路 MiniMax 结构化输出契约。"""
    reply: str
    inline_correction: str | None = None
    goal_reached: bool = False
