"""FastAPI application factory shared by all backend modules."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, FastAPI

from hla_host.auth import IdentityMiddleware, IdentityProvider, dev_identity_provider
from hla_host.config import HostSettings
from hla_host.errors import register_exception_handlers
from hla_host.events import EventBus, InMemoryEventBus
from hla_host.health import ReadinessCheck, ReadinessRegistry, create_health_router
from hla_host.observability import (
    BodySizeLimitMiddleware,
    MetricsRegistry,
    RequestContextMiddleware,
    TimeoutMiddleware,
    configure_logging,
)


def create_module_app(
    *,
    module_id: str,
    name: str,
    version: str,
    description: str,
    settings: HostSettings,
    routers: Sequence[APIRouter] = (),
    readiness_checks: Sequence[ReadinessCheck] = (),
    identity_provider: IdentityProvider | None = None,
    event_bus: EventBus | None = None,
    metrics: MetricsRegistry | None = None,
    dev_permissions: Sequence[str] = (),
    timeout_exempt_paths: Sequence[str] = (),
) -> FastAPI:
    logger = configure_logging(module_id, settings.log_level)
    metrics = metrics if metrics is not None else MetricsRegistry()

    if identity_provider is None:
        identity_provider = dev_identity_provider(settings, dev_permissions)
    if event_bus is None:
        if settings.environment != "dev":
            raise RuntimeError(
                "a real host.event.bus.v1 adapter is required when HLA_ENV is not 'dev'; "
                "refusing to start with the in-memory bus"
            )
        event_bus = InMemoryEventBus(module_id=module_id, metrics=metrics)

    readiness = ReadinessRegistry(readiness_checks)
    app = FastAPI(
        title=f"HLA-MEM {name}",
        version=version,
        description=description,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    app.state.module_id = module_id
    app.state.settings = settings
    app.state.metrics = metrics
    app.state.event_bus = event_bus
    app.state.readiness = readiness
    app.state.logger = logger

    # Middleware is added innermost-first; the request context is outermost.
    app.add_middleware(
        TimeoutMiddleware,
        module_id=module_id,
        timeout_seconds=settings.request_timeout_ms / 1000,
        exempt_paths=timeout_exempt_paths,
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        module_id=module_id,
        max_bytes=settings.max_body_bytes,
    )
    app.add_middleware(IdentityMiddleware, provider=identity_provider)
    app.add_middleware(
        RequestContextMiddleware,
        module_id=module_id,
        metrics=metrics,
        logger=logger,
        excluded_prefixes=("/internal/",),
    )

    register_exception_handlers(app, module_id)
    app.include_router(create_health_router(module_id=module_id, version=version, registry=readiness, metrics=metrics))
    for router in routers:
        app.include_router(router)
    return app


def state_value(app: FastAPI, key: str, default: Any = None) -> Any:
    return getattr(app.state, key, default)
