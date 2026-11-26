"""Stable error model and FastAPI exception handlers."""

from __future__ import annotations

import logging
import re
from typing import Any, NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("hla.error")

ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


def make_error_code(module_id: str, domain: str, reason: str) -> str:
    parts = [module_id, domain, reason]
    normalized = [re.sub(r"[^A-Z0-9]+", "_", part.upper()).strip("_") for part in parts]
    code = "_".join(part for part in normalized if part)
    if not ERROR_CODE_RE.fullmatch(code):
        raise ValueError(f"invalid error code: {code!r}")
    return code


class ErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str = Field(pattern=ERROR_CODE_RE.pattern)
    message: str
    request_id: str = Field(alias="requestId")
    details: dict[str, Any] | None = None


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Request is structurally valid but semantically invalid."},
    401: {"model": ErrorResponse, "description": "Authentication required."},
    403: {"model": ErrorResponse, "description": "Authenticated but not authorized."},
    404: {"model": ErrorResponse, "description": "Resource not found or not visible."},
    409: {"model": ErrorResponse, "description": "Version or idempotency conflict."},
    413: {"model": ErrorResponse, "description": "Request body exceeds the configured limit."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
    500: {"model": ErrorResponse, "description": "Unexpected server error; no internal details are exposed."},
    501: {"model": ErrorResponse, "description": "Capability is declared by contract but not implemented yet."},
    503: {"model": ErrorResponse, "description": "Dependency unavailable and no safe degradation is possible."},
    504: {"model": ErrorResponse, "description": "Request exceeded the configured timeout."},
}


class ModuleError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not ERROR_CODE_RE.fullmatch(code):
            raise ValueError(f"invalid module error code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class AuthenticationError(ModuleError):
    def __init__(self) -> None:
        super().__init__("HOST_AUTH_UNAUTHENTICATED", "authentication required", 401)


class AuthorizationError(ModuleError):
    def __init__(self, permission: str) -> None:
        super().__init__(
            "HOST_AUTH_FORBIDDEN",
            "permission denied",
            403,
            details={"requiredPermission": permission},
        )


class NotFoundError(ModuleError):
    def __init__(self, module_id: str, resource: str, resource_id: str | None = None) -> None:
        details = {"resourceId": resource_id} if resource_id else None
        super().__init__(make_error_code(module_id, resource, "NOT_FOUND"), "resource not found", 404, details)


class ConflictError(ModuleError):
    def __init__(self, module_id: str, resource: str, reason: str = "VERSION_CONFLICT") -> None:
        super().__init__(make_error_code(module_id, resource, reason), "resource conflict", 409)


class IdempotencyConflictError(ModuleError):
    def __init__(self, module_id: str) -> None:
        super().__init__(make_error_code(module_id, "IDEMPOTENCY", "CONFLICT"), "idempotency key reused with a different request", 409)


class FeatureNotImplementedError(ModuleError):
    def __init__(self, module_id: str, capability: str) -> None:
        super().__init__(
            make_error_code(module_id, "FEATURE", "NOT_IMPLEMENTED"),
            f"capability {capability} is declared but not implemented in this phase",
            501,
            details={"capability": capability},
        )


class PayloadTooLargeError(ModuleError):
    def __init__(self, module_id: str, max_bytes: int) -> None:
        super().__init__(
            make_error_code(module_id, "PAYLOAD", "TOO_LARGE"),
            "request body exceeds the configured limit",
            413,
            details={"maxBytes": max_bytes},
        )


class DependencyUnavailableError(ModuleError):
    def __init__(self, module_id: str, dependency: str) -> None:
        super().__init__(
            make_error_code(module_id, "DEPENDENCY", "UNAVAILABLE"),
            "required dependency is unavailable",
            503,
            details={"dependency": dependency},
        )


class RequestTimeoutError(ModuleError):
    def __init__(self, module_id: str) -> None:
        super().__init__(make_error_code(module_id, "REQUEST", "TIMEOUT"), "request timed out", 504)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    header = request.headers.get("x-request-id")
    return header if header else "unknown"


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ErrorResponse(code=code, message=message, requestId=request_id, details=details)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True),
        headers={"X-Request-Id": request_id},
    )


def register_exception_handlers(app: FastAPI, module_id: str) -> None:
    @app.exception_handler(ModuleError)
    async def _module_error(request: Request, exc: ModuleError) -> JSONResponse:
        logger.warning(
            "module error",
            extra={
                "requestId": _request_id(request),
                "code": exc.code,
                "status": exc.status_code,
            },
        )
        return _response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "location": [str(part) for part in error.get("loc", ())],
                    "message": str(error.get("msg", "invalid value")),
                    "type": str(error.get("type", "validation_error")),
                }
            )
        return _response(
            request,
            422,
            make_error_code(module_id, "REQUEST", "VALIDATION_FAILED"),
            "request validation failed",
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = exc.status_code
        if status == 401:
            code, message = "HOST_AUTH_UNAUTHENTICATED", "authentication required"
        elif status == 403:
            code, message = "HOST_AUTH_FORBIDDEN", "permission denied"
        elif status == 404:
            code, message = make_error_code(module_id, "ROUTE", "NOT_FOUND"), "route not found"
        elif status == 405:
            code, message = make_error_code(module_id, "ROUTE", "METHOD_NOT_ALLOWED"), "method not allowed"
        elif status == 413:
            code, message = make_error_code(module_id, "PAYLOAD", "TOO_LARGE"), "request body too large"
        elif 400 <= status < 500:
            code, message = make_error_code(module_id, "REQUEST", "INVALID"), "request rejected"
        else:
            code, message = make_error_code(module_id, "INTERNAL", "ERROR"), "internal error"
        return _response(request, status, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled exception",
            extra={"requestId": _request_id(request), "code": make_error_code(module_id, "INTERNAL", "ERROR")},
        )
        return _response(
            request,
            500,
            make_error_code(module_id, "INTERNAL", "ERROR"),
            "internal error",
        )


def raise_not_implemented(module_id: str, capability: str) -> NoReturn:
    raise FeatureNotImplementedError(module_id, capability)
