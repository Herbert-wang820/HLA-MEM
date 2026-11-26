"""Request/response DTOs for persona-state.

The tenant is derived from the trusted identity, never from the payload.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TraitValue(APIModel):
    trait: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=512)
    confidence: float = Field(ge=0.0, le=1.0)


class IdentityChangeSet(APIModel):
    """A complete proposed identity snapshot; partial patches are not accepted."""

    traits: list[TraitValue] = Field(min_length=1, max_length=64)
    narrative: str = Field(default="", max_length=8_000)


class PersonaIdentity(APIModel):
    version: int = Field(ge=1)
    traits: list[TraitValue]
    narrative: str = Field(max_length=8_000)
    effective_from: datetime = Field(alias="effectiveFrom")
    created_at: datetime = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")


class IdentityVersionCreateRequest(APIModel):
    traits: list[TraitValue] = Field(min_length=1, max_length=64)
    narrative: str = Field(default="", max_length=8_000)
    change_reason: str = Field(alias="changeReason", min_length=1, max_length=500)


class IdentityRollbackRequest(APIModel):
    target_version: int = Field(alias="targetVersion", ge=1)
    change_reason: str = Field(alias="changeReason", min_length=1, max_length=500)


class Adaptation(APIModel):
    version: int = Field(ge=1)
    values: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime = Field(alias="updatedAt")
    drift: float = Field(default=0.0, ge=0.0, le=1.0)


class AdaptationUpdateRequest(APIModel):
    expected_version: int = Field(alias="expectedVersion", ge=1)
    deltas: dict[str, float] = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


class Proposal(APIModel):
    proposal_id: str = Field(alias="proposalId")
    status: Literal["pending", "approved", "rejected"]
    proposer: str
    rationale: str
    changes: IdentityChangeSet
    evidence_episode_ids: list[str] = Field(default_factory=list, alias="evidenceEpisodeIds")
    created_at: datetime = Field(alias="createdAt")
    reviewed_at: datetime | None = Field(None, alias="reviewedAt")
    reviewer: str | None = None
    review_note: str | None = Field(None, alias="reviewNote")


class ProposalCreateRequest(APIModel):
    rationale: str = Field(min_length=1, max_length=2_000)
    changes: IdentityChangeSet
    evidence_episode_ids: list[str] = Field(default_factory=list, alias="evidenceEpisodeIds", max_length=50)


class ProposalReviewRequest(APIModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=2_000)


class ProposalPage(APIModel):
    items: list[Proposal]
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")


class Experience(APIModel):
    experience_id: str = Field(alias="experienceId")
    turn_id: str = Field(alias="turnId")
    summary: str
    outcome: Literal["success", "partial", "failure"]
    occurred_at: datetime = Field(alias="occurredAt")
    created_at: datetime = Field(alias="createdAt")


class ExperienceAppendRequest(APIModel):
    turn_id: str = Field(alias="turnId", min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2_000)
    outcome: Literal["success", "partial", "failure"]
    occurred_at: datetime = Field(alias="occurredAt")
    metadata: dict[str, str] = Field(default_factory=dict)


class ExperiencePage(APIModel):
    items: list[Experience]
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")
