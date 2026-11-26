from __future__ import annotations

from fastapi.testclient import TestClient
from hla_consolidator.app import create_app

MODULE_ID = "async-consolidator"
ERROR_PREFIX = "ASYNC_CONSOLIDATOR"


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_readiness_and_metrics() -> None:
    client = _client()
    health = client.get("/internal/health")
    assert health.status_code == 200
    assert health.json()["module"] == MODULE_ID
    assert health.headers["x-request-id"]

    ready = client.get("/internal/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    metrics = client.get("/internal/metrics")
    assert metrics.status_code == 200
    assert "module_ready" in metrics.text


def test_declared_endpoint_returns_501_placeholder() -> None:
    response = _client().post(
        "/api/async-consolidator/v1/jobs",
        headers={"Idempotency-Key": "idem-1"},
        json={"trigger": "manual"},
    )
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == ERROR_PREFIX + "_FEATURE_NOT_IMPLEMENTED"
    assert body["requestId"] == response.headers["x-request-id"]


def test_missing_idempotency_key_is_422() -> None:
    response = _client().post(
        "/api/async-consolidator/v1/jobs",
        json={"trigger": "manual"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == ERROR_PREFIX + "_REQUEST_VALIDATION_FAILED"


def test_tenant_in_body_is_rejected() -> None:
    response = _client().post(
        "/api/async-consolidator/v1/jobs",
        headers={"Idempotency-Key": "idem-tenant"},
        json={"trigger":"manual","tenantId":"attacker"},
    )
    assert response.status_code == 422


def test_unknown_route_uses_error_envelope() -> None:
    response = _client().get("/api/async-consolidator/v1/nope")
    assert response.status_code == 404
    assert response.json()["code"] == ERROR_PREFIX + "_ROUTE_NOT_FOUND"
