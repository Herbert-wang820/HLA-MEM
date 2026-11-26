# 契约对齐与设计决策（ADR-000）

> **状态**：已采纳（阶段 0）  
> **输入**：《HLM-MEM开发计划》v1.1、《模块开发契约》v2.0  
> **用途**：解决两份输入文档在命名、职责、数据边界与验收口径上的差异；后续实现以本文件归一后的结论为准。  
> **变更方式**：新增决策追加 ADR 编号；修改既有结论必须评审并同步 `docs/architecture.md`、受影响模块的 `DESIGN.md` 与 `contracts/`。

## 1. 文档关系与效力

| 维度 | 《模块开发契约》v2.0 | 《HLM-MEM开发计划》v1.1 |
| --- | --- | --- |
| 定位 | 模块**如何治理**：目录、清单、接口、事件、数据、安全、验收 | 系统**做什么、何时做**：架构、技术选型、阶段、量化门槛 |
| 效力 | 治理规则冲突时以契约为准 | 业务目标与量化指标冲突时以计划为准 |
| 强制项 | 模块清单、契约文件、授权、数据所有权、测试 | 阶段里程碑、延迟/规模/人格/巩固约束 |

**项目标识**：仓库与项目统一为 **HLA-MEM**；计划文件名写作 `HLM-MEM开发计划.md`，视为笔误。原始输入文件不重命名，避免破坏外部引用。

**阶段 0 的“契约通过”口径**：`module.yaml` 通过 Schema 与语义校验；能力/事件/权限/菜单命名符合契约；每个模块可独立构建与测试；OpenAPI 与实现无漂移。业务端点允许返回 `501`，但必须显式标注“仅声明”。

## 2. 模块标识归一

计划中的 `orchestrator`、`memory`、`persona`、`consolidator` 是简称。仓库内统一使用下列**完整模块 ID**；能力、事件、权限的 module 段一律使用完整 ID（允许连字符），避免简称与模块 ID 两套命名长期并存。

| 模块 ID | 计划简称 | 中文名 | 类型 | Python 包 / 前端目录 | 本地端口 | 入口 |
| --- | --- | --- | --- | --- | --- | --- |
| `reasoning-orchestrator` | orchestrator | 推理编排器 | backend | `hla_orchestrator` | 8081 | `/api/reasoning-orchestrator/v1` |
| `memory-graph` | memory | 记忆图 | backend | `hla_memory_graph` | 8082 | `/api/memory-graph/v1` |
| `persona-state` | persona | 人格状态 | backend | `hla_persona_state` | 8083 | `/api/persona-state/v1` |
| `async-consolidator` | consolidator | 异步巩固器 | backend | `hla_consolidator` | 8084 | `/api/async-consolidator/v1` |
| `conversation-web` | conversation | 对话前端 | frontend | `web/` | 4173 | `/conversation` |
| `admin-web` | admin | 管理前端 | frontend | `web/` | 4173 | `/admin` |

**前端同源**：`conversation-web` 与 `admin-web` 由同一个 Web 服务在 4173 提供，路径分别为 `/conversation/` 与 `/admin/`；开发态 Vite 仍可分别用 4173/4174。

## 3. 能力、事件、权限命名归一

### 3.1 规则

- 能力：`{module-id}.{domain}.{action}.v{major}`，如 `memory-graph.episode.retrieve.v1`。
- **宿主命名空间例外**：契约与计划都使用 `host.config.v1`（仅两段）。为保留已发布名称，`host.*` 允许 `host.{domain}.v{major}`；业务模块仍必须是三段。该例外仅适用于宿主基础能力。
- **复合动作**：`action` 允许用点号连接的多段动词（如 `persona-state.identity.version.create.v1`），用于表达“创建版本”这类动词+名词语义；`module` 与 `domain` 仍必须是单段，且动作至少一段。
- 事件：`{module-id}.{aggregate}.{past-tense}.v{major}`，如 `memory-graph.coactivation.recorded.v1`。
- 权限：`{module-id}.{resource}.{action}`，如 `memory-graph.episode.read`。
- module 段允许 `[a-z][a-z0-9-]*`；domain/action 使用 `[a-z][a-z0-9]*`；事件 aggregate 允许连字符，past-tense 允许连字符（如 `rolled-back`）。

