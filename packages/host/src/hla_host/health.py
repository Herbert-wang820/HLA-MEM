"""Liveness, readiness and Prometheus endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict

from hla_host.config import ModuleConfig
from hla_host.observability import MetricsRegistry


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"
    module: str
    version: str
    time: datetime


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    ready: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ready", "not_ready"]
    module: str
    checks: list[CheckResult]
    time: datetime


class ReadinessCheck(Protocol):
    name: str

    async def __call__(self) -> tuple[bool, str | None]: ...


class ConfigReadinessCheck:
    name = "config"

    def __init__(self, config: ModuleConfig) -> None:
        self._config = config

    async def __call__(self) -> tuple[bool, str | None]:
        issues = self._config.issues
        if issues:
            return False, "; ".join(issues)
        return True, None


class ReadinessRegistry:
    def __init__(self, checks: Sequence[ReadinessCheck] = ()) -> None:
        self._checks = tuple(checks)

    async def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for check in self._checks:
            try:
                ready, detail = await check()
            except Exception as exc:  # noqa: BLE001 - readiness must never crash the process
                results.append(CheckResult(name=check.name, ready=False, detail=f"check failed: {type(exc).__name__}"))
            else:
                results.append(CheckResult(name=check.name, ready=bool(ready), detail=detail))
        return results


def create_health_router(
    *,
    module_id: str,
    version: str,
    registry: ReadinessRegistry,
    metrics: MetricsRegistry,
) -> APIRouter:
    router = APIRouter(tags=["operations"], include_in_schema=True)

    @router.get("/internal/health", response_model=HealthResponse, summary="Liveness probe")
    async def health() -> HealthResponse:
        return HealthResponse(module=module_id, version=version, time=datetime.now(UTC))

    @router.get(
        "/internal/ready",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse, "description": "A dependency or required configuration is not ready."}},
        summary="Readiness probe",
    )
    async def ready() -> Response:
        checks = await registry.run()
        is_ready = all(check.ready for check in checks)
        metrics.set("module_ready", 1 if is_ready else 0, {"module": module_id})
        payload = ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            module=module_id,
            checks=checks,
            time=datetime.now(UTC),
        )
        if not is_ready:
            return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
        return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

    @router.get("/internal/metrics", response_class=PlainTextResponse, summary="Prometheus metrics")
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")

    return router
