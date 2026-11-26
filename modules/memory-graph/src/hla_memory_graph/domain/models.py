"""Pure domain model for the memory graph."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime


def _visible(episode: Episode, as_of: datetime | None) -> bool:
    if as_of is not None and episode.occurred_at > as_of:
        return False
    if episode.retracted_at is None:
        return True
    # A retraction is itself time-bound: as-of queries before it still see the episode.
    return as_of is not None and episode.retracted_at > as_of


@dataclass(frozen=True, slots=True)
class Episode:
    episode_id: str
    tenant_id: str
    session_id: str
    content: str
    occurred_at: datetime
    source: str
    metadata: dict[str, str]
    content_hash: str
    embedding: tuple[float, ...]
    created_at: datetime
    retracted_at: datetime | None = None
    retract_reason: str | None = None

    def visible_at(self, as_of: datetime | None) -> bool:
        return _visible(self, as_of)

    def retracted(self, at: datetime, reason: str) -> Episode:
        return replace(self, retracted_at=at, retract_reason=reason)


@dataclass(frozen=True, slots=True)
class CoactivationEdge:
    edge_id: str
    tenant_id: str
    source_id: str
    target_id: str
    weight: float
    last_activated_at: datetime
    activation_count: int

    def canonical(self) -> tuple[str, str]:
        return (self.source_id, self.target_id) if self.source_id <= self.target_id else (self.target_id, self.source_id)

    def reinforced(self, delta: float, at: datetime) -> CoactivationEdge:
        return replace(
            self,
            weight=min(1.0, self.weight + delta),
            last_activated_at=at,
            activation_count=self.activation_count + 1,
        )


@dataclass(frozen=True, slots=True)
class Candidate:
    episode_id: str
    score: float
    sources: tuple[str, ...]
    hop_count: int | None = None


@dataclass(frozen=True, slots=True)
class RetrievalAudit:
    retrieval_id: str
    tenant_id: str
    query_hash: str
    candidates: tuple[Candidate, ...]
    merged_top_k: int
    latency_ms: float
    degraded: bool
    degradation_reasons: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GraphNodeData:
    node_id: str
    node_type: str
    label: str
    degree: int


@dataclass(frozen=True, slots=True)
class GraphEdgeData:
    edge_id: str
    source_id: str
    target_id: str
    weight: float


@dataclass(frozen=True, slots=True)
class GraphView:
    nodes: tuple[GraphNodeData, ...]
    edges: tuple[GraphEdgeData, ...]
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ConsolidationOutcome:
    batch_id: str
    applied_count: int
    skipped_count: int
    max_weight: float
    skipped_reasons: tuple[str, ...] = field(default_factory=tuple)
