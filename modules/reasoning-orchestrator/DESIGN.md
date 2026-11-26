# reasoning-orchestrator 设计说明

> 状态：最小 Demo 已实现（SSE 回合、记忆检索/写入、模板/LLM 回退、配置保存、persona 快照与人格写标记）；真实门控、重排与持久化未实现。  
> 权威来源：`module.yaml`、`contracts/openapi.yaml`、`contracts/events/*`。

## 1. 定位

编排器是对话的唯一入口：接收回合请求，获取人格快照，判断是否需要记忆，调用记忆图检索，按门控筛选后注入 LLM，流式返回，并记录可审计的决策。它不存储记忆或人格，只编排。

## 1.1 最小 Demo 实现

- `POST /turns` 已实现 SSE：先完成检索/门控/生成，再按 24 字符分块发送 `token`，最后发送 `done`。
- 记忆：调用 `memory-graph` 的 `retrievals` 与 `episodes`；检索超时 800ms，写入失败不阻断回复但标记 `MEMORY_WRITE_FAILED`。
- 门控：`max(score) + beta×0.05`（有扩散来源时），默认 `tau=0.2`（哈希嵌入下的 Demo 口径）；真实 BGE-M3 接入后需重新校准。
- 生成：默认 `TemplateCompleter`；管理端启用 LLM 后走 OpenAI 兼容 `/chat/completions`，失败回退模板并标记 `LLM_UNAVAILABLE`。
- 审计/回合/幂等：进程内 `TurnStore`；重启丢失。事件经进程内总线发布。
- 人格：每回合读取 persona-state 身份层与适应层并拼入 system prompt；失败时用静态兜底并标记 `personaDegraded`。
- 人格写通道：解析模型回复中的 `<persona_update>` 与 `<persona_proposal>` 标记，剥离后分别调用适应层更新与提案创建；契约见 `contracts/persona-actions.v1.yaml`。

## 2. 回合状态机（阶段 2 目标）

```
queued → running → completed
                 ↘ degraded → completed
                 ↘ failed
```

- `POST /turns` 创建回合并返回 SSE；客户端断开不取消已提交的回合（可重连读取终态）。
- `GET /turns/{id}` 读取状态；`GET /audits/{id}` 读取门控/检索审计。
- 幂等：同一 `Idempotency-Key` 在 24h 内返回同一 `turnId`；并发重复请求返回 409 或同一流。

## 3. System-One / System-Two 门控

```
score = α·semantic + β·spreading + γ·recency
use_memory = calibrate(score) ≥ τ
```

- System-One：快速启发式（相似度、边权、时近性），目标 <50ms。
- System-Two：在不确定区间触发更昂贵的重排/校验（阶段 2 实现）。
- `τ`（tau）与 `β`（spreading 权重）可管理端配置；每次变更记录旧值/新值/操作者。
- 审计字段：`gateScore`、`gateThreshold`、`candidatesConsidered`、`usedEpisodeIds`、`retrievalIds`。
- 校准：默认 `identity`，可选 `isotonic`/`platt`；校准器版本随配置记录。

## 4. 回合流程

1. 鉴权与租户解析；校验幂等键。
2. 获取人格快照（身份层 + 适应层，500ms 超时），再按需检索记忆；各自独立超时。
3. 计算门控；选择 Top-K（≤50，默认 8）注入。
4. 调用 LLM，剥离人格标记后 SSE 输出 `token` 事件。
5. 结束输出 `done`（含 `turnId`、`memories`、`persona`、`degraded`）或 `error`。
6. 发布 `turn.processed`（成功/降级完成）或 `turn.degraded`；审计落库。

SSE 事件：

```
event: token   data: {"text":"..."}
event: done    data: {"turnId":"...","degraded":false,"reasons":[],"usedEpisodeIds":[],"memories":[],"persona":{"identityVersion":2,"adaptationVersion":4,"updated":false,"degraded":false,"identityProposalId":null}}
event: error   data: {"code":"...","requestId":"..."}
```

### 4.1 模型可发起的人格修改

| 标记 | 下游能力 | 生效方式 |
| --- | --- | --- |
| `<persona_update>{"deltas":{...},"reason":"..."}</persona_update>` | `persona-state.adaptation.update.v1` | 直接更新适应层，带 `expectedVersion` 乐观锁 |
| `<persona_proposal>{"rationale":"...","changes":{...}}</persona_proposal>` | `persona-state.proposal.create.v1` | 仅创建 `pending` 提案，需管理员审批 |

