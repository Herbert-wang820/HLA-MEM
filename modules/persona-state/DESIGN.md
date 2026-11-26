# persona-state 设计说明

> 状态：**最小实现**（进程内存储，非 PostgreSQL）；经历日志仍为 501。  
> 权威来源：`module.yaml`、`contracts/openapi.yaml`、`contracts/events/*`。

## 1. 定位

人格状态模块维护“我是谁”的稳定身份层与“当前状态如何”的有界适应层，并提供身份变更提案与经历日志。它不负责检索记忆或生成回复；编排器通过只读能力获取人格快照。

## 2. 领域模型（当前为进程内实现，阶段 2 迁移 PostgreSQL）

| 实体 | 关键字段 | 约束 |
| --- | --- | --- |
| `IdentityVersion` | `version`、`tenantId`、`traits`、`narrative`、`effectiveFrom`、`createdBy`、`changeReason` | 追加写；`(tenantId, version)` 唯一；版本号单调递增 |
| `Adaptation` | `tenantId`、`version`、`values`、`updatedAt`、`drift` | 单行乐观锁；有界更新 |
| `AdaptationLedger` | `tenantId`、`delta`、`reason`、`occurredAt` | 用于窗口漂移计算与审计 |
| `Proposal` | `proposalId`、`status`、`proposer`、`changes`、`rationale`、`reviewer` | 状态单向；审结后不可变 |
| `Experience` | `experienceId`、`turnId`、`summary`、`outcome`、`occurredAt` | 追加写；按保留期归档 |

**身份层 vs 适应层**：身份层是低频、需审批的“长期人格”；适应层是高频、有界的“短期状态”。两者分离，避免一次对话直接改写人格。

## 3. 身份版本与回滚

- 创建版本：校验 traits 数量/置信度，写入新版本，发布 `persona-state.identity.versioned.v1`。
- 回滚：读取 `targetVersion`，**创建新版本**复制其 traits/narrative，并记录 `rolledBackFrom`；不删除中间版本。发布 `persona-state.identity.rolled-back.v1`。
- 并发（目标）：以 `(tenantId, version)` 唯一约束保证；当前由进程内 `asyncio.Lock` 串行化，冲突返回 409。
- 审批：高风险变更必须先走提案；当前已实现——批准提案时由应用层在同一锁内创建新版本。

## 4. 有界适应层

```
delta 校验：|δ| ≤ maxDelta
窗口漂移：Σ|δ| (windowHours) ≤ maxDrift
写入：版本号必须等于 expectedVersion（当前在进程内锁内比较；目标为 SQL 条件更新）
```

- 超限：422（单次过大）或 409（漂移/版本冲突），附当前 `drift` 与剩余额度。
- 目标形态：更新与 ledger、outbox 同事务；当前为进程内单锁串行化 + 提交后发事件。
- 漂移衰减：窗口外增量不再计入；不自动“回弹”，避免隐式改写。

## 5. 提案

- 创建：`pending`，记录提案人、理由、变更内容与证据 `episodeIds`（≤50）。
- 审批：`approve` 生成新身份版本并置 `approved`；`reject` 仅置状态并记录备注。
- 权限分离：创建需 `proposal.create`，审批需 `proposal.review`；管理端另有 `admin.*`。
- 提案内容可能含敏感信息：列表默认只返回摘要，详情按权限读取（阶段 2 细化）。

## 6. 经历日志

- 追加写，按 `occurredAt` 倒序游标分页；不提供更新/删除 API，保留期由配置与归档任务处理。
- `summary` 限制 2000 字符，禁止写入完整对话原文；需要原文时只存 `turnId` 引用。
- 发布 `persona-state.experience.appended.v1`。

## 7. API 与能力

| 方法与路径 | 能力 | 权限 |
| --- | --- | --- |
| `GET /api/persona-state/v1/identity` | `persona-state.identity.read.v1` | `persona-state.identity.read` |
| `POST /api/persona-state/v1/identity/versions` | `persona-state.identity.version.create.v1` | `persona-state.identity.write` |
| `POST /api/persona-state/v1/identity/rollback` | `persona-state.identity.rollback.v1` | `persona-state.identity.rollback` |
| `GET /api/persona-state/v1/adaptation` | `persona-state.adaptation.read.v1` | `persona-state.adaptation.read` |
| `PATCH /api/persona-state/v1/adaptation` | `persona-state.adaptation.update.v1` | `persona-state.adaptation.write` |
| `POST /api/persona-state/v1/proposals` | `persona-state.proposal.create.v1` | `persona-state.proposal.create` |
| `GET /api/persona-state/v1/proposals` | `persona-state.proposal.read.v1` | `persona-state.proposal.read` |
| `POST /api/persona-state/v1/proposals/{id}/review` | `persona-state.proposal.review.v1` | `persona-state.proposal.review` |
| `GET /api/persona-state/v1/experiences` | `persona-state.experience.read.v1` | `persona-state.experience.read` |
| `POST /api/persona-state/v1/experiences` | `persona-state.experience.append.v1` | `persona-state.experience.append` |

