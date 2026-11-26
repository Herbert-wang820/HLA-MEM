# 最小可用 Demo 运行手册

> 状态：可运行（2026-11-13）。范围限定为“对话端/管理端 → 编排器 → 记忆图 + persona-state”；不含 async-consolidator / FalkorDB / BGE-M3。

## 1. 它能演示什么

- 用户发送一句话，编排器通过 SSE 逐块返回回复。
- 编排器先检索 `memory-graph`，把命中的记忆放进回复并显示在“本次回忆”面板。
- 回合结束后，用户消息与助手回复都写回记忆图；下一轮可以召回上一轮内容。
- 管理端可以保存 OpenAI 兼容的大模型配置；未配置或调用失败时自动回退到确定性模板回复，并标记降级。
- 所有请求带 `Idempotency-Key`；同一 key 重放不会产生第二个回合。
- 管理端可查看/编辑身份层（保存即新版本）、查看/有界编辑适应层、审批模型或管理员提交的身份提案。
- 模型可通过隐藏标记请求人格修改：适应层直接有界生效；身份层只生成待审批提案。标记不会出现在对话正文。

## 2. 拓扑

```
web (4173)
  ├── /conversation/  对话端
  ├── /admin/         管理端
  ├── /api/reasoning-orchestrator/*  SSE 反向代理
  ├── /api/persona-state/*           persona 同源代理
  ├── /internal/orchestrator/llm/config  模型配置代理
  └── /internal/upstreams            上游健康探测
        │
        ├──▶ reasoning-orchestrator (8081)
        │       ├── HTTP /retrievals, /episodes ▶ memory-graph (8082, 进程内)
        │       └── HTTP /identity, /adaptation, /proposals ▶ persona-state (8083, 进程内)
        │
        └──▶ persona-state (8083)  管理端人格读写与提案审批
```

## 3. 启动

```bash
make install          # Python 共享包 + 4 个后端（editable）
make web-build        # 两个前端生产构建
make demo             # 启动 memory / orchestrator / conversation / admin
```

`make demo` 会等待 4 个服务（memory / persona / orchestrator / web）的 `/internal/health` 就绪后打印地址；Ctrl+C 统一停止。

地址：

- 对话：`http://127.0.0.1:4173/conversation/`
- 管理：`http://127.0.0.1:4173/admin/`
- 编排器 OpenAPI：`http://127.0.0.1:8081/docs`
- 记忆图 OpenAPI：`http://127.0.0.1:8082/docs`
- 人格状态 OpenAPI：`http://127.0.0.1:8083/docs`

也可以手动启动四个进程：

```bash
make run-memory-graph
make run-persona-state
make run-reasoning-orchestrator
make web-build
node tools/serve_web.mjs                          # 4173：/conversation/ 与 /admin/
```

## 4. 演示脚本

1. 打开对话页，输入：`我最近在喝龙井，喜欢清淡的茶。`
2. 第一轮回复会说明尚未找到相关记忆（因为还没写入），随后把这句话写入记忆。
3. 再输入：`我喜欢什么茶？`
4. 第二轮回复会引用“龙井/清淡的茶”，页面下方的“本次回忆”会显示命中的记忆与分数。
5. 打开管理端 → **模型设置**，可保存 Base URL、模型、API Key、温度与最大 tokens。
6. 打开管理端 → **人格/身份层**，修改叙事或特质并保存，会创建新版本；对话端下一回合的 system prompt 立即使用新版本。
7. 打开管理端 → **人格/适应层**，把某维度在 ±0.15 内调整并提交，页面显示新版本与漂移额度。
8. 打开管理端 → **提案审批**：模型在回复中提交的 `<persona_proposal>` 会出现在这里；批准后生成新身份版本，拒绝则仅记录状态。

> 当前嵌入器是 256 维哈希替身，召回是**词面匹配**；演示话术要保留重叠词（如“茶”“龙井”）。真实语义检索需接入 BGE-M3。

## 5. 大模型配置

- 入口：管理端 → 模型设置（菜单权限 `admin-web.llm.manage`）。
- 后端：`PUT /internal/v1/llm/config`（能力 `reasoning-orchestrator.llm.configure.v1`，权限 `reasoning-orchestrator.admin.write`）。
- 持久化：默认 `var/reasoning-orchestrator/llm.json`，文件权限 `0600`；可通过 `HLA_REASONING_ORCHESTRATOR_LLM_CONFIG_PATH` 修改。
- 密钥只写不读：`GET` 只返回 `apiKeySet`，接口与页面都不回显密钥。
- 启用后编排器调用 OpenAI 兼容的 `/chat/completions`；失败回退模板并标记 `LLM_UNAVAILABLE`。
- 管理端通过同源 Web 服务的受限代理访问编排器，浏览器不直连 8081。

