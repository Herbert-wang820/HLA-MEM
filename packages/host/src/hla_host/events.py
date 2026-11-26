"""Versioned domain events, in-memory bus, dedupe and outbox primitives."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hla_host.observability import MetricsRegistry

EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9]*\.[a-z][a-z0-9-]*\.v(0|[1-9][0-9]*)$")

logger = logging.getLogger("hla.events")

Handler = Callable[["DomainEvent"], Awaitable[None]]
DedupeKeyBuilder = Callable[["DomainEvent"], str]


class DomainEvent(BaseModel):
    """Matches the DomainEvent<T> envelope in 模块开发契约 §7."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    spec_version: Literal["1.0"] = Field("1.0", alias="specVersion")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(pattern=EVENT_TYPE_RE.pattern)
    source: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str = Field(alias="tenantId", min_length=1)
    correlation_id: str | None = Field(None, alias="correlationId")
    causation_id: str | None = Field(None, alias="causationId")
    data_version: int = Field(1, alias="dataVersion", ge=1)
    data: dict[str, Any]

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        uuid.UUID(value)
        return str(value)

    @field_validator("time")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("event time must be timezone-aware (UTC)")
        return value.astimezone(UTC)

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


def new_event(
    *,
    type: str,
    source: str,
    subject: str,
    tenant_id: str,
    data: dict[str, Any],
    data_version: int = 1,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> DomainEvent:
    payload: dict[str, Any] = {
        "type": type,
        "source": source,
        "subject": subject,
        "tenant_id": tenant_id,
        "data": data,
        "data_version": data_version,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
    }
    if event_id is not None:
        payload["id"] = event_id
    if occurred_at is not None:
        payload["time"] = occurred_at
    return DomainEvent(**payload)


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe(self, event_type: str, handler: Handler) -> None: ...


class EventDispatchError(RuntimeError):
    pass


class InMemoryEventBus:
    """Local host.event.bus.v1 adapter. Not durable; test/dev only."""

    def __init__(self, module_id: str = "host", metrics: MetricsRegistry | None = None) -> None:
        self.module_id = module_id
        self._metrics = metrics
        self._subscribers: dict[str, list[Handler]] = {}
        self._published: list[DomainEvent] = []

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._published)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        if not EVENT_TYPE_RE.fullmatch(event_type):
            raise ValueError(f"invalid event type: {event_type!r}")
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("publish requires a DomainEvent")
        self._published.append(event)
        if self._metrics is not None:
            self._metrics.inc("events_published_total", {"module": self.module_id, "event_type": event.type})
        errors: list[Exception] = []
        for handler in tuple(self._subscribers.get(event.type, ())):
            try:
                await handler(event)
            except Exception as exc:  # noqa: BLE001 - isolate one consumer from the rest
                logger.exception("event handler failed", extra={"code": "EVENT_HANDLER_FAILED"})
                errors.append(exc)
                if self._metrics is not None:
                    self._metrics.inc("event_handler_errors_total", {"module": self.module_id, "event_type": event.type})
        if errors:
            raise EventDispatchError(f"{len(errors)} event handler(s) failed for {event.type}") from errors[0]


class DedupeStore(Protocol):
    async def claim(self, key: str) -> bool: ...

    async def release(self, key: str) -> None: ...


class InMemoryDedupeStore:
    """Idempotency store keyed by event id (or a stable pairId+batchId key)."""

    def __init__(
        self,
        ttl_seconds: float = 86_400,
        max_entries: int = 100_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def claim(self, key: str) -> bool:
        async with self._lock:
            self._purge()
            if key in self._entries:
                return False
            if len(self._entries) >= self._max_entries:
                oldest = min(self._entries, key=self._entries.__getitem__)
                self._entries.pop(oldest, None)
            self._entries[key] = self._clock() + self._ttl
            return True

    async def release(self, key: str) -> None:
        async with self._lock:
            self._entries.pop(key, None)

    def _purge(self) -> None:
        now = self._clock()
        expired = [key for key, expires_at in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


class IdempotentConsumer:
    """Wraps a handler so duplicate event deliveries have no repeated side effects."""

    def __init__(
        self,
        handler: Handler,
        store: DedupeStore | None = None,
        key_builder: DedupeKeyBuilder | None = None,
    ) -> None:
        self._handler = handler
        self._store = store if store is not None else InMemoryDedupeStore()
        self._key_builder = key_builder if key_builder is not None else (lambda event: event.id)

    async def __call__(self, event: DomainEvent) -> bool:
        key = self._key_builder(event)
        if not await self._store.claim(key):
            return False
        try:
            await self._handler(event)
        except Exception:
            await self._store.release(key)
            raise
        return True


class Outbox(Protocol):
    async def enqueue(self, event: DomainEvent) -> None: ...

    async def pending(self, limit: int = 100) -> list[DomainEvent]: ...

    async def mark_published(self, event_id: str) -> None: ...


class InMemoryOutbox:
    """Local outbox used by tests; production must persist this atomically with data."""

    def __init__(self) -> None:
        self._entries: dict[str, DomainEvent] = {}
        self._published: set[str] = set()
        self._lock = asyncio.Lock()

    async def enqueue(self, event: DomainEvent) -> None:
        async with self._lock:
            self._entries[event.id] = event
            self._published.discard(event.id)

    async def pending(self, limit: int = 100) -> list[DomainEvent]:
        async with self._lock:
            items = [event for event_id, event in self._entries.items() if event_id not in self._published]
        return items[:limit]

    async def mark_published(self, event_id: str) -> None:
        async with self._lock:
            self._published.add(event_id)

    @property
    def pending_count(self) -> int:
        return sum(1 for event_id in self._entries if event_id not in self._published)


class OutboxPublisher:
    def __init__(self, outbox: Outbox, bus: EventBus, batch_size: int = 100) -> None:
        self._outbox = outbox
        self._bus = bus
        self._batch_size = batch_size

    async def drain(self) -> int:
        published = 0
        for event in await self._outbox.pending(self._batch_size):
            await self._bus.publish(event)
            await self._outbox.mark_published(event.id)
            published += 1
        return published
