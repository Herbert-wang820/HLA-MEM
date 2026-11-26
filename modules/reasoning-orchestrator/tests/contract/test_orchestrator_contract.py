from __future__ import annotations

import json
from pathlib import Path

from hla_orchestrator.app import create_app
from jsonschema import Draft202012Validator

from hla_contract_kit.checks import check_module
from hla_contract_kit.manifest import load_manifest
from hla_contract_kit.openapi import iter_operations

MODULE_DIR = Path(__file__).resolve().parents[2]
EVENTS_DIR = MODULE_DIR / "contracts" / "events"


def test_module_contract_is_clean() -> None:
    assert not check_module(MODULE_DIR).issues


def test_openapi_covers_every_declared_capability() -> None:
    manifest = load_manifest(MODULE_DIR)
    exposed = {operation.capability for operation in iter_operations(create_app().openapi()) if operation.capability}
    assert set(manifest.capabilities) <= exposed


def test_event_schemas_are_valid_and_typed() -> None:
    schemas = sorted(EVENTS_DIR.glob("*.schema.json"))
    assert schemas, "module must declare at least one event schema"
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        event_type = path.name.removesuffix(".schema.json")
        assert schema["properties"]["type"]["const"] == event_type
        assert schema["$defs"]["data"]["additionalProperties"] is False


def test_event_envelope_sample_validates() -> None:
    envelope = json.loads((MODULE_DIR.parents[1] / "schemas" / "event-envelope.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(envelope).validate(
        {
            "specVersion": "1.0",
            "id": "11111111-1111-4111-8111-111111111111",
            "type": "reasoning-orchestrator.turn.processed.v1",
            "source": "reasoning-orchestrator",
            "subject": "subject-1",
            "time": "2026-11-10T00:00:00Z",
            "tenantId": "tenant-1",
            "dataVersion": 1,
            "data": {},
        }
    )
