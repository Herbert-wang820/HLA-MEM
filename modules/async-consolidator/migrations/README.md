# 迁移说明

阶段 0 没有持久化实现，因此没有可执行迁移。

阶段 3 计划（PostgreSQL，独立实例/库 `consolidator`）：

1. `0001_init.sql`：`job`、`dead_letter`、`outbox`、`worker_heartbeat`。
2. 约束：`job.status` 检查；`dead_letter.job_id` 外键仅限本库；`outbox.event_id` 唯一。
3. 索引：`(status, scheduled_for, priority desc)`、`(tenant_id, created_at desc)`、死信 `(replayed, created_at)`。
4. 并发验证：多 worker `FOR UPDATE SKIP LOCKED` 认领、租约过期重领、崩溃恢复。

规则：迁移与应用同 PR、只前进、生产前演练；禁止跨库外键或 Join。
