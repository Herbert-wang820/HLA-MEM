"""Structured logging, Prometheus metrics and ASGI middleware."""

from __future__ import annotations

import asyncio
import bisect
import json
import logging
import re
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hla_host.errors import make_error_code

SERVICE_NAME = "hla-mem"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")
UUID_RE = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_ROUTE_METRIC_EXCLUDED_PREFIXES = ("/internal/",)


class JsonFormatter(logging.Formatter):
    def __init__(self, module_id: str, service: str = SERVICE_NAME) -> None:
        super().__init__()
        self.module_id = module_id
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "module": self.module_id,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("requestId", "traceId", "tenantId", "subject", "code", "status", "method", "path", "durationMs"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(module_id: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("hla")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(module_id))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: tuple[tuple[str, str], ...], extra: tuple[str, str] | None = None) -> str:
    items = list(labels)
    if extra is not None:
        items.append(extra)
    if not items:
        return ""
    body = ",".join(f'{key}="{_escape_label(value)}"' for key, value in items)
    return "{" + body + "}"


def _format_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


@dataclass(slots=True)
class _Histogram:
    buckets: tuple[float, ...]
    counts: list[int] = field(default_factory=list)
    overflow: int = 0
    total: float = 0.0
    count: int = 0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0] * len(self.buckets)

    def observe(self, value: float) -> None:
        index = bisect.bisect_left(self.buckets, value)
        if index >= len(self.buckets):
            self.overflow += 1
        else:
            self.counts[index] += 1
        self.total += value
        self.count += 1


