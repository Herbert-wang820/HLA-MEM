"""FastAPI application for persona-state."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from hla_host.app import create_module_app
from hla_host.config import ModuleConfig
from hla_host.events import InMemoryEventBus
from hla_host.health import ConfigReadinessCheck
from hla_host.idempotency import InMemoryIdempotencyStore
from hla_host.observability import MetricsRegistry
from hla_persona_state.api.idempotency import IdempotencyGuard
from hla_persona_state.api.routes import router
from hla_persona_state.application.service import PersonaService
from hla_persona_state.infrastructure.store import InMemoryPersonaStore
from hla_persona_state.internal.settings import (
    DEV_PERMISSIONS,
    MODULE_ID,
    MODULE_VERSION,
    Settings,
)

MODULE_NAME = "人格状态"
MODULE_DESCRIPTION = "身份层版本化、有界适应层、变更提案审批与经历日志"


def _float(config: ModuleConfig, key: str, default: float) -> float:
    value: Any = config.get(key)
    return float(value) if value is not None else default


def _int(config: ModuleConfig, key: str, default: int) -> int:
    value: Any = config.get(key)
    return int(value) if value is not None else default


def create_app() -> FastAPI:
    settings = Settings.load()
    metrics = MetricsRegistry()
    event_bus = InMemoryEventBus(module_id=MODULE_ID, metrics=metrics) if settings.host.environment == "dev" else None

    async def publish(event) -> None:
        if event_bus is not None:
            await event_bus.publish(event)

    service = PersonaService(
        store=InMemoryPersonaStore(),
        publish=publish,
        max_delta=_float(settings.config, "persona-state.adaptation.maxDelta", 0.15),
        window_hours=_int(settings.config, "persona-state.adaptation.windowHours", 24),
        max_drift=_float(settings.config, "persona-state.adaptation.maxDrift", 0.30),
    )

    app = create_module_app(
        module_id=MODULE_ID,
        name=MODULE_NAME,
        version=MODULE_VERSION,
        description=MODULE_DESCRIPTION,
        settings=settings.host,
        routers=(router,),
        readiness_checks=(ConfigReadinessCheck(settings.config),),
        event_bus=event_bus,
        metrics=metrics,
        dev_permissions=DEV_PERMISSIONS,
    )
    app.state.persona_service = service
    app.state.idempotency_guard = IdempotencyGuard(InMemoryIdempotencyStore(), MODULE_ID)
    return app
