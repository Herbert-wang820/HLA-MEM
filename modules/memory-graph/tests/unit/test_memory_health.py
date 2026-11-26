from __future__ import annotations

from fastapi.testclient import TestClient
from hla_memory_graph.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_readiness_and_metrics() -> None:
    client = _client()
    health = client.get("/internal/health")
    assert health.status_code == 200
    assert health.json()["module"] == "memory-graph"
    assert health.headers["x-request-id"]

    ready = client.get("/internal/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["checks"][0]["name"] == "config"

    metrics = client.get("/internal/metrics")
    assert metrics.status_code == 200
    assert "module_ready" in metrics.text


def test_request_id_is_propagated() -> None:
    response = _client().get("/internal/health", headers={"X-Request-Id": "req-abc-123"})
    assert response.headers["x-request-id"] == "req-abc-123"


def test_write_episode_returns_201() -> None:
    response = _client().post(
        "/api/memory-graph/v1/episodes",
        headers={"Idempotency-Key": "idem-1"},
        json={"sessionId": "s1", "content": "hello", "occurredAt": "2026-11-10T00:00:00Z"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tenantId"] == "tenant-dev"
    assert body["content"] == "hello"
    assert body["retracted"] is False
    assert len(body["contentHash"]) == 64


def test_missing_idempotency_key_is_422() -> None:
    response = _client().post(
        "/api/memory-graph/v1/episodes",
        json={"sessionId": "s1", "content": "hello", "occurredAt": "2026-11-10T00:00:00Z"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MEMORY_GRAPH_REQUEST_VALIDATION_FAILED"


def test_tenant_in_body_is_rejected() -> None:
    response = _client().post(
        "/api/memory-graph/v1/episodes",
        headers={"Idempotency-Key": "idem-2"},
        json={
            "sessionId": "s1",
            "content": "hello",
            "occurredAt": "2026-11-10T00:00:00Z",
            "tenantId": "attacker-tenant",
        },
    )
    assert response.status_code == 422


def test_unknown_route_uses_error_envelope() -> None:
    response = _client().get("/api/memory-graph/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "MEMORY_GRAPH_ROUTE_NOT_FOUND"
