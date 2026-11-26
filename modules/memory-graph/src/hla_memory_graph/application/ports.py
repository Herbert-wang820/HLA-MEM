"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from hla_memory_graph.domain.models import (
    CoactivationEdge,
    Episode,
    RetrievalAudit,
)


class MemoryStore(Protocol):
    async def add_episode(self, episode: Episode) -> None: ...

    async def get_episode(self, tenant_id: str, episode_id: str) -> Episode | None: ...

    async def update_episode(self, episode: Episode) -> None: ...

    async def list_episodes(self, tenant_id: str) -> Sequence[Episode]: ...

    async def list_edges(self, tenant_id: str) -> Sequence[CoactivationEdge]: ...

    async def find_edge(self, tenant_id: str, source_id: str, target_id: str) -> CoactivationEdge | None: ...

    async def upsert_edge(self, edge: CoactivationEdge) -> None: ...

    async def delete_edge(self, tenant_id: str, edge_id: str) -> bool: ...

    async def add_retrieval(self, audit: RetrievalAudit) -> None: ...

    async def get_retrieval(self, tenant_id: str, retrieval_id: str) -> RetrievalAudit | None: ...

    async def health(self) -> tuple[bool, str | None]: ...


class Embedder(Protocol):
    dimension: int

    def embed(self, text: str) -> tuple[float, ...]: ...
