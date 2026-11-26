"""In-memory persona store.  PostgreSQL replaces it in Phase 2."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from hla_persona_state.domain.models import Adaptation, IdentityState, IdentityVersion, Trait

DEFAULT_TRAITS = (
    Trait(trait="tone", value="温和、务实", confidence=0.8),
    Trait(trait="directness", value="直接指出不确定", confidence=0.7),
    Trait(trait="memory_style", value="引用具体记忆", confidence=0.8),
)

DEFAULT_NARRATIVE = "你是一位耐心、务实、重视长期记忆的对话伙伴。回答简洁，并明确说明你记得什么。"

DEFAULT_ADAPTATION = {
    "warmth": 0.6,
    "verbosity": 0.4,
    "humor": 0.3,
}


class InMemoryPersonaStore:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._states: dict[str, IdentityState] = {}
        self._lock = asyncio.Lock()

    async def get(self, tenant_id: str) -> IdentityState:
        async with self._lock:
            state = self._states.get(tenant_id)
            if state is None:
                now = self._clock()
                state = IdentityState(
                    identity_id=str(uuid.uuid4()),
                    versions=[
                        IdentityVersion(
                            version=1,
                            traits=DEFAULT_TRAITS,
                            narrative=DEFAULT_NARRATIVE,
                            effective_from=now,
                            created_at=now,
                            created_by="system",
                        )
                    ],
                    adaptation=Adaptation(
                        version=1,
                        values=dict(DEFAULT_ADAPTATION),
                        updated_at=now,
                        drift=0.0,
                    ),
                    window_start=now,
                    drift=0.0,
                )
                self._states[tenant_id] = state
            return state
