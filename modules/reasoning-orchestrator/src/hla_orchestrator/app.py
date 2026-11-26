"""FastAPI application for reasoning-orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from hla_host.app import create_module_app
from hla_host.config import ModuleConfig
from hla_host.events import InMemoryEventBus
from hla_host.health import ConfigReadinessCheck
from hla_host.observability import MetricsRegistry
from hla_orchestrator.api.routes import internal_router, router
from hla_orchestrator.application.ports import CompleterPort, MemoryPort, PersonaPort
from hla_orchestrator.application.service import GateSettings, TurnService
from hla_orchestrator.infrastructure.llm_completer import OpenAICompatibleCompleter
from hla_orchestrator.infrastructure.llm_config import LLMConfig, LLMConfigStore
from hla_orchestrator.infrastructure.memory_client import HttpMemoryClient
from hla_orchestrator.infrastructure.persona_client import HttpPersonaClient
from hla_orchestrator.infrastructure.template_completer import TemplateCompleter
from hla_orchestrator.infrastructure.turn_store import TurnStore
from hla_orchestrator.internal.settings import (
    DEV_PERMISSIONS,
    MODULE_ID,
    MODULE_VERSION,
    Settings,
)

MODULE_NAME = "推理编排器"
MODULE_DESCRIPTION = "对话回合编排、System-One 门控、记忆检索与降级路径"


def _str(config: ModuleConfig, key: str, default: str) -> str:
    value: Any = config.get(key)
    return str(value) if value is not None else default


def _int(config: ModuleConfig, key: str, default: int) -> int:
    value: Any = config.get(key)
    return int(value) if value is not None else default


def _float(config: ModuleConfig, key: str, default: float) -> float:
    value: Any = config.get(key)
    return float(value) if value is not None else default


def create_app(
    *,
    memory_client: MemoryPort | None = None,
    template_completer: CompleterPort | None = None,
    llm_completer: CompleterPort | None = None,
    config_store: LLMConfigStore | None = None,
    gate_settings: GateSettings | None = None,
    persona_client: PersonaPort | None = None,
) -> FastAPI:
    settings = Settings.load()
    metrics = MetricsRegistry()
    event_bus = InMemoryEventBus(module_id=MODULE_ID, metrics=metrics) if settings.host.environment == "dev" else None

    memory_created = memory_client is None
    memory = memory_client or HttpMemoryClient(
        _str(settings.config, "reasoning-orchestrator.memory.baseUrl", "http://127.0.0.1:8082"),
        retrieval_timeout=_int(settings.config, "reasoning-orchestrator.memory.timeoutMs", 800) / 1000,
        write_timeout=2.0,
    )

    default_llm = LLMConfig(
        enabled=bool(_str(settings.config, "reasoning-orchestrator.llm.apiKey", "")),
        base_url=_str(settings.config, "reasoning-orchestrator.llm.baseUrl", "https://api.openai.com/v1"),
        model=_str(settings.config, "reasoning-orchestrator.llm.model", "gpt-4o-mini"),
        api_key=_str(settings.config, "reasoning-orchestrator.llm.apiKey", ""),
        temperature=_float(settings.config, "reasoning-orchestrator.llm.temperature", 0.7),
        max_tokens=_int(settings.config, "reasoning-orchestrator.llm.maxTokens", 512),
    )
    store = config_store or LLMConfigStore(
        Path(_str(settings.config, "reasoning-orchestrator.llm.configPath", "var/reasoning-orchestrator/llm.json")),
        default_llm,
    )
    llm = llm_completer or OpenAICompatibleCompleter(
        store,
        timeout=_int(settings.config, "reasoning-orchestrator.llm.timeoutMs", 20_000) / 1000,
    )
    template = template_completer or TemplateCompleter()
    persona_created = persona_client is None
    persona = persona_client or HttpPersonaClient(
        _str(settings.config, "reasoning-orchestrator.persona.baseUrl", "http://127.0.0.1:8083"),
        timeout=_int(settings.config, "reasoning-orchestrator.persona.timeoutMs", 500) / 1000,
    )
    gate = gate_settings or GateSettings(
        tau=_float(settings.config, "reasoning-orchestrator.gate.tau", 0.2),
        beta=_float(settings.config, "reasoning-orchestrator.gate.beta", 0.4),
        top_k=_int(settings.config, "reasoning-orchestrator.retrieval.topK", 8),
        updated_at=datetime.now(UTC),
    )

    async def publish(event) -> None:
        if event_bus is not None:
            await event_bus.publish(event)

    service = TurnService(
        memory=memory,
        template=template,
        llm=llm,
        store=TurnStore(),
        publish=publish,
        gate=gate,
        persona=persona,
        persona_fallback=_str(
            settings.config,
            "reasoning-orchestrator.persona.static",
            "你是一位耐心、务实、重视长期记忆的对话伙伴。",
        ),
    )

    app = create_module_app(
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
        timeout_exempt_paths=("/api/reasoning-orchestrator/v1/turns",),
    )
    app.state.turn_service = service
    app.state.llm_store = store
    app.state.gate_settings = gate
    shutdown = getattr(app.router, "on_shutdown", None)
    if shutdown is not None:
        if memory_created:
            shutdown.append(memory.close)  # type: ignore[attr-defined]
        if persona_created:
            shutdown.append(persona.close)  # type: ignore[attr-defined]
    return app


__all__ = ["create_app", "GateSettings"]
