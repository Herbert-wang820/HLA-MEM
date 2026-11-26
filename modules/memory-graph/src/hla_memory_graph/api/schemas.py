"""Request/response DTOs for memory-graph.

Tenant is never part of a request body: it comes from the trusted identity
context.  ``extra="forbid"`` makes a client-supplied ``tenantId`` a 422.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class EpisodeWriteRequest(APIModel):
    session_id: str = Field(alias="sessionId", min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=20_000)
    occurred_at: datetime = Field(alias="occurredAt")
    source: str = Field(default="conversation", min_length=1, max_length=64)
    metadata: dict[str, str] = Field(default_factory=dict)


class Episode(APIModel):
    episode_id: str = Field(alias="episodeId")
    tenant_id: str = Field(alias="tenantId")
    session_id: str = Field(alias="sessionId")
    content: str
    occurred_at: datetime = Field(alias="occurredAt")
    source: str
    metadata: dict[str, str] = Field(default_factory=dict)
    content_hash: str = Field(alias="contentHash")
    retracted: bool = False
    retracted_at: datetime | None = Field(None, alias="retractedAt")
    retract_reason: str | None = Field(None, alias="retractReason")
    created_at: datetime = Field(alias="createdAt")


class EpisodeRetractRequest(APIModel):
    reason_code: str = Field(alias="reasonCode", min_length=1, max_length=64)
    note: str | None = Field(None, max_length=1_000)


class RetrievalRequest(APIModel):
    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(50, alias="topK", ge=1, le=50)
    semantic_top_k: int = Field(20, alias="semanticTopK", ge=1, le=50)
    spreading_top_k: int = Field(20, alias="spreadingTopK", ge=1, le=50)
    session_id: str | None = Field(None, alias="sessionId", max_length=128)
    as_of: datetime | None = Field(None, alias="asOf")


class RetrievalCandidate(APIModel):
    episode_id: str = Field(alias="episodeId")
    score: float = Field(ge=0.0, le=1.0)
    sources: list[Literal["semantic", "spreading"]] = Field(min_length=1)
    hop_count: int | None = Field(None, alias="hopCount", ge=0)


class RetrievalResult(APIModel):
    retrieval_id: str = Field(alias="retrievalId")
    tenant_id: str = Field(alias="tenantId")
    candidates: list[RetrievalCandidate]
    merged_top_k: int = Field(alias="mergedTopK", ge=0, le=50)
    latency_ms: float = Field(alias="latencyMs", ge=0.0)
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list, alias="degradationReasons")


class GraphQueryRequest(APIModel):
    node_types: list[str] = Field(alias="nodeTypes", min_length=1, max_length=10)
    filters: dict[str, str] = Field(default_factory=dict)
    depth: int = Field(1, ge=0, le=3)
    limit: int = Field(100, ge=1, le=500)


class GraphNode(APIModel):
    node_id: str = Field(alias="nodeId")
    node_type: Literal["episode", "concept"] = Field(alias="nodeType")
    label: str
    degree: int = Field(ge=0)


class GraphEdge(APIModel):
    edge_id: str = Field(alias="edgeId")
    source_id: str = Field(alias="sourceId")
    target_id: str = Field(alias="targetId")
    weight: float = Field(ge=0.0, le=1.0)


class GraphQueryResult(APIModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = False


class ConsolidationOperation(APIModel):
    operation: Literal["reinforce", "forget", "distill"]
    edge_id: str | None = Field(None, alias="edgeId")
    source_episode_id: str | None = Field(None, alias="sourceEpisodeId")
    target_episode_id: str | None = Field(None, alias="targetEpisodeId")
    episode_id: str | None = Field(None, alias="episodeId")
    weight_delta: float | None = Field(None, alias="weightDelta", ge=0.0, le=1.0)
    hub_id: str | None = Field(None, alias="hubId")


class ConsolidationApplyRequest(APIModel):
    batch_id: str = Field(alias="batchId", min_length=1, max_length=128)
    job_id: str = Field(alias="jobId", min_length=1, max_length=128)
    operations: list[ConsolidationOperation] = Field(min_length=1, max_length=5_000)


class ConsolidationApplyResult(APIModel):
    batch_id: str = Field(alias="batchId")
    applied_count: int = Field(alias="appliedCount", ge=0)
    skipped_count: int = Field(alias="skippedCount", ge=0)
    max_weight: float = Field(alias="maxWeight", ge=0.0, le=1.0)
