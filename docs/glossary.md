# 领域术语表

| 术语 | 英文/标识 | 含义 |
| --- | --- | --- |
| 情景 | Episode | 一次对话/事件的最小不可变记忆单元；只增不改，更正通过新增 + `retracted` 标记 |
| 概念 | Concept | 由多个情景蒸馏出的语义节点；用于压缩记忆图 |
| 共激活 | CO_ACTIVATED | 同一检索批次中被共同命中的情景之间的带权边；权重归一化到 `[0,1]` |
| 扩散激活 | Spreading activation | 从语义种子沿 `CO_ACTIVATED` 边扩散，寻找关联记忆的检索路径 |
| 枢纽蒸馏 | Hub distillation | 连接度高且簇规模达标的节点被蒸馏为概念，压缩图规模 |
| 遗忘 | Forgetting | 对长时间未强化且权重低于阈值的边降权/移除；必选模块，不是可选优化 |
| System-One | 快思考 | 本地轻量门控，判断回合能否走快路径；决策 ≤ 15ms，不调用 LLM |
| System-Two | 慢思考 | 完整生成路径；只做生成，不逐条筛选记忆 |
| 门控 | Gate | System-One 的判定器；规则 + 可替换轻量分类器；命中率是一阶指标 |
| 快路径 | Fast path | 不触发图检索与完整 System-Two 生成的回合路径；目标 P50 ≤ 400ms |
| 慢路径 | Slow path | 触发双路径检索、重排序与完整生成的回合路径；目标 P50 ≤ 1.2s / P95 ≤ 2.5s |
| 检索预算 | Retrieval budget | 编排器分配给语义/扩散路径的候选上限与 Top-K；合并后 K ≤ 50 |
| 重排序 | Reranking | 用轻量模型把 Top-20 收敛到 Top-5；不得由大模型逐条承担 |
| 工作记忆 | Working memory | 当前会话的短期上下文，不属于长期记忆图 |
| 身份层 | Identity layer | 人格的稳定层；版本化、人工/审批变更、禁止自动写入 |
| 适应层 | Adaptation layer | 人格的可变层；由巩固有界更新，单次变化 ≤ `adaptation_step_max` |
| 人格动作标记 | Persona action marker | 模型回复中的 `<persona_update>` / `<persona_proposal>` 隐藏标记；编排器剥离后调用 persona-state，不进入可见文本 |
| 人格快照 | Persona snapshot | 编排器读取的只读身份摘要；人格不可用时使用带 TTL 的最近一次快照并标记 `personaDegraded` |
| 身份变更提案 | Identity proposal | 适应层同方向变化累计达阈值后创建的人工审批项；不是自动写身份层 |
| 经历日志 | Experience log | 只追加、不可删除的人格经历时间线；支持完整回放与导出 |
| 巩固 | Consolidation | 异步后台过程：边权更新、遗忘、枢纽蒸馏、适应层更新、proposal 创建 |
| 巩固作业 | Consolidation job | 持久化、幂等、可重试的异步工作单元；携带 `jobId` + `idempotencyKey` |
| 死信 | Dead letter | 超过重试上限或永久失败的作业记录；可查询、可审计、可重放 |
| 检索审计 | Retrieval audit | 记录门控、预算、双路径候选、重排、最终提示引用的可回放证据 |
| 回合 | Turn | 一次用户输入到系统完整响应的处理单元；有 `turnId` |
| 降级 | Degradation | 依赖故障时按声明策略继续提供受限功能；不绕过授权、不伪造成功 |
| 租户 | Tenant | 数据隔离边界；`tenantId` 只来自宿主可信身份上下文 |
| 能力 | Capability | 跨模块依赖的版本化名称：`{module}.{domain}.{action}.v{major}` |
| 事件信封 | Event envelope | 统一事件外层：`specVersion/id/type/source/subject/time/tenantId/dataVersion/data/...` |
| Outbox | 事务外盒 | 业务事务提交后可靠发布事件的机制，避免“事件已发、数据未落库” |
| 幂等键 | Idempotency-Key | 非幂等动作的请求去重键；作用域为 主体+租户+操作+请求摘要 |
| 乐观锁 | Optimistic lock | 用 `version`/`expectedVersion` 防止并发覆盖；冲突返回 409 |
| 投影 | Projection | 从其他模块事件/接口同步来的只读副本；必须标注来源、源版本、同步时间 |
| 契约漂移 | Contract drift | 实现生成的 OpenAPI 与提交的 `contracts/openapi.yaml` 不一致；CI 直接失败 |