实现状态：

| 能力 | 状态 |
| --- | --- |
| 身份读取 / 新版本 / 回滚 | 已实现（内存存储；回滚创建新版本，历史保留） |
| 适应层读取 / 有界更新 | 已实现（乐观锁、单次 δ、窗口漂移校验） |
| 提案创建 / 列表 / 审批 | 已实现（批准后由服务端创建身份版本，审结不可重复） |
| 经历日志读取 / 追加 | **未实现**，返回 `501 PERSONA_STATE_FEATURE_NOT_IMPLEMENTED` |

- 写接口均要求 `Idempotency-Key`；提案创建与审批按 `(subject, tenant, operation, key)` 幂等重放。
- 提案列表使用游标分页（`cursor` + `limit ≤100`），按创建时间倒序。
- 提案 `changes` 必须是完整身份快照（`traits[]` + 可选 `narrative`），创建时即校验，避免审批时才发现不可应用。
- 身份变更有两种合法入口：管理端/运营方直接调用 `identity.version.create.v1`；或模型/员工提交提案后由审批人调用 `proposal.review.v1`（批准时生成新版本）。两者都只追加，不原地修改。

### 7.1 模型可发起的人格修改

编排器在回复文本中识别隐藏标记，并转换为下面的能力调用；契约见
`modules/reasoning-orchestrator/contracts/persona-actions.v1.yaml`。

| 模型标记 | persona-state 调用 | 效果 |
| --- | --- | --- |
| `<persona_update>{deltas,reason}</persona_update>` | `persona-state.adaptation.update.v1` | 直接生效，受 δ/漂移/乐观锁约束 |
| `<persona_proposal>{rationale,changes,...}</persona_proposal>` | `persona-state.proposal.create.v1` | 仅创建 `pending` 提案，不产生身份版本 |

编排器必须先剥离标记再向用户输出；不得把标记泄漏到可见文本或 SSE `token` 事件。

## 8. 事件

| 事件 | 触发 | 数据要点 |
| --- | --- | --- |
| `persona-state.identity.versioned.v1` | 新版本提交 | `version/traits?/effectiveFrom`（按 Schema） |
| `persona-state.identity.rolled-back.v1` | 回滚完成 | `fromVersion/toVersion` |
| `persona-state.adaptation.updated.v1` | 适应层提交 | `version/drift` |
| `persona-state.proposal.created.v1` | 提案创建 | `proposalId/status` |
| `persona-state.proposal.reviewed.v1` | 审批完成 | `proposalId/decision` |
| `persona-state.experience.appended.v1` | 经历追加 | `experienceId/turnId/outcome` |

**当前实现**：事件经进程内事件总线发布，仅在 dev 环境启用；没有 outbox、没有重试、没有跨副本投递。
阶段 2 的目标是 outbox + 至少一次投递，消费者按 `event.id` 去重——在此之前不得声称事件可靠。

## 9. 数据所有权与迁移

- 独占 PostgreSQL 数据库 `persona_state` 与角色 `persona_state`；其他模块只有能力调用权。
- `tenantId` 为所有表的首列索引前缀；阶段 2 评估 PostgreSQL RLS 作为纵深防御。
- 迁移脚本放 `migrations/`，只前进不修改历史脚本；生产前影子库演练。
- 不建跨模块外键/视图/Join。

## 10. 依赖与降级

- 必选：`host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`。
- 可选：无。
- 目标约束（阶段 2）：数据库不可用时读返回 503、写快速失败；编排器将 `personaDegraded=true` 并继续，不伪造人格。
- **当前实现无数据库**，因此没有连接失败路径；进程退出即丢失全部状态。

## 11. 非功能目标（阶段 2 验证，当前未验证）

- 身份读取 P95 ≤ 50ms；适应层更新 P95 ≤ 80ms。
- 适应层并发更新无丢失（乐观锁重试 ≤3 次）。
- 提案审批审计完整率 100%。
- 经历日志写入不阻塞对话主路径（由编排器异步追加）。

## 12. 待决问题

- 身份版本保留上限与归档策略。
- 提案详情中的敏感信息分级与脱敏。
- 适应层漂移是否需要“日常回弹”或人工重置入口。
- 多设备/多会话下的适应层合并规则。
