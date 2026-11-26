"""FastAPI application for async-consolidator."""

from __future__ import annotations

from fastapi import FastAPI

from hla_consolidator.api.routes import internal_router, router
from hla_consolidator.internal.settings import (
    DEV_PERMISSIONS,
    MODULE_ID,
    MODULE_VERSION,
    Settings,
)
from hla_host.app import create_module_app
from hla_host.events import InMemoryEventBus
from hla_host.health import ConfigReadinessCheck
from hla_host.observability import MetricsRegistry

MODULE_NAME = "异步巩固器"
MODULE_DESCRIPTION = "巩固作业队列、重试/死信、边权强化与枢纽蒸馏"


def create_app() -> FastAPI:
    settings = Settings.load()
    metrics = MetricsRegistry()
    event_bus = InMemoryEventBus(module_id=MODULE_ID, metrics=metrics) if settings.host.environment == "dev" else None
    return create_module_app(
        module_id=MODULE_ID,
        name=MODULE_NAME,
        version=MODULE_VERSION,
        description=MODULE_DESCRIPTION,
        settings=settings.host,
        routers=(router, internal_router),
        readiness_checks=(ConfigReadinessCheck(settings.config),),
        event_bus=event_bus,
        metrics=metrics,
        dev_permissions=DEV_PERMISSIONS,
    )
