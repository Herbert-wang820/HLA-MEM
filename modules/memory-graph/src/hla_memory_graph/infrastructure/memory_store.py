"""In-memory graph store.  Process-local; replace with FalkorDB in Phase 1b."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from hla_memory_graph.domain.models import CoactivationEdge, Episode, RetrievalAudit


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._episodes: dict[tuple[str, str], Episode] = {}
        self._edges: dict[tuple[str, str], CoactivationEdge] = {}
        self._retrievals: dict[tuple[str, str], RetrievalAudit] = {}
        self._lock = asyncio.Lock()

    async def add_episode(self, episode: Episode) -> None:
        async with self._lock:
            key = (episode.tenant_id, episode.episode_id)
            if key in self._episodes:
                raise ValueError(f"episode already exists: {episode.episode_id}")
            self._episodes[key] = episode

    async def get_episode(self, tenant_id: str, episode_id: str) -> Episode | None:
        async with self._lock:
            return self._episodes.get((tenant_id, episode_id))

    async def update_episode(self, episode: Episode) -> None:
        async with self._lock:
            self._episodes[(episode.tenant_id, episode.episode_id)] = episode

    async def list_episodes(self, tenant_id: str) -> Sequence[Episode]:
        async with self._lock:
            return tuple(
                sorted(
                    (episode for (tenant, _), episode in self._episodes.items() if tenant == tenant_id),
                    key=lambda episode: (episode.occurred_at, episode.episode_id),
                )
            )

    async def list_edges(self, tenant_id: str) -> Sequence[CoactivationEdge]:
        async with self._lock:
            return tuple(edge for (tenant, _), edge in self._edges.items() if tenant == tenant_id)

    async def find_edge(self, tenant_id: str, source_id: str, target_id: str) -> CoactivationEdge | None:
        wanted = (source_id, target_id) if source_id <= target_id else (target_id, source_id)
        async with self._lock:
            for (tenant, _), edge in self._edges.items():
                if tenant == tenant_id and edge.canonical() == wanted:
                    return edge
        return None

    async def upsert_edge(self, edge: CoactivationEdge) -> None:
        async with self._lock:
            self._edges[(edge.tenant_id, edge.edge_id)] = edge

    async def delete_edge(self, tenant_id: str, edge_id: str) -> bool:
        async with self._lock:
            return self._edges.pop((tenant_id, edge_id), None) is not None

    async def add_retrieval(self, audit: RetrievalAudit) -> None:
        async with self._lock:
            self._retrievals[(audit.tenant_id, audit.retrieval_id)] = audit

    async def get_retrieval(self, tenant_id: str, retrieval_id: str) -> RetrievalAudit | None:
        async with self._lock:
            return self._retrievals.get((tenant_id, retrieval_id))

    async def health(self) -> tuple[bool, str | None]:
        return True, None