### 3.2 计划中的简写映射

| 计划原文 | 归一后 | 说明 |
| --- | --- | --- |
| `memory.retrieve.v1` | `memory-graph.episode.retrieve.v1` | 原写法只有两段，不符合能力格式；补 module 全名与 domain |
| `co_activated_pairs` | `memory-graph.coactivation.recorded.v1` | 作为事件类型；载荷字段仍保留 `pairs` |
| `turn.processed` | `reasoning-orchestrator.turn.processed.v1` | 补 module 段 |
| `memory.admin.*` | `memory-graph.admin.*` | 权限 module 段用完整 ID |
| `persona.admin.*` | `persona-state.admin.*` | 同上 |
| `host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1` | 不变 | 均为契约原文；`host.config.v1` 是两段，按宿主命名空间例外保留 |

### 3.3 能力清单（v1）

| 模块 | 能力 | 权限 | 说明 |
| --- | --- | --- | --- |
| memory-graph | `memory-graph.episode.write.v1` | `memory-graph.episode.write` | 写入不可变情景节点 |
| memory-graph | `memory-graph.episode.read.v1` | `memory-graph.episode.read` | 读取单个情景 |
| memory-graph | `memory-graph.episode.retract.v1` | `memory-graph.episode.write` | 追加更正/撤回标记，不改原文 |
| memory-graph | `memory-graph.episode.retrieve.v1` | `memory-graph.episode.read` | 双路径检索（语义 + 扩散） |
| memory-graph | `memory-graph.retrieval.read.v1` | `memory-graph.retrieval.read` | 检索审计记录 |
| memory-graph | `memory-graph.consolidation.apply.v1` | `memory-graph.consolidation.write` | 应用共激活边权/遗忘/蒸馏批次（巩固器调用） |
| memory-graph | `memory-graph.graph.read.v1` | `memory-graph.admin.read` | 管理端受限只读图查询，不透传原始 Cypher |
| persona-state | `persona-state.identity.read.v1` | `persona-state.identity.read` | 读取当前身份层与只读摘要 |
| persona-state | `persona-state.identity.version.create.v1` | `persona-state.identity.write` | 新建身份版本（人工/审批后） |
| persona-state | `persona-state.identity.rollback.v1` | `persona-state.identity.rollback` | 回滚到历史版本 |
| persona-state | `persona-state.adaptation.read.v1` | `persona-state.adaptation.read` | 读取适应层 |
| persona-state | `persona-state.adaptation.update.v1` | `persona-state.adaptation.write` | 有界适应层更新（巩固器调用） |
| persona-state | `persona-state.proposal.create.v1` | `persona-state.proposal.create` | 创建身份变更 proposal |
| persona-state | `persona-state.proposal.read.v1` | `persona-state.proposal.read` | 读取身份变更 proposal |
| persona-state | `persona-state.proposal.review.v1` | `persona-state.proposal.review` | 审批/拒绝 proposal |
| persona-state | `persona-state.experience.append.v1` | `persona-state.experience.append` | 追加经历日志 |
| persona-state | `persona-state.experience.read.v1` | `persona-state.experience.read` | 读取经历时间线 |
| reasoning-orchestrator | `reasoning-orchestrator.turn.process.v1` | `reasoning-orchestrator.turn.create` | 处理一个对话回合（SSE） |
| reasoning-orchestrator | `reasoning-orchestrator.turn.read.v1` | `reasoning-orchestrator.turn.read` | 回合状态/结果 |
| reasoning-orchestrator | `reasoning-orchestrator.audit.read.v1` | `reasoning-orchestrator.audit.read` | 回合检索审计回放 |
| reasoning-orchestrator | `reasoning-orchestrator.gate.configure.v1` | `reasoning-orchestrator.admin.write` | 门控阈值/校准配置 |
| reasoning-orchestrator | `reasoning-orchestrator.llm.configure.v1` | `reasoning-orchestrator.admin.write` | 读取/保存大模型配置（密钥只写不读） |
| async-consolidator | `async-consolidator.job.enqueue.v1` | `async-consolidator.job.create` | 入队巩固作业 |
| async-consolidator | `async-consolidator.job.read.v1` | `async-consolidator.job.read` | 作业状态查询 |
| async-consolidator | `async-consolidator.job.retry.v1` | `async-consolidator.job.retry` | 重试失败作业 |
| async-consolidator | `async-consolidator.deadletter.read.v1` | `async-consolidator.deadletter.read` | 死信查询 |
| async-consolidator | `async-consolidator.deadletter.replay.v1` | `async-consolidator.deadletter.replay` | 死信重放 |
| async-consolidator | `async-consolidator.backlog.read.v1` | `async-consolidator.admin.read` | 积压/队列健康 |

