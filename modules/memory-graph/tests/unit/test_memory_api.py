from __future__ import annotations

from fastapi.testclient import TestClient
from hla_memory_graph.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _write(
    client: TestClient,
    content: str,
    key: str,
    *,
    session: str = "s1",
    occurred: str = "2026-11-10T10:00:00Z",
) -> dict:
    response = client.post(
        "/api/memory-graph/v1/episodes",
        headers={"Idempotency-Key": key},
        json={"sessionId": session, "content": content, "occurredAt": occurred},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _retrieve(client: TestClient, query: str, key: str, **extra: object) -> dict:
    response = client.post(
        "/api/memory-graph/v1/retrievals",
        headers={"Idempotency-Key": key},
        json={"query": query, "topK": 10, **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_write_read_and_retract() -> None:
    client = _client()
    episode = _write(client, "green tea is calming", "w1")

    read = client.get(f"/api/memory-graph/v1/episodes/{episode['episodeId']}")
    assert read.status_code == 200
    assert read.json()["content"] == "green tea is calming"

    retracted = client.post(
        f"/api/memory-graph/v1/episodes/{episode['episodeId']}/retract",
        headers={"Idempotency-Key": "r1"},
        json={"reasonCode": "user_request", "note": "asked to forget"},
    )
    assert retracted.status_code == 200
    body = retracted.json()
    assert body["retracted"] is True
    assert body["retractedAt"]
    assert body["retractReason"].startswith("user_request")

    # The original content is preserved; retraction is a marker.
    assert body["content"] == "green tea is calming"


def test_write_is_idempotent_and_conflicts_on_different_body() -> None:
    client = _client()
    first = _write(client, "hello world", "same-key")
    second = _write(client, "hello world", "same-key")
    assert second["episodeId"] == first["episodeId"]

    conflict = client.post(
        "/api/memory-graph/v1/episodes",
        headers={"Idempotency-Key": "same-key"},
        json={"sessionId": "s1", "content": "different", "occurredAt": "2026-11-10T10:00:00Z"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "MEMORY_GRAPH_IDEMPOTENCY_CONFLICT"


def test_retrieval_creates_audit_and_coactivation_edge() -> None:
    client = _client()
    _write(client, "green tea", "a1")
    _write(client, "green tea with jasmine", "a2")
    _write(client, "basketball", "a3")

    result = _retrieve(client, "green tea", "ret-1")
    assert result["mergedTopK"] >= 2
    ids = {candidate["episodeId"] for candidate in result["candidates"]}
    assert len(ids) >= 2
    assert all(candidate["sources"] for candidate in result["candidates"])

    audit = client.get(f"/api/memory-graph/v1/retrievals/{result['retrievalId']}")
    assert audit.status_code == 200
    assert audit.json()["retrievalId"] == result["retrievalId"]

    graph = client.post(
        "/internal/v1/graph/query",
        json={"nodeTypes": ["episode"], "filters": {}, "depth": 1, "limit": 50},
    )
    assert graph.status_code == 200
    body = graph.json()
    assert body["nodes"]
    assert body["nodes"][0]["nodeType"] == "episode"
    assert body["edges"], "retrieval of two relevant episodes must create a coactivation edge"
    assert 0.0 <= body["edges"][0]["weight"] <= 1.0


def test_retrieval_replays_with_same_key_and_rejects_other_query() -> None:
    client = _client()
    _write(client, "alpha beta", "b1")
    first = _retrieve(client, "alpha", "ret-same")
    second = _retrieve(client, "alpha", "ret-same")
    assert second["retrievalId"] == first["retrievalId"]

    conflict = client.post(
        "/api/memory-graph/v1/retrievals",
        headers={"Idempotency-Key": "ret-same"},
        json={"query": "gamma", "topK": 10},
    )
    assert conflict.status_code == 409


def test_retrieval_filters_retracted_and_honors_as_of() -> None:
    client = _client()
    episode = _write(client, "alpha memory", "c1", occurred="2026-01-01T00:00:00Z")
    client.post(
        f"/api/memory-graph/v1/episodes/{episode['episodeId']}/retract",
        headers={"Idempotency-Key": "c1-retract"},
        json={"reasonCode": "user_request"},
    )

    before_retraction = _retrieve(client, "alpha", "c1-before", asOf="2026-06-01T00:00:00Z")
    assert {c["episodeId"] for c in before_retraction["candidates"]} == {episode["episodeId"]}

    after_retraction = _retrieve(client, "alpha", "c1-after", asOf="2027-01-01T00:00:00Z")
    assert after_retraction["candidates"] == []

    before_existence = _retrieve(client, "alpha", "c1-past", asOf="2025-01-01T00:00:00Z")
    assert before_existence["candidates"] == []

    current = _retrieve(client, "alpha", "c1-now")
    assert current["candidates"] == []


def test_consolidation_reinforces_edge_idempotently() -> None:
    client = _client()
    _write(client, "tea", "d1")
    _write(client, "tea cup", "d2")
    _retrieve(client, "tea", "d-ret")

    graph = client.post(
        "/internal/v1/graph/query",
        json={"nodeTypes": ["episode"], "filters": {}, "depth": 1, "limit": 50},
    ).json()
    edge = graph["edges"][0]
    body = {
        "batchId": "batch-1",
        "jobId": "job-1",
        "operations": [{"operation": "reinforce", "edgeId": edge["edgeId"], "weightDelta": 0.1}],
    }
    first = client.post(
        "/internal/v1/consolidation/apply",
        headers={"Idempotency-Key": "apply-1"},
        json=body,
    )
    assert first.status_code == 200
    assert first.json()["appliedCount"] == 1
    weight_after_first = first.json()["maxWeight"]

    replay = client.post(
        "/internal/v1/consolidation/apply",
        headers={"Idempotency-Key": "apply-1"},
        json=body,
    )
    assert replay.json() == first.json()

    graph_after = client.post(
        "/internal/v1/graph/query",
        json={"nodeTypes": ["episode"], "filters": {}, "depth": 1, "limit": 50},
    ).json()
    assert graph_after["edges"][0]["weight"] == weight_after_first
