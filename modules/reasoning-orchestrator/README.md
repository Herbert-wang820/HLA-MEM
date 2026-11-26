# reasoning-orchestrator

对话编排模块：SSE 回合、记忆检索/写入、门控、模板/LLM 回复、降级与审计。

## 状态

**最小 Demo 已实现（进程内）**。`POST /turns` 会读取 `persona-state` 身份层与适应层拼入 system prompt、检索 `memory-graph`、按阈值门控、生成回复（默认模板，可在管理端配置 OpenAI 兼容模型）、把用户与助手消息写回记忆，并记录回合/审计。

**未实现**：真实 token 流式（当前生成完成后分块）、System-One 分类器、重排、持久化回合/审计、persona 快照本地缓存、多租户服务认证。不能作为生产服务。

人格写通道：解析模型回复中的 `<persona_update>` / `<persona_proposal>` 隐藏标记，剥离后分别调用适应层更新与提案创建；契约见 `contracts/persona-actions.v1.yaml`。身份层永远不会被模型直接写入。

## 运行

```bash
make install
make run-reasoning-orchestrator     # 127.0.0.1:8081
# 或完整 Demo
make web-build && make demo
```

交互式文档：`http://127.0.0.1:8081/docs`（仅 dev）。

## 回合流程

1. 校验 `Idempotency-Key`，创建 `turnId`。
2. 调用 `memory-graph` 检索（默认 800ms 预算）；失败则 `MEMORY_UNAVAILABLE` 降级。
3. 门控：`max(score) + beta×0.05`（若有扩散来源），低于 `tau` 不注入。
4. 取命中情景的摘要，最多 5 条。
5. 生成：管理端启用 LLM 时调用 OpenAI 兼容 `/chat/completions`；未启用或失败则使用确定性模板（失败标记 `LLM_UNAVAILABLE`）。
6. 把用户消息与助手回复写回记忆；失败标记 `MEMORY_WRITE_FAILED`。
7. 发布 `turn.processed` / `turn.degraded`，保存回合与审计。

SSE 事件：

```
event: token   data: {"text":"..."}
event: done    data: {"turnId":"...","degraded":false,"reasons":[],
                      "usedEpisodeIds":["..."],
                      "memories":[{"episodeId":"...","score":0.3,"excerpt":"..."}]}
```

## 端点

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| POST | `/api/reasoning-orchestrator/v1/turns` | 已实现（SSE） |
| GET | `/api/reasoning-orchestrator/v1/turns/{turnId}` | 已实现（进程内） |
| GET | `/api/reasoning-orchestrator/v1/audits/{turnId}` | 已实现（进程内） |
| PUT | `/internal/v1/gate/config` | 已实现（进程内） |
| GET/PUT | `/internal/v1/llm/config` | 已实现（文件持久化，密钥只写不读） |
| GET | `/internal/health` `/internal/ready` `/internal/metrics` | 已实现 |

## 大模型配置

- 管理端“模型设置”通过同源 Web 服务代理调用 `PUT /internal/v1/llm/config`。
- 默认文件：`var/reasoning-orchestrator/llm.json`，权限 `0600`；可用 `HLA_REASONING_ORCHESTRATOR_LLM_CONFIG_PATH` 修改。
- 密钥只写不读；`GET` 只返回 `apiKeySet`。
- 启用但无密钥返回 `REASONING_ORCHESTRATOR_LLM_KEY_REQUIRED`。
- 单进程内存缓存 + 文件持久化；多副本需改用共享配置服务。

## 测试

```bash
make test-module M=reasoning-orchestrator
.venv/bin/pytest modules/reasoning-orchestrator -q
```

16 个测试：SSE/回合/审计、幂等冲突、记忆不可用降级、LLM 失败回退、LLM 配置保存/脱敏、记忆 HTTP 客户端。

## 配置

键前缀 `HLA_REASONING_ORCHESTRATOR_`：

- `MEMORY_BASEURL`（默认 `http://127.0.0.1:8082`）
- `MEMORY_TIMEOUTMS`（800）
- `GATE_TAU`（Demo 0.2；真实嵌入接入后需校准）
- `GATE_BETA`（0.4）
- `RETRIEVAL_TOPK`（8）
- `LLM_CONFIGPATH`、`LLM_BASEURL`、`LLM_MODEL`、`LLM_APIKEY`（敏感）、`LLM_TEMPERATURE`、`LLM_MAXTOKENS`

完整列表见 `internal/settings.py`。