前端不提供后端能力；`conversation-web` 只消费 `reasoning-orchestrator.turn.process.v1`，`admin-web` 只消费各模块的只读/审批类能力。

### 3.4 事件清单（v1）

| 事件 | 触发 | 载荷要点（不含原文/敏感内容） |
| --- | --- | --- |
| `memory-graph.episode.written.v1` | 情景写入成功提交后 | `episodeId`、`sessionId`、`occurredAt`、`contentHash` |
| `memory-graph.episode.retracted.v1` | 追加撤回标记后 | `episodeId`、`retractedAt`、`reasonCode` |
| `memory-graph.coactivation.recorded.v1` | 检索命中候选形成共激活批次 | `batchId`、`retrievalId`、`pairs[]`、`pairCount` |
| `persona-state.identity.versioned.v1` | 新身份版本提交 | `identityId`、`version`、`previousVersion`、`reasonCode` |
| `persona-state.identity.rolled-back.v1` | 回滚完成 | `identityId`、`version`、`targetVersion`、`reasonCode` |
| `persona-state.adaptation.updated.v1` | 适应层有界更新提交 | `identityId`、`version`、`jobId`、`applied[]`、`maxStep` |
| `persona-state.proposal.created.v1` | proposal 创建 | `proposalId`、`identityId`、`status` |
| `persona-state.proposal.reviewed.v1` | proposal 审批 | `proposalId`、`decision`、`reviewerSubject` |
| `persona-state.experience.appended.v1` | 经历日志追加 | `experienceId`、`kind`、`occurredAt` |
| `reasoning-orchestrator.turn.processed.v1` | 回合完成（含降级完成） | `turnId`、`sessionId`、`path`、`gateDecision`、`latencyMs`、`degradedFlags`、引用 ID |
| `reasoning-orchestrator.turn.degraded.v1` | 回合发生降级 | `turnId`、`reasons[]` |
| `async-consolidator.job.completed.v1` | 作业成功 | `jobId`、`jobType`、`idempotencyKey`、`durationMs`、`attempts` |
| `async-consolidator.job.failed.v1` | 作业失败（可重试/永久） | `jobId`、`jobType`、`attempts`、`errorCode`、`retryable` |
| `async-consolidator.job.deadlettered.v1` | 进入死信 | `jobId`、`deadLetterId`、`errorCode` |
| `async-consolidator.edge.reinforced.v1` | 共激活边权批量应用 | `batchId`、`pairCount`、`appliedCount` |
| `async-consolidator.hub.distilled.v1` | 枢纽蒸馏完成 | `hubId`、`clusterId`、`memberCount` |

事件载荷只携带引用 ID 与元数据；记忆原文、人格内容、经历正文不进入通用事件总线。消费者按事件 `id` 去重，处理幂等。

## 4. 职责边界冲突消解

### 4.1 “orchestrator 是唯一同时接触 memory-graph 和 persona-state 的服务”

计划 0.1 的表述与以下事实冲突：

- `async-consolidator` 需要写回边权（`memory-graph`）并提交适应层更新/proposal（`persona-state`）。
- `admin-web` 需要调用 `memory-graph` 与 `persona-state` 的管理接口。

**归一结论**：该约束限定的是**对话回合的运行时路径**——只有 `reasoning-orchestrator` 在同一回合中同步调用二者，负责门控、检索、人格快照、提示组装与生成。异步巩固与管理端是两类显式例外：

