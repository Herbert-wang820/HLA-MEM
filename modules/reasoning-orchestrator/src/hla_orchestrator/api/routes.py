"""HTTP adapter for reasoning-orchestrator.

The demo implements a real SSE turn path, memory retrieval/write and a
file-backed LLM configuration.  Token events are chunked after generation;
true token streaming is recorded as a follow-up optimization.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Request
from fastapi.responses import StreamingResponse

from hla_host.auth import require_permission
from hla_host.context import Identity
from hla_host.errors import ERROR_RESPONSES, ModuleError
from hla_orchestrator.api.mappers import to_audit, to_gate, to_llm_view, to_turn
from hla_orchestrator.api.schemas import (
    GateConfig,
    GateConfigUpdate,
    LLMConfigUpdate,
    LLMConfigView,
    Turn,
    TurnAudit,
    TurnCreateRequest,
)
from hla_orchestrator.application.service import TurnService
from hla_orchestrator.infrastructure.llm_config import LLMConfigStore

CAP_TURN_PROCESS = "reasoning-orchestrator.turn.process.v1"
CAP_TURN_READ = "reasoning-orchestrator.turn.read.v1"
CAP_AUDIT_READ = "reasoning-orchestrator.audit.read.v1"
CAP_GATE_CONFIGURE = "reasoning-orchestrator.gate.configure.v1"
CAP_LLM_CONFIGURE = "reasoning-orchestrator.llm.configure.v1"

PERM_TURN_CREATE = "reasoning-orchestrator.turn.create"
PERM_TURN_READ = "reasoning-orchestrator.turn.read"
PERM_AUDIT_READ = "reasoning-orchestrator.audit.read"
PERM_ADMIN_WRITE = "reasoning-orchestrator.admin.write"

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200, description="Stable key for this turn."),
]
TurnId = Annotated[str, Path(min_length=1, max_length=64)]

router = APIRouter(prefix="/api/reasoning-orchestrator/v1", tags=["turns"])
internal_router = APIRouter(prefix="/internal/v1", tags=["admin"])

SSE_RESPONSES = {
    200: {
        "description": "Server-sent events: token deltas, then a final done event.",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    },
    **ERROR_RESPONSES,
}


def _service(request: Request) -> TurnService:
    return request.app.state.turn_service


def _config_store(request: Request) -> LLMConfigStore:
    return request.app.state.llm_store


def _chunks(text: str, size: int = 24) -> AsyncIterator[str]:
    for index in range(0, len(text), size):
        yield text[index : index + size]


@router.post(
    "/turns",
    response_class=StreamingResponse,
    responses=SSE_RESPONSES,
    openapi_extra={"x-capability": CAP_TURN_PROCESS, "x-permission": PERM_TURN_CREATE},
    summary="处理一个对话回合（SSE 流式）",
)
async def process_turn(
    payload: TurnCreateRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_TURN_CREATE))],
    idempotency_key: IdempotencyKey,
) -> StreamingResponse:
    outcome = await _service(request).process(
        session_id=payload.session_id,
        message=payload.message,
        subject=identity.subject,
        tenant_id=identity.tenant_id,
        idempotency_key=idempotency_key,
        request_id=getattr(request.state, "request_id", None),
    )

    async def event_stream() -> AsyncIterator[str]:
        for chunk in _chunks(outcome.text):
            yield f"event: token\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        done = {
            "turnId": outcome.turn_id,
            "degraded": outcome.status == "degraded",
            "reasons": list(outcome.reasons),
            "usedEpisodeIds": [hit.episode_id for hit in outcome.memories],
            "memories": [
                {"episodeId": hit.episode_id, "score": hit.score, "excerpt": hit.excerpt}
                for hit in outcome.memories
            ],
            "persona": {
                "identityVersion": outcome.persona_version,
                "adaptationVersion": outcome.adaptation_version,
                "updated": outcome.persona_updated,
                "degraded": outcome.persona_degraded,
                "identityProposalId": outcome.identity_proposal_id,
            },
        }
        yield f"event: done\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/turns/{turn_id}",
    response_model=Turn,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_TURN_READ, "x-permission": PERM_TURN_READ},
    summary="读取回合状态",
)
async def read_turn(
    turn_id: TurnId,
    request: Request,
    _identity: Annotated[Identity, Depends(require_permission(PERM_TURN_READ))],
) -> Turn:
    return to_turn(await _service(request).get_turn(turn_id))


@router.get(
    "/audits/{turn_id}",
    response_model=TurnAudit,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_AUDIT_READ, "x-permission": PERM_AUDIT_READ},
    summary="读取回合的门控与检索审计",
)
async def read_audit(
    turn_id: TurnId,
    request: Request,
    _identity: Annotated[Identity, Depends(require_permission(PERM_AUDIT_READ))],
) -> TurnAudit:
    return to_audit(await _service(request).get_audit(turn_id))


@internal_router.put(
    "/gate/config",
    response_model=GateConfig,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_GATE_CONFIGURE, "x-permission": PERM_ADMIN_WRITE},
    summary="更新门控阈值与校准参数",
)
async def update_gate_config(
    payload: GateConfigUpdate,
    request: Request,
    _identity: Annotated[Identity, Depends(require_permission(PERM_ADMIN_WRITE))],
) -> GateConfig:
    gate = request.app.state.gate_settings
    gate.tau = payload.tau
    gate.beta = payload.beta
    gate.top_k = payload.top_k
    gate.calibrator = payload.calibrator
    gate.updated_at = datetime.now(UTC)
    return to_gate(gate, gate.updated_at)


@internal_router.get(
    "/llm/config",
    response_model=LLMConfigView,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_LLM_CONFIGURE, "x-permission": PERM_ADMIN_WRITE},
    summary="读取大模型配置（不返回密钥）",
)
async def read_llm_config(
    request: Request,
    _identity: Annotated[Identity, Depends(require_permission(PERM_ADMIN_WRITE))],
) -> LLMConfigView:
    return to_llm_view(await _config_store(request).get())


@internal_router.put(
    "/llm/config",
    response_model=LLMConfigView,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_LLM_CONFIGURE, "x-permission": PERM_ADMIN_WRITE},
    summary="保存大模型配置（密钥只写不读）",
)
async def update_llm_config(
    payload: LLMConfigUpdate,
    request: Request,
    _identity: Annotated[Identity, Depends(require_permission(PERM_ADMIN_WRITE))],
) -> LLMConfigView:
    store = _config_store(request)
    current = await store.get()
    effective_key = payload.api_key if payload.api_key is not None else current.api_key
    if payload.enabled and not effective_key.strip():
        raise ModuleError(
            "REASONING_ORCHESTRATOR_LLM_KEY_REQUIRED",
            "apiKey is required when the LLM is enabled",
            422,
            details={"field": "apiKey"},
        )
    config = await store.update(
        enabled=payload.enabled,
        base_url=payload.base_url,
        model=payload.model,
        api_key=payload.api_key,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    return to_llm_view(config)
