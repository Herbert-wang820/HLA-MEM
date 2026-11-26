# 迁移说明

阶段 0 没有持久化实现，因此没有可执行迁移。

阶段 2 计划（PostgreSQL，独立库 `persona_state`）：

1. `0001_init.sql`：`identity_version`、`adaptation`、`adaptation_ledger`、`proposal`、`experience`、`outbox`。
2. 约束：`(tenant_id, version)` 唯一；`proposal.status` 检查；`experience` 按 `occurred_at` 分区或归档。
3. 索引：所有表以 `tenant_id` 为前缀；经历按 `(tenant_id, occurred_at desc)`。
4. RLS：阶段 2 评估并默认启用租户隔离策略。

规则：

- 迁移只前进；已发布脚本不改写，修正用新脚本。
- 与应用代码同 PR 提交，包含回滚说明。
- 生产执行前在影子库演练并记录耗时/锁影响。
