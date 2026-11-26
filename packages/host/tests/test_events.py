from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hla_host.events import (
    DomainEvent,
    EventDispatchError,
    IdempotentConsumer,
    InMemoryDedupeStore,
    InMemoryEventBus,
    InMemoryOutbox,
    OutboxPublisher,
    new_event,
)


def _event(**overrides: object) -> DomainEvent:
    payload = {
        "type": "memory-graph.episode.written.v1",
        "source": "memory-graph",
        "subject": "episode-1",
        "tenant_id": "tenant-1",
        "data": {"episodeId": "episode-1"},
    }
    payload.update(overrides)
    return new_event(**payload)  # type: ignore[arg-type]


def test_event_envelope_serializes_camel_case() -> None:
    event = _event()
    wire = event.to_wire()
    assert wire["specVersion"] == "1.0"
    assert wire["tenantId"] == "tenant-1"
    assert wire["dataVersion"] == 1
    assert wire["type"] == "memory-graph.episode.written.v1"


def test_event_rejects_naive_time() -> None:
    with pytest.raises(ValidationError):
        new_event(
            type="memory-graph.episode.written.v1",
            source="memory-graph",
            subject="episode-1",
            tenant_id="tenant-1",
            data={},
            occurred_at=datetime(2026, 1, 1, 12, 0, 0),
        )


def test_event_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        _event(type="memory.retrieve.v1")


def test_bus_dispatches_to_matching_subscribers_only() -> None:
    async def run() -> None:
        bus = InMemoryEventBus()
        seen: list[str] = []

        async def handler(event: DomainEvent) -> None:
            seen.append(event.subject)

        bus.subscribe("memory-graph.episode.written.v1", handler)
        await bus.publish(_event())
        await bus.publish(_event(type="memory-graph.episode.retracted.v1"))
        assert seen == ["episode-1"]
        assert len(bus.published_events) == 2

    asyncio.run(run())


def test_bus_reports_handler_failure_after_running_others() -> None:
    async def run() -> None:
        bus = InMemoryEventBus()
        seen: list[str] = []

        async def failing(event: DomainEvent) -> None:
            raise RuntimeError("boom")

        async def healthy(event: DomainEvent) -> None:
            seen.append(event.id)

        bus.subscribe("memory-graph.episode.written.v1", failing)
        bus.subscribe("memory-graph.episode.written.v1", healthy)
        with pytest.raises(EventDispatchError):
            await bus.publish(_event())
        assert len(seen) == 1

    asyncio.run(run())


def test_idempotent_consumer_processes_each_event_once() -> None:
    async def run() -> None:
        calls: list[str] = []

        async def handler(event: DomainEvent) -> None:
            calls.append(event.id)

        consumer = IdempotentConsumer(handler, store=InMemoryDedupeStore())
        event = _event()
        assert await consumer(event) is True
        assert await consumer(event) is False
        assert calls == [event.id]

    asyncio.run(run())


def test_idempotent_consumer_releases_key_on_failure() -> None:
    async def run() -> None:
        attempts: list[int] = []

        async def handler(event: DomainEvent) -> None:
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient")

        consumer = IdempotentConsumer(handler, store=InMemoryDedupeStore())
        event = _event()
        with pytest.raises(RuntimeError):
            await consumer(event)
        assert await consumer(event) is True
        assert len(attempts) == 2

    asyncio.run(run())


def test_dedupe_store_expires_entries() -> None:
    async def run() -> None:
        now = [0.0]
        store = InMemoryDedupeStore(ttl_seconds=10, clock=lambda: now[0])
        assert await store.claim("k") is True
        assert await store.claim("k") is False
        now[0] = 11.0
        assert await store.claim("k") is True

    asyncio.run(run())


def test_outbox_publisher_drains_pending_events() -> None:
    async def run() -> None:
        outbox = InMemoryOutbox()
        bus = InMemoryEventBus()
        await outbox.enqueue(_event())
        await outbox.enqueue(_event(event_id="22222222-2222-4222-8222-222222222222", subject="episode-2"))
        assert outbox.pending_count == 2

        publisher = OutboxPublisher(outbox, bus)
        assert await publisher.drain() == 2
        assert outbox.pending_count == 0
        assert len(bus.published_events) == 2

    asyncio.run(run())


def test_event_time_is_normalized_to_utc() -> None:
    event = _event(occurred_at=datetime(2026, 1, 1, 20, 0, 0, tzinfo=timezone(timedelta(hours=8))))
    assert event.time.tzinfo is UTC
    assert event.time.hour == 12
