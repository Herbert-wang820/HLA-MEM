"""Trusted identity context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Identity:
    """Authenticated caller identity.

    ``tenant_id`` comes from the host identity provider.  It is never read from
    query parameters, request bodies or ordinary client headers.
    """

    subject: str
    tenant_id: str
    permissions: frozenset[str]
    roles: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("identity subject must not be empty")
        if not self.tenant_id:
            raise ValueError("identity tenant_id must not be empty")
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "roles", frozenset(self.roles))

    def has_permission(self, permission: str) -> bool:
        """Exact-match authorization. Unknown permissions are denied."""
        return permission in self.permissions
