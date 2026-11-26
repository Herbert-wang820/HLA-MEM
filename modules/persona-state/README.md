# persona-state

人格状态模块：版本化身份层、有界适应层、变更提案与经历日志。

## 状态

**最小实现（进程内存储）**。身份层读取/新版本/回滚、适应层读取/有界更新、提案创建/列表/审批已实现；
经历日志仍返回 `501`。**没有 PostgreSQL 连接、迁移或 RLS**，数据随进程重启丢失，不能当作生产人格服务。

## 本地运行

```bash
make install
python -m hla_persona_state        # 127.0.0.1:8083
make run-persona-state
```

开发模式使用静态身份与 `internal/settings.py` 中的 `DEV_PERMISSIONS`；非 dev 环境必须注入真实 `host.auth.identity.v1` 适配器，否则启动失败。

## 端点

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| GET | `/internal/health` `/internal/ready` `/internal/metrics` | 已实现 |
| GET | `/api/persona-state/v1/identity` | 已实现（内存） |
| POST | `/api/persona-state/v1/identity/versions` | 已实现（内存、幂等、只追加） |
| POST | `/api/persona-state/v1/identity/rollback` | 已实现（创建新版本，历史保留） |
| GET | `/api/persona-state/v1/adaptation` | 已实现（内存） |
| PATCH | `/api/persona-state/v1/adaptation` | 已实现（乐观锁 + 步长/窗口漂移上限） |
| POST/GET | `/api/persona-state/v1/proposals` | 已实现（创建幂等、游标分页） |
| POST | `/api/persona-state/v1/proposals/{id}/review` | 已实现（批准生成新版本、不可重复审结） |
| GET/POST | `/api/persona-state/v1/experiences` | 仅声明（501） |

OpenAPI：`contracts/openapi.yaml`（`make contracts` 生成）。交互式文档：`http://127.0.0.1:8083/docs`（仅 dev）。

## 模型可发起的人格修改

编排器把模型回复中的隐藏标记转为本模块的能力调用（契约见
`modules/reasoning-orchestrator/contracts/persona-actions.v1.yaml`）：

- `<persona_update>` → `PATCH /adaptation`：直接生效，受 `maxDelta`/`maxDrift`/`expectedVersion` 约束。
- `<persona_proposal>` → `POST /proposals`：只创建 `pending` 提案，审批通过后才生成身份版本。

模型永远不能直接调用 `POST /identity/versions`。

## 测试

```bash
make test-module M=persona-state
.venv/bin/pytest modules/persona-state -q
```

覆盖：健康/就绪/指标、身份版本与幂等重放、回滚保留历史、适应层乐观锁/步长/漂移、
提案创建-审批-重复审结 409、缺失幂等键 422、请求体携带租户 422、404 错误信封、
契约清洁、OpenAPI 能力覆盖、事件 Schema 校验。

## 配置

键前缀 `HLA_PERSONA_STATE_`，例如 `HLA_PERSONA_STATE_DB_DSN`（敏感，尚未使用）、
`HLA_PERSONA_STATE_ADAPTATION_MAXDELTA`。完整列表见 `internal/settings.py`。
当前实现不建立数据库连接；`DB_DSN` 仅为阶段 2 预留。