| 调用方 | 调用性质 | 允许能力 | 禁止 |
| --- | --- | --- | --- |
| reasoning-orchestrator | 回合内同步 | 检索、人格只读、回合审计、作业入队 | 直写身份层；直连存储 |
| async-consolidator | 异步作业 | 边权/遗忘/蒸馏写入、适应层有界更新、proposal 创建 | 写身份层；绕过 proposal 流程 |
| admin-web | 管理端只读/审批 | `*.admin.*` / 审批类能力 | 直连图库/人格库；动态 Cypher 透传；绕过后端最终校验 |
| conversation-web | 对话端 | 仅 orchestrator 的回合能力 | 直连 memory-graph/persona-state |

### 4.2 身份层不可自动写入

`async-consolidator` 只能更新**适应层**并创建**proposal**；身份层的新版本必须经 `persona-state.identity.version.create.v1`（人工/审批流）产生。任何“自动写身份层”的实现都视为违反计划 2.3 与契约安全原则。

### 4.2.1 模型可发起的人格修改（已采纳）

模型不允许直接调用 persona-state 的写能力。需要修改人格时，模型在回复文本中输出隐藏标记，由编排器剥离并转为能力调用：

| 标记 | 能力 | 写身份层？ | 约束 |
| --- | --- | --- | --- |
| `<persona_update>` | `persona-state.adaptation.update.v1` | 否 | 单维 `|δ| ≤ 0.15`、单轮 ≤4 维、窗口漂移 ≤0.30、`expectedVersion` 乐观锁 |
| `<persona_proposal>` | `persona-state.proposal.create.v1` | 否（只创建 `pending` 提案） | 完整 `traits[]` 快照；需 `proposal.review` 审批后才生成版本 |

- 契约文件：`modules/reasoning-orchestrator/contracts/persona-actions.v1.yaml`，在 `module.yaml` 的 `contracts.personaActions` 登记。
- 该通道仅扩展“适应层可被模型有界调整、身份层可被模型提议”的授权边界，**不改变 4.2 的身份层不可自动写入**。
- 管理端直接编辑身份层仍走 `identity.version.create.v1`（需 `identity.write`），与模型提案是两条独立路径。

### 4.3 管理端能力命名

管理端只读图查询使用 `memory-graph.graph.read.v1`，请求体是**结构化查询**（节点类型、过滤条件、深度、上限），不接受原始 Cypher。人格管理复用 `persona-state.*` 的读写/回滚/审批能力，额外要求调用方具备对应 `*.admin.*` 权限（由目标模块在服务端校验）。前端菜单权限只控制可见性，不构成授权。

## 5. 数据所有权与隔离

| 实体 | 所属模块 | 权威数据 | 对外读取 | 产生事件 |
| --- | --- | ---: | --- | --- |
| Episode（情景） | memory-graph | 是 | API | `episode.written/retracted` |
| Concept（概念） | memory-graph | 是 | API | `hub.distilled`（由巩固器触发） |
| CO_ACTIVATED 边 | memory-graph | 是 | API（审计/图查询） | `coactivation.recorded` |
| 向量索引 | memory-graph | 否（可重建派生） | 内部 | — |
| RetrievalAudit（检索候选/路径） | memory-graph | 是 | API | — |
| PersonaIdentity（身份层版本） | persona-state | 是 | API | `identity.versioned/rolled-back` |
| PersonaAdaptation（适应层） | persona-state | 是 | API | `adaptation.updated` |
| ExperienceLog（经历日志） | persona-state | 是（只追加） | API | `experience.appended` |
| IdentityProposal | persona-state | 是 | API | `proposal.created/reviewed` |
| ConsolidationJob / DeadLetter | async-consolidator | 是 | API | `job.*` |
| Turn / TurnAudit / GateDecision | reasoning-orchestrator | 是 | API | `turn.processed/degraded` |
| 前端会话与视图状态 | 各前端 | 否 | 浏览器本地 | — |

**物理隔离**：

- `memory-graph` 使用 FalkorDB（图 + 原生 HNSW）；`tenantId` 作为节点/边属性并建索引，不跨租户共享可变结果缓存。
- `persona-state` 使用 PostgreSQL 数据库 `persona_state` 与独立角色 `persona_state_app`。
- `async-consolidator` 使用 PostgreSQL 数据库 `consolidator` 与独立角色 `consolidator_app`，作业表与死信表属于巩固器，不放进人格库。
- 三个存储不共享连接池、事务或迁移目录；`docker-compose.yml` 用两个独立 PostgreSQL 实例强化该边界。
- 跨模块只通过能力或事件同步；投影必须标注来源模块、源版本、同步时间，缺失即视为无效。

