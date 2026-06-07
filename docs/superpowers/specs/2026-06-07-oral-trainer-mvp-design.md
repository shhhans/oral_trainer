# 英语口语陪练 App — MVP 设计文档

- 日期:2026-06-07
- 状态:待评审
- 场景:餐厅点餐(restaurant ordering),单场景全链路

## 1. 背景与目标

比赛题目要求开发一款英语口语练习工具,在指定场景下进行真实对话训练。需支持:场景选择、实时语音对话、发音测评、语法/表达纠错、课后总结。评价维度:对话交互自然度、语音端到端流畅性与延迟、纠错的精准度与时机、口语能力提升的可量化反馈。

本 MVP 目标:把**单个场景(点餐)**从实时对话 → 发音打分 → 纠错 → 课后总结**全链路跑通**,并提供一个简单的 Web playground 演示。架构上为多场景、多 provider 预留扩展点,但不在 MVP 实现。

## 2. 选型与分工

| 环节 | 选型 | 说明 |
|------|------|------|
| 主链路 STT(对话用) | **浏览器 Web Speech API**(MVP 默认) | STT 在浏览器本地跑,零网络往返、免 key、延迟最低;限 Chrome、质量一般。通义 Paraformer 作为 provider 抽象后的后端备选(已有 DashScope key) |
| 发音测评 | SpeechAce(spontaneous 自由说接口) | 暂用;Azure Pronunciation Assessment key 到位后无缝替换 |
| 对话 LLM / 纠错 / 总结 | MiniMax M2(结构化输出) | 国内低延迟;M2 系列支持结构化输出 |
| TTS 语音回复 | MiniMax TTS | 国内第一梯队音质 |
| 后端 | Python + FastAPI | AI/语音生态最顺 |
| 前端 | Web(简单 playground 单页) | press-to-talk 录音、对话、纠错卡、总结页 |
| 存储 | SQLite + 本地音频文件 | MVP 足够 |

**Provider 抽象原则**:STT、发音测评、LLM、TTS 各封装为统一接口,具体厂商可替换。Azure key 到位后,发音测评从 SpeechAce 切回 Azure 不影响上层。

## 3. 整体架构

```
浏览器(Web playground)
  │  录音(press-to-talk, MediaRecorder)+ Web Speech API 本地 STT
  ▼
WebSocket ──► FastAPI 后端 orchestrator(dialogue.py)
                 │  (收到:转写文本 + 音频段)
   ┌─────────────┼──────────────────────────────┐
   ▼ 主链路(同步,低延迟)                         ▼ 副链路(异步,不阻塞)
  文本(浏览器已转写)                            SpeechAce 发音测评(同段音频)
     │                                          MiniMax 细颗粒语法/用词纠错卡
  MiniMax LLM(结构化:reply/inline_correction/goal_reached)
     │
  MiniMax TTS ─► 音频
     │
  回传浏览器(文本+音频+inline纠错)

每步耗时 ──► timing.py 打点 ──► DB(per turn)
课程结束 ──► analysis.py 聚合 ──► 总结(整体分 + 词级发音 + 延迟分解)
```

### 主链路(同步,追求低延迟)

1. 浏览器 press-to-talk:Web Speech API 本地转写出文本,同时 MediaRecorder 录下音频段;经 WebSocket 把**文本 + 音频段**发给后端。
2. 后端音频转码(webm/opus → 16k PCM wav),供副链路 SpeechAce 用。
3. 主链路直接拿到浏览器转写文本(无需后端 STT);通义 Paraformer 作为后端备选 provider,默认不走。
4. MiniMax M2 LLM 调用,**结构化输出** `{reply, inline_correction?, goal_reached}`:
   - prompt 含场景角色(服务员)+ 真实菜单 + 对话历史 + `inline_correction` 槽位指令。
   - 指令:仅当用户犯了**严重/影响理解**的错误时,在回复中自然轻点纠正,填 `inline_correction`;否则正常对话。
   - `goal_reached` 用于终止判定(点餐完成)。
5. MiniMax TTS → 音频。
6. 文本 + 音频 + inline 纠错回传浏览器播放/展示。

### 副链路(异步,不阻塞对话)

每轮用户音频落盘后,后台任务并行:
- **发音测评**:同段音频发 SpeechAce → 词级发音分 + 流畅度,入库。
- **延迟纠错**:MiniMax 对该轮文本做细颗粒语法/用词分析 → 纠错卡片(侧边栏展示,进总结)。

副链路与主链路的关系:**两级纠错**。
- 即时(inline):严重错误,由主链路 LLM 在回复中即时轻点 —— 不额外加调用、不加延迟。架构上 `dialogue.py` 暴露 `inline_correction` 槽位,副链路可随时往该槽位推 hint。
- 延迟(deferred):所有细颗粒问题走副链路异步 → 卡片 + 总结。

### 终止判定

放主链路:LLM 每轮回复附带 `goal_reached`。点餐目标达成(下单完成)即可结束课程,触发总结。比单独副链路判定更稳。

## 4. 模块划分

