"""Minimal OpenAPI inspection used by contract checks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
HEALTH_PATHS = ("/internal/health", "/internal/ready", "/internal/metrics")


@dataclass(frozen=True, slots=True)
class Operation:
    path: str
    method: str
    operation_id: str | None
    capability: str | None
    permission: str | None
    raw: dict[str, Any]


def load_openapi(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        from hla_contract_kit.schema import load_yaml

        data = load_yaml(path)
    else:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: OpenAPI document must be an object")
    return data


def iter_operations(spec: dict[str, Any]) -> Iterator[Operation]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            yield Operation(
                path=str(path),
                method=method.upper(),
                operation_id=operation.get("operationId"),
                capability=operation.get("x-capability"),
                permission=operation.get("x-permission"),
                raw=operation,
            )
