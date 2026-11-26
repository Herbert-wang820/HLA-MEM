# 模块目录（自动生成）

> 由 `make catalog` 从各模块的 `module.yaml` 与 `contracts/` 生成，请勿手工编辑。
> 生成命令：`python tools/render_catalog.py`

## 1. 模块

| 模块 ID | 名称 | 类型 | 版本 | 入口 | 能力数 | 事件数 |
| --- | --- | --- | --- | --- | ---: | ---: |
| `reasoning-orchestrator` | 推理编排器 | backend | 0.1.0 | `/api/reasoning-orchestrator/v1` | 5 | 2 |
| `memory-graph` | 记忆图 | backend | 0.1.0 | `/api/memory-graph/v1` | 7 | 3 |
| `persona-state` | 人格状态 | backend | 0.1.0 | `/api/persona-state/v1` | 10 | 6 |
| `async-consolidator` | 异步巩固器 | backend | 0.1.0 | `/api/async-consolidator/v1` | 6 | 5 |
| `conversation-web` | 对话前端 | frontend | 0.1.0 | `/conversation` | 0 | 0 |
| `admin-web` | 管理前端 | frontend | 0.1.0 | `/admin` | 0 | 0 |

## 2. 能力与端点

| 模块 | 能力 | 权限 | 端点 |
| --- | --- | --- | --- |
| `reasoning-orchestrator` | `reasoning-orchestrator.turn.process.v1` | `reasoning-orchestrator.turn.create` | `POST /api/reasoning-orchestrator/v1/turns` |
| `reasoning-orchestrator` | `reasoning-orchestrator.turn.read.v1` | `reasoning-orchestrator.turn.read` | `GET /api/reasoning-orchestrator/v1/turns/{turn_id}` |
| `reasoning-orchestrator` | `reasoning-orchestrator.audit.read.v1` | `reasoning-orchestrator.audit.read` | `GET /api/reasoning-orchestrator/v1/audits/{turn_id}` |
| `reasoning-orchestrator` | `reasoning-orchestrator.gate.configure.v1` | `reasoning-orchestrator.admin.write` | `PUT /internal/v1/gate/config` |
| `reasoning-orchestrator` | `reasoning-orchestrator.llm.configure.v1` | `reasoning-orchestrator.admin.write` | `GET /internal/v1/llm/config`, `PUT /internal/v1/llm/config` |
| `memory-graph` | `memory-graph.episode.write.v1` | `memory-graph.episode.write` | `POST /api/memory-graph/v1/episodes` |
| `memory-graph` | `memory-graph.episode.read.v1` | `memory-graph.episode.read` | `GET /api/memory-graph/v1/episodes/{episode_id}` |
| `memory-graph` | `memory-graph.episode.retract.v1` | `memory-graph.episode.write` | `POST /api/memory-graph/v1/episodes/{episode_id}/retract` |
| `memory-graph` | `memory-graph.episode.retrieve.v1` | `memory-graph.episode.read` | `POST /api/memory-graph/v1/retrievals` |
| `memory-graph` | `memory-graph.retrieval.read.v1` | `memory-graph.retrieval.read` | `GET /api/memory-graph/v1/retrievals/{retrieval_id}` |
| `memory-graph` | `memory-graph.consolidation.apply.v1` | `memory-graph.consolidation.write` | `POST /internal/v1/consolidation/apply` |
| `memory-graph` | `memory-graph.graph.read.v1` | `memory-graph.admin.read` | `POST /internal/v1/graph/query` |
| `persona-state` | `persona-state.identity.read.v1` | `persona-state.identity.read` | `GET /api/persona-state/v1/identity` |
| `persona-state` | `persona-state.identity.version.create.v1` | `persona-state.identity.write` | `POST /api/persona-state/v1/identity/versions` |
| `persona-state` | `persona-state.identity.rollback.v1` | `persona-state.identity.rollback` | `POST /api/persona-state/v1/identity/rollback` |
| `persona-state` | `persona-state.adaptation.read.v1` | `persona-state.adaptation.read` | `GET /api/persona-state/v1/adaptation` |
| `persona-state` | `persona-state.adaptation.update.v1` | `persona-state.adaptation.write` | `PATCH /api/persona-state/v1/adaptation` |
| `persona-state` | `persona-state.proposal.create.v1` | `persona-state.proposal.create` | `POST /api/persona-state/v1/proposals` |
| `persona-state` | `persona-state.proposal.read.v1` | `persona-state.proposal.read` | `GET /api/persona-state/v1/proposals` |
| `persona-state` | `persona-state.proposal.review.v1` | `persona-state.proposal.review` | `POST /api/persona-state/v1/proposals/{proposal_id}/review` |
| `persona-state` | `persona-state.experience.append.v1` | `persona-state.experience.append` | `POST /api/persona-state/v1/experiences` |
| `persona-state` | `persona-state.experience.read.v1` | `persona-state.experience.read` | `GET /api/persona-state/v1/experiences` |
| `async-consolidator` | `async-consolidator.job.enqueue.v1` | `async-consolidator.job.create` | `POST /api/async-consolidator/v1/jobs` |
| `async-consolidator` | `async-consolidator.job.read.v1` | `async-consolidator.job.read` | `GET /api/async-consolidator/v1/jobs`, `GET /api/async-consolidator/v1/jobs/{job_id}` |
| `async-consolidator` | `async-consolidator.job.retry.v1` | `async-consolidator.job.retry` | `POST /api/async-consolidator/v1/jobs/{job_id}/retry` |
| `async-consolidator` | `async-consolidator.deadletter.read.v1` | `async-consolidator.deadletter.read` | `GET /api/async-consolidator/v1/dead-letters` |
| `async-consolidator` | `async-consolidator.deadletter.replay.v1` | `async-consolidator.deadletter.replay` | `POST /api/async-consolidator/v1/dead-letters/{dead_letter_id}/replay` |
| `async-consolidator` | `async-consolidator.backlog.read.v1` | `async-consolidator.admin.read` | `GET /internal/v1/backlog` |

