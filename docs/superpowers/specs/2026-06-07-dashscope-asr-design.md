# DashScope 实时 ASR 设计

日期:2026-06-07
分支:`feat/dashscope-asr`

## 目标

把语音转写从浏览器 Web Speech 换成服务端 DashScope Paraformer 实时 ASR,获得更快、可流式回传的「边说边出字」体验;DashScope 不可用时无缝回退浏览器 Web Speech。

## 现状

- 转写在前端浏览器(Web Speech API),后端不参与;`stt.py` 的 `DashscopeStt` 只是注释占位。
- 录音流程(`frontend/app.js:stopRec`):MediaRecorder 产出 webm blob(供发音评分 `audio_b64`)+ Web Speech 产出 `recognizing` 文本 → `ws.send({type:'turn', text, audio_b64, stt_ms})`。
- `config.dashscope_api_key`(env `DASHSCOPE_API_KEY`)字段已存在,但未使用。

## 技术依据(已核实)

- DashScope Python SDK:`dashscope.audio.asr.Recognition`,流式接口 `start()` / `send_audio_frame(buf)` / `stop()`,回调 `RecognitionCallback.on_event(result)` 实时回传中间结果。
- model `paraformer-realtime-v2`;`format='pcm'`、`sample_rate=16000`、`language_hints=['en']`。
- 鉴权:`dashscope.api_key`(取自 `DASHSCOPE_API_KEY`)。
- SDK 仅支持 Python/Java —— 后端正是 Python,直接用 SDK。

## 架构

### 后端

1. **依赖**:`pyproject.toml` 增加 `dashscope>=1.20`。

2. **`app/services/stt.py` 重构为流式服务**:
   - 保留 `BrowserStt`(回退路径)与 `SttResult` 不变。
   - 新增 `DashscopeStreamingSession`:封装一次识别会话,暴露
     - `feed(pcm: bytes)` —— 推一帧 PCM16/16k;
     - `final() -> str` —— 停止并返回最终文本;
     - 通过构造时传入的 `on_partial(text)` 回调实时回传中间结果。
   - **可测试性**:通过注入 `recognizer_factory`(默认构造真实 `Recognition`)解耦 SDK;测试注入 fake recognizer,不触网。与 `llm.py` 的 transport 注入同构。

3. **WS 端点 `/ws/asr/{session_id}`**(与对话主链路 `/ws/{session_id}` 分离):
   - 客户端二进制帧 = PCM16/16k 音频;JSON 控制帧 `{type:'stop'}` 结束本次识别。
   - 后端把帧喂给 `DashscopeStreamingSession`;`on_partial` → 推 `{type:'partial', text}`;结束推 `{type:'final', text}`。
   - 未配 `DASHSCOPE_API_KEY` 时端点立即回 `{type:'unavailable'}` 并关闭,前端据此回退。

4. **能力探测**:`/api/health` 的 `keys_configured` 增加 `dashscope` 布尔(已有结构,加一项),前端据此决定走流式 ASR 还是 Web Speech。

### 前端

1. **PCM 采集**:`getUserMedia` → `AudioContext` + `AudioWorklet`(降级 `ScriptProcessor`)→ Float32 → 降采样到 16k、转 Int16 PCM → 录音期间经 `/ws/asr` 二进制流式上传。
2. **实时回显**:收到 `partial` 在状态区滚动显示;`stopRec` 时用 `final` 文本作为本轮 turn text。
3. **发音评分不变**:MediaRecorder webm → `audio_b64` 照旧并行采集。
4. **回退**:能力探测为假、或 ASR WS 连接/识别失败时,回退现有 Web Speech 路径(保留现有代码,不删除)。

## 数据流

```
录音中: mic ──┬─ AudioWorklet → PCM16/16k → /ws/asr ──→ DashScope ──→ partial/final ──→ 状态区/turn text
             └─ MediaRecorder → webm blob (audio_b64, 发音评分)
停止: /ws/asr final text ─→ ws.send({type:'turn', text, audio_b64, stt_ms})
```

## 错误处理与边界

- 未配 key / SDK 未装 / WS 失败 → 回退 Web Speech,用户无感。
- DashScope 中途报错(`on_error`)→ 关闭本次 ASR 会话,本轮回退当次 Web Speech 结果(若有),否则提示重说。
- 浏览器不支持 AudioWorklet → 回退 ScriptProcessor;都不支持 → 回退 Web Speech。

## 测试策略

- **可自动化**:`DashscopeStreamingSession`(fake recognizer,验证 feed/partial/final 与文本聚合)、`/ws/asr` 端点(fake session,验证 partial/final/unavailable 协议)、`/api/health` 增项、回退判定。
- **需人工验证(无法自动化)**:真实 DashScope 实时识别(需 `DASHSCOPE_API_KEY`)、浏览器麦克风采集与 AudioWorklet 降采样。spec 标注:合并前需在配好 key 的环境手动走一次端到端。

## 不在本分支范围(YAGNI)

- 实时翻译(gummy)、说话人分离、情感识别。
- 把发音评分也改用 PCM 复用(暂仍用 webm,避免一次改太多)。

## PR 规范

单分支 `feat/dashscope-asr`,完成后 Codex review → PR → 合并(按既有流程)。需人工端到端验证项在 PR 描述中列明。
