from __future__ import annotations

from fastapi.testclient import TestClient
from hla_persona_state.app import create_app

MODULE_ID = "persona-state"
ERROR_PREFIX = "PERSONA_STATE"


def _client() -> TestClient:
    return TestClient(create_app())


def _traits() -> list[dict]:
    return [{"trait": "tone", "value": "warm", "confidence": 0.8}]


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


def test_identity_reads_a_versioned_default() -> None:
    response = _client().get("/api/persona-state/v1/identity")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["traits"]
    assert body["narrative"]


def test_identity_version_creation_and_rollback_keep_history() -> None:
    client = _client()
    created = client.post(
        "/api/persona-state/v1/identity/versions",
        headers={"Idempotency-Key": "idem-version-1"},
        json={"traits": _traits(), "narrative": "更直接", "changeReason": "test"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 2

    replayed = client.post(
        "/api/persona-state/v1/identity/versions",
        headers={"Idempotency-Key": "idem-version-1"},
        json={"traits": _traits(), "narrative": "更直接", "changeReason": "test"},
    )
    assert replayed.status_code == 201
    assert replayed.json()["version"] == 2

    rolled = client.post(
        "/api/persona-state/v1/identity/rollback",
        headers={"Idempotency-Key": "idem-rollback-1"},
        json={"targetVersion": 1, "changeReason": "restore"},
    )
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["version"] == 3
    assert rolled.json()["createdBy"]


def test_adaptation_is_bounded_and_uses_optimistic_lock() -> None:
    client = _client()
    current = client.get("/api/persona-state/v1/adaptation").json()
    version = current["version"]
    assert version >= 1

    updated = client.patch(
        "/api/persona-state/v1/adaptation",
        json={"expectedVersion": version, "deltas": {"warmth": 0.1}, "reason": "test"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == version + 1

    stale = client.patch(
        "/api/persona-state/v1/adaptation",
        json={"expectedVersion": version, "deltas": {"warmth": 0.1}, "reason": "test"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "PERSONA_STATE_ADAPTATION_VERSION_CONFLICT"

    too_large = client.patch(
        "/api/persona-state/v1/adaptation",
        json={"expectedVersion": updated.json()["version"], "deltas": {"warmth": 0.5}, "reason": "test"},
    )
    assert too_large.status_code == 422
    assert too_large.json()["code"] == "PERSONA_STATE_ADAPTATION_DELTA_TOO_LARGE"

    drift = client.patch(
        "/api/persona-state/v1/adaptation",
        json={
            "expectedVersion": updated.json()["version"],
            "deltas": {"warmth": 0.15, "verbosity": 0.15},
            "reason": "test",
        },
    )
    assert drift.status_code == 409
    assert drift.json()["code"] == "PERSONA_STATE_ADAPTATION_DRIFT_EXCEEDED"


def test_missing_idempotency_key_is_422() -> None:
    response = _client().post(
        "/api/persona-state/v1/identity/versions",
        json={"traits": _traits(), "changeReason": "test"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == ERROR_PREFIX + "_REQUEST_VALIDATION_FAILED"


def test_tenant_in_body_is_rejected() -> None:
    response = _client().post(
        "/api/persona-state/v1/proposals",
        headers={"Idempotency-Key": "idem-tenant"},
        json={
            "rationale": "r",
            "changes": {"traits": _traits(), "narrative": ""},
            "tenantId": "attacker",
        },
    )
    assert response.status_code == 422


def test_proposal_approval_creates_identity_version_once() -> None:
    client = _client()
    created = client.post(
        "/api/persona-state/v1/proposals",
        headers={"Idempotency-Key": "idem-proposal-1"},
        json={
            "rationale": "用户多次希望更直接",
            "changes": {"traits": _traits(), "narrative": "直接、务实"},
            "evidenceEpisodeIds": ["ep-1"],
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()
    assert proposal["status"] == "pending"
    assert proposal["changes"]["narrative"] == "直接、务实"

    approved = client.post(
        f"/api/persona-state/v1/proposals/{proposal['proposalId']}/review",
        headers={"Idempotency-Key": "idem-review-1"},
        json={"decision": "approve", "note": "ok"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert client.get("/api/persona-state/v1/identity").json()["version"] == 2

    second = client.post(
        f"/api/persona-state/v1/proposals/{proposal['proposalId']}/review",
        headers={"Idempotency-Key": "idem-review-2"},
        json={"decision": "approve"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "PERSONA_STATE_PROPOSAL_ALREADY_REVIEWED"

    listing = client.get("/api/persona-state/v1/proposals")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["proposalId"] == proposal["proposalId"]


def test_proposal_with_incomplete_snapshot_is_rejected() -> None:
    response = _client().post(
        "/api/persona-state/v1/proposals",
        headers={"Idempotency-Key": "idem-proposal-bad"},
        json={"rationale": "r", "changes": {"narrative": "无 traits"}},
    )
    assert response.status_code == 422


def test_unknown_route_uses_error_envelope() -> None:
    response = _client().get("/api/persona-state/v1/nope")
    assert response.status_code == 404
    assert response.json()["code"] == ERROR_PREFIX + "_ROUTE_NOT_FOUND"
