"""Configuration loading with explicit types, defaults and secret redaction."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfigField:
    key: str
    type: type
    default: Any = None
    required: bool = False
    sensitive: bool = False
    dynamic: bool = False
    scope: str = "module"
    description: str = ""


def env_name(key: str) -> str:
    """memory-graph.store.dsn -> HLA_MEMORY_GRAPH_STORE_DSN."""
    normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
    return f"HLA_{normalized}"


def module_port(module_id: str, default: int) -> int:
    name = f"HLA_{re.sub(r'[^A-Z0-9]+', '_', module_id.upper()).strip('_')}_PORT"
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be a valid TCP port, got {port}")
    return port


def _parse_bool(raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"not a boolean: {raw!r}")


def _parse(raw: str, field: ConfigField) -> Any:
    if field.type is bool:
        return _parse_bool(raw)
    if field.type is int:
        return int(raw)
    if field.type is float:
        return float(raw)
    if field.type is str:
        return raw
    raise TypeError(f"unsupported config type for {field.key}: {field.type!r}")


class ModuleConfig:
    """Validated module configuration.

    Empty required values are treated as missing; optional empty values fall back
    to the declared default.  Secrets are redacted by ``describe``.
    """

    def __init__(
        self,
        module_id: str,
        fields: Sequence[ConfigField],
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.module_id = module_id
        self._fields = {field_def.key: field_def for field_def in fields}
        self._values: dict[str, Any] = {}
        self._issues: list[str] = []
        source = os.environ if environ is None else environ
        for field_def in fields:
            name = env_name(field_def.key)
            raw = source.get(name)
            if raw is None or raw == "":
                if field_def.required:
                    self._issues.append(f"{field_def.key}: required configuration {name} is not set")
                else:
                    self._values[field_def.key] = field_def.default
                continue
            try:
                self._values[field_def.key] = _parse(raw, field_def)
            except (TypeError, ValueError):
                self._issues.append(f"{field_def.key}: invalid value for {name}")
                self._values[field_def.key] = field_def.default

    def get(self, key: str) -> Any:
        if key not in self._fields:
            raise KeyError(f"unknown configuration key: {key}")
        return self._values.get(key)

    @property
    def issues(self) -> tuple[str, ...]:
        return tuple(self._issues)

    @property
    def is_ready(self) -> bool:
        return not self._issues

    def describe(self) -> dict[str, dict[str, Any]]:
        described: dict[str, dict[str, Any]] = {}
        for key, field_def in self._fields.items():
            value = self._values.get(key)
            if field_def.sensitive and value not in (None, ""):
                rendered: Any = "***redacted***"
            else:
                rendered = value
            described[key] = {
                "value": rendered,
                "type": field_def.type.__name__,
                "required": field_def.required,
                "sensitive": field_def.sensitive,
                "dynamic": field_def.dynamic,
                "scope": field_def.scope,
                "description": field_def.description,
            }
        return described


@dataclass(frozen=True, slots=True)
class HostSettings:
    environment: str = "dev"
    log_level: str = "INFO"
    dev_tenant_id: str = "tenant-dev"
    dev_subject: str = "dev-user"
    dev_permissions: tuple[str, ...] = ()
    request_timeout_ms: int = 30_000
    max_body_bytes: int = 1_048_576
    extra: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> HostSettings:
        source = os.environ if environ is None else environ

        def read_int(name: str, default: int) -> int:
            raw = source.get(name)
            if raw is None or raw == "":
                return default
            return int(raw)

        permissions = tuple(
            item.strip() for item in source.get("HLA_DEV_PERMISSIONS", "").split(",") if item.strip()
        )
        return cls(
            environment=source.get("HLA_ENV", "dev").strip() or "dev",
            log_level=source.get("HLA_LOG_LEVEL", "INFO").strip().upper() or "INFO",
            dev_tenant_id=source.get("HLA_DEV_TENANT_ID", "tenant-dev"),
            dev_subject=source.get("HLA_DEV_SUBJECT", "dev-user"),
            dev_permissions=permissions,
            request_timeout_ms=read_int("HLA_REQUEST_TIMEOUT_MS", 30_000),
            max_body_bytes=read_int("HLA_MAX_BODY_BYTES", 1_048_576),
        )
