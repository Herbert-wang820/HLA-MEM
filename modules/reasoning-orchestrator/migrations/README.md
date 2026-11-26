# 迁移说明

阶段 0 没有持久化实现，因此没有可执行迁移。

阶段 2 计划：

- 若采用自有 PostgreSQL：`migrations/0001_init.sql` 创建 `turn`、`turn_audit`、`gate_config`、`outbox`。
- 若回合状态仅为短生命周期：使用 Redis/内存并在 `DESIGN.md` 记录取舍，不建库。
- 索引：`(tenant_id, created_at desc)`；审计按 `turn_id` 唯一。
- 审计保留期与租户删除流程必须可执行、可验证。

规则：迁移与应用同 PR、只前进、生产前影子库演练。
