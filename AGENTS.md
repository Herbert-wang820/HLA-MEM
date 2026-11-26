# 仓库级协作约束（AGENTS.md）

本文件约束在本仓库工作的 AI 与人类协作者。每个模块还有自己的 `modules/{module-id}/AGENTS.md`，两者叠加生效；模块文件可以更严格，但不能放宽本文件与《模块开发契约》。

## 1. 开始前必读

1. `模块开发契约.md`：模块治理、目录、清单、接口、事件、数据所有权、安全、验收的**规则来源**。
2. `HLM-MEM开发计划.md`：业务架构、阶段、量化门槛的**目标来源**。
3. `docs/contract-alignment.md`：两份文档的差异归一与已采纳决策（ADR-000）。
4. 目标模块的 `AGENTS.md`、`DESIGN.md`、`module.yaml` 与 `contracts/`。

两者冲突时：治理规则以契约为准，业务目标与量化指标以计划为准；命名/职责冲突以 `docs/contract-alignment.md` 为准。新增冲突必须先改文档，再改代码。

## 2. 工程原则

- **契约先行**：先改 `module.yaml`、`contracts/openapi.yaml`、事件 Schema、权限清单，再改实现。破坏性变更升主版本并给迁移期。
- **可独立构建/测试**：模块不得依赖先构建其他业务模块。测试中的外部依赖用替身，替身只存在于测试代码。
- **依赖单向**：`api → application → domain`；`infrastructure` 实现端口；`domain` 不依赖 FastAPI、数据库驱动、消息客户端或网络库。
- **数据自持**：不跨模块读库、建外键/视图/Join；跨模块只走版本化能力或事件。
- **配置外置**：配置与密钥不写死；配置键加模块前缀并登记类型、默认值、敏感标记。
- **可观测**：每个后端模块保留 `/internal/health`、`/internal/ready`、`/internal/metrics`，日志为结构化 JSON。
- **租户可信**：`tenantId` 只来自宿主身份上下文；禁止从 query、body、普通请求头读取或覆盖。

## 3. 目录与命名

- 模块目录 kebab-case；Python 包 snake_case，统一 `hla_` 前缀（如 `hla_memory_graph`）。
- 能力：`{module-id}.{domain}.{action}.v{major}`；事件：`{module-id}.{aggregate}.{past-tense}.v{major}`；权限：`{module-id}.{resource}.{action}`。
- 模块 ID、能力名、事件类型、权限 ID、菜单 ID 发布后保持稳定；更名需新建并迁移。
- 错误码：`{MODULE}_{DOMAIN}_{REASON}`（大写、下划线），不把堆栈、SQL、内部地址返回客户端。

## 4. 常用命令

```bash
make install            # 安装共享包与后端模块（editable）
make validate           # 契约/清单/命名校验
make lint               # ruff
make test               # 全部 Python 测试
make test-module M=memory-graph
make contracts          # 由 FastAPI 重新生成 contracts/openapi.yaml
make contracts-check    # CI 用：检查 OpenAPI 漂移
make catalog            # 重新生成 docs/module-catalog.md
make web-test           # 两个前端组件测试
make web-build          # 两个前端生产构建
make demo               # 启动最小可用 Demo（需先 web-build）
make build              # compileall + wheel
make run-memory-graph   # 启动单模块
```

## 5. 禁止项

- 禁止模块间 `import` 对方内部包、直连对方数据库、共享事务或连接池。
- 禁止把其他业务模块声明为 `requires.mandatory`；必选依赖只能是宿主基础能力。
- 禁止在日志、事件、错误响应、前端缓存中写入凭据、完整个人数据、记忆原文或内部地址。
- 禁止用前端隐藏/禁用代替后端鉴权；未知入口与未知权限默认拒绝。
- 禁止为了「接口路径没变」而删除校验、放宽范围或添加通配权限。
- 禁止把设计、占位实现、测试替身描述为「已实现」或「已验证」。

## 6. 完成定义（Definition of Done）

一个模块变更只有在以下全部满足时才可合入：

1. `make validate`、`make contracts-check`、`make lint` 通过。
2. 该模块单元/契约测试通过；涉及事件、幂等、降级路径的变更补齐对应测试。
3. 新增/修改的能力、事件、权限、配置、迁移同步到 `module.yaml`、`DESIGN.md`、`contracts/`。
4. 报告明确区分**已实现 / 仅声明 / 未验证**，并列出未验证项的原因（如缺少 Docker、模型权重或宿主能力）。
