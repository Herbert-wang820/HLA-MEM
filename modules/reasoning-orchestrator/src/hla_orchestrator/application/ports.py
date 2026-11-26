"""Ports used by the turn use case."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from hla_orchestrator.domain.models import Generation, MemoryHit, MemoryRetrieval
from hla_orchestrator.domain.persona import PersonaProfile


class MemoryPort(Protocol):
    async def retrieve(self, query: str, top_k: int, *, request_id: str | None = None) -> MemoryRetrieval: ...

    async def get_episode(self, episode_id: str) -> str | None: ...

    async def write_episode(
        self,
        *,
        session_id: str,
        content: str,
        occurred_at: datetime,
        source: str,
        idempotency_key: str,
    ) -> str: ...


class CompleterPort(Protocol):
    async def complete(
        self,
        *,
        message: str,
        memories: Sequence[MemoryHit],
        persona: str,
    ) -> Generation: ...


class PersonaPort(Protocol):
    async def fetch_profile(self) -> PersonaProfile: ...

    async def update_adaptation(
        self,
        *,
        expected_version: int,
        deltas: dict[str, float],
        reason: str,
    ) -> int: ...

    async def create_identity_proposal(
        self,
        *,
        turn_id: str,
        rationale: str,
        changes: dict[str, Any],
        evidence_episode_ids: Sequence[str],
    ) -> str: ...

    async def close(self) -> None: ...
