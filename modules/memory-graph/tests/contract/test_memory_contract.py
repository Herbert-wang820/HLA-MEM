from __future__ import annotations

import json
from pathlib import Path

from hla_memory_graph.app import create_app
from jsonschema import Draft202012Validator

from hla_contract_kit.checks import check_module
from hla_contract_kit.manifest import load_manifest
from hla_contract_kit.openapi import iter_operations

MODULE_DIR = Path(__file__).resolve().parents[2]


def test_module_contract_is_clean() -> None:
    result = check_module(MODULE_DIR)
    assert not result.issues


def test_openapi_covers_every_declared_capability() -> None:
    manifest = load_manifest(MODULE_DIR)
    spec = create_app().openapi()
    exposed = {operation.capability for operation in iter_operations(spec) if operation.capability}
    assert set(manifest.capabilities) <= exposed


def _event_schema(name: str) -> dict:
    path = MODULE_DIR / "contracts" / "events" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_episode_written_event_matches_schema() -> None:
    schema = _event_schema("memory-graph.episode.written.v1.schema.json")
    Draft202012Validator(schema).validate(
        {
            "type": "memory-graph.episode.written.v1",
            "data": {
                "episodeId": "11111111-1111-4111-8111-111111111111",
                "sessionId": "session-1",
                "occurredAt": "2026-11-10T00:00:00Z",
                "contentHash": "a" * 64,
            },
        }
    )


def test_coactivation_event_rejects_unknown_field() -> None:
    schema = _event_schema("memory-graph.coactivation.recorded.v1.schema.json")
    validator = Draft202012Validator(schema)
    errors = list(
        validator.iter_errors(
            {
                "type": "memory-graph.coactivation.recorded.v1",
                "data": {
                    "batchId": "22222222-2222-4222-8222-222222222222",
                    "retrievalId": "33333333-3333-4333-8333-333333333333",
                    "pairs": [],
                    "pairCount": 0,
                    "unexpected": True,
                },
            }
        )
    )
    assert errors
