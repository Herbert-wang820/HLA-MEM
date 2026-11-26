"""Use cases for the memory graph."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from hla_host.errors import ModuleError, NotFoundError
from hla_host.events import DomainEvent, new_event
from hla_memory_graph.application.commands import ConsolidationOperation, WriteEpisodeCommand
from hla_memory_graph.application.ports import Embedder, MemoryStore
from hla_memory_graph.domain.models import (
    CoactivationEdge,
    ConsolidationOutcome,
    Episode,
    GraphEdgeData,
    GraphNodeData,
    GraphView,
    RetrievalAudit,
)
from hla_memory_graph.domain.retrieval import cosine, fuse_candidates, spreading_scores

MODULE_ID = "memory-graph"

Publish = Callable[[DomainEvent], Awaitable[None]]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MemoryService:
    def __init__(
        self,
        *,
        store: MemoryStore,
        embedder: Embedder,
        publish: Publish,
        semantic_top_k: int = 20,
        spreading_top_k: int = 20,
        top_k_max: int = 50,
        min_score: float = 0.05,
        coactivation_top_n: int = 10,
        spreading_decay: float = 0.6,
        max_hops: int = 2,
        w_min: float = 0.05,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._publish = publish
        self._semantic_top_k = max(1, semantic_top_k)
        self._spreading_top_k = max(1, spreading_top_k)
        self._top_k_max = max(1, top_k_max)
        self._min_score = min_score
        self._coactivation_top_n = max(2, coactivation_top_n)
        self._spreading_decay = spreading_decay
        self._max_hops = max(0, max_hops)
        self._w_min = w_min
        self._clock = clock or (lambda: datetime.now(UTC))
        self._applied_batches: dict[tuple[str, str, str], ConsolidationOutcome] = {}
        self._batch_lock = asyncio.Lock()

    async def write_episode(self, tenant_id: str, command: WriteEpisodeCommand) -> Episode:
        now = _utc(self._clock())
        occurred_at = _utc(command.occurred_at)
        assert now is not None and occurred_at is not None
        if occurred_at > now:
            raise ModuleError(
                "MEMORY_GRAPH_REQUEST_INVALID_TIME",
                "occurredAt must not be in the future",
                422,
            )
        content_hash = hashlib.sha256(command.content.encode("utf-8")).hexdigest()
        episode = Episode(
            episode_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            session_id=command.session_id,
            content=command.content,
            occurred_at=occurred_at,
            source=command.source,
            metadata=dict(command.metadata),
            content_hash=content_hash,
            embedding=self._embedder.embed(command.content),
            created_at=now,
        )
        await self._store.add_episode(episode)
        await self._publish(
            new_event(
                type="memory-graph.episode.written.v1",
                source=MODULE_ID,
                subject=episode.episode_id,
                tenant_id=tenant_id,
                data={
                    "episodeId": episode.episode_id,
                    "sessionId": episode.session_id,
                    "occurredAt": episode.occurred_at.isoformat(),
                    "contentHash": episode.content_hash,
                },
            )
        )
        return episode

    async def get_episode(self, tenant_id: str, episode_id: str) -> Episode:
        episode = await self._store.get_episode(tenant_id, episode_id)
        if episode is None:
            raise NotFoundError(MODULE_ID, "EPISODE", episode_id)
        return episode

    async def retract_episode(
        self,
        tenant_id: str,
        episode_id: str,
        reason_code: str,
        note: str | None,
    ) -> Episode:
        episode = await self.get_episode(tenant_id, episode_id)
        if episode.retracted_at is not None:
            return episode
        now = _utc(self._clock())
        assert now is not None
        reason = reason_code if not note else f"{reason_code}: {note}"
        retracted = episode.retracted(now, reason)
        await self._store.update_episode(retracted)
        await self._publish(
            new_event(
                type="memory-graph.episode.retracted.v1",
                source=MODULE_ID,
                subject=retracted.episode_id,
                tenant_id=tenant_id,
                data={
                    "episodeId": retracted.episode_id,
                    "retractedAt": now.isoformat(),
                    "reasonCode": reason_code,
                },
            )
        )
        return retracted

    async def retrieve(
        self,
        tenant_id: str,
        *,
        query: str,
        top_k: int,
        semantic_top_k: int,
        spreading_top_k: int,
        as_of: datetime | None = None,
    ) -> RetrievalAudit:
        started = time.perf_counter()
        as_of_utc = _utc(as_of)
        episodes = [episode for episode in await self._store.list_episodes(tenant_id) if episode.visible_at(as_of_utc)]
        visible_ids = {episode.episode_id for episode in episodes}
        by_id = {episode.episode_id: episode for episode in episodes}

        degraded = False
        reasons: list[str] = []
        semantic: dict[str, float] = {}
        try:
            query_embedding = self._embedder.embed(query)
            scored = [
                (episode.episode_id, cosine(query_embedding, episode.embedding))
                for episode in episodes
            ]
            scored.sort(key=lambda item: (-item[1], item[0]))
            semantic = {
                episode_id: max(0.0, score)
                for episode_id, score in scored[: min(semantic_top_k, self._semantic_top_k)]
            }
        except Exception:  # noqa: BLE001 - retrieval must degrade, not fail the turn
            degraded = True
            reasons.append("EMBEDDING_UNAVAILABLE")

        seed_scores = dict(sorted(semantic.items(), key=lambda item: -item[1])[:5])
        spreading = spreading_scores(
            seed_scores,
            await self._store.list_edges(tenant_id),
            decay=self._spreading_decay,
            max_hops=self._max_hops,
            visible_ids=visible_ids,
        )
        spreading_limit = max(1, min(spreading_top_k, self._spreading_top_k))
        if len(spreading) > spreading_limit:
            spreading = dict(sorted(spreading.items(), key=lambda item: -item[1][0])[:spreading_limit])

        limit = max(1, min(top_k, self._top_k_max))
        fused = fuse_candidates(semantic, spreading, min_score=self._min_score, limit=limit)
        # Keep the audit ordered and bounded exactly like the response.
        fused = fused[:limit]
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        now = _utc(self._clock())
        assert now is not None
        audit = RetrievalAudit(
            retrieval_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            candidates=tuple(fused),
            merged_top_k=len(fused),
            latency_ms=latency_ms,
            degraded=degraded,
            degradation_reasons=tuple(reasons),
            created_at=now,
        )
        await self._store.add_retrieval(audit)
        await self._record_coactivation(tenant_id, audit, by_id, now)
        return audit

    async def _record_coactivation(
        self,
        tenant_id: str,
        audit: RetrievalAudit,
        by_id: dict[str, Episode],
        now: datetime,
    ) -> None:
        candidates = list(audit.candidates[: self._coactivation_top_n])
        if len(candidates) < 2:
            return
        pairs: list[dict[str, Any]] = []
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                if left.episode_id not in by_id or right.episode_id not in by_id:
                    continue
                delta = round(0.02 + 0.08 * min(left.score, right.score), 4)
                existing = await self._store.find_edge(tenant_id, left.episode_id, right.episode_id)
                if existing is None:
                    edge = CoactivationEdge(
                        edge_id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        source_id=min(left.episode_id, right.episode_id),
                        target_id=max(left.episode_id, right.episode_id),
                        weight=min(1.0, delta),
                        last_activated_at=now,
                        activation_count=1,
                    )
                else:
                    edge = existing.reinforced(delta, now)
                await self._store.upsert_edge(edge)
                pairs.append(
                    {
                        "sourceEpisodeId": edge.source_id,
                        "targetEpisodeId": edge.target_id,
                        "weightDelta": delta,
                    }
                )
        if not pairs:
            return
        await self._publish(
            new_event(
                type="memory-graph.coactivation.recorded.v1",
                source=MODULE_ID,
                subject=audit.retrieval_id,
                tenant_id=tenant_id,
                data={
                    "batchId": str(uuid.uuid4()),
                    "retrievalId": audit.retrieval_id,
                    "pairs": pairs,
                    "pairCount": len(pairs),
                },
            )
        )

    async def get_retrieval(self, tenant_id: str, retrieval_id: str) -> RetrievalAudit:
        audit = await self._store.get_retrieval(tenant_id, retrieval_id)
        if audit is None:
            raise NotFoundError(MODULE_ID, "RETRIEVAL", retrieval_id)
        return audit

    async def query_graph(
        self,
        tenant_id: str,
        *,
        node_types: list[str],
        filters: dict[str, str],
        depth: int,
        limit: int,
    ) -> GraphView:
        if "episode" not in node_types:
            return GraphView(nodes=(), edges=())
        wanted_session = filters.get("sessionId")
        wanted_source = filters.get("source")
        after = self._parse_filter_time(filters.get("after"), "after")
        before = self._parse_filter_time(filters.get("before"), "before")
        unknown = set(filters) - {"sessionId", "source", "after", "before"}
        if unknown:
            raise ModuleError(
                "MEMORY_GRAPH_QUERY_INVALID_FILTER",
                f"unsupported filter(s): {', '.join(sorted(unknown))}",
                400,
            )

        episodes = [episode for episode in await self._store.list_episodes(tenant_id) if episode.visible_at(None)]
        matching = [
            episode
            for episode in episodes
            if (wanted_session is None or episode.session_id == wanted_session)
            and (wanted_source is None or episode.source == wanted_source)
            and (after is None or episode.occurred_at >= after)
            and (before is None or episode.occurred_at <= before)
        ]
        by_id = {episode.episode_id: episode for episode in episodes}
        edges = list(await self._store.list_edges(tenant_id))

        selected: dict[str, Episode] = {episode.episode_id: episode for episode in matching}
        truncated = False
        if depth > 0:
            frontier = set(selected)
            for _ in range(depth):
                neighbors: set[str] = set()
                for edge in edges:
                    if edge.source_id in frontier and edge.target_id in by_id:
                        neighbors.add(edge.target_id)
                    elif edge.target_id in frontier and edge.source_id in by_id:
                        neighbors.add(edge.source_id)
                new_ids = neighbors - set(selected)
                if not new_ids:
                    break
                for episode_id in new_ids:
                    selected[episode_id] = by_id[episode_id]
                frontier = new_ids
                if len(selected) >= limit * 2:
                    truncated = True
                    break

        truncated = truncated or len(selected) > limit
        ordered = list(selected.items())[:limit]
        kept_ids = {episode_id for episode_id, _ in ordered}
        kept_edges = (
            [edge for edge in edges if edge.source_id in kept_ids and edge.target_id in kept_ids]
            if depth > 0
            else []
        )
        degree: dict[str, int] = {episode_id: 0 for episode_id in kept_ids}
        for edge in kept_edges:
            degree[edge.source_id] = degree.get(edge.source_id, 0) + 1
            degree[edge.target_id] = degree.get(edge.target_id, 0) + 1
        nodes = tuple(
            GraphNodeData(
                node_id=episode_id,
                node_type="episode",
                label=episode_id,
                degree=degree.get(episode_id, 0),
            )
            for episode_id, _ in ordered
        )
        view_edges = tuple(
            GraphEdgeData(
                edge_id=edge.edge_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                weight=edge.weight,
            )
            for edge in kept_edges
        )
        return GraphView(nodes=nodes, edges=view_edges, truncated=truncated)

    @staticmethod
    def _parse_filter_time(raw: str | None, name: str) -> datetime | None:
        if raw is None:
            return None
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ModuleError(
                "MEMORY_GRAPH_QUERY_INVALID_FILTER",
                f"filter {name!r} must be an ISO-8601 date-time",
                400,
            ) from exc
        return _utc(value)

    async def apply_consolidation(
        self,
        tenant_id: str,
        *,
        batch_id: str,
        job_id: str,
        operations: list[ConsolidationOperation],
    ) -> ConsolidationOutcome:
        batch_key = (tenant_id, batch_id, job_id)
        async with self._batch_lock:
            existing = self._applied_batches.get(batch_key)
            if existing is not None:
                return existing
            outcome = await self._apply_operations(tenant_id, batch_id, operations)
            self._applied_batches[batch_key] = outcome
            return outcome

    async def _apply_operations(
        self,
        tenant_id: str,
        batch_id: str,
        operations: list[ConsolidationOperation],
    ) -> ConsolidationOutcome:
        now = _utc(self._clock())
        assert now is not None
        applied = 0
        skipped = 0
        reasons: list[str] = []
        for operation in operations:
            if operation.operation == "reinforce":
                edge = await self._find_operation_edge(tenant_id, operation)
                if edge is None:
                    skipped += 1
                    reasons.append("EDGE_NOT_FOUND")
                    continue
                delta = operation.weight_delta if operation.weight_delta is not None else 0.05
                await self._store.upsert_edge(edge.reinforced(delta, now))
                applied += 1
            elif operation.operation == "forget":
                edge = await self._find_operation_edge(tenant_id, operation)
                if edge is None:
                    skipped += 1
                    reasons.append("EDGE_NOT_FOUND")
                    continue
                if await self._store.delete_edge(tenant_id, edge.edge_id):
                    applied += 1
                else:
                    skipped += 1
                    reasons.append("EDGE_NOT_FOUND")
            else:
                # Hub distillation is scheduled for Phase 3; do not fake a concept node.
                skipped += 1
                reasons.append("DISTILL_NOT_IMPLEMENTED")
        remaining = await self._store.list_edges(tenant_id)
        max_weight = max((edge.weight for edge in remaining), default=0.0)
        return ConsolidationOutcome(
            batch_id=batch_id,
            applied_count=applied,
            skipped_count=skipped,
            max_weight=max_weight,
            skipped_reasons=tuple(sorted(set(reasons))),
        )

    async def _find_operation_edge(
        self,
        tenant_id: str,
        operation: ConsolidationOperation,
    ) -> CoactivationEdge | None:
        edges = await self._store.list_edges(tenant_id)
        if operation.edge_id:
            return next((edge for edge in edges if edge.edge_id == operation.edge_id), None)
        if operation.source_episode_id and operation.target_episode_id:
            return await self._store.find_edge(
                tenant_id,
                operation.source_episode_id,
                operation.target_episode_id,
            )
        return None