## 6. 接口、数据与治理补充约定

### 6.1 路径与端点

- 业务接口：`/api/{module-id}/v1/{resources}`。
- 内部管理接口：`/internal/v1/{resources}`；`internal` 不构成免鉴权理由。
- 运维端点：`/internal/health`、`/internal/ready`、`/internal/metrics`，无业务数据、不依赖用户会话。
- 前端入口：`webBasePath`（`/conversation`、`/admin`），由前端静态服务器提供同名路由；这是对契约 `entrypoints` 的最小扩展，已在 `schemas/module.schema.json` 中声明。

### 6.2 ID、时间与分页

- 资源 ID 使用 UUIDv4（不承载业务顺序）；事件 ID 使用 UUIDv4。
- 时间统一 UTC、RFC 3339（`...Z`）；数据库列使用 `timestamptz`。
- 列表统一使用**游标分页**：`cursor`（不透明 base64）+ `limit`（默认 20，最大 100），返回 `items`、`nextCursor`、`hasMore`。同一模块不混用 page/pageSize。
- 检索候选合并后返回 Top-K，`K ≤ 50`；内部 `semanticTopK`/`spreadingTopK` 各自有上限。

### 6.3 幂等与并发

- 非幂等动作必须支持 `Idempotency-Key`：写入情景、处理回合、入队作业、创建身份版本、创建 proposal、死信重放。
- 幂等记录作用域：调用主体 + 租户 + 操作 + 请求摘要；默认保留 24 小时；同 key 不同摘要返回 `409 {MODULE}_IDEMPOTENCY_CONFLICT`。
- 身份层/适应层更新使用 `expectedVersion` 乐观锁；提交过期版本返回 `409 {MODULE}_VERSION_CONFLICT`。
- 共激活事件消费按 `pairId + batchId` 去重；边权增量由 `async-consolidator` 异步应用，检索路径不执行同步写。

### 6.4 错误码

格式 `{MODULE}_{DOMAIN}_{REASON}`。模块前缀中的连字符转下划线（`memory-graph` → `MEMORY_GRAPH`）。认证失败由宿主适配层返回 `HOST_AUTH_UNAUTHENTICATED`（401），已认证但无权返回 `HOST_AUTH_FORBIDDEN`（403）。通用模块错误：

| HTTP | 错误码示例 | 场景 |
| ---: | --- | --- |
| 400 | `MEMORY_GRAPH_REQUEST_INVALID` | 语义非法但通过结构校验 |
| 401 | `HOST_AUTH_UNAUTHENTICATED` | 缺少/无效身份 |
| 403 | `HOST_AUTH_FORBIDDEN` | 权限不足、未知权限 |
| 404 | `MEMORY_GRAPH_EPISODE_NOT_FOUND` | 资源不存在或不可见 |
| 409 | `PERSONA_STATE_VERSION_CONFLICT` | 乐观锁冲突 |
| 409 | `ASYNC_CONSOLIDATOR_IDEMPOTENCY_CONFLICT` | 幂等键摘要冲突 |
| 413 | `{MODULE}_PAYLOAD_TOO_LARGE` | 请求体超限 |
| 422 | `{MODULE}_REQUEST_VALIDATION_FAILED` | 结构校验失败 |
| 500 | `{MODULE}_INTERNAL_ERROR` | 未预期异常（不返回堆栈） |
| 501 | `{MODULE}_FEATURE_NOT_IMPLEMENTED` | 阶段 0 契约占位 |
| 503 | `{MODULE}_DEPENDENCY_UNAVAILABLE` | 依赖故障且无法降级 |
| 504 | `{MODULE}_REQUEST_TIMEOUT` | 请求超时 |

### 6.5 请求治理与限制

| 项 | 值 | 说明 |
| --- | --- | --- |
| 最大请求体 | 1 MiB（可配置） | 超出返回 413；网关层同样限制 |
| 请求超时 | 30s（可配置） | SSE 回合端点豁免，改用 120s 空闲超时 |
| 分页上限 | 100 | `limit` 超过上限按 422 处理 |
| 检索 Top-K 硬上限 | 50 | 超过按 422 处理 |
| 图查询节点上限 | 500 | 管理端只读查询 |
| 幂等保留 | 24h | 可配置 |
| `X-Request-Id` | 透传或生成 | 响应头回传，错误体带 `requestId` |

