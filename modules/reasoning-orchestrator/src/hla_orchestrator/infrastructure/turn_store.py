"""Process-local turn, audit and idempotency store for the demo."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from hla_orchestrator.domain.models import TurnAudit, TurnOutcome


@dataclass(frozen=True, slots=True)
class CachedTurn:
    fingerprint: str
    outcome: TurnOutcome


class TurnStore:
    def __init__(self) -> None:
        self._turns: dict[str, TurnOutcome] = {}
        self._audits: dict[str, TurnAudit] = {}
        self._cache: dict[str, CachedTurn] = {}
        self._lock = asyncio.Lock()

    async def save(self, outcome: TurnOutcome, *, scope: str, fingerprint: str) -> None:
        async with self._lock:
            self._turns[outcome.turn_id] = outcome
            if outcome.audit is not None:
                self._audits[outcome.turn_id] = outcome.audit
            self._cache[scope] = CachedTurn(fingerprint=fingerprint, outcome=outcome)

    async def get_turn(self, turn_id: str) -> TurnOutcome | None:
        async with self._lock:
            return self._turns.get(turn_id)

    async def get_audit(self, turn_id: str) -> TurnAudit | None:
        async with self._lock:
            return self._audits.get(turn_id)

    async def get_cached(self, scope: str) -> CachedTurn | None:
        async with self._lock:
            return self._cache.get(scope)
