from __future__ import annotations

import pytest

from hla_host.config import ConfigField, HostSettings, ModuleConfig, env_name, module_port


def test_env_name_normalizes_punctuation() -> None:
    assert env_name("memory-graph.store.dsn") == "HLA_MEMORY_GRAPH_STORE_DSN"
    assert env_name("persona-state.adaptation.maxDelta") == "HLA_PERSONA_STATE_ADAPTATION_MAXDELTA"


def test_required_config_reports_missing_value() -> None:
    config = ModuleConfig("demo", [ConfigField("demo.db.dsn", str, required=True)], environ={})
    assert not config.is_ready
    assert config.get("demo.db.dsn") is None
    assert "demo.db.dsn" in config.issues[0]


def test_optional_config_falls_back_to_default() -> None:
    config = ModuleConfig("demo", [ConfigField("demo.retries", int, default=3)], environ={})
    assert config.is_ready
    assert config.get("demo.retries") == 3


def test_invalid_value_is_an_issue_and_uses_default() -> None:
    config = ModuleConfig(
        "demo",
        [ConfigField("demo.retries", int, default=3)],
        environ={"HLA_DEMO_RETRIES": "many"},
    )
    assert not config.is_ready
    assert config.get("demo.retries") == 3


def test_sensitive_values_are_redacted() -> None:
    config = ModuleConfig(
        "demo",
        [ConfigField("demo.db.dsn", str, default="postgres://secret", sensitive=True)],
        environ={},
    )
    described = config.describe()
    assert described["demo.db.dsn"]["value"] == "***redacted***"
    assert described["demo.db.dsn"]["sensitive"] is True


def test_module_port_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLA_MEMORY_GRAPH_PORT", "18082")
    assert module_port("memory-graph", 8082) == 18082


def test_module_port_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLA_MEMORY_GRAPH_PORT", "70000")
    with pytest.raises(ValueError):
        module_port("memory-graph", 8082)


def test_host_settings_from_env() -> None:
    settings = HostSettings.from_env(
        {
            "HLA_ENV": "test",
            "HLA_LOG_LEVEL": "debug",
            "HLA_DEV_TENANT_ID": "t-1",
            "HLA_DEV_PERMISSIONS": "a.b.c, d.e.f",
            "HLA_REQUEST_TIMEOUT_MS": "1500",
            "HLA_MAX_BODY_BYTES": "2048",
        }
    )
    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert settings.dev_tenant_id == "t-1"
    assert settings.dev_permissions == ("a.b.c", "d.e.f")
    assert settings.request_timeout_ms == 1500
    assert settings.max_body_bytes == 2048
