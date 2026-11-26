# HLA-MEM · 思维模拟系统

HLA-MEM 是一个以**记忆图（双路径检索）**、**人格双层治理**与**异步巩固**为核心的思维模拟系统。仓库按《模块开发契约》组织为 6 个可独立构建、独立测试的模块，按《HLM-MEM开发计划》分 5 个阶段、16 周推进。

> **当前阶段：最小可用 Demo — 可运行**
> 6 个模块、28 个能力、16 个事件、37 个权限通过校验；对话端 → 编排器（SSE + 记忆检索/写入 + 模板/LLM 回退 + persona 快照）→ 记忆图 / persona-state 已串通；管理端可保存模型配置、编辑身份层与适应层、审批人格提案。
> 151 个 Python 测试、conversation 3 个、admin 8 个前端测试通过；OpenAPI 无漂移。
> **未实现/未验证**：persona-state 经历日志与 PostgreSQL 持久化、async-consolidator、FalkorDB、BGE-M3、真实 token 流、生产认证。运行与边界见 [docs/demo-minimal.md](docs/demo-minimal.md)，后续项见 [docs/optimization-backlog.md](docs/optimization-backlog.md)。

## 模块一览

| 模块 ID | 职责 | 类型 | 本地端口 |
| --- | --- | --- | --- |
| `reasoning-orchestrator` | System-One 门控、检索预算、轻量重排序、提示组装、System-Two 生成、SSE 回合 | backend | 8081 |
| `memory-graph` | 情景/概念节点、共激活边、双路径检索、检索审计 | backend | 8082 |
| `persona-state` | 身份层版本化、适应层有界更新、经历日志、身份变更 proposal | backend | 8083 |
| `async-consolidator` | 持久化巩固作业、边权更新、遗忘、枢纽蒸馏、死信重放 | backend | 8084 |
| `conversation-web` | 对话界面、SSE 流式渲染、降级提示 | frontend | 4173（`/conversation/`） |
| `admin-web` | 模型设置、健康面板、身份层/适应层编辑、提案审批；记忆/审计/巩固页占位 | frontend | 4173（`/admin/`） |

跨模块依赖只通过版本化**能力名称**（`{module}.{domain}.{action}.v{major}`）表达，不依赖服务名、主机名或代码包路径。完整能力/事件/权限清单由 [docs/module-catalog.md](docs/module-catalog.md) 汇总，源头是各模块的 `module.yaml` 与 `contracts/`。

## 快速开始

要求：Python 3.12+、Node.js 20.19+（仅前端，CI 用 22）、GNU Make。

```bash
# 1. 创建虚拟环境并安装共享包与 4 个后端模块（editable）
make install

# 2. 校验全部模块清单、能力/事件/权限命名与契约文件
make validate

# 3. 运行 Python 测试（含契约测试与降级/幂等基础测试）
make test

# 4. 校验已提交的 OpenAPI 与实现是否漂移
make contracts-check

# 5. 重新生成模块目录（能力/事件/权限汇总）
make catalog

# 6. 启动一个后端模块（示例：记忆图）
make run-memory-graph
curl -s http://127.0.0.1:8082/internal/health
curl -s http://127.0.0.1:8082/internal/ready
curl -s http://127.0.0.1:8082/internal/metrics | head
```

前端：

```bash
make web-install
make web-test
make web-build
node tools/serve_web.mjs   # 4173：/conversation/ 与 /admin/ 同源
```

## 最小可用 Demo

```bash
make install
make web-build
make demo          # 启动 memory / orchestrator / 单一 Web 服务（对话+管理同源）
```

- 对话：`http://127.0.0.1:4173/conversation/`
- 管理：`http://127.0.0.1:4173/admin/`（模型设置可保存 API Key，密钥只写不读）
- 演示：先输入“我最近在喝龙井，喜欢清淡的茶。”，再问“我喜欢什么茶？”，第二轮会展示“本次回忆”。
- 没有配置大模型时使用确定性模板回复；配置后调用 OpenAI 兼容端点，失败自动回退并标记降级。

## 仓库结构

