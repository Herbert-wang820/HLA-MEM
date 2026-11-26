# memory-graph 设计说明

> 状态：阶段 1（内存纵向切片）已实现；FalkorDB、BGE-M3、概念节点与枢纽蒸馏未实现。  
> 权威来源：`module.yaml`、`contracts/openapi.yaml`、`contracts/events/*`；本文件解释设计意图，冲突时以契约文件为准。

## 1. 定位

记忆图是 HLA-MEM 的长期记忆存储与检索边界：保存不可变情景、概念与共激活关系，提供“语义 + 扩散”双路径检索，并在巩固阶段应用边权更新、遗忘与枢纽蒸馏。它不决定“该不该回忆”，也不生成人格文本；这些属于编排器与人格状态模块。

## 2. 领域模型（阶段 1 已实现，概念节点除外）

| 实体/关系 | 关键字段 | 约束 |
| --- | --- | --- |
| `Episode` | `episodeId`、`tenantId`、`sessionId`、`content`、`contentHash`、`occurredAt`、`source`、`metadata`、`retractedAt`、`retractReason` | 不可变；`contentHash = sha256(content)`；撤回只追加标记 |
| `Concept` | `conceptId`、`tenantId`、`label`、`embedding`、`salience` | 标签在租户内唯一；向量维度由嵌入模型固定 |
| `CO_ACTIVATED` | `sourceEpisodeId`、`targetEpisodeId`、`weight`、`lastActivatedAt`、`activationCount` | 无向语义、存储为规范方向；`weight ∈ [0,1]`；同租户 |
| `RetrievalAudit` | `retrievalId`、`tenantId`、`queryHash`、`candidateIds`、`scores`、`latencyMs`、`degraded` | 不保存 query 原文；保留期按租户策略 |

**租户隔离**：所有节点/边携带租户键，所有查询强制注入租户过滤。当前内存存储以 `(tenant, id)` 为键，读取/检索/图查询均先按租户过滤；这是逻辑隔离，**不是**数据库级 RLS 或物理隔离。阶段 1b 在 FalkorDB 上对比“共享图 + 租户属性 + 强制过滤”与“租户独立图”两种方案，基准后定稿。

**阶段 1 实现范围**：情景、共激活边、检索审计、结构化图查询、边权强化与遗忘已实现；`Concept` 节点与 `DERIVED_FROM` 关系尚未实现，`nodeTypes: ["concept"]` 返回空图。

## 3. 写入流程

1. 从 `Identity` 取 `tenantId`，校验权限 `memory-graph.episode.write`。
2. 校验 `Idempotency-Key`（主体+租户+操作+请求摘要，24h）；重复同请求返回首次结果，不同请求 409。
3. 计算 `contentHash`，生成 UUIDv4 `episodeId`。
4. 写入 `Episode`，随后发布 `memory-graph.episode.written.v1`。
5. 当前内存实现直接发布到进程内总线；生产必须改为与数据同事务的 outbox，消费者按 `event.id` 幂等。

撤回：追加 `retractedAt/retractReason`，发布 `memory-graph.episode.retracted.v1`；不删除节点，保证审计与事件可重放。

## 4. 双路径检索

```
query ──► 嵌入 ──► HNSW Top-N 语义候选 ─┐
  │                                      ├─► 归一化/融合 ─► 过滤撤回/租户 ─► Top-K ≤50 ─► 审计
  └──► 种子实体 ──► 扩散激活（≤2 跳）───┘
```

- 语义路径：向量相似度，默认 `semanticTopK=20`。
- 扩散路径：从查询命中的实体出发，按边权与跳数衰减，默认 `spreadingTopK=20`，最多 2 跳。
- 融合：两路分数用概率并集 `1 - (1 - semantic)(1 - spreading)` 合并，记录来源与跳数；`topK` 硬上限 50。
- 阶段 1 实现：嵌入器为 256 维确定性哈希（token + CJK 字符/双字），**不是 BGE-M3**，只用于验证管线；语义分数无质量声明。
- 共激活：每次检索取前 10 个候选两两配对，`delta = 0.02 + 0.08·min(score)`，边权夹在 `[0,1]`；同一边重复检索会累积。
- 过滤：租户、`retracted=false`、`asOf` 时间边界；`asOf` 只影响可见性，不修改数据。
- 审计：保存候选、分数、来源、耗时、是否降级；不保存 query 原文。
- 降级：图库超时/不可用返回 `503 MEMORY_GRAPH_DEPENDENCY_UNAVAILABLE`；部分路径失败时返回 `degraded=true` 与原因，禁止静默返回空列表。

