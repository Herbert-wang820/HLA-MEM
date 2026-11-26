# conversation-web

HLA-MEM 对话前端：SSE 对话、降级提示与“本次回忆”。

## 状态

**最小 Demo 已实现**。页面通过同源 `/api` 代理调用编排器，逐块渲染回复；结束事件携带本次使用的记忆，显示在“本次回忆”面板。

`done.persona` 携带 `identityVersion`、`adaptationVersion`、`updated`、`degraded`、`identityProposalId`；
页面在适应层更新时提示新版本、在身份提案提交时提示“等待管理员审批”，不展示也不缓存人格内容。

**未实现**：会话历史/多会话、断线重连、真实浏览器端到端测试；记忆、回合与人格均为进程内，重启丢历史。

## 运行

```bash
make install
make web-build
make demo
# 或
cd modules/conversation-web/web
npm run dev      # Vite 4173（仅对话端），/api 代理到 8081
npm start        # 与 admin 同源：node ../../../tools/serve_web.mjs
```

地址：`http://127.0.0.1:4173/conversation/`。

## 代理与端点

- 同源 Web 服务将 `/api/*` 原样代理到 `ORCHESTRATOR_URL`（默认 `http://127.0.0.1:8081`），保留 SSE 流与 `Idempotency-Key`。
- 自带 `/internal/health`、`/internal/ready`、`/internal/metrics`。
- 直接 `npm run dev` 时使用 Vite 的 `/api` 代理，不经过 sidecar 的运营端点。

## SSE 协议

| 事件 | 数据 | UI 行为 |
| --- | --- | --- |
| `token` | `{"text":"..."}` | 追加到当前助手消息 |
| `done` | `turnId/degraded/reasons/usedEpisodeIds/memories` | 结束 pending；显示降级；渲染“本次回忆” |
| `error` | `code/message/requestId` | 显示稳定错误码 |

非 200 响应按统一错误信封解析；网络错误显示 `NETWORK_ERROR`。

## 测试

```bash
npm test
```

3 个测试：对话壳、权限过滤、阶段边界提示。SSE 解析为纯函数式逻辑，当前未做浏览器端到端。

## 结构

```
web/
  src/
    api/orchestrator.ts   # 回合创建 + SSE 分帧 + done 解析
    components/           # 消息列表、输入框、降级提示
    config/menu.ts
    App.tsx               # 对话 + 本次回忆
  （仓库根）tools/serve_web.mjs  # 静态服务 + /api 代理 + 运营端点
```

## 边界

- 只调用编排器；不直连记忆/人格模块。
- 不在浏览器持久化消息或凭据。
- 前端菜单权限不构成授权。
