# 阶段 0 验收报告（契约基线与工程骨架）

> **历史记录**：本文记录 2026-11-11 阶段 0 验收时的状态。
> 之后 memory-graph、reasoning-orchestrator 与 persona-state 已落地业务实现，
> 当前状态请看 [README](../README.md)、[demo-minimal.md](demo-minimal.md) 与各模块 `DESIGN.md`。

> 日期：2026-11-10  
> 范围：6 个模块的契约、工程骨架、宿主适配层、前端骨架、校验与 CI。  
> 口径：严格区分 **已实现 / 仅声明 / 未验证**；不以设计文档或占位代码冒充完成。  
> 后续说明：阶段 1 已将 `memory-graph` 的业务端点从 501 替换为内存实现；本报告保留阶段 0 时点的验收结论，当前进度见 [phase1-memory-graph.md](phase1-memory-graph.md)。

## 1. 结论

阶段 0 的**契约基线与工程骨架已完成**：

- 6 个模块目录、`module.yaml`、`AGENTS.md`、`DESIGN.md`、`README.md`、`contracts/`、`tests/` 全部就位。
- 27 个能力、16 个事件、36 个权限、菜单与依赖声明通过 Schema 与语义校验。
- 4 个后端模块可独立启动，健康/就绪/指标可用；业务端点统一返回稳定 `501`。
- 2 个前端可独立测试与构建，静态服务提供健康/就绪/指标；管理端另有受控上游探测。
- Python 测试 115 个通过；OpenAPI 无漂移；ruff 全通过；两个前端 `npm test`/`npm run build` 通过。

**未完成**：任何真实记忆、人格、编排、巩固业务逻辑；数据库/图库集成；模型接入；浏览器端到端。这些属于阶段 1+，当前明确为“仅声明/未验证”。

## 2. 交付物

| 交付物 | 状态 | 证据 |
| --- | --- | --- |
| 契约对齐 ADR-000 | 已实现 | `docs/contract-alignment.md`（含 22 条差异归一） |
| 架构与阶段计划 | 已实现 | `docs/architecture.md`、`docs/roadmap.md`、`docs/glossary.md` |
| JSON Schema（module/envelope/permissions/menu） | 已实现 | `schemas/` + 校验测试 |
| 契约校验库与 CLI | 已实现 | `packages/contract-kit`，`hla-contract-kit check-all` |
| 宿主适配层（身份/配置/事件/错误/可观测/幂等/分页/降级） | 已实现（本地适配器） | `packages/host`，74 个测试 |
| 6 个模块清单与契约 | 已实现 | `modules/*/module.yaml`、`contracts/` |
| 4 个后端模块骨架 | 已实现（业务端点 501） | `modules/*/src`、OpenAPI、健康端点 |
| 2 个前端骨架 | 已实现（页面为阶段 0 占位） | `modules/*/web`，构建产物 |
| OpenAPI 生成与漂移检查 | 已实现 | `tools/export_openapi.py`、`make contracts-check` |
| 模块目录生成 | 已实现 | `tools/render_catalog.py`、`docs/module-catalog.md` |
| 本地依赖编排 | 已提供，未运行 | `docker-compose.yml`（FalkorDB + 两个 PostgreSQL） |
| CI | 已提供，未在远端运行 | `.github/workflows/ci.yml` |
| 阶段 0 验收 | 本文件 | — |

## 3. 已实现（可复现验证）

### 3.1 契约与命名

- 能力格式：`{module}.{domain}.{action}.v{major}`；允许复合动作（如 `identity.version.create`）与宿主两段例外（`host.config.v1`），已在 ADR 记录。
- 事件：`{module}.{aggregate}.{past-tense}.v{major}`，每个事件有独立 `type + data` Schema。
- 权限：`{module}.{resource}.{action}`；模块只能引用自身前缀的权限。
- 菜单：`menu/v1`，路由、权限、所需能力均校验；前端菜单与 `contracts/menu.yaml` 对应。
- 必选依赖仅允许 `host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`。

