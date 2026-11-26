from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from hla_memory_graph.application.commands import ConsolidationOperation, WriteEpisodeCommand
from hla_memory_graph.application.service import MemoryService
from hla_memory_graph.infrastructure.embedding import HashingEmbedder
from hla_memory_graph.infrastructure.memory_store import InMemoryMemoryStore

from hla_host.errors import ModuleError, NotFoundError
from hla_host.events import DomainEvent

FIXED_NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def _service() -> tuple[MemoryService, InMemoryMemoryStore, list[DomainEvent]]:
    events: list[DomainEvent] = []

    async def publish(event: DomainEvent) -> None:
        events.append(event)

    store = InMemoryMemoryStore()
    service = MemoryService(
        store=store,
        embedder=HashingEmbedder(64),
        publish=publish,
        semantic_top_k=20,
        spreading_top_k=20,
        top_k_max=50,
        min_score=0.01,
        coactivation_top_n=10,
        spreading_decay=0.6,
        max_hops=2,
        clock=lambda: FIXED_NOW,
    )
    return service, store, events


def _command(content: str, *, occurred_at: datetime | None = None) -> WriteEpisodeCommand:
    return WriteEpisodeCommand(
        session_id="s1",
        content=content,
        occurred_at=occurred_at or (FIXED_NOW - timedelta(hours=1)),
    )


def test_tenant_isolation_across_reads_retrievals_and_graph_queries() -> None:
    async def run() -> None:
        service, _, _ = _service()
        episode = await service.write_episode("tenant-a", _command("green tea"))

        with pytest.raises(NotFoundError):
            await service.get_episode("tenant-b", episode.episode_id)

        audit = await service.retrieve("tenant-b", query="green tea", top_k=10, semantic_top_k=10, spreading_top_k=10)
        assert audit.candidates == ()
        view = await service.query_graph("tenant-b", node_types=["episode"], filters={}, depth=1, limit=10)
        assert view.nodes == ()

    asyncio.run(run())


def test_write_emits_written_event_and_retract_emits_retracted_event() -> None:
    async def run() -> None:
        service, _, events = _service()
        episode = await service.write_episode("tenant-a", _command("hello"))
        assert [event.type for event in events] == ["memory-graph.episode.written.v1"]
        written = events[0]
        assert written.tenant_id == "tenant-a"
        assert written.data["episodeId"] == episode.episode_id
        assert written.data["contentHash"] == episode.content_hash

        await service.retract_episode("tenant-a", episode.episode_id, "user_request", None)
        assert [event.type for event in events][-1] == "memory-graph.episode.retracted.v1"
        assert events[-1].tenant_id == "tenant-a"

    asyncio.run(run())


def test_retrieval_records_coactivation_and_reinforces_on_repetition() -> None:
    async def run() -> None:
        service, store, events = _service()
        await service.write_episode("tenant-a", _command("green tea"))
        await service.write_episode("tenant-a", _command("green tea cup"))

        first = await service.retrieve("tenant-a", query="green tea", top_k=10, semantic_top_k=10, spreading_top_k=10)
        assert len(first.candidates) >= 2
        edges = await store.list_edges("tenant-a")
        assert len(edges) == 1
        initial_weight = edges[0].weight
        assert any(event.type == "memory-graph.coactivation.recorded.v1" for event in events)

        await service.retrieve("tenant-a", query="green tea", top_k=10, semantic_top_k=10, spreading_top_k=10)
        edges = await store.list_edges("tenant-a")
        assert edges[0].weight > initial_weight
        assert edges[0].activation_count == 2

    asyncio.run(run())


