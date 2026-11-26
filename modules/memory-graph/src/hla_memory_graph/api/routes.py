"""HTTP adapter for memory-graph (Phase 1 vertical slice).

The OpenAPI surface is unchanged from Phase 0; only the 501 placeholders are
replaced by real in-memory implementations.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Request

from hla_host.auth import require_permission
from hla_host.context import Identity
from hla_host.errors import ERROR_RESPONSES
from hla_host.idempotency import request_fingerprint
from hla_memory_graph.api.idempotency import IdempotencyGuard
from hla_memory_graph.api.mappers import to_consolidation, to_episode, to_graph, to_retrieval
from hla_memory_graph.api.schemas import (
    ConsolidationApplyRequest,
    ConsolidationApplyResult,
    Episode,
    EpisodeRetractRequest,
    EpisodeWriteRequest,
    GraphQueryRequest,
    GraphQueryResult,
    RetrievalRequest,
    RetrievalResult,
)
from hla_memory_graph.application.commands import (
    ConsolidationOperation as DomainOperation,
)
from hla_memory_graph.application.commands import WriteEpisodeCommand
from hla_memory_graph.application.service import MemoryService

CAP_EPISODE_WRITE = "memory-graph.episode.write.v1"
CAP_EPISODE_READ = "memory-graph.episode.read.v1"
CAP_EPISODE_RETRACT = "memory-graph.episode.retract.v1"
CAP_RETRIEVE = "memory-graph.episode.retrieve.v1"
CAP_RETRIEVAL_READ = "memory-graph.retrieval.read.v1"
CAP_CONSOLIDATION_APPLY = "memory-graph.consolidation.apply.v1"
CAP_GRAPH_READ = "memory-graph.graph.read.v1"

PERM_EPISODE_READ = "memory-graph.episode.read"
PERM_EPISODE_WRITE = "memory-graph.episode.write"
PERM_RETRIEVAL_READ = "memory-graph.retrieval.read"
PERM_CONSOLIDATION_WRITE = "memory-graph.consolidation.write"
PERM_ADMIN_READ = "memory-graph.admin.read"

OP_WRITE = "episode.write"
OP_RETRACT = "episode.retract"
OP_RETRIEVE = "episode.retrieve"
OP_CONSOLIDATION = "consolidation.apply"

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=200,
        description="Stable key for this non-idempotent operation.",
    ),
]
EpisodeId = Annotated[str, Path(min_length=1, max_length=64)]
RetrievalId = Annotated[str, Path(min_length=1, max_length=64)]

router = APIRouter(prefix="/api/memory-graph/v1", tags=["episodes"])
internal_router = APIRouter(prefix="/internal/v1", tags=["admin"])


def _service(request: Request) -> MemoryService:
    return request.app.state.memory_service


def _guard(request: Request) -> IdempotencyGuard:
    return request.app.state.idempotency_guard


@router.post(
    "/episodes",
    response_model=Episode,
    status_code=201,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_EPISODE_WRITE, "x-permission": PERM_EPISODE_WRITE},
    summary="写入不可变情景节点",
)
async def write_episode(
    payload: EpisodeWriteRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_EPISODE_WRITE))],
    idempotency_key: IdempotencyKey,
) -> Episode:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_WRITE, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_WRITE, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, Episode)
        if cached is not None:
            return cached
        record = await _service(request).write_episode(
            identity.tenant_id,
            WriteEpisodeCommand(
                session_id=payload.session_id,
                content=payload.content,
                occurred_at=payload.occurred_at,
                source=payload.source,
                metadata=payload.metadata,
            ),
        )
        episode = to_episode(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_WRITE,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=201,
            value=episode,
        )
        return episode


@router.get(
    "/episodes/{episode_id}",
    response_model=Episode,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_EPISODE_READ, "x-permission": PERM_EPISODE_READ},
    summary="读取单个情景节点",
)
async def read_episode(
    episode_id: EpisodeId,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_EPISODE_READ))],
) -> Episode:
    record = await _service(request).get_episode(identity.tenant_id, episode_id)
    return to_episode(record)


@router.post(
    "/episodes/{episode_id}/retract",
    response_model=Episode,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_EPISODE_RETRACT, "x-permission": PERM_EPISODE_WRITE},
    summary="追加撤回标记（不修改原文）",
)
async def retract_episode(
    episode_id: EpisodeId,
    payload: EpisodeRetractRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_EPISODE_WRITE))],
    idempotency_key: IdempotencyKey,
) -> Episode:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_RETRACT, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_RETRACT, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, Episode)
        if cached is not None:
            return cached
        record = await _service(request).retract_episode(
            identity.tenant_id,
            episode_id,
            payload.reason_code,
            payload.note,
        )
        episode = to_episode(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_RETRACT,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=200,
            value=episode,
        )
        return episode


@router.post(
    "/retrievals",
    response_model=RetrievalResult,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_RETRIEVE, "x-permission": PERM_EPISODE_READ},
    summary="双路径检索（语义 + 扩散）",
)
async def retrieve(
    payload: RetrievalRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_EPISODE_READ))],
    idempotency_key: IdempotencyKey,
) -> RetrievalResult:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_RETRIEVE, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_RETRIEVE, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, RetrievalResult)
        if cached is not None:
            return cached
        audit = await _service(request).retrieve(
            identity.tenant_id,
            query=payload.query,
            top_k=payload.top_k,
            semantic_top_k=payload.semantic_top_k,
            spreading_top_k=payload.spreading_top_k,
            as_of=payload.as_of,
        )
        result = to_retrieval(audit)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_RETRIEVE,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=200,
            value=result,
        )
        return result


@router.get(
    "/retrievals/{retrieval_id}",
    response_model=RetrievalResult,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_RETRIEVAL_READ, "x-permission": PERM_RETRIEVAL_READ},
    summary="读取检索审计记录",
)
async def read_retrieval(
    retrieval_id: RetrievalId,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_RETRIEVAL_READ))],
) -> RetrievalResult:
    audit = await _service(request).get_retrieval(identity.tenant_id, retrieval_id)
    return to_retrieval(audit)


@internal_router.post(
    "/graph/query",
    response_model=GraphQueryResult,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_GRAPH_READ, "x-permission": PERM_ADMIN_READ},
    summary="管理端受限只读图查询",
)
async def query_graph(
    payload: GraphQueryRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_ADMIN_READ))],
) -> GraphQueryResult:
    view = await _service(request).query_graph(
        identity.tenant_id,
        node_types=payload.node_types,
        filters=payload.filters,
        depth=payload.depth,
        limit=payload.limit,
    )
    return to_graph(view)


@internal_router.post(
    "/consolidation/apply",
    response_model=ConsolidationApplyResult,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_CONSOLIDATION_APPLY, "x-permission": PERM_CONSOLIDATION_WRITE},
    summary="应用共激活边权/遗忘/蒸馏批次",
)
async def apply_consolidation(
    payload: ConsolidationApplyRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_CONSOLIDATION_WRITE))],
    idempotency_key: IdempotencyKey,
) -> ConsolidationApplyResult:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_CONSOLIDATION, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_CONSOLIDATION, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, ConsolidationApplyResult)
        if cached is not None:
            return cached
        outcome = await _service(request).apply_consolidation(
            identity.tenant_id,
            batch_id=payload.batch_id,
            job_id=payload.job_id,
            operations=[
                DomainOperation(
                    operation=operation.operation,
                    edge_id=operation.edge_id,
                    source_episode_id=operation.source_episode_id,
                    target_episode_id=operation.target_episode_id,
                    episode_id=operation.episode_id,
                    hub_id=operation.hub_id,
                    weight_delta=operation.weight_delta,
                )
                for operation in payload.operations
            ],
        )
        result = to_consolidation(outcome)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_CONSOLIDATION,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=200,
            value=result,
        )
        return result

