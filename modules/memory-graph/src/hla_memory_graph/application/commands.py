"""Application-level write commands (API-independent)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class WriteEpisodeCommand:
    session_id: str
    content: str
    occurred_at: datetime
    source: str = "conversation"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConsolidationOperation:
    operation: Literal["reinforce", "forget", "distill"]
    edge_id: str | None = None
    source_episode_id: str | None = None
    target_episode_id: str | None = None
    episode_id: str | None = None
    hub_id: str | None = None
    weight_delta: float | None = None
