# persona-state 模块协作约束

本文件在仓库根 `AGENTS.md` 之上叠加，**只加严，不放宽**。

## 1. 职责边界

- 拥有：身份层版本、适应层、身份变更提案、经历日志、以及独占的 `persona_state` PostgreSQL 库。
- 不拥有：记忆图（`memory-graph`）、对话编排（`reasoning-orchestrator`）、巩固队列（`async-consolidator`）。
- 禁止其他模块直连本库；跨模块只走版本化能力或事件。

## 2. 不可破坏的规则

1. **身份层不可变**：已发布的身份版本不得原地修改；回滚是创建新版本并引用目标版本，历史仍可追溯。
2. **适应层有界**：单次增量 ≤ `maxDelta`，滚动窗口累计漂移 ≤ `maxDrift`；超限返回 409/422，不得静默截断。
3. **乐观锁**：适应层更新必须带 `expectedVersion`；版本不匹配返回 409，禁止后写覆盖。
4. **提案状态机**：`pending → approved | rejected` 单向；已审结提案不得再次审结。
5. **租户可信**：`tenantId` 只来自 `Identity`；请求体携带租户必须 422。
6. **不记录敏感原文**：日志/事件/指标不写身份叙事全文、经历摘要原文或凭据；事件只带版本号、ID、状态。
7. **数据隔离**：独立数据库与角色；所有查询强制租户过滤；迁移只由本模块执行。

## 3. 当前实现状态

- **已实现（内存存储）**：身份读取/新版本/回滚、适应层读取/有界更新、提案创建/列表/审批。
  身份层只追加；回滚创建新版本并保留历史；提案 `pending → approved | rejected` 单向，批准时才生成新版本。
- **已声明未实现**：经历日志读取/追加，返回 `501 PERSONA_STATE_FEATURE_NOT_IMPLEMENTED`。
- **未验证**：PostgreSQL 持久化、RLS、迁移、并发压力与 P95 门槛；当前为进程内存储与 `asyncio.Lock` 串行化。
- 不得把内存实现描述为生产可用，也不得声明事件已通过真实 outbox 投递（当前走进程内事件总线）。
- 单元/契约/就绪测试可运行；PostgreSQL 集成测试需 Docker，当前环境不可用。

## 3.1 模型发起的修改

- 模型只能通过编排器的隐藏标记触发：`<persona_update>` → 适应层能力，`<persona_proposal>` → 提案能力。
- 模型**永远不能**直接调用身份版本创建；身份层变更必须经人工/审批入口。
- 提案 `changes` 必须是完整快照（`traits[]` + 可选 `narrative`），创建时校验。

## 4. 命令

```bash
make install
make test-module M=persona-state
make contracts
make validate
make run-persona-state
```

## 5. 评审关注点

- 身份变更是否经过提案审批，还是绕过直接写版本？
- 适应层漂移上限是否在并发下仍成立？
- 回滚是否保留完整历史，事件是否可重放？
- 经历日志的保留期与删除是否可审计？
