# admin-web

HLA-MEM 管理前端：模块健康、模型配置、人格身份层/适应层编辑与提案审批；记忆图/审计/巩固页仍为占位。

## 状态

**最小 Demo 已实现**。管理壳、菜单权限过滤、上游健康探测、**模型设置**、**身份层编辑器**、
**适应层编辑器**、**提案审批**可用。前三个业务页通过同源 `/api/persona-state/*` 代理读写
persona-state（进程内存储，重启丢数据）。

**未实现**：记忆图浏览、检索审计、巩固监控页面；身份回滚入口；浏览器端到端测试。

## 运行

```bash
make install
make web-build
make demo
# 或
cd modules/admin-web/web && npm start    # 4173，同时服务 /conversation/ 与 /admin/
```

> `npm run dev` 仍是 Vite 4174 独立开发端口；生产/演示用 `npm start` 或 `make demo`，对话与管理同端口 4173。

## 模型设置

- 菜单：模型设置（`admin-web.llm.manage`，所需能力 `reasoning-orchestrator.llm.configure.v1`）。
- 页面通过同源 `/internal/orchestrator/llm/config` 访问 Web 服务，再由它代理到编排器；浏览器不直连 8081。
- GET 不返回密钥；PUT 可保存新密钥，留空保持原值。
- 编排器写入 `var/reasoning-orchestrator/llm.json`（0600）；关闭启用时使用模板回复。
- 启用但无密钥会返回 422；页面显示稳定错误码。

## 人格编辑与提案审批

- **身份层**（`admin-persona-identity`）：读取当前版本；保存调用 `POST /identity/versions`，
  必须先填变更原因并二次确认，成功后展示新版本号。历史版本不被修改。
- **适应层**（`admin-persona-adaptation`）：读取当前取值与窗口漂移；提交“目标值 − 当前值”的差值，
  单次 `|Δ| ≤ 0.15` 仅作前端提示，真正上限由 persona-state 的 409/422 强制。
- **提案审批**（`admin-proposals`）：列出提案；批准/拒绝前二次确认。批准后由 persona-state 创建新身份版本；
  已审结提案不再显示操作按钮，服务端仍拒绝重复审结。
- 三者都不读取或缓存身份叙事以外的敏感数据，不持久化任何人格内容。

## 同源 Web 端点

| 路径 | 说明 |
| --- | --- |
| `GET /internal/health` | 存活 |
| `GET /internal/ready` | `dist/index.html` 存在才 ready |
| `GET /internal/metrics` | 就绪、上游健康数、请求计数 |
| `GET /internal/upstreams` | 服务端探测 4 个模块 `/internal/health` |
| `GET/PUT /internal/orchestrator/llm/config` | 代理到编排器 LLM 配置 |
| `/api/persona-state/*` | 代理到 persona-state（`PERSONA_URL`，默认 8083） |
| `/api/*`（其余） | 代理到编排器（SSE 保留） |

上游地址：`ORCHESTRATOR_URL`（默认 `http://127.0.0.1:8081`）、`PERSONA_URL`（默认 `http://127.0.0.1:8083`）；
健康探测目标可用 `UPSTREAMS` JSON 覆盖，且只允许配置内的 http(s) origin。

## 测试

```bash
npm test
```

8 个测试：管理壳、上游健康、权限过滤、默认菜单、模型配置保存与密钥不回显、
身份层新建版本、适应层有界调整、提案批准（含二次确认）。

## 结构

```
web/
  src/
    api/health.ts        # 上游健康
    api/llm.ts           # 模型配置
    api/persona.ts       # persona-state 读写（身份/适应/提案）
    components/LLMSettings.tsx
    components/IdentityEditor.tsx
    components/AdaptationEditor.tsx
    components/ProposalReview.tsx
    config/menu.ts       # 与 contracts/menu.yaml 对应
  （仓库根）tools/serve_web.mjs  # 静态服务 + 健康/指标 + 受控代理
```

## 边界

- 菜单权限只控制可见性，最终授权由目标模块在服务端校验。
- 前端不持久化 API Key；密钥只存在于密码输入框与请求体中。
- 不缓存人格叙事/提案内容到 localStorage；刷新后重新从 persona-state 读取。
- 当前单租户开发身份；生产需接入真实管理端认证。