class MetricsRegistry:
    """Small Prometheus text-format registry (no external dependency)."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], _Histogram] = {}

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        key = (_sanitize_name(name), _label_tuple(labels))
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = (_sanitize_name(name), _label_tuple(labels))
        self._gauges[key] = float(value)

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: Sequence[float] = DEFAULT_BUCKETS,
    ) -> None:
        key = (_sanitize_name(name), _label_tuple(labels))
        histogram = self._histograms.get(key)
        if histogram is None:
            histogram = _Histogram(buckets=tuple(sorted(float(item) for item in buckets)))
            self._histograms[key] = histogram
        histogram.observe(float(value))

    def render(self) -> str:
        lines: list[str] = []
        for (name, labels), value in sorted(self._counters.items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{_format_labels(labels)} {_format_value(value)}")
        for (name, labels), value in sorted(self._gauges.items()):
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{_format_labels(labels)} {_format_value(value)}")
        for (name, labels), histogram in sorted(self._histograms.items()):
            lines.append(f"# TYPE {name} histogram")
            cumulative = 0
            for bucket, count in zip(histogram.buckets, histogram.counts, strict=True):
                cumulative += count
                lines.append(
                    f"{name}_bucket{_format_labels(labels, ('le', _format_value(bucket)))} {cumulative}"
                )
            cumulative += histogram.overflow
            lines.append(f'{name}_bucket{_format_labels(labels, ("le", "+Inf"))} {cumulative}')
            lines.append(f"{name}_sum{_format_labels(labels)} {_format_value(histogram.total)}")
            lines.append(f"{name}_count{_format_labels(labels)} {histogram.count}")
        return "\n".join(lines) + "\n"


def _label_tuple(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


class RequestContextMiddleware:
    """Propagates request/trace ids and records request metrics."""

    def __init__(
        self,
        app: ASGIApp,
        module_id: str,
        metrics: MetricsRegistry,
        logger: logging.Logger | None = None,
        excluded_prefixes: Sequence[str] = _ROUTE_METRIC_EXCLUDED_PREFIXES,
    ) -> None:
        self.app = app
        self.module_id = module_id
        self.metrics = metrics
        self.logger = logger or logging.getLogger("hla.request")
        self.excluded_prefixes = tuple(excluded_prefixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        raw_request_id = headers.get("x-request-id", "")
        request_id = raw_request_id if REQUEST_ID_RE.fullmatch(raw_request_id) else f"req_{uuid.uuid4().hex}"
        trace_match = TRACEPARENT_RE.fullmatch(headers.get("traceparent", ""))
        trace_id = trace_match.group(1) if trace_match else request_id
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["trace_id"] = trace_id

        path = str(scope.get("path", "/"))
        method = str(scope.get("method", "GET"))
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_started = True
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-Id"] = request_id
                response_headers["X-Trace-Id"] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            self.logger.exception(
                "request failed",
                extra={"requestId": request_id, "traceId": trace_id, "method": method, "path": path},
            )
            raise
        finally:
            if not response_started:
                status_code = 500
            elapsed = time.perf_counter() - started
            if not any(path.startswith(prefix) for prefix in self.excluded_prefixes) and method != "OPTIONS":
                route = _route_label(scope, path)
                labels = {"method": method, "route": route, "status": str(status_code)}
                self.metrics.inc("http_requests_total", labels)
                self.metrics.observe("http_request_duration_seconds", elapsed, {"method": method, "route": route})
            log_extra = {
                "requestId": request_id,
                "traceId": trace_id,
                "method": method,
                "path": path,
                "status": status_code,
                "durationMs": round(elapsed * 1000, 3),
            }
            if status_code >= 500:
                self.logger.error("request completed with server error", extra=log_extra)
            elif status_code >= 400:
                self.logger.warning("request completed with client error", extra=log_extra)
            else:
                self.logger.debug("request completed", extra=log_extra)


def _route_label(scope: Scope, fallback: str) -> str:
    route = scope.get("route")
    if route is not None:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            return path
    normalized = UUID_RE.sub("/{id}", fallback)
    return re.sub(r"/\d+(?=/|$)", "/{id}", normalized)


class BodySizeLimitMiddleware:
    """Rejects requests whose declared Content-Length exceeds the limit.

    Chunked bodies are additionally bounded at the gateway; this adapter only
    enforces the declared length to avoid buffering streaming requests.
    """

    def __init__(self, app: ASGIApp, module_id: str, max_bytes: int) -> None:
        self.app = app
        self.module_id = module_id
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return
        raw_length = Headers(scope=scope).get("content-length")
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError:
                await _send_json_error(
                    scope,
                    send,
                    400,
                    make_error_code(self.module_id, "REQUEST", "INVALID"),
                    "invalid Content-Length",
                )
                return
            if content_length > self.max_bytes:
                await _send_json_error(
                    scope,
                    send,
                    413,
                    make_error_code(self.module_id, "PAYLOAD", "TOO_LARGE"),
                    "request body exceeds the configured limit",
                )
                return
        await self.app(scope, receive, send)


class TimeoutMiddleware:
    """Cancels non-streaming requests that exceed the configured timeout."""

    def __init__(
        self,
        app: ASGIApp,
        module_id: str,
        timeout_seconds: float,
        exempt_paths: Sequence[str] = (),
        exempt_prefixes: Sequence[str] = ("/internal/",),
    ) -> None:
        self.app = app
        self.module_id = module_id
        self.timeout_seconds = timeout_seconds
        self.exempt_paths = tuple(exempt_paths)
        self.exempt_prefixes = tuple(exempt_prefixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.timeout_seconds <= 0:
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", "/"))
        if path in self.exempt_paths or any(path.startswith(prefix) for prefix in self.exempt_prefixes):
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self.app(scope, receive, send_wrapper)
        except TimeoutError:
            if started:
                raise
            await _send_json_error(
                scope,
                send,
                504,
                make_error_code(self.module_id, "REQUEST", "TIMEOUT"),
                "request timed out",
            )


async def _send_json_error(scope: Scope, send: Send, status: int, code: str, message: str) -> None:
    request_id = str(scope.get("state", {}).get("request_id", "unknown"))
    body = json.dumps(
        {"code": code, "message": message, "requestId": request_id},
        ensure_ascii=False,
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"x-request-id", request_id.encode("ascii", "replace")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
