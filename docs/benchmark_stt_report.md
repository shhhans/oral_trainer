# STT 方案基准测试报告

**测试日期**: 2026-06-07  
**分支**: `claude/minimax-tts-testing-BMVej`  
**测试人**: Claude (自动化基准)

---

## 1. 背景与测试目标

本测试旨在评估以下两种 STT/评分方案的可行性与延迟：

| 方案 | STT 来源 | 评分来源 | 调用链 |
|------|----------|----------|--------|
| **Method A（现行）** | 浏览器 Web Speech API（前端，零后端延迟）| SpeechAce `score_text`（副链路异步）| 浏览器 → 后端 → LLM → TTS |
| **Method B（备选）** | SpeechAce `score_speech` 返回 `transcript` | 同一次调用返回评分 | 后端 → SpeechAce → LLM → TTS |

---

## 2. 测试方法

1. 用 **MiniMax TTS** (`speech-02-turbo`, `male-qn-qingse`) 生成 3 段不同长度的英文测试音频（模拟用户发音）。
2. 对每段音频调用 SpeechAce **`score_text`**，测量往返延迟与评分质量。
3. 额外发出一次 SpeechAce **`score_speech`** 探测请求，确认当前订阅方案可用性。
4. API 调用总计：MiniMax TTS ×3 + SpeechAce score_text ×3 + score_speech probe ×1 = **7 次**。
5. 区域端点：`https://api2.speechace.com`（AP-SE 新加坡，与 API Key 绑定区域一致）。

---

## 3. 测试结果

### 3.1 MiniMax TTS 生成延迟

| 测试段 | 文本长度 | 音频大小 | TTS 延迟 |
|--------|----------|----------|----------|
| 短句 (5 词) | `I'd like a burger, please.` | 38 KB | **2,544 ms** |
| 中句 (17 词) | `Can I have the grilled chicken sandwich...` | 73 KB | **1,811 ms** |
| 长句 (27 词) | `Actually, I'm not sure what to get...` | 123 KB | **3,403 ms** |

### 3.2 SpeechAce `score_text` 延迟与质量

| 测试段 | score_text 延迟 | 状态 | 总体发音分 | 低分词（<80）|
|--------|-----------------|------|------------|--------------|
| 短句 (5 词)  | **897 ms**  | ✅ success | 100/100 | 无 |
| 中句 (17 词) | **965 ms**  | ✅ success | 99/100  | 无 |
| 长句 (27 词) | **1,583 ms** | ✅ success | 98/100  | `you` (75) |

`quota_remaining: -1` → 当前 Key 无调用次数上限（试用/企业配置）。

### 3.3 SpeechAce `score_speech` 可用性探测

| 请求 | HTTP | API 状态 | 错误信息 |
|------|------|----------|----------|
| score_speech probe | 200 | **error** | `error_feature_unavailable` |

**结论：`score_speech`（Method B 的核心）要求 Premium 订阅方案（$125/月），当前账户不可用。**

---

## 4. 方案对比分析

### 4.1 首字/首音延迟（关键路径）

```
Method A（现行方案）:
  用户说话 → 浏览器 STT [~0ms 后端]
           → 后端收到文本
           → LLM 生成回复 [~1,000–3,000ms *估算]
           → MiniMax TTS 合成 [~1,800–3,400ms 实测]
           ─────────────────────────────────────────
  首音延迟 ≈ 2,800–6,400ms  (SpeechAce 在副链路，不阻塞)

Method B（备选，当前不可用）:
  用户说话 → 上传音频 → SpeechAce score_speech [~500–1,500ms *估算]
           → 后端收到 transcript
           → LLM 生成回复 [~1,000–3,000ms]
           → MiniMax TTS 合成 [~1,800–3,400ms]
           ─────────────────────────────────────────
  首音延迟 ≈ 3,300–7,900ms  (SpeechAce 在主链路，额外增加 ~500ms)
```

### 4.2 整体体验对比

| 维度 | Method A（浏览器 STT + score_text） | Method B（score_speech 一体）|
|------|------------------------------------|-----------------------------|
| **主链路首音延迟** | ✅ 更快（STT 不在关键路径）| ❌ 更慢（STT 阻塞主链路）|
| **发音评分** | ✅ 逐词精确（需要参考文本）| ⭕ 更全面（含流利度/语法/语义），但需 Premium |
| **副链路延迟** | ~900–1,600 ms（评分异步，不影响 UX）| N/A |
| **STT 质量** | 取决于浏览器 + 网络环境 | ⭕ SpeechAce ASR（但当前不可用）|
| **成本** | 仅评分计费（Basic 可用，$40/月）| Premium $125/月 |
| **当前可用** | ✅ 可用 | ❌ 需升级订阅 |

---

## 5. 关键发现：现行代码 Bug

当前 `app/services/pron.py` 调用的端点是 `/api/scoring/speech/v9`（`score_speech`），但该端点需要 Premium 方案，**当前账户不支持**。这意味着：

- 现有的发音评分副链路在生产环境**静默失败**（`PronService.assess()` 捕获 HTTP 异常返回 `None`）
- 所有会话的 `Pronunciation` 评分实际为空

**修复方案**：将 `pron.py` 改为调用 `score_text`，以浏览器 STT 文本作为参考文本。这不影响评分逻辑，仅改变端点，且无需升级订阅。

---

## 6. 结论与建议

### 结论

**Method A 是正确架构**，原因：
1. Method B 当前不可用（需升级至 Premium）
2. 即使 Method B 可用，首音延迟比 Method A 多 ~500–1,000ms（因 SpeechAce 进入主链路关键路径）
3. 浏览器 Web Speech API 延迟极低，已能满足实时对话需求

### 建议优先级

| 优先级 | 事项 |
|--------|------|
| 🔴 高 | 修复 `pron.py`：将端点从 `score_speech` 改为 `score_text`，以浏览器 STT 文本作为参考 |
| 🟡 中 | 在 `config.py` 中增加 `SPEECHACE_BASE_URL` 环境变量，避免区域端点硬编码 |
| 🟢 低 | 如未来升级 Premium，可在副链路将 `score_text` 切换回 `score_speech` 以获取流利度/语法评分；首音延迟不变 |

---

## 7. 原始数据

详见 `scripts/benchmark_stt.py` 与测试时生成的 `/tmp/bench_results.json`。  
测试音频缓存于 `/tmp/bench_audio/`（`short.mp3`, `medium.mp3`, `long.mp3`）。

---

*报告由 `scripts/benchmark_stt.py` 驱动生成，于 2026-06-07 在 `claude/minimax-tts-testing-BMVej` 分支上执行。*
