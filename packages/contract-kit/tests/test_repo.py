from __future__ import annotations

from pathlib import Path

import pytest

from hla_contract_kit.checks import check_module, check_repo
from hla_contract_kit.manifest import load_manifest
from hla_contract_kit.schema import validate_instance

ROOT = Path(__file__).resolve().parents[3]
MODULES = {
    "reasoning-orchestrator",
    "memory-graph",
    "persona-state",
    "async-consolidator",
    "conversation-web",
    "admin-web",
}


def test_repository_contract_is_clean() -> None:
    result = check_repo(ROOT)
    assert result.issues == []
    assert {module.module_id for module in result.modules} == MODULES


def test_every_module_directory_matches_its_manifest_id() -> None:
    for module_id in MODULES:
        manifest = load_manifest(ROOT / "modules" / module_id)
        assert manifest.module_id == module_id
        assert manifest.kind in {"backend", "frontend"}


def test_memory_graph_module_check_is_clean() -> None:
    result = check_module(ROOT / "modules" / "memory-graph")
    assert result.issues == []
    assert result.stats["capabilities"] == 7
    assert result.stats["events"] == 3


def test_event_envelope_schema_rejects_missing_tenant() -> None:
    issues = validate_instance(
        {
            "specVersion": "1.0",
            "id": "11111111-1111-4111-8111-111111111111",
            "type": "memory-graph.episode.written.v1",
            "source": "memory-graph",
            "subject": "episode-1",
            "time": "2026-11-10T00:00:00Z",
            "dataVersion": 1,
            "data": {},
        },
        "event-envelope.schema.json",
    )
    assert any("tenantId" in issue for issue in issues)


def test_event_envelope_schema_accepts_valid_envelope() -> None:
    issues = validate_instance(
        {
            "specVersion": "1.0",
            "id": "11111111-1111-4111-8111-111111111111",
            "type": "memory-graph.episode.written.v1",
            "source": "memory-graph",
            "subject": "episode-1",
            "time": "2026-11-10T00:00:00Z",
            "tenantId": "tenant-1",
            "dataVersion": 1,
            "data": {},
        },
        "event-envelope.schema.json",
    )
    assert issues == []


@pytest.mark.parametrize(
    "relative",
    [
        "schemas/module.schema.json",
        "schemas/event-envelope.schema.json",
        "schemas/permissions.schema.json",
        "schemas/menu.schema.json",
    ],
)
def test_declared_schemas_are_valid_documents(relative: str) -> None:
    import json

    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