- 标记在拼接 `token` 事件前被移除，未知/非法标记同样移除。
- 适应层被拒（409/422）→ `PERSONA_UPDATE_REJECTED`；提案被拒 → `PERSONA_PROPOSAL_REJECTED`；
  依赖失败 → `PERSONA_UPDATE_FAILED` / `PERSONA_PROPOSAL_FAILED` / `PERSONA_UNAVAILABLE`。
- 身份层永远不会被模型直接写入。

## 5. 降级矩阵

| 依赖 | 超时 | 行为 | 标记 |
| --- | --- | --- | --- |
| memory-graph | 800ms | 跳过记忆，直接回答 | `memoryDegraded=true` |
| persona-state | 500ms | 使用静态兜底叙事；仍剥离人格标记并拒绝写操作 | `personaDegraded=true`、`PERSONA_UNAVAILABLE` |
| LLM | 20s | 返回错误事件，回合 `failed` | `llmDegraded=true` |
| consolidator | 异步 | 不影响回合，仅记录入队失败指标 | 不标记 |

降级原因使用稳定代码（如 `MEMORY_TIMEOUT`），不得包含内部地址。

## 6. API 与能力

| 方法与路径 | 能力 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST /api/reasoning-orchestrator/v1/turns` | `reasoning-orchestrator.turn.process.v1` | `reasoning-orchestrator.turn.create` | SSE；需幂等键 |
| `GET /api/reasoning-orchestrator/v1/turns/{turnId}` | `reasoning-orchestrator.turn.read.v1` | `reasoning-orchestrator.turn.read` | 回合状态 |
| `GET /api/reasoning-orchestrator/v1/audits/{turnId}` | `reasoning-orchestrator.audit.read.v1` | `reasoning-orchestrator.audit.read` | 门控审计 |
| `PUT /internal/v1/gate/config` | `reasoning-orchestrator.gate.configure.v1` | `reasoning-orchestrator.admin.write` | 门控配置 |

阶段 0 全部返回 `501 REASONING_ORCHESTRATOR_FEATURE_NOT_IMPLEMENTED`；OpenAPI 仍按契约声明 SSE `200 text/event-stream`。

## 7. 事件

| 事件 | 触发 | 数据要点 |
| --- | --- | --- |
| `reasoning-orchestrator.turn.processed.v1` | 回合完成（含降级完成） | `turnId/status/latencyMs/degraded` |
| `reasoning-orchestrator.turn.degraded.v1` | 发生降级 | `turnId/reasons[]` |

事件不包含消息或记忆原文。

## 8. 依赖与集成

- 必选：`host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`。
- 可选：`memory-graph.episode.retrieve.v1`、`memory-graph.retrieval.read.v1`、`persona-state.identity.read.v1`、`persona-state.adaptation.read.v1`、`persona-state.adaptation.update.v1`、`persona-state.proposal.create.v1`、`async-consolidator.job.enqueue.v1`。
- 仅通过 HTTP 能力调用；使用 `X-Request-Id` 与 `traceparent` 传播上下文。
- 重试：GET 可重试；POST 仅在幂等键存在且确认未执行时重试。

## 9. 可观测性

- 指标：回合总数/失败/降级、端到端 P50/P95、各依赖耗时、门控使用率、SSE 断开数。
- 日志：`turnId`、`sessionId`（哈希/截断）、`requestId`、耗时、降级原因；不含消息文本。
- 审计：保留候选 ID、分数、阈值、使用 ID；按租户保留期清理。

## 10. 非功能目标（阶段 2 验证，当前未验证）

- 首 token P95 ≤ 1.5s（不含 LLM 冷启动）。
- 门控决策 P95 ≤ 50ms；记忆调用 P95 ≤ 300ms。
- 降级路径成功率 100%（依赖超时仍返回可用回复）。
- SSE 断连后资源回收 ≤ 5s。

## 11. 待决问题

- LLM 供应商与流式协议适配（阶段 2 定稿）。
- 门控校准数据来源与离线评估流程。
- 回合状态持久化位置（编排器自有库或仅 Redis/内存）。
- 多轮对话的上下文窗口与记忆注入上限。
