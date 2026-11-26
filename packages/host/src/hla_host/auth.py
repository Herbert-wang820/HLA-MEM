"""Trusted identity resolution and FastAPI authorization dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from fastapi import Request
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp, Receive, Scope, Send

from hla_host.config import HostSettings
from hla_host.context import Identity
from hla_host.errors import AuthenticationError, AuthorizationError


class IdentityProvider(Protocol):
    async def resolve(self, request: Request) -> Identity | None: ...


class StaticIdentityProvider:
    """Development/test provider.

    The identity is configured out-of-band; request headers cannot override the
    tenant or permissions.
    """

    def __init__(self, identity: Identity) -> None:
        self._identity = identity

    async def resolve(self, request: Request) -> Identity | None:
        return self._identity


class IdentityMiddleware:
    def __init__(self, app: ASGIApp, provider: IdentityProvider) -> None:
        self.app = app
        self.provider = provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = StarletteRequest(scope)
        identity = await self.provider.resolve(request)  # type: ignore[arg-type]
        scope.setdefault("state", {})["identity"] = identity
        await self.app(scope, receive, send)


def get_identity(request: Request) -> Identity | None:
    identity = getattr(request.state, "identity", None)
    return identity if isinstance(identity, Identity) else None


def require_identity(request: Request) -> Identity:
    identity = get_identity(request)
    if identity is None:
        raise AuthenticationError()
    return identity


def require_permission(permission: str) -> Callable[..., Awaitable[Identity]]:
    async def dependency(request: Request) -> Identity:
        identity = require_identity(request)
        if not identity.has_permission(permission):
            raise AuthorizationError(permission)
        return identity

    return dependency


def build_dev_identity(settings: HostSettings, declared_permissions: Sequence[str]) -> Identity:
    permissions = settings.dev_permissions or tuple(declared_permissions)
    return Identity(
        subject=settings.dev_subject,
        tenant_id=settings.dev_tenant_id,
        permissions=frozenset(permissions),
    )


def dev_identity_provider(settings: HostSettings, declared_permissions: Sequence[str]) -> StaticIdentityProvider:
    if settings.environment != "dev":
        raise RuntimeError(
            "a real host.auth.identity.v1 provider is required when HLA_ENV is not 'dev'; "
            "refusing to start with the development identity adapter"
        )
    return StaticIdentityProvider(build_dev_identity(settings, declared_permissions))
