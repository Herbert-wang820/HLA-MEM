"""Idempotency around persona identity writes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypeVar

from pydantic import BaseModel

from hla_host.idempotency import (
    IdempotencyStore,
    ensure_same_request,
    new_record,
    scope_key,
)

T = TypeVar("T", bound=BaseModel)


class IdempotencyGuard:
    def __init__(self, store: IdempotencyStore, module_id: str) -> None:
        self._store = store
        self._module_id = module_id
        self._locks_guard = asyncio.Lock()
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def scope(subject: str, tenant_id: str, operation: str, key: str) -> str:
        return scope_key(subject, tenant_id, operation, key)

    @asynccontextmanager
    async def key_lock(self, scope: str) -> AsyncIterator[None]:
        async with self._locks_guard:
            lock = self._locks.setdefault(scope, asyncio.Lock())
        async with lock:
            yield

    async def get(self, scope: str, fingerprint: str, model: type[T]) -> T | None:
        record = await self._store.get(scope)
        if record is None:
            return None
        ensure_same_request(record, fingerprint, self._module_id)
        return model.model_validate(record.response_body)

    async def put(
        self,
        scope: str,
        *,
        subject: str,
        tenant_id: str,
        operation: str,
        key: str,
        fingerprint: str,
        status_code: int,
        value: BaseModel,
    ) -> None:
        await self._store.put(
            scope,
            new_record(
                key=key,
                subject=subject,
                tenant_id=tenant_id,
                operation=operation,
                fingerprint=fingerprint,
                status_code=status_code,
                response_body=value.model_dump(mode="json", by_alias=True),
            ),
        )
