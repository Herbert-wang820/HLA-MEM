# admin-web 设计说明

> 状态：最小 Demo 已实现模型设置、身份层编辑、适应层编辑与提案审批；记忆图/检索审计/巩固监控仍为只读占位。

## 1. 定位

面向运维与人格管理者的控制台：查看模块健康、浏览记忆图结构化查询结果、查看检索审计、监控巩固积压、审批人格提案。它不直接访问数据库，只通过各模块的版本化能力读写。

## 1.1 模型设置（最小 Demo）

- 菜单 `admin-llm`，权限 `admin-web.llm.manage`，所需能力 `reasoning-orchestrator.llm.configure.v1`。
- 页面读取/保存 Base URL、模型、API Key、温度、最大 tokens 与启用开关。
- 请求经同源 Web 服务 `/internal/orchestrator/llm/config` 代理，浏览器不直连 8081。
- 密钥只写不读：`GET` 返回 `apiKeySet`，不返回密钥；保存后写入编排器本机文件（0600）。
- 保存后下一回合生效；LLM 调用失败自动回退模板并标记降级。

## 1.2 人格编辑与提案审批（最小 Demo）

- 菜单/权限：`admin-persona-identity`、`admin-persona-adaptation` 使用 `admin-web.persona.view`
  （新增写权限 `admin-web.persona.edit` 已在 `contracts/permissions.yaml` 声明，供后续按按钮细分）；
  `admin-proposals` 使用 `admin-web.proposal.review`。
- 同源代理：`tools/serve_web.mjs` 将 `/api/persona-state/*` 转发到 `PERSONA_URL`（默认 8083），
  浏览器不直连 persona-state，也不缓存人格原文。
- 身份层编辑器：读取 `GET /identity`，保存调用 `POST /identity/versions`（`Idempotency-Key` 由前端生成）；
  保存前后端二次确认，成功后展示新版本号。回滚入口尚未提供 UI。
- 适应层编辑器：读取 `GET /adaptation`，只提交“目标值 − 当前值”的差值，并先做 `|Δ| ≤ 0.15` 的本地提示；
  真正的窗口漂移与上限仍由 persona-state 校验，超限原样显示 `PERSONA_STATE_*` 错误码。
- 提案审批：`GET /proposals?limit=50` 列表；批准/拒绝调用 `POST /proposals/{id}/review`，
  批准前二次确认；审结后的提案不再显示操作按钮，服务端仍会拒绝重复审结。
- 所有写请求都必须带 `Idempotency-Key`；前端不把 `tenantId` 放进请求体。

## 2. 页面结构

```
┌────────────┬──────────────────────────────────┐
│ 品牌/菜单   │ 标题 + 阶段徽章                    │
│ 人格        │ 上游健康卡片（模块/延迟/可达）      │
│  身份层     │ 刷新健康                           │
│  适应层     │ 当前模块：路由/能力/权限/边界说明    │
│ 记忆图      │                                  │
│ 检索审计    │                                  │
│ 巩固监控    │                                  │
│ 提案审批    │                                  │
└────────────┴──────────────────────────────────┘
```

- 菜单来自 `src/config/menu.ts`，与 `contracts/menu.yaml` 一一对应，按 `admin-web.*` 权限过滤。
- 已接入 persona-state 的页面显示真实后端数据；未实现页面仍只展示契约元数据与边界说明，不展示假数据。

## 3. 健康探测（BFF）

浏览器直连 8081–8084 会受 CORS 限制，且不应让浏览器决定探测目标。因此由同源 Web 服务 `tools/serve_web.mjs` 提供服务端探测：

```
GET /internal/upstreams
→ {"upstreams":[{"module":"memory-graph","url":"http://127.0.0.1:8082",
                 "healthy":true,"latencyMs":12,"detail":null}]}
```

- 目标来自 `UPSTREAMS` 环境变量（JSON 数组），仅允许 http/https 且取 origin；默认四个本地模块。
- 每个探测 1.5s 超时，失败返回 `healthy=false` 与简短原因，不抛出。
- `/internal/metrics` 复用同一探测，导出 `frontend_upstreams_healthy`。

## 4. 页面能力映射

| 菜单 | 所需能力 | 菜单权限 | 阶段 0 |
| --- | --- | --- | --- |
| 人格/身份层 | `persona-state.identity.read.v1` / `.identity.version.create.v1` | `admin-web.persona.view` (+`edit`) | 已实现（读/新建版本） |
| 人格/适应层 | `persona-state.adaptation.read.v1` / `.update.v1` | `admin-web.persona.view` (+`edit`) | 已实现（读/有界更新） |
| 记忆图 | `memory-graph.graph.read.v1` | `admin-web.memory.view` | 占位 |
| 检索审计 | `reasoning-orchestrator.audit.read.v1` | `admin-web.audit.view` | 占位 |
| 巩固监控 | `async-consolidator.backlog.read.v1` | `admin-web.consolidation.view` | 占位 |
| 提案审批 | `persona-state.proposal.read.v1` / `.review.v1` | `admin-web.proposal.review` | 已实现（列表/批准/拒绝） |
| 模型设置 | `reasoning-orchestrator.llm.configure.v1` | `admin-web.llm.manage` | 已实现（保存/脱敏） |

写/审批动作在阶段 2+ 接入，需额外 `persona-state.admin.write` 等后端权限。

## 5. 安全

- 不持久化敏感数据；刷新即丢失。
- 健康探测只允许配置内的 origin，避免 SSRF；不探测用户提供的 URL。
- 静态服务加 CSP、`nosniff`、`referrer-policy`；仅监听 `127.0.0.1`。
- 图查询界面只发送 `nodeTypes/filters/depth/limit` 结构，禁止 Cypher 文本框。

## 6. 运行与端点

| 端点 | 说明 |
| --- | --- |
| `GET /internal/health` | 存活 |
| `GET /internal/ready` | `dist/index.html` 存在才 ready |
| `GET /internal/metrics` | 就绪、上游健康数、请求计数、构建信息 |
| `GET /internal/upstreams` | 上游健康探测结果 |

开发：`npm run dev`（Vite 4174，仅管理端；`/internal/upstreams` 不可用）。生产/演示：`npm run build && npm start` 或 `make demo`，由同一个 Web 服务在 4173 提供 `/conversation/` 与 `/admin/`。

## 7. 技术栈

React 19、TypeScript、Vite 7、Vitest + Testing Library、原生 CSS、Node 静态服务。

## 8. 非功能目标（阶段 4 验证，当前未验证）

- 首屏 LCP ≤ 1.5s；健康探测总耗时 ≤ 1.6s。
- 管理操作二次确认覆盖率 100%。
- 所有审批动作可追溯到操作者、时间、前后值。
- 图查询节点上限 500、深度 ≤3 在 UI 层同样限制。

## 9. 待决问题

- 管理端登录与租户选择（当前用开发权限）。
- 大图查询的可视化方案与性能。
- 提案 diff 的展示与敏感字段脱敏。
- 审计导出与保留期设置。