验证：

```bash
make validate          # 6 modules, 27 capabilities, 16 events, 36 permissions, 0 issue
make contracts-check   # 4 个后端 OpenAPI 无漂移
```

### 3.2 宿主适配层

| 能力 | 实现 |
| --- | --- |
| `host.auth.identity.v1` | `IdentityProvider` 协议、静态开发适配器、`require_identity`/`require_permission`；非 dev 拒绝本地适配器 |
| `host.config.v1` | 带类型/默认值/敏感标记的 `ModuleConfig`，环境变量映射与就绪检查 |
| `host.event.bus.v1` | 版本化信封、`InMemoryEventBus`、去重消费者、outbox 与 drain |
| 横切 | 结构化 JSON 日志、请求 ID/trace ID、Prometheus 文本指标、统一错误信封、体积/超时限制、幂等存储、游标分页、降级标记 |

限制：事件总线、幂等与 outbox 均为**进程内实现**，不具备持久化或跨进程投递；生产必须替换。

### 3.3 后端模块

| 模块 | 能力 | 事件 | 运行端点 | 业务端点 |
| --- | ---: | ---: | --- | --- |
| `reasoning-orchestrator` | 4 | 2 | 8081 | 501；OpenAPI 声明 SSE |
| `memory-graph` | 7 | 3 | 8082 | 501 |
| `persona-state` | 10 | 6 | 8083 | 501 |
| `async-consolidator` | 6 | 5 | 8084 | 501 |

每个模块均具备：独立 `pyproject.toml`、应用工厂、`__main__`、分层目录、OpenAPI、单元/契约/就绪测试。

进程级冒烟（本机，8081–8084）：

| 模块 | `/internal/health` | `/internal/ready` | 业务端点 |
| --- | --- | --- | --- |
| reasoning-orchestrator | 200 `ok` | 200 | 501 `REASONING_ORCHESTRATOR_FEATURE_NOT_IMPLEMENTED` |
| memory-graph | 200 `ok` | 200 | 501 `MEMORY_GRAPH_FEATURE_NOT_IMPLEMENTED` |
| persona-state | 200 `ok` | 200 | 501 `PERSONA_STATE_FEATURE_NOT_IMPLEMENTED` |
| async-consolidator | 200 `ok` | 200 | 501 `ASYNC_CONSOLIDATOR_FEATURE_NOT_IMPLEMENTED` |

### 3.4 前端

| 模块 | 已实现 | 构建 | 测试 |
| --- | --- | --- | --- |
| `conversation-web` | 对话壳、SSE 分帧解析、错误/降级提示、菜单过滤 | 通过 | 3 通过 |
| `admin-web` | 管理壳、菜单过滤、上游健康探测、能力边界说明 | 通过 | 4 通过 |

两个静态服务均验证了 `/internal/health`、`/internal/ready`、`/internal/metrics`；管理端另验证 `/internal/upstreams`。

## 4. 仅声明（未实现业务）

- 所有业务端点：写入、检索、图查询、巩固应用、身份版本、适应层、提案、经历、回合、作业、死信、门控配置。
- 所有 16 个领域事件的**发布端**：事件 Schema 已定义，但业务代码尚未产生事件。
- 数据模型与迁移：仅有设计说明与迁移 README，没有 SQL/Cypher。
- 租户隔离：仅约定从 `Identity` 取值并在 DTO 禁止 `tenantId`；没有数据库级 RLS 或图库隔离。
- 幂等：存储与摘要工具已实现，但业务端点尚未接入（当前 501）。
- 降级：编排器仅定义矩阵与标记；没有真实超时/降级路径。

## 5. 未验证（环境或依赖缺失）

