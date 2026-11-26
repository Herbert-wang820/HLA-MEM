"""HTTP adapter for async-consolidator (Phase 0: declared, returns 501)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query

from hla_consolidator.api.schemas import (
    Backlog,
    ConsolidationJob,
    DeadLetterPage,
    JobCreateRequest,
    JobPage,
    ReplayResult,
)
from hla_consolidator.internal.settings import MODULE_ID
from hla_host.auth import require_permission
from hla_host.context import Identity
from hla_host.errors import ERROR_RESPONSES, FeatureNotImplementedError

CAP_JOB_ENQUEUE = "async-consolidator.job.enqueue.v1"
CAP_JOB_READ = "async-consolidator.job.read.v1"
CAP_JOB_RETRY = "async-consolidator.job.retry.v1"
CAP_DEADLETTER_READ = "async-consolidator.deadletter.read.v1"
CAP_DEADLETTER_REPLAY = "async-consolidator.deadletter.replay.v1"
CAP_BACKLOG_READ = "async-consolidator.backlog.read.v1"

PERM_JOB_CREATE = "async-consolidator.job.create"
PERM_JOB_READ = "async-consolidator.job.read"
PERM_JOB_RETRY = "async-consolidator.job.retry"
PERM_DEADLETTER_READ = "async-consolidator.deadletter.read"
PERM_DEADLETTER_REPLAY = "async-consolidator.deadletter.replay"
PERM_ADMIN_READ = "async-consolidator.admin.read"

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200, description="Stable key for this operation."),
]
JobId = Annotated[str, Path(min_length=1, max_length=64)]
DeadLetterId = Annotated[str, Path(min_length=1, max_length=64)]
Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=100)]

router = APIRouter(prefix="/api/async-consolidator/v1", tags=["jobs"])
internal_router = APIRouter(prefix="/internal/v1", tags=["admin"])


@router.post(
    "/jobs",
    response_model=ConsolidationJob,
    status_code=202,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_JOB_ENQUEUE, "x-permission": PERM_JOB_CREATE},
    summary="入队巩固作业",
)
async def enqueue_job(
    payload: JobCreateRequest,
    _identity: Annotated[Identity, Depends(require_permission(PERM_JOB_CREATE))],
    idempotency_key: IdempotencyKey,
) -> ConsolidationJob:
    raise FeatureNotImplementedError(MODULE_ID, CAP_JOB_ENQUEUE)


@router.get(
    "/jobs",
    response_model=JobPage,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_JOB_READ, "x-permission": PERM_JOB_READ},
    summary="分页查询作业",
)
async def list_jobs(
    _identity: Annotated[Identity, Depends(require_permission(PERM_JOB_READ))],
    cursor: Cursor = None,
    limit: Limit = 20,
) -> JobPage:
    raise FeatureNotImplementedError(MODULE_ID, CAP_JOB_READ)


@router.get(
    "/jobs/{job_id}",
    response_model=ConsolidationJob,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_JOB_READ, "x-permission": PERM_JOB_READ},
    summary="读取单个作业",
)
async def read_job(
    job_id: JobId,
    _identity: Annotated[Identity, Depends(require_permission(PERM_JOB_READ))],
) -> ConsolidationJob:
    raise FeatureNotImplementedError(MODULE_ID, CAP_JOB_READ)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=ConsolidationJob,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_JOB_RETRY, "x-permission": PERM_JOB_RETRY},
    summary="重试失败作业",
)
async def retry_job(
    job_id: JobId,
    _identity: Annotated[Identity, Depends(require_permission(PERM_JOB_RETRY))],
    idempotency_key: IdempotencyKey,
) -> ConsolidationJob:
    raise FeatureNotImplementedError(MODULE_ID, CAP_JOB_RETRY)


@router.get(
    "/dead-letters",
    response_model=DeadLetterPage,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_DEADLETTER_READ, "x-permission": PERM_DEADLETTER_READ},
    summary="分页查询死信",
)
async def list_dead_letters(
    _identity: Annotated[Identity, Depends(require_permission(PERM_DEADLETTER_READ))],
    cursor: Cursor = None,
    limit: Limit = 20,
) -> DeadLetterPage:
    raise FeatureNotImplementedError(MODULE_ID, CAP_DEADLETTER_READ)


@router.post(
    "/dead-letters/{dead_letter_id}/replay",
    response_model=ReplayResult,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_DEADLETTER_REPLAY, "x-permission": PERM_DEADLETTER_REPLAY},
    summary="重放死信",
)
async def replay_dead_letter(
    dead_letter_id: DeadLetterId,
    _identity: Annotated[Identity, Depends(require_permission(PERM_DEADLETTER_REPLAY))],
    idempotency_key: IdempotencyKey,
) -> ReplayResult:
    raise FeatureNotImplementedError(MODULE_ID, CAP_DEADLETTER_REPLAY)


@internal_router.get(
    "/backlog",
    response_model=Backlog,
    responses=ERROR_RESPONSES,
    openapi_extra={"x-capability": CAP_BACKLOG_READ, "x-permission": PERM_ADMIN_READ},
    summary="查询积压与队列健康",
)
async def read_backlog(
    _identity: Annotated[Identity, Depends(require_permission(PERM_ADMIN_READ))],
) -> Backlog:
    raise FeatureNotImplementedError(MODULE_ID, CAP_BACKLOG_READ)
