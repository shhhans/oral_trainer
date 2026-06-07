# Oral Trainer · 英语口语陪练

在指定场景下进行真实英语对话训练的口语练习工具。比赛项目,当前为 **MVP**:打通"点餐"单场景的 **实时语音对话 → 异步发音测评 → 两级纠错 → 课后量化总结** 全链路,并提供一个 Web playground 演示。

## 核心设计

- **主链路(同步,低延迟)**:浏览器 Web Speech API 本地转写 → MiniMax M2 结构化对话 → MiniMax TTS 语音回复。
- **副链路(异步,不阻塞对话)**:同段录音转码后送 SpeechAce 做发音测评,MiniMax 做细颗粒语法/用词纠错。
- **两级纠错**:
  - *即时(inline)*:仅对严重/影响理解的错误,由主链路 LLM 在回复中自然轻点。
  - *延迟(deferred)*:所有细颗粒问题走副链路,生成纠错卡片并进课后总结。
- **流畅性反馈**:每轮 STT/LLM/TTS/端到端各步耗时打点,课后画延迟分解图。
- **可量化总结**:整体分 + 发音/流利/语法分项 + 词级发音可视化 + LLM 中文点评。
- **Provider 抽象**:STT/发音/LLM/TTS 均封装为统一接口,可替换厂商(发音测评预留 Azure,后端 STT 预留通义 Paraformer)。

```
浏览器(Web Speech 转写 + 录音)
   │  WebSocket
   ▼
FastAPI 编排  ──主链路──►  MiniMax M2(对话)─► MiniMax TTS
   │
   └──副链路(异步)──►  SpeechAce(发音测评) + MiniMax(纠错)
   │
   ▼
SQLite + 本地音频 ──► 课后总结(整体分 / 词级发音 / 延迟分解图)
```

## 技术栈

Python 3.11 · FastAPI · pydantic v2 · httpx · pydub · SQLite · pytest
前端:原生 HTML/JS · MediaRecorder · Web Speech API · WebSocket · Chart.js

## 目录结构

| 路径 | 说明 |
|------|------|
| `app/services/` | STT/发音/LLM/TTS 封装、主链路编排、副链路分析、计时、音频转码 |
| `app/scenarios/ordering.py` | 点餐场景配置 + 内置默认菜单 |
| `app/main.py` | FastAPI:WebSocket 主链路 + 后台副链路 + REST |
| `app/storage.py` `app/models.py` | SQLite 持久化 + 全链路数据模型 |
| `scripts/build_menu_dataset.py` | 清洗 Kaggle Restaurant Menu Items 数据集 |
| `frontend/` | playground 单页 |
| `docs/superpowers/` | 设计 spec 与实现计划 |

## 快速开始

依赖管理用 [uv](https://github.com/astral-sh/uv)。

```powershell
# 1. 建虚拟环境并装依赖
uv venv --python 3.11
uv pip install -e ".[dev]"

# 2. 配置 API key:复制 .env.example 为 .env 并填写
#    MINIMAX_API_KEY / MINIMAX_GROUP_ID / SPEECHACE_API_KEY

# 3. (可选)重建菜单数据
.venv\Scripts\python.exe scripts/build_menu_dataset.py "Menu Items.csv"

# 4. 启动
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000`(**需用 Chrome**,Web Speech API 依赖)。按住"按住说话"用英文点餐,结束后点"结束课程"查看总结。

> **运行时依赖 ffmpeg**:发音测评要把浏览器录音(webm/opus)转成 16k wav,需系统装 ffmpeg(`winget install Gyan.FFmpeg` 或 conda)。未装时对话与总结仍可用,仅发音测评会被跳过。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

单元/集成测试全程 mock 外部 API,不需要 key、不打真网络。

## 环境变量

| 变量 | 说明 |
|------|------|
| `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` | MiniMax 对话 + TTS |
| `MINIMAX_LLM_MODEL` / `MINIMAX_TTS_MODEL` | 默认 `MiniMax-M2` / `speech-02-turbo` |
| `SPEECHACE_API_KEY` | SpeechAce 发音测评 |
| `DASHSCOPE_API_KEY` | 通义 Paraformer(后端 STT 备选,MVP 默认不用) |
| `DATA_DIR` | SQLite 与音频存储目录,默认 `data` |

## 已知限制 / 待办

- 仅支持 Chrome 系浏览器(Web Speech API);其它浏览器暂无后端 STT 兜底。
- 单场景(点餐),多场景为配置化预留。
- press-to-talk 分段处理,未做连续 VAD 与流式 STT/TTS。
- 待修 review 项:课程结束时序(可能在后台分析完成前生成总结)、麦克风权限竞态等。
- 真实 API 端到端体验需自行配置 key + ffmpeg + Chrome。
