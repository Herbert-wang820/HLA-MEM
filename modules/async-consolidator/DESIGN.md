# async-consolidator 设计说明

> 状态：阶段 0（契约与骨架），业务实现未开始。  
> 权威来源：`module.yaml`、`contracts/openapi.yaml`、`contracts/events/*`。

## 1. 定位

异步巩固器把“对话中产生的共激活/经历”转化为长期结构：批量强化边权、执行遗忘、蒸馏枢纽，并（可选）生成人格变更提案。它在对话主路径之外运行，允许延迟，但必须可重试、可观测、不重复加权。

## 2. 队列模型（阶段 3 目标）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `job` | `job_id`、`status`、`trigger`、`priority`、`attempts`、`max_attempts`、`scheduled_for`、`lease_until`、`last_error` | 状态 `pending/running/completed/failed/dead_lettered` |
| `dead_letter` | `dead_letter_id`、`job_id`、`reason`、`attempts`、`replayed` | 超过重试上限后写入 |
| `outbox` | `event_id`、`payload`、`published_at` | 与状态变更同事务 |

认领：

```sql
SELECT ... FROM job
WHERE status = 'pending' AND scheduled_for <= now()
ORDER BY priority DESC, scheduled_for
FOR UPDATE SKIP LOCKED
LIMIT :batch;
```

- 租约 `visibilityTimeoutSeconds`；worker 心跳续租，崩溃后过期可重领。
- 退避：指数 + 抖动，上限受 `maxAttempts` 约束。
- 幂等：入队 `Idempotency-Key`；执行批次 `batchId + jobId` 由目标模块去重。

## 3. 作业类型

| 类型 | 输入 | 副作用 |
| --- | --- | --- |
| `reinforce` | 共激活批次（episode 对 + 权重增量） | `memory-graph.consolidation.apply.v1` |
| `forget` | 低权重边/过期阈值 | 同上（forget 操作） |
| `distill` | 高度数社区 | 同上（distill 操作） |
| `persona_proposal` | 经历摘要/证据 ID | `persona-state.proposal.create.v1` |

作业载荷只含 ID 与数值；需要原文时由目标模块按 ID 读取，避免复制敏感数据。

## 4. 死信与重放

- 失败达上限：`job.status=dead_lettered`，写 `dead_letter`，发布 `job.deadlettered`。
- 重放：`POST /dead-letters/{id}/replay` 创建新作业并标记 `replayed=true`；原记录保留。
- 重放需 `deadletter.replay` 权限与幂等键；批量重放必须限速（阶段 3 实现）。

## 5. API 与能力

| 方法与路径 | 能力 | 权限 |
| --- | --- | --- |
| `POST /api/async-consolidator/v1/jobs` | `async-consolidator.job.enqueue.v1` | `async-consolidator.job.create` |
| `GET /api/async-consolidator/v1/jobs` | `async-consolidator.job.read.v1` | `async-consolidator.job.read` |
| `GET /api/async-consolidator/v1/jobs/{jobId}` | `async-consolidator.job.read.v1` | `async-consolidator.job.read` |
| `POST /api/async-consolidator/v1/jobs/{jobId}/retry` | `async-consolidator.job.retry.v1` | `async-consolidator.job.retry` |
| `GET /api/async-consolidator/v1/dead-letters` | `async-consolidator.deadletter.read.v1` | `async-consolidator.deadletter.read` |
| `POST /api/async-consolidator/v1/dead-letters/{id}/replay` | `async-consolidator.deadletter.replay.v1` | `async-consolidator.deadletter.replay` |
| `GET /internal/v1/backlog` | `async-consolidator.backlog.read.v1` | `async-consolidator.admin.read` |

阶段 0 全部返回 `501 ASYNC_CONSOLIDATOR_FEATURE_NOT_IMPLEMENTED`；入队成功在阶段 3 返回 `202`。

## 6. 事件

| 事件 | 触发 | 数据要点 |
| --- | --- | --- |
| `async-consolidator.job.completed.v1` | 作业成功 | `jobId/type/appliedCount` |
| `async-consolidator.job.failed.v1` | 单次失败（未到上限） | `jobId/attempt/errorCode` |
| `async-consolidator.job.deadlettered.v1` | 进入死信 | `jobId/deadLetterId/reason` |
| `async-consolidator.edge.reinforced.v1` | 边权批量应用 | `jobId/batchId/edgeCount` |
| `async-consolidator.hub.distilled.v1` | 枢纽蒸馏完成 | `jobId/hubCount` |

事件不含原文/内部地址；走 outbox，消费者按 `event.id` 去重。

## 7. 数据所有权与迁移

- 独占 PostgreSQL 数据库 `consolidator`（第二实例，端口 5433）与角色 `consolidator`。
- 表：`job`、`dead_letter`、`outbox`、`worker_heartbeat`（阶段 3）。
- 索引：`(status, scheduled_for)`、`(tenant_id, created_at desc)`、死信 `(replayed, created_at)`。
- 迁移只前进；生产前做并发认领与崩溃恢复演练。

## 8. 依赖与降级

- 必选：`host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`。
- 可选：`memory-graph.consolidation.apply.v1`、`persona-state.adaptation.update.v1`、`persona-state.proposal.create.v1`。
- 目标模块不可用：作业失败并按退避重试；超过上限进死信。不得丢弃作业。
- 积压超阈值：`backlog.degraded=true` 并告警；对话主路径不受影响。

## 9. 非功能目标（阶段 3 验证，当前未验证）

- 认领吞吐 ≥ 100 jobs/s（单实例，批量 50）。
- 作业至少一次执行，重复应用不改变最终边权（幂等）。
- 崩溃后 ≤ 2×租约时间恢复；无永久 running 作业。
- 死信重放成功率与限速可观测。

## 10. 待决问题

- 是否引入独立消息队列（如 Redis Streams）还是仅 PostgreSQL 队列。
- 多租户下的公平调度（避免大租户饿死小租户）。
- 枢纽蒸馏算法与可追溯关系（与 memory-graph 共同定稿）。
- 死信保留期与自动清理策略。
