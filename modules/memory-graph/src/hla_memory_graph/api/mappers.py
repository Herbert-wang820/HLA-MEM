"""Map domain objects to API DTOs (aliases are applied by FastAPI)."""

from __future__ import annotations

from hla_memory_graph.api.schemas import (
    ConsolidationApplyResult,
    Episode,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    RetrievalCandidate,
    RetrievalResult,
)
from hla_memory_graph.domain.models import (
    ConsolidationOutcome,
    GraphView,
    RetrievalAudit,
)
from hla_memory_graph.domain.models import (
    Episode as EpisodeRecord,
)


def to_episode(record: EpisodeRecord) -> Episode:
    return Episode(
        episode_id=record.episode_id,
        tenant_id=record.tenant_id,
        session_id=record.session_id,
        content=record.content,
        occurred_at=record.occurred_at,
        source=record.source,
        metadata=record.metadata,
        content_hash=record.content_hash,
        retracted=record.retracted_at is not None,
        retracted_at=record.retracted_at,
        retract_reason=record.retract_reason,
        created_at=record.created_at,
    )


def to_retrieval(audit: RetrievalAudit) -> RetrievalResult:
    return RetrievalResult(
        retrieval_id=audit.retrieval_id,
        tenant_id=audit.tenant_id,
        candidates=[
            RetrievalCandidate(
                episode_id=candidate.episode_id,
                score=candidate.score,
                sources=list(candidate.sources),  # type: ignore[arg-type]
                hop_count=candidate.hop_count,
            )
            for candidate in audit.candidates
        ],
        merged_top_k=audit.merged_top_k,
        latency_ms=audit.latency_ms,
        degraded=audit.degraded,
        degradation_reasons=list(audit.degradation_reasons),
    )


def to_graph(view: GraphView) -> GraphQueryResult:
    return GraphQueryResult(
        nodes=[
            GraphNode(
                node_id=node.node_id,
                node_type=node.node_type,  # type: ignore[arg-type]
                label=node.label,
                degree=node.degree,
            )
            for node in view.nodes
        ],
        edges=[
            GraphEdge(
                edge_id=edge.edge_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                weight=edge.weight,
            )
            for edge in view.edges
        ],
        truncated=view.truncated,
    )


def to_consolidation(outcome: ConsolidationOutcome) -> ConsolidationApplyResult:
    return ConsolidationApplyResult(
        batch_id=outcome.batch_id,
        applied_count=outcome.applied_count,
        skipped_count=outcome.skipped_count,
        max_weight=outcome.max_weight,
    )
