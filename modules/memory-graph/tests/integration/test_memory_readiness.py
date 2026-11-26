from __future__ import annotations

from fastapi.testclient import TestClient

from hla_host.app import create_module_app
from hla_host.config import ConfigField, HostSettings, ModuleConfig
from hla_host.events import InMemoryEventBus
from hla_host.health import ConfigReadinessCheck


def _app_with_missing_config():
    config = ModuleConfig(
        "memory-graph",
        [ConfigField("memory-graph.required.setting", str, required=True)],
        environ={},
    )
    return create_module_app(
        module_id="memory-graph",
        name="test",
        version="0.1.0",
        description="test",
        settings=HostSettings(environment="dev"),
        readiness_checks=(ConfigReadinessCheck(config),),
        event_bus=InMemoryEventBus(),
        dev_permissions=(),
    )


def test_readiness_returns_503_when_required_config_is_missing() -> None:
    response = TestClient(_app_with_missing_config()).get("/internal/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"][0]["ready"] is False
    assert "memory-graph.required.setting" in body["checks"][0]["detail"]
