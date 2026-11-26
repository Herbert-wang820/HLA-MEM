# memory-graph

记忆图模块：不可变情景、概念、共激活边与双路径检索。

## 状态

**阶段 1（内存纵向切片）**。7 个能力已用进程内适配器实现：写入/读取/撤回、双路径检索、审计、共激活、结构化图查询、边权强化/遗忘，并有 31 个模块测试。

**未实现**：FalkorDB/Neo4j、BGE-M3/HNSW、概念节点、枢纽蒸馏、跨进程持久化、真实宿主身份。数据在进程重启后丢失，嵌入器只是确定性替身，不代表语义质量；不要把它当作生产记忆服务。

## 本地运行

```bash
# 在仓库根目录
make install
python -m hla_memory_graph          # 监听 127.0.0.1:8082
# 或
make run-memory-graph
```

开发模式（`HLA_ENV=dev`，默认）使用静态身份，权限来自 `internal/settings.py` 的 `DEV_PERMISSIONS`；生产必须注入真实的 `host.auth.identity.v1` 适配器，否则启动失败。

## 端点

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| GET | `/internal/health` | 已实现（存活） |
| GET | `/internal/ready` | 已实现（配置就绪） |
| GET | `/internal/metrics` | 已实现（Prometheus 文本） |
| POST | `/api/memory-graph/v1/episodes` | 已实现（内存，需幂等键） |
| GET | `/api/memory-graph/v1/episodes/{episodeId}` | 已实现（内存） |
| POST | `/api/memory-graph/v1/episodes/{episodeId}/retract` | 已实现（追加标记） |
| POST | `/api/memory-graph/v1/retrievals` | 已实现（语义 + 扩散） |
| GET | `/api/memory-graph/v1/retrievals/{retrievalId}` | 已实现（审计） |
| POST | `/internal/v1/graph/query` | 已实现（结构化、无 Cypher） |
| POST | `/internal/v1/consolidation/apply` | 已实现（reinforce/forget；distill 跳过） |

OpenAPI：`contracts/openapi.yaml`（由 `make contracts` 生成，CI 检查漂移）。  
交互式文档：`http://127.0.0.1:8082/docs`（仅 dev）。

## 测试

```bash
make test-module M=memory-graph
# 或
.venv/bin/pytest modules/memory-graph -q
```

覆盖：健康/就绪/指标、请求 ID、缺失幂等键 422、请求体携带租户 422、路由 404、写入/读取/撤回、幂等冲突、双路径检索与审计、asOf 可见性、共激活边、图查询、强化/遗忘、批次幂等、租户隔离、事件发布、契约清洁、OpenAPI 能力覆盖、事件 Schema。

## 结构

```
src/hla_memory_graph/
  api/            # FastAPI 路由与 DTO
  application/    # 用例（阶段 1）
  domain/         # 纯领域模型与算法（阶段 1）
  infrastructure/ # 图库/向量/事件适配器（阶段 1）
  internal/       # 模块私有配置
  app.py          # 应用工厂
  __main__.py     # uvicorn 入口
contracts/        # OpenAPI、权限、事件 Schema
```

## 配置

所有键以 `HLA_MEMORY_GRAPH_` 开头，例如 `HLA_MEMORY_GRAPH_STORE_DSN`、`HLA_MEMORY_GRAPH_RETRIEVAL_TOPKMAX`、`HLA_MEMORY_GRAPH_EMBEDDING_DIM`。完整列表见 `internal/settings.py`。当前始终使用进程内存储与哈希嵌入器，不连接外部图库。
