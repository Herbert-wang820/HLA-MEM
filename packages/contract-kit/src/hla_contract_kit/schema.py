"""Schema loading and JSON/YAML helpers."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def find_repo_root(start: Path) -> Path:
    """Locate the repository root from any path inside it."""
    env = os.environ.get("HLA_REPO_ROOT")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).resolve())
    start = start.resolve()
    candidates.extend([start, *start.parents])
    for candidate in candidates:
        if (candidate / "schemas" / "module.schema.json").is_file() and (candidate / "modules").is_dir():
            return candidate
    raise FileNotFoundError(f"cannot locate HLA-MEM repo root from {start}")


def schemas_dir() -> Path:
    env = os.environ.get("HLA_SCHEMAS_DIR")
    if env:
        path = Path(env).resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"HLA_SCHEMAS_DIR does not exist: {path}")
        return path
    # <repo>/packages/contract-kit/src/hla_contract_kit/schema.py
    repo = Path(__file__).resolve().parents[4]
    path = repo / "schemas"
    if not path.is_dir():
        raise FileNotFoundError(
            f"schemas directory not found at {path}; set HLA_SCHEMAS_DIR or install contract-kit editable from the repo"
        )
    return path


def load_schema(name: str) -> dict[str, Any]:
    if name not in _SCHEMA_CACHE:
        path = schemas_dir() / name
        if not path.is_file():
            raise FileNotFoundError(f"unknown schema: {name}")
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"schema {name} must be a JSON object")
        _SCHEMA_CACHE[name] = data
    return _SCHEMA_CACHE[name]


@lru_cache(maxsize=16)
def validator_for(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:  # pragma: no cover - schema authoring error
        raise ValueError(f"invalid JSON Schema {name}: {exc.message}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_instance(instance: Any, schema_name: str) -> list[str]:
    """Return human-readable validation issues (empty list means valid)."""
    validator = validator_for(schema_name)
    issues: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda err: (list(err.absolute_path), err.message)):
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        issues.append(f"{path}: {error.message}")
    return issues


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        try:
            return yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML in {path}: {exc}") from exc


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc
