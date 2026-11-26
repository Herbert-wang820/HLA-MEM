from __future__ import annotations

import pytest

from hla_contract_kit.naming import (
    error_code,
    is_capability,
    is_event_type,
    is_module_id,
    is_permission,
    module_code_prefix,
    validate_capability,
    validate_event_type,
    validate_permission,
)


@pytest.mark.parametrize(
    "value",
    [
        "memory-graph.episode.retrieve.v1",
        "memory-graph.consolidation.apply.v1",
        "persona-state.identity.version.create.v1",
        "host.config.v1",
        "host.auth.identity.v1",
    ],
)
def test_valid_capabilities(value: str) -> None:
    assert is_capability(value)
    assert validate_capability(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "memory.retrieve.v1",
        "memory-graph.episode.retrieve",
        "memory-graph.episode.retrieve.v0beta",
        "Memory-Graph.episode.retrieve.v1",
        "memory-graph..retrieve.v1",
        "",
        None,
        123,
    ],
)
def test_invalid_capabilities(value: object) -> None:
    assert not is_capability(value)
    with pytest.raises(ValueError):
        validate_capability(value)


def test_compound_action_and_host_namespace_are_documented_exceptions() -> None:
    assert is_capability("persona-state.identity.version.create.v1")
    assert is_capability("host.config.v1")
    # Business capabilities still require a domain and an action.
    assert not is_capability("memory-graph.v1")


@pytest.mark.parametrize(
    "value",
    [
        "memory-graph.episode.written.v1",
        "memory-graph.coactivation.recorded.v1",
        "persona-state.identity.rolled-back.v1",
        "async-consolidator.job.deadlettered.v1",
    ],
)
def test_valid_event_types(value: str) -> None:
    assert is_event_type(value)
    assert validate_event_type(value) == value


@pytest.mark.parametrize(
    "value",
    ["memory-graph.episode.written", "memory-graph.episode.written.v1.2", "episode.written.v1"],
)
def test_invalid_event_types(value: str) -> None:
    assert not is_event_type(value)
    with pytest.raises(ValueError):
        validate_event_type(value)


@pytest.mark.parametrize(
    "value",
    ["memory-graph.episode.read", "persona-state.proposal.review", "async-consolidator.job.create"],
)
def test_valid_permissions(value: str) -> None:
    assert is_permission(value)
    assert validate_permission(value) == value


@pytest.mark.parametrize("value", ["memory-graph.episode", "memory-graph.Episode.read", "memory-graph.episode.read.v1"])
def test_invalid_permissions(value: str) -> None:
    assert not is_permission(value)
    with pytest.raises(ValueError):
        validate_permission(value)


def test_module_ids_and_error_codes() -> None:
    assert is_module_id("memory-graph")
    assert not is_module_id("MemoryGraph")
    assert module_code_prefix("memory-graph") == "MEMORY_GRAPH"
    assert error_code("memory-graph", "feature", "not-implemented") == "MEMORY_GRAPH_FEATURE_NOT_IMPLEMENTED"
    with pytest.raises(ValueError):
        error_code("", "", "")
