"""HTTP adapter for persona-state.

Identity/adaptation and the proposal workflow are implemented; experience
logging remains a declared Phase 0 capability.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request

from hla_host.auth import require_permission
from hla_host.context import Identity
from hla_host.errors import ERROR_RESPONSES, FeatureNotImplementedError
from hla_host.idempotency import request_fingerprint
from hla_persona_state.api.idempotency import IdempotencyGuard
from hla_persona_state.api.mappers import to_adaptation, to_identity, to_proposal
from hla_persona_state.api.schemas import (
    Adaptation,
    AdaptationUpdateRequest,
    Experience,
    ExperienceAppendRequest,
    ExperiencePage,
    IdentityRollbackRequest,
    IdentityVersionCreateRequest,
    PersonaIdentity,
    Proposal,
    ProposalCreateRequest,
    ProposalPage,
    ProposalReviewRequest,
)
from hla_persona_state.application.service import PersonaService
from hla_persona_state.domain.models import Trait
from hla_persona_state.internal.settings import MODULE_ID

CAP_IDENTITY_READ = "persona-state.identity.read.v1"
CAP_IDENTITY_VERSION = "persona-state.identity.version.create.v1"
CAP_IDENTITY_ROLLBACK = "persona-state.identity.rollback.v1"
CAP_ADAPTATION_READ = "persona-state.adaptation.read.v1"
CAP_ADAPTATION_UPDATE = "persona-state.adaptation.update.v1"
CAP_PROPOSAL_CREATE = "persona-state.proposal.create.v1"
CAP_PROPOSAL_READ = "persona-state.proposal.read.v1"
CAP_PROPOSAL_REVIEW = "persona-state.proposal.review.v1"
CAP_EXPERIENCE_APPEND = "persona-state.experience.append.v1"
CAP_EXPERIENCE_READ = "persona-state.experience.read.v1"

PERM_IDENTITY_READ = "persona-state.identity.read"
PERM_IDENTITY_WRITE = "persona-state.identity.write"
PERM_IDENTITY_ROLLBACK = "persona-state.identity.rollback"
PERM_ADAPTATION_READ = "persona-state.adaptation.read"
PERM_ADAPTATION_WRITE = "persona-state.adaptation.write"
PERM_PROPOSAL_CREATE = "persona-state.proposal.create"
PERM_PROPOSAL_READ = "persona-state.proposal.read"
PERM_PROPOSAL_REVIEW = "persona-state.proposal.review"
PERM_EXPERIENCE_APPEND = "persona-state.experience.append"
PERM_EXPERIENCE_READ = "persona-state.experience.read"

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200, description="Stable key for this write."),
]
ProposalId = Annotated[str, Path(min_length=1, max_length=64)]
Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=100)]

OP_IDENTITY_VERSION = "identity.version.create"
OP_IDENTITY_ROLLBACK = "identity.rollback"
OP_PROPOSAL_CREATE = "proposal.create"

router = APIRouter(prefix="/api/persona-state/v1", tags=["persona"])


def _service(request: Request) -> PersonaService:
    return request.app.state.persona_service


def _guard(request: Request) -> IdempotencyGuard:
    return request.app.state.idempotency_guard


def _not_implemented(capability: str):
    raise FeatureNotImplementedError(MODULE_ID, capability)


@router.get(
    "/identity",
    response_model=PersonaIdentity,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_IDENTITY_READ, "x-permission": PERM_IDENTITY_READ},
    summary="读取当前身份层",
)
async def read_identity(
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_IDENTITY_READ))],
) -> PersonaIdentity:
    return to_identity(await _service(request).get_identity(identity.tenant_id))


@router.post(
    "/identity/versions",
    response_model=PersonaIdentity,
    status_code=201,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_IDENTITY_VERSION, "x-permission": PERM_IDENTITY_WRITE},
    summary="创建新的身份层版本",
)
async def create_identity_version(
    payload: IdentityVersionCreateRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_IDENTITY_WRITE))],
    idempotency_key: IdempotencyKey,
) -> PersonaIdentity:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_IDENTITY_VERSION, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_IDENTITY_VERSION, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, PersonaIdentity)
        if cached is not None:
            return cached
        record = await _service(request).create_identity_version(
            identity.tenant_id,
            subject=identity.subject,
            traits=[Trait(trait=item.trait, value=item.value, confidence=item.confidence) for item in payload.traits],
            narrative=payload.narrative,
            reason=payload.change_reason,
        )
        response = to_identity(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_IDENTITY_VERSION,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=201,
            value=response,
        )
        return response


@router.post(
    "/identity/rollback",
    response_model=PersonaIdentity,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_IDENTITY_ROLLBACK, "x-permission": PERM_IDENTITY_ROLLBACK},
    summary="回滚到历史身份版本",
)
async def rollback_identity(
    payload: IdentityRollbackRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_IDENTITY_ROLLBACK))],
    idempotency_key: IdempotencyKey,
) -> PersonaIdentity:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_IDENTITY_ROLLBACK, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_IDENTITY_ROLLBACK, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, PersonaIdentity)
        if cached is not None:
            return cached
        record = await _service(request).rollback_identity(
            identity.tenant_id,
            subject=identity.subject,
            target_version=payload.target_version,
            reason=payload.change_reason,
        )
        response = to_identity(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_IDENTITY_ROLLBACK,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=200,
            value=response,
        )
        return response


@router.get(
    "/adaptation",
    response_model=Adaptation,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_ADAPTATION_READ, "x-permission": PERM_ADAPTATION_READ},
    summary="读取适应层",
)
async def read_adaptation(
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_ADAPTATION_READ))],
) -> Adaptation:
    return to_adaptation(await _service(request).get_adaptation(identity.tenant_id))


@router.patch(
    "/adaptation",
    response_model=Adaptation,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_ADAPTATION_UPDATE, "x-permission": PERM_ADAPTATION_WRITE},
    summary="有界更新适应层（乐观锁 + 漂移上限）",
)
async def update_adaptation(
    payload: AdaptationUpdateRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_ADAPTATION_WRITE))],
) -> Adaptation:
    record = await _service(request).update_adaptation(
        identity.tenant_id,
        expected_version=payload.expected_version,
        deltas=payload.deltas,
        reason=payload.reason,
    )
    return to_adaptation(record)


@router.post(
    "/proposals",
    response_model=Proposal,
    status_code=201,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_PROPOSAL_CREATE, "x-permission": PERM_PROPOSAL_CREATE},
    summary="创建身份变更提案",
)
async def create_proposal(
    payload: ProposalCreateRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_PROPOSAL_CREATE))],
    idempotency_key: IdempotencyKey,
) -> Proposal:
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, OP_PROPOSAL_CREATE, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, OP_PROPOSAL_CREATE, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, Proposal)
        if cached is not None:
            return cached
        record = await _service(request).create_proposal(
            identity.tenant_id,
            proposer=identity.subject,
            rationale=payload.rationale,
            changes=payload.changes.model_dump(by_alias=False),
            evidence_episode_ids=payload.evidence_episode_ids,
        )
        response = to_proposal(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=OP_PROPOSAL_CREATE,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=201,
            value=response,
        )
        return response


@router.get(
    "/proposals",
    response_model=ProposalPage,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_PROPOSAL_READ, "x-permission": PERM_PROPOSAL_READ},
    summary="分页读取提案",
)
async def list_proposals(
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_PROPOSAL_READ))],
    cursor: Cursor = None,
    limit: Limit = 20,
) -> ProposalPage:
    items, next_cursor = await _service(request).list_proposals(
        identity.tenant_id,
        cursor=cursor,
        limit=limit,
    )
    return ProposalPage(
        items=[to_proposal(item) for item in items],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.post(
    "/proposals/{proposal_id}/review",
    response_model=Proposal,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_PROPOSAL_REVIEW, "x-permission": PERM_PROPOSAL_REVIEW},
    summary="审批或拒绝提案",
)
async def review_proposal(
    proposal_id: ProposalId,
    payload: ProposalReviewRequest,
    request: Request,
    identity: Annotated[Identity, Depends(require_permission(PERM_PROPOSAL_REVIEW))],
    idempotency_key: IdempotencyKey,
) -> Proposal:
    operation = f"proposal.review:{proposal_id}"
    fingerprint = request_fingerprint(identity.subject, identity.tenant_id, operation, payload)
    scope = _guard(request).scope(identity.subject, identity.tenant_id, operation, idempotency_key)
    async with _guard(request).key_lock(scope):
        cached = await _guard(request).get(scope, fingerprint, Proposal)
        if cached is not None:
            return cached
        record = await _service(request).review_proposal(
            identity.tenant_id,
            proposal_id=proposal_id,
            reviewer=identity.subject,
            decision=payload.decision,
            note=payload.note,
        )
        response = to_proposal(record)
        await _guard(request).put(
            scope,
            subject=identity.subject,
            tenant_id=identity.tenant_id,
            operation=operation,
            key=idempotency_key,
            fingerprint=fingerprint,
            status_code=200,
            value=response,
        )
        return response


@router.get(
    "/experiences",
    response_model=ExperiencePage,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_EXPERIENCE_READ, "x-permission": PERM_EXPERIENCE_READ},
    summary="分页读取经历时间线",
)
async def list_experiences(
    _identity: Annotated[Identity, Depends(require_permission(PERM_EXPERIENCE_READ))],
    cursor: Cursor = None,
    limit: Limit = 20,
) -> ExperiencePage:
    _not_implemented(CAP_EXPERIENCE_READ)


@router.post(
    "/experiences",
    response_model=Experience,
    status_code=201,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_EXPERIENCE_APPEND, "x-permission": PERM_EXPERIENCE_APPEND},
    summary="追加经历日志",
)
async def append_experience(
    payload: ExperienceAppendRequest,
    _identity: Annotated[Identity, Depends(require_permission(PERM_EXPERIENCE_APPEND))],
    idempotency_key: IdempotencyKey,
) -> Experience:
    _not_implemented(CAP_EXPERIENCE_APPEND)
