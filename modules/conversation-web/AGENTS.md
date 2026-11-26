# conversation-web 模块协作约束

本文件在仓库根 `AGENTS.md` 之上叠加，**只加严，不放宽**。

## 1. 职责边界

- 拥有：对话端 UI、SSE 渲染、降级提示、会话侧栏。
- 不拥有：回合编排、记忆检索、人格状态；只调用 `reasoning-orchestrator` 的能力。
- 禁止在前端直连 `memory-graph`/`persona-state`，禁止在浏览器保存租户或权限的“可信”来源。

## 2. 不可破坏的规则

1. **前端不是授权边界**：菜单隐藏/按钮禁用只影响可见性；所有写操作仍由后端校验权限。
2. **不缓存敏感数据**：不在 localStorage/sessionStorage 存消息原文、 token、人格内容；仅存非敏感 UI 偏好。
3. **降级可见**：收到 `degraded=true` 或错误码必须显式提示，不得把失败渲染成空回复。
4. **SSE 健壮性**：断连、超时、非 JSON 帧不得导致白屏；错误统一显示稳定错误码。
5. **租户不进入前端请求体**：前端不构造 `tenantId`；租户由网关注入的会话/令牌决定。
6. **不伪造状态**：未实现或未验证的功能必须标注，不得用假数据演示。

## 3. 最小 Demo 状态

- 已实现：对话壳、SSE 解析、错误/降级提示、`/api` Node 代理、“本次回忆”面板。
- 已实现：解析 SSE `done.persona`，在适应层更新时提示版本、在身份提案提交时提示
  “等待管理员审批”；**不**在浏览器缓存人格内容。
- 编排器默认使用模板回复；管理端配置 LLM 后可用真实模型，失败会回退并显示降级。
- 记忆与人格均为进程内存储，重启丢历史；浏览器端到端未验证。

## 4. 命令

```bash
cd modules/conversation-web/web
npm install
npm test
npm run build
npm start                 # 4173：/conversation/ 与 /admin/（同源）
```

## 5. 评审关注点

- 错误是否显示稳定错误码，而不是堆栈？
- SSE 解析是否处理分帧、CRLF、非 JSON 心跳？
- 菜单权限与 `contracts/menu.yaml` 是否一致？
- 依赖升级是否保持 React 19 / Vite 7 兼容？
