from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from hla_host.errors import IdempotencyConflictError
from hla_host.idempotency import (
    InMemoryIdempotencyStore,
    ensure_same_request,
    new_record,
    request_fingerprint,
    scope_key,
    validate_idempotency_key,
)


def test_fingerprint_is_stable_and_order_insensitive() -> None:
    left = request_fingerprint("user-1", "tenant-1", "episode.write", {"a": 1, "b": 2})
    right = request_fingerprint("user-1", "tenant-1", "episode.write", {"b": 2, "a": 1})
    assert left == right
    assert len(left) == 64


def test_fingerprint_changes_with_subject_or_body() -> None:
    base = request_fingerprint("user-1", "tenant-1", "op", {"a": 1})
    assert base != request_fingerprint("user-2", "tenant-1", "op", {"a": 1})
    assert base != request_fingerprint("user-1", "tenant-1", "op", {"a": 2})
    assert base != request_fingerprint("user-1", "tenant-1", "other", {"a": 1})


def test_idempotency_key_is_required_and_bounded() -> None:
    assert validate_idempotency_key("key-1") == "key-1"
    assert validate_idempotency_key(None, required=False) is None
    with pytest.raises(ValueError):
        validate_idempotency_key(None)
    with pytest.raises(ValueError):
        validate_idempotency_key("x" * 201)


def test_scope_key_is_tenant_and_operation_scoped() -> None:
    assert scope_key("u", "t", "op", "k") != scope_key("u", "t2", "op", "k")
    assert scope_key("u", "t", "op", "k") != scope_key("u", "t", "op2", "k")


def test_different_body_with_same_key_conflicts() -> None:
    record = new_record(
        key="k",
        subject="u",
        tenant_id="t",
        operation="op",
        fingerprint=request_fingerprint("u", "t", "op", {"a": 1}),
        status_code=201,
        response_body={"ok": True},
    )
    ensure_same_request(record, request_fingerprint("u", "t", "op", {"a": 1}), "demo")
    with pytest.raises(IdempotencyConflictError):
        ensure_same_request(record, request_fingerprint("u", "t", "op", {"a": 2}), "demo")


def test_store_round_trip_and_expiry() -> None:
    async def run() -> None:
        now = [0.0]
        store = InMemoryIdempotencyStore(ttl_seconds=10, clock=lambda: now[0])
        record = new_record(
            key="k",
            subject="u",
            tenant_id="t",
            operation="op",
            fingerprint="f",
            status_code=200,
            response_body={},
        )
        key = scope_key("u", "t", "op", "k")
        assert await store.get(key) is None
        await store.put(key, record)
        assert (await store.get(key)) is not None
        now[0] = 11.0
        assert await store.get(key) is None

    asyncio.run(run())


def test_record_created_at_is_utc() -> None:
    record = new_record(
        key="k",
        subject="u",
        tenant_id="t",
        operation="op",
        fingerprint="f",
        status_code=200,
        response_body={},
    )
    assert record.created_at.tzinfo is UTC
    assert record.created_at <= datetime.now(UTC)