def test_retraction_hides_episode_but_as_of_keeps_history() -> None:
    async def run() -> None:
        service, _, _ = _service()
        occurred = FIXED_NOW - timedelta(days=100)
        episode = await service.write_episode("tenant-a", _command("alpha memory", occurred_at=occurred))
        await service.retract_episode("tenant-a", episode.episode_id, "user_request", None)

        visible_before = await service.retrieve(
            "tenant-a",
            query="alpha",
            top_k=10,
            semantic_top_k=10,
            spreading_top_k=10,
            as_of=FIXED_NOW - timedelta(days=50),
        )
        assert visible_before.candidates

        hidden_now = await service.retrieve(
            "tenant-a", query="alpha", top_k=10, semantic_top_k=10, spreading_top_k=10
        )
        assert hidden_now.candidates == ()

    asyncio.run(run())


def test_future_occurred_at_is_rejected() -> None:
    async def run() -> None:
        service, _, _ = _service()
        with pytest.raises(ModuleError) as captured:
            await service.write_episode("tenant-a", _command("future", occurred_at=FIXED_NOW + timedelta(seconds=1)))
        assert captured.value.status_code == 422
        assert captured.value.code == "MEMORY_GRAPH_REQUEST_INVALID_TIME"

    asyncio.run(run())


def test_graph_query_rejects_unknown_filters() -> None:
    async def run() -> None:
        service, _, _ = _service()
        with pytest.raises(ModuleError) as captured:
            await service.query_graph(
                "tenant-a",
                node_types=["episode"],
                filters={"tenant": "other"},
                depth=1,
                limit=10,
            )
        assert captured.value.status_code == 400
        assert captured.value.code == "MEMORY_GRAPH_QUERY_INVALID_FILTER"

    asyncio.run(run())


def test_forget_removes_edge_and_distill_is_explicitly_skipped() -> None:
    async def run() -> None:
        service, store, _ = _service()
        await service.write_episode("tenant-a", _command("tea"))
        await service.write_episode("tenant-a", _command("tea cup"))
        await service.retrieve("tenant-a", query="tea", top_k=10, semantic_top_k=10, spreading_top_k=10)
        edge = (await store.list_edges("tenant-a"))[0]

        outcome = await service.apply_consolidation(
            "tenant-a",
            batch_id="b1",
            job_id="j1",
            operations=[
                ConsolidationOperation(operation="forget", edge_id=edge.edge_id),
                ConsolidationOperation(operation="distill", hub_id="hub-1"),
            ],
        )
        assert outcome.applied_count == 1
        assert outcome.skipped_count == 1
        assert "DISTILL_NOT_IMPLEMENTED" in outcome.skipped_reasons
        assert await store.list_edges("tenant-a") == ()

    asyncio.run(run())


def test_consolidation_batch_is_idempotent_across_http_idempotency_keys() -> None:
    async def run() -> None:
        service, store, _ = _service()
        await service.write_episode("tenant-a", _command("tea"))
        await service.write_episode("tenant-a", _command("tea cup"))
        await service.retrieve("tenant-a", query="tea", top_k=10, semantic_top_k=10, spreading_top_k=10)
        edge = (await store.list_edges("tenant-a"))[0]

        first = await service.apply_consolidation(
            "tenant-a",
            batch_id="batch-42",
            job_id="job-42",
            operations=[ConsolidationOperation(operation="reinforce", edge_id=edge.edge_id, weight_delta=0.1)],
        )
        weight_after_first = (await store.list_edges("tenant-a"))[0].weight

        replay = await service.apply_consolidation(
            "tenant-a",
            batch_id="batch-42",
            job_id="job-42",
            operations=[ConsolidationOperation(operation="reinforce", edge_id=edge.edge_id, weight_delta=0.5)],
        )
        assert replay == first
        assert (await store.list_edges("tenant-a"))[0].weight == weight_after_first

    asyncio.run(run())


def test_graph_query_reports_truncation_when_limit_is_smaller_than_reachable_set() -> None:
    async def run() -> None:
        service, _, _ = _service()
        for index in range(3):
            await service.write_episode("tenant-a", _command(f"tea {index}"))
        view = await service.query_graph("tenant-a", node_types=["episode"], filters={}, depth=0, limit=1)
        assert len(view.nodes) == 1
        assert view.truncated is True

    asyncio.run(run())