| 项 | 原因 | 影响 |
| --- | --- | --- |
| FalkorDB / Neo4j 集成 | 当前环境无 Docker | 图 schema、HNSW、租户隔离、查询性能均未验证 |
| PostgreSQL 集成 | 当前环境无 Docker | 迁移、事务、`SKIP LOCKED`、RLS 未验证 |
| BGE-M3 / MemReranker-0.6B | 无模型权重与推理服务 | 嵌入、重排、检索质量未验证 |
| LLM 供应商 | 未接入 | SSE 真实流式、首 token、超时降级未验证 |
| 跨模块集成 | 业务端点均为 501 | 编排→记忆/人格/巩固调用链未验证 |
| 浏览器端到端 | 无 Playwright/E2E 环境 | 仅验证构建与 Vitest 组件测试 |
| 真实宿主身份/配置/事件总线 | 仅有本地适配器 | 生产认证、密钥管理、持久事件未验证 |
| CI 远端执行 | 工作区尚未初始化 Git 仓库，未推送 | 工作流文件有效但未在 GitHub 上跑过 |

## 6. 关键决策与偏差

1. **`host.config.v1` 两段例外**：保留契约原文，Schema 与校验器对 `host.*` 开放两段；业务能力仍至少三段。
2. **复合动作**：允许 `identity.version.create` 这类点号动作，避免为格式而重命名已发布能力。
3. **新增能力**：`memory-graph.consolidation.apply.v1`、`persona-state.proposal.read.v1`，用于闭合巩固写入与提案读取路径。
4. **OpenAPI 由代码生成**：FastAPI 为唯一事实源，`contracts/openapi.yaml` 提交并由 CI 检查漂移；未采用手写 YAML。
5. **阶段 0 业务端点返回 501**：错误码 `{MODULE}_FEATURE_NOT_IMPLEMENTED`，不返回假数据。
6. **前端健康端点由 Web 服务提供**：Vite 构建产物本身不含服务端；阶段 0 时点为两个 sidecar，当前已合并为一个同源 Web 服务。

## 7. 阶段 0 退出检查

- [x] 6 个模块目录与标准文件齐全
- [x] `module.yaml` 通过 Schema 与语义校验
- [x] 能力/事件/权限/菜单命名符合契约
- [x] 每个模块可独立构建与测试
- [x] 4 个后端健康/就绪/指标可用
- [x] OpenAPI 与实现无漂移
- [x] 业务端点显式 501，未伪造实现
- [x] 报告区分已实现/仅声明/未验证
- [ ] Docker 依赖集成（阻塞：环境无 Docker）
- [ ] 真实模型与 LLM（阻塞：无权重/供应商）
- [ ] 浏览器端到端（阻塞：无业务实现）

后三项不阻塞阶段 0 的“契约基线”结论，但会阻塞阶段 1 的量化门槛验收。

## 8. 进入阶段 1 的前置条件

1. 提供可运行 Docker 的环境，启动 `docker-compose.yml` 并完成图库/PostgreSQL 连通性测试。
2. 确定图库（FalkorDB 或 Neo4j）并完成 tenant 隔离方案基准。
3. 接入 BGE-M3 嵌入服务与至少一个 LLM 供应商（或确定性替身），用于检索/回合基线。
4. 为 `memory-graph` 实现写入、读取、撤回、双路径检索与审计，并把 501 替换为真实响应。
5. 补齐集成测试：幂等重放、租户隔离、检索降级、事件 outbox。

## 9. 复现命令

```bash
make install
make validate
make contracts-check
make lint
make test
make build
make catalog

make web-install
make web-test
make web-build
```

结果（本机，2026-11-10）：

- `make validate`：6 modules，0 issue，0 warning。
- `make contracts-check`：4 个后端 `[ok]`。
- `make lint`：All checks passed。
- `make test`：115 passed。
- `make web-test`：conversation-web 3 passed；admin-web 4 passed。
- `make web-build`：两个前端构建成功。
- 四模块进程冒烟：health/ready 均 200；业务端点分别返回上述 501 错误码。
- `docker compose config`：未执行（本机没有 Docker CLI）。
