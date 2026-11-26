"""Idempotency primitives for non-idempotent actions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from hla_host.errors import IdempotencyConflictError

MAX_IDEMPOTENCY_KEY_LENGTH = 200


class IdempotencyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    subject: str
    tenant_id: str
    operation: str
    request_hash: str
    status_code: int
    response_body: dict[str, Any]
    created_at: datetime


class IdempotencyStore(Protocol):
    async def get(self, scope_key: str) -> IdempotencyRecord | None: ...

    async def put(self, scope_key: str, record: IdempotencyRecord) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(
        self,
        ttl_seconds: float = 86_400,
        max_entries: int = 100_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: dict[str, tuple[float, IdempotencyRecord]] = {}
        self._lock = asyncio.Lock()

    async def get(self, scope_key: str) -> IdempotencyRecord | None:
        async with self._lock:
            self._purge()
            entry = self._entries.get(scope_key)
            return entry[1] if entry else None

    async def put(self, scope_key: str, record: IdempotencyRecord) -> None:
        async with self._lock:
            self._purge()
            if len(self._entries) >= self._max_entries and scope_key not in self._entries:
                oldest_key = min(self._entries, key=lambda key: self._entries[key][0])
                self._entries.pop(oldest_key, None)
            self._entries[scope_key] = (self._clock() + self._ttl, record)

    def _purge(self) -> None:
        now = self._clock()
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


def validate_idempotency_key(key: str | None, *, required: bool = True) -> str | None:
    if key is None or key == "":
        if required:
            raise ValueError("Idempotency-Key is required for this operation")
        return None
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(f"Idempotency-Key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters")
    return key


def request_fingerprint(subject: str, tenant_id: str, operation: str, body: Any) -> str:
    canonical_body = body.model_dump(mode="json", by_alias=True) if isinstance(body, BaseModel) else body
    canonical = json.dumps(canonical_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    material = f"{subject}\0{tenant_id}\0{operation}\0{canonical}".encode()
    return hashlib.sha256(material).hexdigest()


def scope_key(subject: str, tenant_id: str, operation: str, key: str) -> str:
    return f"{subject}\0{tenant_id}\0{operation}\0{key}"


def ensure_same_request(record: IdempotencyRecord, fingerprint: str, module_id: str) -> None:
    if record.request_hash != fingerprint:
        raise IdempotencyConflictError(module_id)


def new_record(
    *,
    key: str,
    subject: str,
    tenant_id: str,
    operation: str,
    fingerprint: str,
    status_code: int,
    response_body: dict[str, Any],
) -> IdempotencyRecord:
    return IdempotencyRecord(
        key=key,
        subject=subject,
        tenant_id=tenant_id,
        operation=operation,
        request_hash=fingerprint,
        status_code=status_code,
        response_body=response_body,
        created_at=datetime.now(UTC),
    )