### 6.6 OpenAPI 的生成方式（决策）

契约要求 `contracts/openapi.yaml` 与实现一致。为降低手工维护漂移，采用：

1. Pydantic 请求/响应模型、FastAPI 路由声明（含 `x-capability`、`x-permission`、错误响应）是**契约源**，在评审中先行提交。
2. `make contracts` 从应用导出 `contracts/openapi.yaml` 并提交。
3. `make contracts-check` 在 CI 中重新导出并逐字节比对，漂移即失败。

这不是“先写 YAML 再写代码”的字面流程，但保留了契约评审与漂移检测两个关键性质；若后续需要外部契约优先，可切换为手写 YAML + 响应校验，能力命名与错误模型不变。

### 6.7 事件 Schema 的形态

`contracts/events/{type}.schema.json` 约束事件的 `type` 与 `data` 两段；完整信封（`specVersion/id/source/subject/time/tenantId/...`）由 `schemas/event-envelope.schema.json` 统一约束。校验器分别验证信封与 `type+data`，避免每个事件重复信封定义。

## 7. 技术选型落地与当前环境限制

| 计划选型 | 阶段 0 落地 | 状态 |
| --- | --- | --- |
| Python 3.12 + FastAPI + Pydantic v2 | 3.12.3 + FastAPI 0.162 + Pydantic 2.14 | 已实现 |
| FalkorDB 4.16 / Neo4j 5.26 二选一 | 定义 `GraphStore` 端口；未接真实引擎；不提交引擎特定 Cypher | 仅声明；**本机无 Docker，未验证** |
| 图库原生 HNSW | 检索端口预留 `vector_index` 适配；阶段 1 压测后定 | 仅声明 |
| BGE-M3（1024 维） | 定义 `Embedder` 端口；确定性替身用于测试 | 仅声明；模型未下载 |
| MemReranker-0.6B | 定义 `Reranker` 端口；测试用确定性排序替身 | 仅声明；模型未下载 |
| System-One 轻量门控 | 定义 `Gate` 端口；规则替身 | 仅声明 |
| PostgreSQL 16 | 迁移脚本与 Compose 声明；未启动实例 | 未验证 |
| 事件总线 | `hla_host` 内存适配器 + Outbox 端口 | 已实现（本地适配） |
| 巩固作业队列 | 阶段 0 仅定义作业能力契约；PG `SKIP LOCKED` 在阶段 3 实现 | 仅声明 |
| SSE | orchestrator 回合端点声明 `text/event-stream` | 仅声明 |
| React + Vite | 两个前端骨架可构建/测试；NVL 图可视化留到阶段 4 | 部分实现 |
| OpenTelemetry + Prometheus | Prometheus 文本指标 + 结构化 JSON 日志；OTel 导出器未接 | 部分实现 |

**环境阻塞**：当前开发机没有 Docker，无法运行 FalkorDB/PostgreSQL 容器，因此阶段 1 的“容器化图存储集成测试”和计划 6.3 的“图引擎摄入压测”无法在本机完成；需要具备 Docker 或可达数据库的环境后再验收，不能以内存替身替代该验收。

## 8. 未决事项（需产品/平台确认）

| 编号 | 事项 | 当前处理 | 影响阶段 |
| --- | --- | --- | --- |
| O-1 | FalkorDB vs Neo4j 最终选型 | 端口抽象；阶段 1 批量摄入压测为准 | 阶段 1 |
| O-2 | BGE-M3 / MemReranker-0.6B 权重与许可 | 端口 + 替身；不下载 | 阶段 1–2 |
| O-3 | System-One 分类器来源（`system1` 类库/自训） | 规则门控先行，分类器可替换 | 阶段 2 |
| O-4 | LLM 供应商与对话/巩固配额隔离 | 配置外置；阶段 2 前完成 | 阶段 2 |
| O-5 | 宿主真实认证/配置/事件总线 | 本地适配器，`module.yaml` 声明为临时适配 | 阶段 4 前 |
| O-6 | `adaptation_step_max`、`N_consistency`、`T_fade`、`w_min`、`hub_degree_min`、`hub_cluster_min` 的具体值 | 文档给默认占位，配置读取；需产品校准 | 阶段 1/3 |
| O-7 | 经历日志与审计保留期限、导出格式 | 只追加；保留策略待定 | 阶段 3–4 |
| O-8 | 管理端权限与宿主角色的映射 | `*.admin.*` 独立权限；映射待宿主接入 | 阶段 4 |
| O-9 | 多租户图分区策略（属性过滤 vs 每租户独立图） | 阶段 1 用 `tenantId` 属性 + 索引，压测后评估 | 阶段 1 |

