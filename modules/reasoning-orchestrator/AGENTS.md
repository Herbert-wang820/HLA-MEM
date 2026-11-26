# reasoning-orchestrator 模块协作约束

本文件在仓库根 `AGENTS.md` 之上叠加，**只加严，不放宽**。

## 1. 职责边界

- 拥有：对话回合状态机、System-One/Two 门控、记忆检索编排、人格快照获取、降级决策、回合审计。
- 不拥有：记忆图存储（`memory-graph`）、人格数据（`persona-state`）、巩固队列（`async-consolidator`）。
- 只通过版本化能力调用上述模块；禁止导入其内部包或直连其数据库。

## 2. 不可破坏的规则

1. **降级显式**：任何依赖失败都必须返回 `degraded=true` 或 503，并记录原因；禁止用空记忆/默认人格伪装成功。
2. **预算硬限制**：memory 800ms、persona 500ms、LLM 20s；SSE 空闲 120s；超时必须触发降级或终止，不得无限等待。
3. **租户可信**：`tenantId` 只来自 `Identity`；请求体携带租户必须 422。
4. **幂等**：回合创建必须带 `Idempotency-Key`；重复请求返回同一终态，不得产生第二个回合。
5. **不记录原文**：日志/指标/审计不写用户消息与记忆原文；只存 ID、分数、耗时、长度。
6. **门控可解释**：每次使用记忆都要记录门控分数、阈值、候选数与实际使用 ID；禁止“黑盒注入”。
7. **SSE 安全**：事件类型与字段稳定；错误通过 `error` 事件返回错误码，不泄露堆栈/内部地址。

## 3. 最小 Demo 状态

- 已实现：SSE 回合、记忆检索/写入、门控阈值、回合/审计查询、模板回复、LLM 配置读取/保存、LLM 失败回退。
- 已实现：persona-state 人格快照注入（身份层 + 适应层）、模型隐藏标记
  `<persona_update>` / `<persona_proposal>` 剥离与落地、`personaDegraded` 显式降级、
  SSE `done.persona` 元数据。
- 未实现：真实 token 流式、System-One 分类器、重排、持久化回合/审计；persona 快照无 TTL 缓存，
  依赖失败时直接用静态兜底叙事并标记降级。不得宣称生产可用。
- 模型可发起的人格修改契约见 `contracts/persona-actions.v1.yaml`（已登记的 module.yaml `contracts.personaActions`）。

## 3.1 人格写路径约束

1. 模型只能通过隐藏标记发起；编排器在进入 SSE/落库前必须完成剥离，漏剥即视为缺陷。
2. 适应层写入必须携带快照中的 `adaptationVersion` 作为 `expectedVersion`；409/422 一律标记
   `PERSONA_UPDATE_REJECTED`，不得静默重试或截断 delta。
3. 身份层只能 `proposal.create`；禁止在编排器内调用 `identity.version.create.v1`。
4. persona-state 不可用时：仍剥离标记、保留模板回复、设置 `personaDegraded=true` 与 `PERSONA_UNAVAILABLE`。
5. 默认无大模型，使用确定性模板；配置保存在本机 `var/reasoning-orchestrator/llm.json`（0600），密钥只写不读。
6. 单租户开发身份；跨模块认证、多租户传播未验证。

## 4. 命令

```bash
make install
make test-module M=reasoning-orchestrator
make contracts
make validate
make run-reasoning-orchestrator
```

## 5. 评审关注点

- 门控分数是否校准？阈值变更是否有审计与回滚？
- 记忆不可用时是否仍能给出有用回复，同时明确告知降级？
- SSE 断连、客户端取消、超时是否释放资源？
- 回合审计是否足以复现一次决策（不含原文）？
