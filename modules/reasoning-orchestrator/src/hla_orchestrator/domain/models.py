"""Domain objects for a conversational turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

TurnStatus = Literal["completed", "degraded"]


@dataclass(frozen=True, slots=True)
class MemoryHit:
    episode_id: str
    score: float
    sources: tuple[str, ...]
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryRetrieval:
    retrieval_id: str
    hits: tuple[MemoryHit, ...]


@dataclass(frozen=True, slots=True)
class AdaptationRequest:
    deltas: dict[str, float]
    reason: str


@dataclass(frozen=True, slots=True)
class IdentityProposalRequest:
    """A model-originated identity proposal; it never writes an identity version."""

    rationale: str
    changes: dict[str, Any]
    evidence_episode_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Generation:
    text: str
    degraded: bool = False
    reasons: tuple[str, ...] = ()
    adaptation: AdaptationRequest | None = None


@dataclass(frozen=True, slots=True)
class TurnAudit:
    turn_id: str
    retrieval_id: str
    gate_score: float
    gate_threshold: float
    candidates_considered: int
    used_episode_ids: tuple[str, ...]
    latency_ms: float
    degraded: bool
    reasons: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    turn_id: str
    session_id: str
    text: str
    status: TurnStatus
    created_at: datetime
    completed_at: datetime
    memory_degraded: bool
    llm_degraded: bool
    persona_degraded: bool
    persona_updated: bool
    reasons: tuple[str, ...]
    memories: tuple[MemoryHit, ...] = field(default_factory=tuple)
    audit: TurnAudit | None = None
    persona_version: int | None = None
    adaptation_version: int | None = None
    identity_proposal_id: str | None = None