| 模块 | 职责 | 依赖 |
|------|------|------|
| `app/main.py` | FastAPI 应用 + WebSocket 端点 + 静态前端 | dialogue, storage |
| `app/services/stt.py` | STT provider 抽象;MVP 默认浏览器 Web Speech(后端透传文本),通义 Paraformer 作为后端备选实现 | 通义 SDK(备选) |
| `app/services/pron.py` | 发音测评 provider 抽象 + SpeechAce 实现 | SpeechAce API |
| `app/services/llm.py` | MiniMax 对话封装,结构化输出解析 | MiniMax API |
| `app/services/tts.py` | MiniMax TTS 封装 | MiniMax API |
| `app/services/dialogue.py` | 主链路编排:会话状态、prompt 组装、inline 纠错槽、终止判定 | stt, llm, tts, timing |
| `app/services/analysis.py` | 副链路:异步发音测评调度 + 语法纠错卡 + 分数聚合 | pron, llm, storage |
| `app/services/timing.py` | 各步耗时打点 + 聚合查询 | storage |
| `app/services/audio.py` | 音频转码(webm/opus → wav 16k) | pydub/ffmpeg |
| `app/scenarios/ordering.py` | 点餐场景配置:system prompt(注入真实菜单)、目标、终止条件 | resources/menu.json |
| `app/models.py` | 数据模型(pydantic) | — |
| `app/storage.py` | SQLite + 音频文件持久化 | sqlite3 |
| `scripts/scrape_menu.py` | 一次性爬真实菜单 → `resources/menu.json` | requests/bs4 |
| `frontend/` | playground 单页(HTML/JS) | — |

每个 service 单一职责、可独立 mock 测试。

## 5. 数据模型

```
Session
  id, scenario, status(active/completed), created_at, completed_at
  turns: [Turn]

Turn
  id, session_id, index
  user_audio_path, user_transcript
  pronunciation: { overall, accuracy, fluency, words:[{word, score}] }  # SpeechAce, 异步填充
  assistant_text, assistant_audio_path
  inline_correction: text | null            # 主链路即时纠错
  deferred_corrections: [{type, original, suggestion, explanation}]  # 副链路异步填充
  goal_reached: bool
  timings: { stt_ms, llm_ms, tts_ms, total_ms }

Summary(课程结束聚合)
  session_id
  overall_score, sub_scores: { pronunciation, fluency, grammar }
  word_scores: [{word, score, count}]       # 词级发音可视化数据
  correction_list: [...]                    # 汇总所有 deferred + inline
  timing_breakdown: { stt_avg, llm_avg, tts_avg, total_avg, samples }
  llm_comment: text                         # MiniMax 生成的总体点评
```

## 6. 耗时日志与流畅性反馈

- `timing.py` 对每轮的 STT(浏览器端上报)/ LLM / TTS / 端到端各步打点,写入 `Turn.timings`。
- 提供聚合接口 `GET /api/session/{id}/timing` 返回各步均值/分位。
- 前端总结页用该数据画**延迟分解图**(堆叠柱状或分段条),直接呼应"流畅性"评价维度。

## 7. Resources — 真实菜单

- `scripts/scrape_menu.py`:从某餐厅公开菜单页抓取菜品(名称/价格/描述)→ 存 `resources/menu.json`。
- 合规:仅抓公开页面、低频请求、结果缓存到本地,不重复请求;脚本只需跑一次。
- 用途:① playground 左侧菜单面板展示;② 注入"服务员"角色的场景 prompt,使对话基于真实菜品。

## 8. 前端 playground

单页布局:
- 左:真实菜单面板(读 `resources/menu.json`)。
- 中:对话气泡区 + press-to-talk 录音按钮 + 音频播放。
- 右:实时纠错卡(inline + 副链路 deferred 卡片)。
- 结束:总结页 —— 整体分、词级发音色块、延迟分解图、纠错汇总、LLM 点评。

技术:原生 HTML/JS + MediaRecorder + WebSocket;图表用轻量库(如 Chart.js)。

## 9. 错误处理

- 外部 API(通义/SpeechAce/MiniMax)超时或失败:主链路给降级提示并重试一次;副链路失败只记日志、不影响对话。
- 音频转码失败:返回明确错误,提示重录。
- WebSocket 断连:前端自动重连,会话状态后端保留。
- SpeechAce 自由说接口对短音频/噪声可能返回低置信:发音分标注置信度,前端弱化展示。

## 10. 测试策略

- 每个 service(stt/pron/llm/tts/audio)对外部 API 做 mock 单元测试。
- `dialogue.py` 主链路:mock 各 service,验证一轮完整编排 + 结构化输出解析 + 终止判定。
- `analysis.py` 副链路:验证聚合逻辑(分数、纠错汇总)用确定性输入。
- `timing.py`:验证打点与聚合数值。
- 一个集成测试:全 mock API 跑通"录音→回复→落盘→聚合总结"一轮。

## 11. MVP 范围(YAGNI)

**做**:点餐单场景全链路、press-to-talk 录音、两级纠错(inline + deferred)、发音测评(SpeechAce 异步)、耗时日志 + 延迟图、真实菜单 resource、课后总结 + 词级发音可视化、简单 playground。

**不做(预留扩展)**:多场景切换 UI(配置化预留)、连续 VAD、流式 STT/TTS(先 press-to-talk 分段,优化项)、用户账号体系、移动端、Azure 切换(provider 抽象已留)、通义 Paraformer 后端 STT(provider 已留,需要后端可控时启用)。

## 12. 已知技术风险

1. **浏览器 Web Speech API 限制**:仅 Chrome 系、识别质量一般、后端拿不到置信度;若 demo 环境受限,切后端通义 Paraformer(provider 已留,已有 key)。
2. **音频格式转码**:浏览器 webm/opus → Azure/通义/SpeechAce 要 16k PCM wav,需 pydub/ffmpeg,最易踩坑,单列 `audio.py`。
3. **SpeechAce 自由说延迟**:偏分析、较慢,故放副链路异步,不阻塞对话。
4. **结构化输出稳定性**:MiniMax 结构化输出需校验/容错解析,失败时降级为纯 reply。
