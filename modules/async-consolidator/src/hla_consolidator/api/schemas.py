"""Request/response DTOs for async-consolidator."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class JobCreateRequest(APIModel):
    trigger: Literal["turn", "schedule", "manual"]
    session_id: str | None = Field(None, alias="sessionId", max_length=128)
    episode_ids: list[str] = Field(default_factory=list, alias="episodeIds", max_length=500)
    priority: int = Field(0, ge=-10, le=10)
    scheduled_for: datetime | None = Field(None, alias="scheduledFor")


class ConsolidationJob(APIModel):
    job_id: str = Field(alias="jobId")
    status: Literal["pending", "running", "completed", "failed", "dead_lettered"]
    trigger: Literal["turn", "schedule", "manual"]
    attempts: int = Field(0, ge=0)
    max_attempts: int = Field(alias="maxAttempts", ge=1)
    created_at: datetime = Field(alias="createdAt")
    started_at: datetime | None = Field(None, alias="startedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")
    last_error: str | None = Field(None, alias="lastError")


class JobPage(APIModel):
    items: list[ConsolidationJob]
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")


class DeadLetter(APIModel):
    dead_letter_id: str = Field(alias="deadLetterId")
    job_id: str = Field(alias="jobId")
    reason: str
    attempts: int = Field(ge=0)
    created_at: datetime = Field(alias="createdAt")
    replayed: bool = False


class DeadLetterPage(APIModel):
    items: list[DeadLetter]
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")


class ReplayResult(APIModel):
    dead_letter_id: str = Field(alias="deadLetterId")
    job_id: str = Field(alias="jobId")
    accepted: bool


class Backlog(APIModel):
    pending: int = Field(ge=0)
    running: int = Field(ge=0)
    dead_lettered: int = Field(alias="deadLettered", ge=0)
    oldest_pending_age_seconds: float = Field(alias="oldestPendingAgeSeconds", ge=0.0)
    degraded: bool = False
