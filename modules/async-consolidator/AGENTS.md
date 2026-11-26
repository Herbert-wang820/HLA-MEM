# async-consolidator 模块协作约束

本文件在仓库根 `AGENTS.md` 之上叠加，**只加严，不放宽**。

## 1. 职责边界

- 拥有：巩固作业队列、重试/退避、死信、积压指标、边权强化/遗忘/枢纽蒸馏的调度，以及独占的 `consolidator` PostgreSQL 库。
- 不拥有：图数据（`memory-graph`）、人格数据（`persona-state`）。
- 通过 `memory-graph.consolidation.apply.v1`、`persona-state.adaptation.update.v1`、`persona-state.proposal.create.v1` 执行副作用；禁止直连其库。

## 2. 不可破坏的规则

1. **至少一次 + 幂等**：作业可能重复执行；应用批次以 `batchId + jobId` 幂等，重复不得重复加权。
2. **租约与可见性**：认领作业使用 `FOR UPDATE SKIP LOCKED` + 租约超时；崩溃后可被重新认领，不得永久卡死。
3. **重试有界**：超过 `maxAttempts` 必须进入死信并发布 `job.deadlettered`，不得无限重试。
4. **死信可重放**：重放是显式操作，需权限与幂等键；重放后保留原死信记录并可追溯。
5. **积压可观测**：`/internal/v1/backlog` 返回 pending/running/deadLettered/最老等待；超过 `warnDepth` 标记 degraded，但不得直接拒绝入队（除非明确配置）。
6. **不携带原文**：作业载荷只存 ID、批次、权重增量；不存记忆原文或人格叙事。
7. **独立数据库**：与 `persona-state` 使用不同 PostgreSQL 实例/库/角色，禁止跨库 Join。

## 3. 阶段 0 状态

- 6 个能力已声明，业务端点返回 `501 ASYNC_CONSOLIDATOR_FEATURE_NOT_IMPLEMENTED`。
- 没有 PostgreSQL 连接、队列、worker、迁移；不得描述为“已实现巩固”。
- 单元/契约/就绪测试可运行；队列并发/故障注入测试需 Docker，当前环境不可用。

## 4. 命令

```bash
make install
make test-module M=async-consolidator
make contracts
make validate
make run-async-consolidator
```

## 5. 评审关注点

- 作业是否会重复加权？幂等键是否覆盖批次与作业？
- 租约超时与 worker 崩溃后的恢复是否可验证？
- 死信重放是否可能造成风暴？是否有速率限制？
- 积压指标是否足以触发告警与容量规划？
