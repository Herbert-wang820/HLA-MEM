"""FastAPI application for memory-graph."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from hla_host.app import create_module_app
from hla_host.config import ModuleConfig
from hla_host.events import DomainEvent, InMemoryEventBus
from hla_host.health import ConfigReadinessCheck
from hla_host.idempotency import InMemoryIdempotencyStore
from hla_host.observability import MetricsRegistry
from hla_memory_graph.api.idempotency import IdempotencyGuard
from hla_memory_graph.api.routes import internal_router, router
from hla_memory_graph.application.service import MemoryService
from hla_memory_graph.infrastructure.embedding import HashingEmbedder
from hla_memory_graph.infrastructure.memory_store import InMemoryMemoryStore
from hla_memory_graph.internal.settings import (
    DEV_PERMISSIONS,
    MODULE_ID,
    MODULE_VERSION,
    Settings,
)

MODULE_NAME = "记忆图"
MODULE_DESCRIPTION = "情景与概念图存储、双路径检索、共激活事件与检索审计"


class StoreReadinessCheck:
    name = "store"

    def __init__(self, store: InMemoryMemoryStore) -> None:
        self._store = store

    async def __call__(self) -> tuple[bool, str | None]:
        return await self._store.health()


def _int(config: ModuleConfig, key: str, default: int) -> int:
    value: Any = config.get(key)
    return int(value) if value is not None else default


def _float(config: ModuleConfig, key: str, default: float) -> float:
    value: Any = config.get(key)
    return float(value) if value is not None else default


def create_app() -> FastAPI:
    settings = Settings.load()
    metrics = MetricsRegistry()
    event_bus = InMemoryEventBus(module_id=MODULE_ID, metrics=metrics) if settings.host.environment == "dev" else None
    store = InMemoryMemoryStore()
    embedder = HashingEmbedder(_int(settings.config, "memory-graph.embedding.dim", 256))

    async def publish(event: DomainEvent) -> None:
        if event_bus is not None:
            await event_bus.publish(event)

    service = MemoryService(
        store=store,
        embedder=embedder,
        publish=publish,
        semantic_top_k=_int(settings.config, "memory-graph.retrieval.semanticTopK", 20),
        spreading_top_k=_int(settings.config, "memory-graph.retrieval.spreadingTopK", 20),
        top_k_max=_int(settings.config, "memory-graph.retrieval.topKMax", 50),
        min_score=_float(settings.config, "memory-graph.retrieval.minScore", 0.05),
        coactivation_top_n=_int(settings.config, "memory-graph.retrieval.coactivationTopN", 10),
        spreading_decay=_float(settings.config, "memory-graph.retrieval.spreadingDecay", 0.6),
        max_hops=_int(settings.config, "memory-graph.retrieval.maxHops", 2),
        w_min=_float(settings.config, "memory-graph.fade.wMin", 0.05),
    )

    app = create_module_app(
        module_id=MODULE_ID,
        name=MODULE_NAME,
        version=MODULE_VERSION,
        description=MODULE_DESCRIPTION,
        settings=settings.host,
        routers=(router, internal_router),
        readiness_checks=(ConfigReadinessCheck(settings.config), StoreReadinessCheck(store)),
        event_bus=event_bus,
        metrics=metrics,
        dev_permissions=DEV_PERMISSIONS,
    )
    app.state.memory_service = service
    app.state.idempotency_guard = IdempotencyGuard(InMemoryIdempotencyStore(), MODULE_ID)
    return app


__all__ = ["create_app", "StoreReadinessCheck"]
