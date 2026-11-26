"""Persona domain: immutable identity versions and a bounded adaptation layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ProposalStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True, slots=True)
class Trait:
    trait: str
    value: str
    confidence: float


@dataclass(frozen=True, slots=True)
class IdentityVersion:
    version: int
    traits: tuple[Trait, ...]
    narrative: str
    effective_from: datetime
    created_at: datetime
    created_by: str


@dataclass(frozen=True, slots=True)
class Adaptation:
    version: int
    values: dict[str, float]
    updated_at: datetime
    drift: float


@dataclass(frozen=True, slots=True)
class Proposal:
    """An identity change proposal.  Only ``pending`` proposals can be reviewed."""

    proposal_id: str
    status: ProposalStatus
    proposer: str
    rationale: str
    changes: dict[str, Any]
    evidence_episode_ids: tuple[str, ...]
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    review_note: str | None = None


@dataclass(slots=True)
class IdentityState:
    identity_id: str
    versions: list[IdentityVersion] = field(default_factory=list)
    adaptation: Adaptation | None = None
    window_start: datetime | None = None
    drift: float = 0.0
    proposals: list[Proposal] = field(default_factory=list)

    @property
    def current(self) -> IdentityVersion:
        return self.versions[-1]
