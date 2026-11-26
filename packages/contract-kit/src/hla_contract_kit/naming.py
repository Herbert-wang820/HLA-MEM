"""Naming rules from 模块开发契约 §5, §7, §12 and §6.4."""

from __future__ import annotations

import re

MODULE_ID_PATTERN = r"^[a-z][a-z0-9-]{1,62}$"
CAPABILITY_PATTERN = r"^(?:host\.[a-z][a-z0-9]*\.v(0|[1-9][0-9]*)|[a-z][a-z0-9-]*\.[a-z][a-z0-9]*\.(?:[a-z][a-z0-9]*\.)+v(0|[1-9][0-9]*))$"
EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9]*\.[a-z][a-z0-9-]*\.v(0|[1-9][0-9]*)$"
PERMISSION_PATTERN = r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9]*\.[a-z][a-z0-9]*$"
ERROR_CODE_PATTERN = r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$"
SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"

MODULE_ID_RE = re.compile(MODULE_ID_PATTERN)
CAPABILITY_RE = re.compile(CAPABILITY_PATTERN)
EVENT_TYPE_RE = re.compile(EVENT_TYPE_PATTERN)
PERMISSION_RE = re.compile(PERMISSION_PATTERN)
ERROR_CODE_RE = re.compile(ERROR_CODE_PATTERN)
SEMVER_RE = re.compile(SEMVER_PATTERN)

HOST_CAPABILITIES = frozenset(
    {
        "host.auth.identity.v1",
        "host.config.v1",
        "host.event.bus.v1",
    }
)


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def is_capability(value: object) -> bool:
    return _matches(CAPABILITY_RE, value)


def is_event_type(value: object) -> bool:
    return _matches(EVENT_TYPE_RE, value)


def is_permission(value: object) -> bool:
    return _matches(PERMISSION_RE, value)


def is_module_id(value: object) -> bool:
    return _matches(MODULE_ID_RE, value)


def is_error_code(value: object) -> bool:
    return _matches(ERROR_CODE_RE, value)


def is_semver(value: object) -> bool:
    return _matches(SEMVER_RE, value)


def _require(pattern: re.Pattern[str], value: object, label: str, example: str) -> str:
    if not _matches(pattern, value):
        raise ValueError(f"invalid {label}: {value!r}; expected format like {example}")
    return str(value)


def validate_capability(value: object) -> str:
    return _require(CAPABILITY_RE, value, "capability", "memory-graph.episode.retrieve.v1")


def validate_event_type(value: object) -> str:
    return _require(EVENT_TYPE_RE, value, "event type", "memory-graph.coactivation.recorded.v1")


def validate_permission(value: object) -> str:
    return _require(PERMISSION_RE, value, "permission", "memory-graph.episode.read")


def module_code_prefix(module_id: str) -> str:
    """memory-graph -> MEMORY_GRAPH (used in error codes)."""
    return re.sub(r"[^A-Z0-9]+", "_", module_id.upper()).strip("_")


def error_code(module_id: str, domain: str, reason: str) -> str:
    parts = [module_code_prefix(module_id), domain, reason]
    normalized = [re.sub(r"[^A-Z0-9]+", "_", part.upper()).strip("_") for part in parts]
    code = "_".join(part for part in normalized if part)
    if not ERROR_CODE_RE.fullmatch(code):
        raise ValueError(f"invalid error code: {code!r}")
    return code
