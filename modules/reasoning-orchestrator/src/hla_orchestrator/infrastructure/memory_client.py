"""HTTP client for memory-graph capabilities."""

from __future__ import annotations

import uuid
from datetime import datetime

import httpx

from hla_orchestrator.application.errors import MemoryUnavailableError
from hla_orchestrator.domain.models import MemoryHit, MemoryRetrieval


class HttpMemoryClient:
    def __init__(
        self,
        base_url: str,
        *,
        retrieval_timeout: float = 0.8,
        write_timeout: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._retrieval_timeout = retrieval_timeout
        self._write_timeout = write_timeout
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=write_timeout,
            transport=transport,
        )

    async def retrieve(self, query: str, top_k: int, *, request_id: str | None = None) -> MemoryRetrieval:
        headers = {
            "Idempotency-Key": f"turn-retrieve-{uuid.uuid4()}",
            "X-Request-Id": request_id or f"req_{uuid.uuid4().hex}",
            "Accept": "application/json",
        }
        try:
            response = await self._client.post(
                "/api/memory-graph/v1/retrievals",
                json={"query": query, "topK": max(1, min(top_k, 50))},
                headers=headers,
                timeout=self._retrieval_timeout,
            )
            response.raise_for_status()
            body = response.json()
            hits = tuple(
                MemoryHit(
                    episode_id=str(item["episodeId"]),
                    score=float(item.get("score", 0.0)),
                    sources=tuple(str(source) for source in item.get("sources", ())),
                )
                for item in body.get("candidates", ())
            )
            return MemoryRetrieval(retrieval_id=str(body.get("retrievalId", "")), hits=hits)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise MemoryUnavailableError("memory-graph retrieval failed") from exc

    async def get_episode(self, episode_id: str) -> str | None:
        try:
            response = await self._client.get(
                f"/api/memory-graph/v1/episodes/{episode_id}",
                timeout=self._retrieval_timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            content = response.json().get("content")
            return str(content) if content is not None else None
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise MemoryUnavailableError("memory-graph episode read failed") from exc

    async def write_episode(
        self,
        *,
        session_id: str,
        content: str,
        occurred_at: datetime,
        source: str,
        idempotency_key: str,
    ) -> str:
        headers = {
            "Idempotency-Key": idempotency_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "sessionId": session_id,
            "content": content[:20_000],
            "occurredAt": occurred_at.isoformat(),
            "source": source,
        }
        try:
            response = await self._client.post(
                "/api/memory-graph/v1/episodes",
                json=payload,
                headers=headers,
                timeout=self._write_timeout,
            )
            response.raise_for_status()
            return str(response.json()["episodeId"])
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise MemoryUnavailableError("memory-graph episode write failed") from exc

    async def close(self) -> None:
        await self._client.aclose()
