# 阶段 1 进度：memory-graph 内存纵向切片

> 日期：2026-11-11  
> 状态：**部分完成**。M1 尚未完成；本文件只声明已实现的内存切片与明确的未验证项。

## 1. 完成内容

阶段 0 的 `memory-graph` 业务端点原本统一返回 `501`。本阶段用进程内适配器替换为真实实现，OpenAPI 路径与能力声明保持不变；同时修正 `GraphNode.nodeType` 的别名（此前误序列化为 `node_type`）。

| 能力 | 实现 | 测试 |
| --- | --- | --- |
| `memory-graph.episode.write.v1` | 不可变情景写入、SHA-256 内容哈希、嵌入、幂等键、事件 | API + service |
| `memory-graph.episode.read.v1` | 按租户读取单节点（含撤回标记） | API |
| `memory-graph.episode.retract.v1` | 追加 `retractedAt/retractReason`，不修改原文 | API + service |
| `memory-graph.episode.retrieve.v1` | 语义 + 扩散双路径、融合、Top-K ≤50、`asOf`、审计 | API + domain |
| `memory-graph.retrieval.read.v1` | 按租户回放检索审计 | API |
| `memory-graph.graph.read.v1` | 结构化节点/过滤/深度/上限查询，无 Cypher | API + service |
| `memory-graph.consolidation.apply.v1` | `reinforce`/`forget`，`batchId + jobId` 幂等；`distill` 跳过 | API + service |

事件：

- 写入发布 `memory-graph.episode.written.v1`（只含 `contentHash`，不含原文）。
- 撤回发布 `memory-graph.episode.retracted.v1`。
- 检索形成 ≥2 个候选时发布 `memory-graph.coactivation.recorded.v1`，并写共激活边。

## 2. 关键实现

### 2.1 存储与租户

- `InMemoryMemoryStore`：`(tenant, episodeId)`、`(tenant, edgeId)`、`(tenant, retrievalId)` 为键；所有读路径先按租户过滤。
- 情景不可变：撤回用 `dataclasses.replace` 追加标记，原文保留。
- 进程内、无持久化；重启即丢。

### 2.2 双路径检索

```
query ──► 哈希嵌入 ──► 余弦 Top-N ─┐
                                  ├─► 概率并集融合 ─► 可见性过滤 ─► Top-K ─► 审计
  └──► 语义种子 ──► 共激活边扩散 ──┘
```

- 语义：`cosine(query, episode.embedding)`，取 `semanticTopK`。
- 扩散：从语义种子出发，最多 2 跳，`score = seedScore · edgeWeight · decay^hop`，取 `spreadingTopK`。
- 融合：`1 - (1 - semantic)(1 - spreading)`；来源去重合并；`topK` 上限 50。
- 可见性：`occurredAt ≤ asOf`；若已撤回，`retractedAt > asOf` 才可见。
- 审计：保存候选、分数、来源、跳数、耗时、降级标记；保存 query 的 SHA-256，不保存原文。

### 2.3 共激活与巩固

- 每次检索取前 10 个候选两两配对：`delta = 0.02 + 0.08·min(score)`；边权 `min(1, w+delta)`。
- 边以 `(min(id), max(id))` 规范化方向，避免重复边。
- `apply` 以 `(tenant, batchId, jobId)` 为幂等键；重复批次即使换 HTTP `Idempotency-Key` 也不重复加权。
- `distill` 显式跳过并计入 `skippedCount`，不伪造枢纽节点。

## 3. 验证结果

```bash
make install
make test-module M=memory-graph
make test
make contracts-check
make lint
```

- `memory-graph`：**31 passed**。
- 全仓库：**141 passed**（加入最小 Demo 的编排器测试后）。
- OpenAPI：`memory-graph` 重新生成后无漂移；契约校验 0 issue。
- 手工 API 流程（TestClient/进程）：写入 201、读取 200、撤回 200、检索 200、审计 200、图查询 200、巩固 200；错误码分别为 `MEMORY_GRAPH_*_NOT_FOUND`、`MEMORY_GRAPH_IDEMPOTENCY_CONFLICT` 等。
- 进程冒烟（真实 uvicorn，8082）：health 200、ready 200、write 201、read 200、retrieve 200、audit 200、graph 200（`nodeType=episode`）。

## 4. 未实现 / 未验证

| 项 | 状态 | 原因/影响 |
| --- | --- | --- |
| FalkorDB/Neo4j 适配 | 未实现 | 本机无 Docker；当前为内存字典 |
| BGE-M3 / HNSW | 未实现 | 无模型权重；当前为 256 维哈希嵌入，**无质量声明** |
| 概念节点 / 枢纽蒸馏 | 未实现 | `nodeTypes: ["concept"]` 返回空；`distill` 跳过 |
| 自动遗忘/边权衰减 | 未实现 | `fade` 配置保留；当前仅显式 `forget` |
| 持久化 outbox | 未实现 | 事件直接发布到进程内总线，非原子 |
| 跨进程幂等 | 未实现 | 幂等与批次去重均在进程内 |
| 检索 P95 ≤300ms / 10 万节点 | 未验证 | 无真实图库与基准数据 |
| 双路径 Recall +10pp | 未验证 | 哈希嵌入不具语义质量 |
| PostgreSQL/RLS | 不适用 | memory-graph 不拥有关系库 |
| 浏览器端到端 | 未验证 | 前端仍以 memory API 为占位/只读 |

## 5. 风险与后续

1. **内存实现不是生产存储**：重启丢数据、单进程、无副本。
2. **哈希嵌入会误导检索评估**：所有质量指标必须等 BGE-M3 接入后重跑。
3. **事件非原子**：写入成功但发布失败会丢事件；阶段 1b 需 outbox。
4. **共激活 O(n²)**：已限制前 10 个候选（45 对），大批量场景需基准。

下一步（M1 收尾）：

1. 抽象 `FalkorDBStore`，实现同样的端口与契约测试；用 Docker 跑租户隔离与并发测试。
2. 接入 BGE-M3 嵌入服务；保留哈希嵌入作为确定性测试替身。
3. 增加批量摄入与检索基准，记录 P95/Recall，决定图引擎。
4. 增加同事务 outbox 与重放测试。
5. 在真实嵌入下重新校准 `minScore`、`decay`、`coactivationTopN`。
