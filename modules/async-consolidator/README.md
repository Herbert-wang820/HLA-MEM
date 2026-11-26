# async-consolidator

异步巩固模块：作业队列、重试/死信、边权强化、遗忘与枢纽蒸馏调度。

## 状态

**阶段 0（契约与骨架）**。6 个能力已声明并进入 OpenAPI；业务端点返回 `501`，没有 PostgreSQL 连接、队列或 worker。

## 本地运行

```bash
make install
python -m hla_consolidator          # 127.0.0.1:8084
make run-async-consolidator
```

开发模式使用静态身份与 `DEV_PERMISSIONS`；非 dev 必须注入真实身份与事件总线适配器。

## 端点

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| GET | `/internal/health` `/internal/ready` `/internal/metrics` | 已实现 |
| POST | `/api/async-consolidator/v1/jobs` | 仅声明（501；契约成功码 202） |
| GET | `/api/async-consolidator/v1/jobs` | 仅声明（501） |
| GET | `/api/async-consolidator/v1/jobs/{jobId}` | 仅声明（501） |
| POST | `/api/async-consolidator/v1/jobs/{jobId}/retry` | 仅声明（501） |
| GET | `/api/async-consolidator/v1/dead-letters` | 仅声明（501） |
| POST | `/api/async-consolidator/v1/dead-letters/{id}/replay` | 仅声明（501） |
| GET | `/internal/v1/backlog` | 仅声明（501） |

OpenAPI：`contracts/openapi.yaml`。交互式文档：`http://127.0.0.1:8084/docs`（仅 dev）。

## 测试

```bash
make test-module M=async-consolidator
.venv/bin/pytest modules/async-consolidator -q
```

覆盖：健康/就绪/指标、501 占位、缺失幂等键 422、请求体携带租户 422、404 错误信封、契约清洁、OpenAPI 能力覆盖、事件 Schema 校验。

## 配置

键前缀 `HLA_ASYNC_CONSOLIDATOR_`，例如 `HLA_ASYNC_CONSOLIDATOR_DB_DSN`（敏感）、`HLA_ASYNC_CONSOLIDATOR_QUEUE_MAXATTEMPTS`、`HLA_ASYNC_CONSOLIDATOR_MEMORY_BASEURL`。完整列表见 `internal/settings.py`。
