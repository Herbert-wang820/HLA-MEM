"""Module manifest loading and typed accessors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hla_contract_kit.schema import load_yaml, validate_instance


class ManifestError(ValueError):
    """Raised when module.yaml is missing, malformed or schema-invalid."""


@dataclass(frozen=True, slots=True)
class Manifest:
    path: Path
    raw: dict[str, Any]

    @property
    def module_dir(self) -> Path:
        return self.path.parent

    @property
    def module_id(self) -> str:
        return str(self.raw["metadata"]["id"])

    @property
    def name(self) -> str:
        return str(self.raw["metadata"]["name"])

    @property
    def description(self) -> str:
        return str(self.raw["metadata"]["description"])

    @property
    def version(self) -> str:
        return str(self.raw["metadata"]["version"])

    @property
    def kind(self) -> str:
        return str(self.raw["metadata"]["kind"])

    @property
    def compatibility(self) -> dict[str, str]:
        return dict(self.raw["compatibility"])

    @property
    def entrypoints(self) -> dict[str, str]:
        return dict(self.raw["entrypoints"])

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(self.raw["provides"]["capabilities"])

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self.raw["provides"]["events"])

    @property
    def mandatory(self) -> tuple[str, ...]:
        return tuple(self.raw["requires"]["mandatory"])

    @property
    def optional(self) -> tuple[str, ...]:
        return tuple(self.raw["requires"]["optional"])

    @property
    def contracts(self) -> dict[str, str]:
        return dict(self.raw["contracts"])


def load_manifest(path: Path) -> Manifest:
    """Load and schema-validate a module manifest.

    ``path`` may point at the module directory or at ``module.yaml``.
    """
    manifest_path = path / "module.yaml" if path.is_dir() else path
    if not manifest_path.is_file():
        raise ManifestError(f"module.yaml not found: {manifest_path}")
    try:
        raw = load_yaml(manifest_path)
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{manifest_path}: top-level YAML must be a mapping")
    issues = validate_instance(raw, "module.schema.json")
    if issues:
        detail = "\n".join(f"  - {issue}" for issue in issues)
        raise ManifestError(f"{manifest_path}: schema validation failed\n{detail}")
    return Manifest(path=manifest_path, raw=raw)