## 3. 事件

| 事件 | 提供方 | 发布时机 |
| --- | --- | --- |
| `reasoning-orchestrator.turn.processed.v1` | `reasoning-orchestrator` | 回合完成（含降级完成） |
| `reasoning-orchestrator.turn.degraded.v1` | `reasoning-orchestrator` | 回合发生降级 |
| `memory-graph.episode.written.v1` | `memory-graph` | 情景写入成功提交后 |
| `memory-graph.episode.retracted.v1` | `memory-graph` | 追加撤回标记后 |
| `memory-graph.coactivation.recorded.v1` | `memory-graph` | 检索形成共激活批次 |
| `persona-state.identity.versioned.v1` | `persona-state` | 新身份版本提交 |
| `persona-state.identity.rolled-back.v1` | `persona-state` | 身份回滚完成 |
| `persona-state.adaptation.updated.v1` | `persona-state` | 适应层有界更新提交 |
| `persona-state.proposal.created.v1` | `persona-state` | 身份变更提案创建 |
| `persona-state.proposal.reviewed.v1` | `persona-state` | 提案审批完成 |
| `persona-state.experience.appended.v1` | `persona-state` | 经历日志追加 |
| `async-consolidator.job.completed.v1` | `async-consolidator` | 作业成功 |
| `async-consolidator.job.failed.v1` | `async-consolidator` | 作业失败 |
| `async-consolidator.job.deadlettered.v1` | `async-consolidator` | 进入死信 |
| `async-consolidator.edge.reinforced.v1` | `async-consolidator` | 边权批量应用 |
| `async-consolidator.hub.distilled.v1` | `async-consolidator` | 枢纽蒸馏完成 |

## 4. 权限

| 权限 | 所属模块 | 类型 | 说明 |
| --- | --- | --- | --- |
| `reasoning-orchestrator.turn.create` | `reasoning-orchestrator` | write | 创建并处理对话回合 |
| `reasoning-orchestrator.turn.read` | `reasoning-orchestrator` | query | 读取回合状态与结果 |
| `reasoning-orchestrator.audit.read` | `reasoning-orchestrator` | query | 读取回合检索审计 |
| `reasoning-orchestrator.admin.read` | `reasoning-orchestrator` | admin | 编排器管理端只读操作 |
| `reasoning-orchestrator.admin.write` | `reasoning-orchestrator` | admin | 配置门控阈值与校准参数 |
| `memory-graph.episode.read` | `memory-graph` | query | 读取单个情景节点 |
| `memory-graph.episode.write` | `memory-graph` | write | 写入情景节点与追加撤回标记 |
| `memory-graph.retrieval.read` | `memory-graph` | query | 读取双路径检索审计记录 |
| `memory-graph.consolidation.write` | `memory-graph` | write | 应用共激活边权/遗忘/蒸馏批次（巩固器内部调用） |
| `memory-graph.admin.read` | `memory-graph` | admin | 管理端受限只读图查询 |
| `persona-state.identity.read` | `persona-state` | query | 读取身份层与只读身份摘要 |
| `persona-state.identity.write` | `persona-state` | write | 创建新的身份层版本 |
| `persona-state.identity.rollback` | `persona-state` | write | 回滚身份层到历史版本 |
| `persona-state.adaptation.read` | `persona-state` | query | 读取适应层 |
| `persona-state.adaptation.write` | `persona-state` | write | 有界更新适应层 |
| `persona-state.proposal.create` | `persona-state` | write | 创建身份变更提案 |
| `persona-state.proposal.read` | `persona-state` | query | 读取身份变更提案 |
| `persona-state.proposal.review` | `persona-state` | write | 审批或拒绝身份变更提案 |
| `persona-state.experience.append` | `persona-state` | write | 追加经历日志 |
| `persona-state.experience.read` | `persona-state` | query | 读取经历时间线 |
| `persona-state.admin.read` | `persona-state` | admin | 人格管理端只读操作 |
| `persona-state.admin.write` | `persona-state` | admin | 人格管理端写入操作 |
| `async-consolidator.job.create` | `async-consolidator` | write | 入队巩固作业 |
| `async-consolidator.job.read` | `async-consolidator` | query | 查询巩固作业状态 |
| `async-consolidator.job.retry` | `async-consolidator` | write | 重试失败作业 |
| `async-consolidator.deadletter.read` | `async-consolidator` | query | 查询死信 |
| `async-consolidator.deadletter.replay` | `async-consolidator` | write | 重放死信 |
| `async-consolidator.admin.read` | `async-consolidator` | admin | 查询巩固积压与队列健康 |
| `conversation-web.chat.use` | `conversation-web` | write | 使用对话界面 |
| `conversation-web.session.read` | `conversation-web` | query | 读取自己的会话列表 |
| `admin-web.persona.view` | `admin-web` | query | 查看人格编辑器 |
| `admin-web.persona.edit` | `admin-web` | write | 编辑人格（仍需人格模块后端授权） |
| `admin-web.memory.view` | `admin-web` | query | 查看记忆图浏览器 |
| `admin-web.audit.view` | `admin-web` | query | 查看检索审计 |
| `admin-web.consolidation.view` | `admin-web` | query | 查看巩固监控 |
| `admin-web.proposal.review` | `admin-web` | write | 进入身份变更提案审批 |
| `admin-web.llm.manage` | `admin-web` | write | 配置并保存大模型连接参数 |

## 5. 前端菜单

| 模块 | 菜单 ID | 路由 | 权限 | 所需能力 |
| --- | --- | --- | --- | --- |
| `conversation-web` | `conversation` | `/conversation` | `conversation-web.chat.use` | `reasoning-orchestrator.turn.process.v1` |
| `admin-web` | `admin-persona` | `/admin/persona` | `admin-web.persona.view` | `persona-state.identity.read.v1` |
| `admin-web` | `admin-memory` | `/admin/memory` | `admin-web.memory.view` | `memory-graph.graph.read.v1` |
| `admin-web` | `admin-audit` | `/admin/audit` | `admin-web.audit.view` | `reasoning-orchestrator.audit.read.v1` |
| `admin-web` | `admin-consolidation` | `/admin/consolidation` | `admin-web.consolidation.view` | `async-consolidator.backlog.read.v1` |
| `admin-web` | `admin-proposals` | `/admin/proposals` | `admin-web.proposal.review` | `persona-state.proposal.review.v1` |
| `admin-web` | `admin-llm` | `/admin/llm` | `admin-web.llm.manage` | `reasoning-orchestrator.llm.configure.v1` |

## 6. 依赖

| 模块 | 必选（仅宿主） | 可选集成 |
| --- | --- | --- |
| `reasoning-orchestrator` | `host.auth.identity.v1`, `host.config.v1`, `host.event.bus.v1` | `memory-graph.episode.retrieve.v1`, `memory-graph.retrieval.read.v1`, `memory-graph.episode.write.v1`, `persona-state.identity.read.v1`, `persona-state.adaptation.read.v1`, `persona-state.adaptation.update.v1`, `persona-state.proposal.create.v1`, `async-consolidator.job.enqueue.v1` |
| `memory-graph` | `host.auth.identity.v1`, `host.config.v1`, `host.event.bus.v1` | - |
| `persona-state` | `host.auth.identity.v1`, `host.config.v1`, `host.event.bus.v1` | - |
| `async-consolidator` | `host.auth.identity.v1`, `host.config.v1`, `host.event.bus.v1` | `memory-graph.consolidation.apply.v1`, `persona-state.adaptation.update.v1`, `persona-state.proposal.create.v1` |
| `conversation-web` | `host.auth.identity.v1`, `host.config.v1` | `reasoning-orchestrator.turn.process.v1` |
| `admin-web` | `host.auth.identity.v1`, `host.config.v1` | `persona-state.identity.read.v1`, `persona-state.identity.version.create.v1`, `persona-state.adaptation.update.v1`, `persona-state.proposal.review.v1`, `memory-graph.graph.read.v1`, `reasoning-orchestrator.audit.read.v1`, `reasoning-orchestrator.llm.configure.v1`, `async-consolidator.backlog.read.v1`, `async-consolidator.deadletter.read.v1`, `async-consolidator.deadletter.replay.v1` |
