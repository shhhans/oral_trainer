# Oral Trainer · 英语口语陪练

面向真实场景的英语口语训练应用。用户通过按住说话进行实时对话，系统完成服务端语音识别、场景化回复、语音合成、发音测评、纠错、反应速度记录与课后评分。

## 演示视频

https://github.com/user-attachments/assets/2765b5ee-9200-4085-b79b-e74e3f40e516

## 当前功能

- **8 个练习场景**：餐厅点餐、酒店入住、购物、问路、看医生、求职面试、电话预约、排球协作。
- **服务端实时 ASR**：浏览器通过 AudioWorklet 上传 16 kHz PCM，后端使用 DashScope Paraformer 流式返回识别文本。
- **稳定启动协议**：ASR 使用 `ready/error/unavailable` 握手；支持多句聚合、幂等清理和启动失败协议化。
- **美式/英式发音**：前端可切换口音，选择会同时作用于 MiniMax TTS 和 SpeechAce 发音评分。
- **场景化 TTS**：开场白与每轮回复均有语音；默认美式点餐开场白使用项目内静态 MP3，避免首次加载等待。
- **两级纠错**：
  - 即时纠错：严重错误由主链路自然提示。
  - 延迟纠错：后台生成细粒度语法、词汇和表达建议。
- **空闲追问**：助手说完后每等待 5 秒自动追问，直到用户开始录音。
- **量化评分**：综合分、发音、流利度、语法、反应速度、词级发音和链路耗时。
- **评分历史**：History 页面展示真实课程记录、统计指标和可切换的趋势曲线；无记录时展示明确标注的演示曲线。
- **三级难度与任务卡**：前端可选择 `beginner/intermediate/advanced`；每场会按难度抽取 3/4/5 项任务，并将目标注入场景提示词。
- **分层菜单抽样**：点餐场景按难度展示 8/12/16 道菜，每次从同一家餐厅抽取并确保覆盖前菜、主菜、甜点和饮料。
- **菜单数据 ETL**：可将 Kaggle CC0 的 Restaurant Menu Items 数据集清洗为带 `course` 分类的菜单目录。

## 系统链路

```text
浏览器麦克风
   │ AudioWorklet: PCM16 / 16 kHz
   ▼
DashScope Paraformer 实时 ASR
   │ 转写文本
   ▼
FastAPI WebSocket 编排
   ├── MiniMax M2：场景对话与即时纠错
   ├── MiniMax TTS：开场白、回复和空闲追问
   └── 后台副链路
       ├── SpeechAce：发音、流利度和词级评分
       └── MiniMax：延迟纠错
   │
   ▼
SQLite + 本地音频
   ├── 课后总结
   └── History 评分趋势
```

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic v2、SQLite、httpx
- 语音：DashScope Paraformer、MiniMax TTS、SpeechAce、pydub/ffmpeg
- 前端：原生 HTML/CSS/JavaScript、AudioWorklet、MediaRecorder、WebSocket、Chart.js
- 测试：pytest、FastAPI TestClient

## 目录结构

| 路径 | 说明 |
|------|------|
| `app/main.py` | REST/WebSocket 端点与主副链路编排 |
| `app/services/` | ASR、LLM、TTS、发音评分、分析和计时服务 |
| `app/scenarios/` | 场景定义、角色、目标和难度提示 |
| `app/data/menus.json` | ETL 生成的标准化菜单目录 |
| `app/models.py` | 会话、轮次、评分和总结数据契约 |
| `app/storage.py` | SQLite 与音频文件持久化 |
| `frontend/` | 场景训练、方言切换、总结和 History 页面 |
| `scripts/build_menu_dataset.py` | Kaggle 菜单数据清洗脚本 |
| `scripts/check_asr.py` | DashScope ASR 可达性检查 |
| `tests/` | 单元、协议和集成测试 |

## 快速开始

依赖管理推荐使用 [uv](https://github.com/astral-sh/uv)。

```powershell
# 1. 创建环境并安装依赖
uv venv --python 3.11
uv pip install -e ".[dev]"

# 2. 复制并配置环境变量
Copy-Item .env.example .env

# 3. 启动服务
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000`。选择口音、难度与场景后，按住录音按钮或空格键开始说话。

## 环境变量

| 变量 | 用途 |
|------|------|
| `DASHSCOPE_API_KEY` | Paraformer 实时语音识别 |
| `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` | 场景对话、纠错和 TTS |
| `MINIMAX_LLM_MODEL` / `MINIMAX_TTS_MODEL` | MiniMax 模型配置 |
| `MINIMAX_VOICE_EN_US` / `MINIMAX_VOICE_EN_GB` | 美式与英式 TTS 音色 |
| `SPEECHACE_API_KEY` | 发音和流利度评分 |
| `DATA_DIR` | SQLite 与录音目录，默认 `data` |
| `DIALOGUE_HISTORY_WINDOW` | LLM 对话历史窗口 |

## 菜单 ETL

数据源：[Restaurant Menu Items](https://www.kaggle.com/datasets/pranalibose/restaurant)，许可证为 CC0-1.0。原始字段为 `Restaurant`、`Section`、`Item`、`Description`、`Price`。

```powershell
# 使用 Kaggle CLI 下载
uvx kaggle datasets download -d pranalibose/restaurant --unzip

# 清洗并生成项目数据
.\.venv\Scripts\python.exe scripts\build_menu_dataset.py "Menu Items.csv"
```

ETL 会清理无效记录、标准化价格、去重，并将菜单项分类为：

- `appetizer`
- `main`
- `dessert`
- `beverage`

当前提交的 `app/data/menus.json` 包含 100 家餐厅、6,464 道菜，每家餐厅均覆盖四个 course。

## API 摘要

| 端点 | 用途 |
|------|------|
| `POST /api/session` | 创建会话并返回抽样任务卡及菜单，支持 `scenario`、`dialect`、`difficulty` |
| `WS /ws/{session_id}` | 对话、TTS 和空闲追问协议 |
| `WS /ws/asr/{session_id}` | 实时 ASR PCM 流 |
| `POST /api/session/{id}/finish` | 结束课程并生成总结 |
| `GET /api/history` | 获取已完成课程的评分历史 |
| `GET /api/session/{id}/turns` | 获取逐轮记录 |
| `GET /api/session/{id}/summary` | 获取课后总结 |
| `GET /api/health` | API key 与服务能力检查 |

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check frontend\app.js
```

自动化测试使用 fake provider，不调用真实外部 API。

## 运行要求与限制

- 浏览器需要支持 `AudioWorklet`、`MediaRecorder` 和 WebSocket。
- 发音测评的 WebM 转 WAV 依赖 ffmpeg；未安装时对话仍可运行，但发音评分可能跳过。
- 当前为按住说话模式，尚未实现连续 VAD。
- 菜单与任务卡在创建会话时完成抽样并持久化，因此刷新或 WebSocket 重连不会改变本场目标。
