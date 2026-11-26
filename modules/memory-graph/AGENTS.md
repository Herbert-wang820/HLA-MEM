# memory-graph 模块协作约束

本文件在仓库根 `AGENTS.md` 之上叠加，**只加严，不放宽**。

## 1. 职责边界

- 拥有：情景节点（Episode）、概念节点（Concept）、共激活边（CO_ACTIVATED）、边权/遗忘/蒸馏结果、检索审计。
- 不拥有：人格身份与适应层（`persona-state`）、对话编排（`reasoning-orchestrator`）、巩固作业队列与死信（`async-consolidator`）。
- 禁止读取其他模块数据库；跨模块只消费版本化能力或事件。

## 2. 不可破坏的规则

1. **情景不可变**：写入后 `content` 不得原地修改；撤回是追加 `retractedAt/retractReason` 标记，检索默认过滤已撤回节点。
2. **租户可信**：`tenantId` 只从 `Identity` 取得；请求体/query/普通头出现 `tenantId` 必须 422 或忽略（当前 DTO `extra="forbid"`，直接 422）。
3. **无原始 Cypher**：管理端图查询只接受结构化 `nodeTypes/filters/depth/limit`，深度 ≤3、节点 ≤500；禁止把用户输入拼进查询字符串。
4. **检索不造假**：图库不可用时返回 503 或显式降级标记，不得用空结果冒充“没有记忆”。
5. **非幂等写必须带 `Idempotency-Key`**；同一 key + 不同请求体返回 409。
6. **不记录原文**：日志、事件、指标标签不得包含 `content`、完整个人数据或内部地址；事件只带 `contentHash`。
7. **契约先行**：能力、事件、权限、OpenAPI 变更先改 `module.yaml`/`contracts/`，再改实现；`make contracts-check` 必须通过。

## 3. 阶段 1 状态（内存纵向切片）

- 已实现：写入/读取/撤回、双路径检索、检索审计、共激活边、结构化图查询、边权强化与遗忘、幂等键、`asOf` 可见性、租户隔离。
- 未实现：FalkorDB/Neo4j、BGE-M3/HNSW、概念节点、枢纽蒸馏、跨进程持久化与 outbox；`distill` 操作显式跳过，不得假装完成。
- 当前存储为进程内字典，重启即丢；嵌入器为哈希替身，不代表语义质量。报告必须写明这些边界。
- FalkorDB/PostgreSQL 集成与量化门槛未验证（本机无 Docker/模型）。

## 4. 命令

```bash
make install
make test-module M=memory-graph
make contracts
make contracts-check
make validate
make run-memory-graph
```

## 5. 评审关注点

- 新增能力是否真的需要跨模块暴露？能否用事件替代同步调用？
- 检索是否同时覆盖语义与扩散两条路径，融合后可解释？
- 撤回、租户过滤、时间旅行（`asOf`）是否在所有读路径一致？
- 事件是否通过 outbox 与数据提交原子化，消费者是否幂等？