配置示例（也可用页面保存）：

```bash
curl -X PUT http://127.0.0.1:4173/internal/orchestrator/llm/config \
  -H 'content-type: application/json' \
  -d '{"enabled":true,"baseUrl":"https://api.openai.com/v1","model":"gpt-4o-mini","apiKey":"sk-...","temperature":0.7,"maxTokens":512}'
```

## 6. 当前已实现

| 能力 | 状态 |
| --- | --- |
| 对话 SSE、逐块 token、done 事件 | 已实现（生成完成后分块，非真实模型流） |
| 记忆检索 + 门控 + “本次回忆” | 已实现 |
| 用户/助手消息写回记忆 | 已实现 |
| 回合状态/审计查询 | 已实现 |
| 幂等键（回合与记忆写入） | 已实现（进程内） |
| 记忆不可用降级 | 已实现（模板回复 + `degraded`） |
| LLM 配置保存/脱敏/文件持久化 | 已实现 |
| LLM 调用失败回退 | 已实现 |
| 管理端 Node 代理 + 对话端 Node 代理 | 已实现 |
| persona-state：身份层读/新版本/回滚 | 已实现（进程内存储；回滚无管理端 UI） |
| persona-state：适应层读/有界更新 | 已实现（乐观锁 + 步长/漂移校验） |
| persona-state：提案创建/列表/审批 | 已实现（批准时生成新版本） |
| 编排器注入 persona 快照 + `personaDegraded` | 已实现 |
| 模型人格标记 → 适应层/提案 | 已实现（`<persona_update>` / `<persona_proposal>`） |
| 管理端身份层/适应层/提案页面 | 已实现（README 与 DESIGN 同步） |
| 端到端：管理端 → 同源代理 → persona-state | 已手工验证（curl，见 §9） |

## 7. 明确未实现/未验证

- persona-state 的经历日志仍是 501；其余人格能力为进程内最小实现，**不是 PostgreSQL**，不满足生产持久化/RLS 要求。
- async-consolidator 仍是 501；没有自动巩固/适应层漂移衰减任务。
- FalkorDB/Neo4j、BGE-M3/HNSW、概念节点、枢纽蒸馏未接入。
- 记忆为进程内存储，重启即丢；重启后记住的内容消失。
- 单租户（开发静态身份 `tenant-dev`）；没有真实服务间认证。
- 回合、审计、幂等、人格状态均为进程内；重启丢失，多副本不一致。
- 真实 LLM 的 token 流式、质量、限流与费用未验证；当前是“非流式生成 + 分块 SSE”。
- 前端只做组件测试与构建，**浏览器端到端未验证**。
- API Key 仅文件 0600 保护，未加密；生产需密钥管理。

## 8. 验证命令

```bash
make test                 # 151 passed（含 persona 14、orchestrator 22、memory 31）
make contracts-check      # 4 个后端 OpenAPI 无漂移
make validate             # 6 modules, 0 issue
make lint
make web-test             # conversation 3、admin 8
make web-build
```

手工 API：

```bash
curl -s http://127.0.0.1:8081/internal/ready
curl -sN -X POST http://127.0.0.1:4173/api/reasoning-orchestrator/v1/turns \
  -H 'content-type: application/json' -H 'Idempotency-Key: demo-1' \
  -d '{"sessionId":"demo","message":"我最近在喝龙井，喜欢清淡的茶。"}'
```

## 9. 重置与排障

- 清空记忆：重启 `memory-graph`（进程内存储）。
- 清空模型配置：删除 `var/reasoning-orchestrator/llm.json`，或在页面关闭启用并保存。
- 端口占用：`4173/8081/8082/8083`；先停旧进程再 `make demo`。
- 人格页 502：确认 `persona-state` 已启动，且 `PERSONA_URL` 指向 8083。
- 人格页 404：确认 `make web-build` 已重新构建（旧 `dist` 没有新页面）。
- 适应层 409：窗口漂移已用尽；等待窗口过期或重启 persona-state（进程内状态清零）。
- 提案批准 409：该提案已审结，不能重复审批。
- 第二轮不召回：确认两轮消息有重叠词；Demo 默认门控 `tau=0.2`，真实嵌入接入后需重新校准。
- 前端 404：确认先执行 `make web-build`，`dist/index.html` 存在。
