from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.testclient import TestClient

from hla_host.app import create_module_app
from hla_host.config import HostSettings
from hla_host.events import InMemoryEventBus


def _app(**settings_overrides: object) -> TestClient:
    router = APIRouter()

    @router.post("/echo")
    async def echo(payload: dict) -> dict:
        return {"size": len(payload)}

    @router.get("/slow")
    async def slow() -> dict[str, bool]:
        await asyncio.sleep(0.5)
        return {"ok": True}

    @router.get("/boom")
    async def boom() -> dict[str, bool]:
        raise RuntimeError("internal detail that must not leak")

    settings = HostSettings(environment="dev", **settings_overrides)  # type: ignore[arg-type]
    return TestClient(
        create_module_app(
            module_id="demo",
            name="demo",
            version="0.1.0",
            description="demo",
            settings=settings,
            routers=(router,),
            event_bus=InMemoryEventBus(),
            dev_permissions=(),
        ),
        raise_server_exceptions=False,
    )


def test_health_ready_and_metrics() -> None:
    client = _app()
    assert client.get("/internal/health").json()["module"] == "demo"
    assert client.get("/internal/ready").json()["status"] == "ready"

    client.get("/internal/health")
    metrics = client.get("/internal/metrics")
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers["content-type"]


def test_request_id_is_kept_when_safe_and_regenerated_when_not() -> None:
    client = _app()
    kept = client.get("/internal/health", headers={"X-Request-Id": "abc-123"})
    assert kept.headers["x-request-id"] == "abc-123"

    replaced = client.get("/internal/health", headers={"X-Request-Id": "bad id!"})
    assert replaced.headers["x-request-id"].startswith("req_")


def test_body_limit_returns_413() -> None:
    response = _app(max_body_bytes=64).post("/echo", json={"payload": "x" * 500})
    assert response.status_code == 413
    assert response.json()["code"] == "DEMO_PAYLOAD_TOO_LARGE"


def test_timeout_returns_504() -> None:
    response = _app(request_timeout_ms=50).get("/slow")
    assert response.status_code == 504
    assert response.json()["code"] == "DEMO_REQUEST_TIMEOUT"


def test_unhandled_error_hides_internal_details() -> None:
    response = _app().get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "DEMO_INTERNAL_ERROR"
    assert "internal detail" not in body["message"]


def test_unknown_route_uses_error_envelope() -> None:
    response = _app().get("/missing")
    assert response.status_code == 404
    assert response.json()["code"] == "DEMO_ROUTE_NOT_FOUND"