## 5. 巩固应用

`POST /internal/v1/consolidation/apply` 接收 `async-consolidator` 生成的批次：

- `batchId + jobId` 作为服务层幂等边界；同一批次即使换 HTTP 幂等键也不会重复应用。
- `reinforce`：`weight = min(1, weight + weightDelta)`；更新 `lastActivatedAt/activationCount`。
- `forget`：显式删除指定边；低权重边自动衰减尚未实现（`fade` 配置保留给阶段 1b/3）。
- `distill`：阶段 1 **显式跳过**并计入 `skippedCount`（原因 `DISTILL_NOT_IMPLEMENTED`）；枢纽节点与追溯关系留到阶段 3。
- 单批最多 5000 操作；返回 `appliedCount/skippedCount/maxWeight`。

## 6. API 与能力

| 方法与路径 | 能力 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST /api/memory-graph/v1/episodes` | `memory-graph.episode.write.v1` | `memory-graph.episode.write` | 写情景，需幂等键 |
| `GET /api/memory-graph/v1/episodes/{episodeId}` | `memory-graph.episode.read.v1` | `memory-graph.episode.read` | 读单节点 |
| `POST /api/memory-graph/v1/episodes/{episodeId}/retract` | `memory-graph.episode.retract.v1` | `memory-graph.episode.write` | 追加撤回 |
| `POST /api/memory-graph/v1/retrievals` | `memory-graph.episode.retrieve.v1` | `memory-graph.episode.read` | 双路径检索 |
| `GET /api/memory-graph/v1/retrievals/{retrievalId}` | `memory-graph.retrieval.read.v1` | `memory-graph.retrieval.read` | 读审计 |
| `POST /internal/v1/graph/query` | `memory-graph.graph.read.v1` | `memory-graph.admin.read` | 结构化只读查询 |
| `POST /internal/v1/consolidation/apply` | `memory-graph.consolidation.apply.v1` | `memory-graph.consolidation.write` | 应用巩固批次 |

阶段 1 全部端点已实现（内存）；`distill` 操作跳过。错误模型仍为 `MEMORY_GRAPH_*`。

## 7. 事件

| 事件 | 触发 | 数据要点 |
| --- | --- | --- |
| `memory-graph.episode.written.v1` | 情景提交后 | `episodeId/sessionId/occurredAt/contentHash` |
| `memory-graph.episode.retracted.v1` | 撤回标记后 | `episodeId/reasonCode/retractedAt` |
| `memory-graph.coactivation.recorded.v1` | 检索形成共激活批次 | `batchId/retrievalId/pairs/pairCount` |

事件信封遵循 `schemas/event-envelope.schema.json`；数据部分由各自 Schema 约束。当前实现直接发布到进程内总线，**没有持久化 outbox**；生产替换时必须保证与数据同事务、至少一次、消费者按 `event.id` 去重。

## 8. 依赖与降级

- 必选：`host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`。
- 可选：无。编排器与巩固器通过能力/事件调用本模块，本模块不反向同步依赖它们。
- 图库不可用：读返回 503/降级标记；写失败快速失败，不进入“假成功”。
- 嵌入模型不可用：语义路径捕获异常并降级（`degraded=true`、`EMBEDDING_UNAVAILABLE`），扩散路径仍可返回；哈希嵌入器本身不会失败，真实模型接入后需补故障注入测试。

## 9. 非功能目标（未验证；内存切片不构成基准）

- 检索 P95 ≤ 300ms（不含嵌入），Top-K ≤50。
- 图查询 ≤500 节点、深度 ≤3。
- 写入幂等窗口 24h；事件重复投递不产生重复边权。
- 单租户 10 万情景、100 万边的基线由 `tests/benchmark` 记录。

## 10. 待决问题

- 租户隔离采用共享图还是独立图（待 FalkorDB/Neo4j 基准；当前仅逻辑隔离）。
- 遗忘是删除边还是保留低权重边（审计与成本权衡；当前显式删除）。
- 枢纽蒸馏的社区算法与可追溯关系（阶段 3 定稿）。
- 检索审计保留期与脱敏策略（需与合规确认）。
