from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient

from hla_host.app import create_module_app
from hla_host.auth import StaticIdentityProvider, dev_identity_provider, require_permission
from hla_host.config import HostSettings
from hla_host.context import Identity
from hla_host.events import InMemoryEventBus


class AnonymousProvider:
    async def resolve(self, request: Request) -> Identity | None:
        return None


def _identity(permissions: tuple[str, ...]) -> Identity:
    return Identity(subject="user-1", tenant_id="tenant-1", permissions=frozenset(permissions))


def _app(
    provider: object,
    permissions: tuple[str, ...] = ("demo.read",),
):
    router = APIRouter()

    @router.get("/secure")
    async def secure(
        identity: Annotated[Identity, Depends(require_permission("demo.read"))],
    ) -> dict[str, str]:
        return {"tenant": identity.tenant_id, "subject": identity.subject}

    return create_module_app(
        module_id="demo",
        name="demo",
        version="0.1.0",
        description="demo",
        settings=HostSettings(environment="dev"),
        routers=(router,),
        identity_provider=provider,  # type: ignore[arg-type]
        event_bus=InMemoryEventBus(),
        dev_permissions=permissions,
    )


def test_anonymous_request_is_rejected() -> None:
    response = TestClient(_app(AnonymousProvider())).get("/secure")
    assert response.status_code == 401
    assert response.json()["code"] == "HOST_AUTH_UNAUTHENTICATED"


def test_missing_permission_is_forbidden() -> None:
    provider = StaticIdentityProvider(_identity(("demo.write",)))
    response = TestClient(_app(provider)).get("/secure")
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "HOST_AUTH_FORBIDDEN"
    assert body["details"]["requiredPermission"] == "demo.read"


def test_granted_permission_reaches_handler() -> None:
    provider = StaticIdentityProvider(_identity(("demo.read",)))
    response = TestClient(_app(provider)).get("/secure")
    assert response.status_code == 200
    assert response.json() == {"tenant": "tenant-1", "subject": "user-1"}


def test_identity_header_cannot_override_tenant() -> None:
    provider = StaticIdentityProvider(_identity(("demo.read",)))
    response = TestClient(_app(provider)).get(
        "/secure",
        headers={"X-Tenant-Id": "attacker", "X-Subject": "attacker"},
    )
    assert response.json()["tenant"] == "tenant-1"


def test_dev_provider_refuses_non_dev_environment() -> None:
    with pytest.raises(RuntimeError):
        dev_identity_provider(HostSettings(environment="prod"), ("demo.read",))


def test_non_dev_app_requires_explicit_provider() -> None:
    with pytest.raises(RuntimeError):
        create_module_app(
            module_id="demo",
            name="demo",
            version="0.1.0",
            description="demo",
            settings=HostSettings(environment="prod"),
            event_bus=InMemoryEventBus(),
        )