## 9. 输入文档问题清单（梳理记录）

| # | 位置 | 问题 | 处理 |
| ---: | --- | --- | --- |
| 1 | 计划文件名 | `HLM-MEM` 与仓库 `HLA-MEM` 不一致 | 统一 HLA-MEM，保留原文件名 |
| 2 | 计划 0.2 / 0.4 | `memory.retrieve.v1` 只有两段，违反能力格式 | 归一为 `memory-graph.episode.retrieve.v1` |
| 3 | 计划 1/阶段 1 | `co_activated_pairs` 不是事件类型格式 | 归一为 `memory-graph.coactivation.recorded.v1` |
| 4 | 计划 2/阶段 2 | `turn.processed` 缺 module 段 | 归一为 `reasoning-orchestrator.turn.processed.v1` |
| 5 | 计划 2.5 | `memory.admin.*`/`persona.admin.*` 与模块 ID 不一致 | 归一为完整模块 ID 前缀 |
| 6 | 计划 0.1 | “orchestrator 唯一同时接触”与巩固器/管理端调用冲突 | 限定为“对话回合运行时路径”，列显式例外 |
| 7 | 计划 0.1 | 文字说 6 模块，图中箭头/框数量易误读 | 固定 4 后端 + 2 前端，见第 2 节 |
| 8 | 计划 0.2 | FalkorDB/Neo4j 未最终定 | 端口抽象 + 阶段 1 压测门槛 |
| 9 | 计划阶段 0 | 契约交付物写“openapi.yaml（或能力声明）” | 后端统一提供 OpenAPI；前端提供菜单/权限 |
| 10 | 契约第 4 章 | 未给出 `module.yaml` 的 Schema | 新增 `schemas/module.schema.json` 并校验 |
| 11 | 契约第 11 章 | 前端也要求健康/就绪/指标 | 前端增加 Node 静态服务器提供运维端点 |
| 12 | 契约 6.1 | 只有 `apiBasePath`，未覆盖纯前端模块 | 增加 `webBasePath` 扩展 |
| 13 | 契约第 13 章 | 未规定初始模块版本 | 阶段 0 统一 `0.1.0` |
| 14 | 计划 0.1 / 2.4 | 人格库与作业队列都可用 PG，易共享实例 | 独立数据库/角色；Compose 两个 PG 实例 |
| 15 | 计划 1 | 16 周无起始日期 | 以 2026-11-10 为 T0，里程碑相对周次 |
| 16 | 计划 2 | 量化门槛缺测量口径 | 阶段 1/2 建基准脚本，阈值写入 DESIGN |
| 17 | 计划 2.2 | 遗忘/蒸馏参数无具体值 | 配置化 + 默认占位，待产品校准 |
| 18 | 计划阶段 3 | 巩固“定时/空闲触发”未定实现 | 队列语义先定，调度器阶段 3 实现 |
| 19 | 契约 6.3 | 幂等键作用域未细化 | 主体+租户+操作+请求摘要，24h |
| 20 | 契约 7 | 事件信封与事件数据 Schema 关系未说明 | 信封统一 + 每事件 `type+data` Schema |
| 21 | 契约 5.1 / 6.1 | `host.config.v1` 只有两段，与三段能力格式冲突 | 保留原名；`host.*` 允许两段，业务能力仍三段；Schema 与校验器同步例外 |
| 22 | 契约 5.1 | `action` 单段无法表达 `identity.version.create` 这类动词+名词 | 允许点号连接的复合动作，module/domain 仍单段；Schema 与校验器同步 |
