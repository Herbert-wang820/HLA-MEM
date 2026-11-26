# conversation-web 设计说明

> 状态：最小 Demo 已实现（SSE 对话 + 本次回忆 + 人格更新提示）；会话历史与断线重连未实现。

## 1. 定位

面向终端用户的对话界面：输入消息、流式展示回复、显式呈现降级与错误。它只消费 `reasoning-orchestrator.turn.process.v1`，不直接访问记忆或人格服务。

## 1.1 最小 Demo 补充

- 同源 Web 服务将 `/api/*` 代理到编排器并保留 SSE；`npm run dev` 使用 Vite 代理。
- `done` 事件新增 `usedEpisodeIds` 与 `memories`（ID、分数、摘要），页面渲染“本次回忆”面板。
- 默认模板回复会标注“演示模式”；管理端配置 LLM 后使用真实模型，失败显示降级提示。
- 记忆与人格均为进程内存储，刷新页面保留当前会话，重启服务丢历史。
- `done.persona` 含 `identityVersion`、`adaptationVersion`、`updated`、`degraded`、`identityProposalId`。
  页面只在 `updated=true` 时提示：提案 → “等待管理员审批”；适应层 → 新版本号。
- 页面不展示、不缓存人格叙事或提案内容；人格编辑与审批只在管理端进行。

## 2. 页面结构

```
┌──────────┬─────────────────────────────┐
│ 品牌/菜单 │ 标题 + 阶段徽章              │
│ 对话      │ 降级提示（按需）              │
│ 会话(禁用) │ 消息列表（用户/助手）         │
│           │ 输入框 + 发送                 │
└──────────┴─────────────────────────────┘
```

- 菜单来自 `src/config/menu.ts`，与 `contracts/menu.yaml` 对应；按权限过滤。
- 阶段 0 的“会话”子项禁用并标注，避免误导。

## 3. SSE 协议

`POST /api/reasoning-orchestrator/v1/turns` 返回 `text/event-stream`：

| 事件 | 数据 | 处理 |
| --- | --- | --- |
| `token` | `{"text":"..."}` | 追加到当前助手消息 |
| `done` | `{"turnId":"...","degraded":false,"reasons":[],"memories":[...],"persona":{...}}` | 结束 pending；降级/人格更新时显示提示 |
| `error` | `{"code":"...","message":"...","requestId":"..."}` | 显示稳定错误码 |

解析器按 `\n\n` 分帧，兼容 `\r\n`、多行 `data:`、非 JSON 心跳；非 200 响应按错误信封解析。

## 4. 错误与降级

- `ApiError` 保留 `code/status/requestId`；UI 显示 `code：message`。
- 回合不会返回 `501`；编排器始终以模板或 LLM 回复，依赖失败通过 `degraded/reasons` 表达。
- 人格原因码：`PERSONA_UNAVAILABLE`、`PERSONA_UPDATE_REJECTED`、`PERSONA_UPDATE_FAILED`、
  `PERSONA_PROPOSAL_REJECTED`、`PERSONA_PROPOSAL_FAILED`。
- 网络失败显示 `NETWORK_ERROR`，并移除空的助手占位。

## 5. 安全与隐私

- 不存储消息原文；刷新即丢失（阶段 2 若需历史，走后端会话能力）。
- 不构造 `tenantId`；租户由可信身份/网关注入。
- 静态服务器加 CSP、`nosniff`、`referrer-policy`；仅监听 `127.0.0.1`（本地开发）。
- 构建产物不含密钥；`VITE_*` 仅用于非敏感配置。

## 6. 运行与端点

| 端点 | 说明 |
| --- | --- |
| `GET /internal/health` | 存活 |
| `GET /internal/ready` | `dist/index.html` 存在才 ready |
| `GET /internal/metrics` | `frontend_ready`、请求计数、构建信息 |

开发：`npm run dev`（Vite 4173，仅对话端，`/api` 代理到 8081）。生产/演示：`npm run build && npm start` 或 `make demo`，同一个 Web 服务在 4173 同时提供 `/conversation/` 与 `/admin/`。

## 7. 技术栈

React 19、TypeScript、Vite 7、Vitest + Testing Library、原生 CSS。无 UI 框架依赖，减少供应链面。

## 8. 非功能目标（阶段 2 验证，当前未验证）

- 首屏 LCP ≤ 1.5s（本地静态）。
- SSE 首 token 渲染 ≤ 100ms（收到后）。
- 断连重试不重复发送（依赖后端幂等键）。
- 键盘可达：输入、发送、关闭提示均可 Tab 操作。

## 9. 待决问题

- 会话历史由后端提供还是仅本地临时？
- 多会话切换与标题生成（阶段 2）。
- 移动端窄屏布局细化。
- 国际化（当前仅中文）。