```text
.
├── HLM-MEM开发计划.md        # 输入文档：架构、阶段、量化约束（v1.1）
├── 模块开发契约.md            # 输入文档：模块治理与验收规则（v2.0）
├── AGENTS.md                 # 仓库级 AI/协作者约束
├── docs/                     # 架构、契约对齐、路线图、Demo 手册、优化清单
├── schemas/                  # module / event envelope / permissions / menu JSON Schema
├── packages/
│   ├── contract-kit/         # 契约校验库与 CLI（manifest、命名、事件、OpenAPI、权限）
│   └── host/                 # 宿主能力适配：身份、配置、事件总线、可观测性、错误与幂等
├── modules/{module-id}/      # 6 个标准模块目录
├── tools/                    # OpenAPI 导出、目录渲染、模块启动、Demo 启动器
├── docker-compose.yml        # FalkorDB + 两个独立 PostgreSQL（阶段 1 起使用）
└── .github/workflows/ci.yml  # 契约校验 + 测试 + 构建 + 前端构建
```

每个模块遵循《模块开发契约》第 3 章：`AGENTS.md`、`DESIGN.md`、`module.yaml`、`README.md`、`src/`、`tests/`、`contracts/`、`migrations/`，含界面时增加 `web/`。

## 契约与状态口径

- **契约先行**：能力、事件、权限、请求/响应模型先落在 `module.yaml` 与 `contracts/`；FastAPI 的 OpenAPI 由代码生成到 `contracts/openapi.yaml`，CI 检查漂移。
- **数据自持**：模块只读写自己的数据库；禁止跨模块外键、视图、Join 与直连存储。
- **租户可信**：`tenantId` 只从宿主身份上下文获得，不接受客户端参数、请求体或普通请求头覆盖。
- **必选依赖**仅限 `host.auth.identity.v1`、`host.config.v1`、`host.event.bus.v1`；其他业务模块全部为可选集成。
- 所有报告区分 **已实现 / 仅声明 / 未验证**，不以占位代码或设计文档冒充通过。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | 6 模块架构、数据拓扑、请求流、降级矩阵 |
| [docs/module-catalog.md](docs/module-catalog.md) | 各模块能力、事件、权限、依赖汇总（可再生成） |
| [docs/contract-alignment.md](docs/contract-alignment.md) | 两份输入文档的差异梳理、命名归一与设计决策（ADR-000） |
| [docs/roadmap.md](docs/roadmap.md) | 阶段/里程碑、验收门槛与当前状态 |
| [docs/phase0-acceptance.md](docs/phase0-acceptance.md) | 阶段 0 验收：已实现/仅声明/未验证与复现命令 |
| [docs/phase1-memory-graph.md](docs/phase1-memory-graph.md) | 阶段 1 进度：记忆图内存纵向切片与未验证项 |
| [docs/demo-minimal.md](docs/demo-minimal.md) | 最小 Demo：启动、演示脚本、模型配置与边界 |
| [docs/optimization-backlog.md](docs/optimization-backlog.md) | Demo 之后的优化项与验收标准 |
| [docs/glossary.md](docs/glossary.md) | 领域术语表 |
| [HLM-MEM开发计划.md](HLM-MEM开发计划.md) | 原始开发计划（架构、技术选型、量化约束） |
| [模块开发契约.md](模块开发契约.md) | 原始模块开发契约（目录、清单、接口、事件、安全、验收） |

## 当前已知边界

- `memory-graph`、`reasoning-orchestrator` 与 `persona-state` 的人格路径已实现（进程内）；`persona-state` 的经历日志与 `async-consolidator` 业务端点仍返回 `501`。
- 人格双层治理已可演示：身份层版本化/回滚、适应层有界更新、提案审批；模型只能通过隐藏标记改适应层或提交提案，不能直接写身份层。
- 记忆、回合、审计、幂等均为进程内存储，重启即丢失；嵌入器是确定性哈希替身，不代表语义质量；不得当作生产记忆服务。
- 当前开发环境**没有 Docker**，因此 FalkorDB/PostgreSQL 容器集成测试尚未运行；`docker-compose.yml` 仅提供编排定义，未在本机启动。
- BGE-M3、MemReranker-0.6B、System-One 分类器未接入；大模型可通过管理端配置，但真实 token 流式、质量与费用未验证。
- 宿主认证、配置、事件总线目前是本地进程内适配器；接入真实宿主能力前不得用于生产。
- 前端已通过组件测试与生产构建，但**浏览器端到端未验证**；管理端已实现模型设置、身份层、适应层与提案审批，记忆/审计/巩固页仍为占位。
- 人格数据为进程内存储，重启丢失；无 RLS、无迁移、无并发压力测试，不能当作生产人格服务。
