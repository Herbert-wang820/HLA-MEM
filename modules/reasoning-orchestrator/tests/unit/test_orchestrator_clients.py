from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from hla_orchestrator.application.errors import MemoryUnavailableError
from hla_orchestrator.infrastructure.memory_client import HttpMemoryClient


def test_memory_client_retrieves_candidates_and_sends_request_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/memory-graph/v1/retrievals"
        assert request.headers["x-request-id"] == "req-demo"
        assert request.headers["idempotency-key"]
        return httpx.Response(
            200,
            json={
                "retrievalId": "11111111-1111-4111-8111-111111111111",
                "candidates": [
                    {"episodeId": "22222222-2222-4222-8222-222222222222", "score": 0.8, "sources": ["semantic"]}
                ],
            },
        )

    async def run() -> None:
        client = HttpMemoryClient("http://memory.test", transport=httpx.MockTransport(handler))
        try:
            result = await client.retrieve("tea", 10, request_id="req-demo")
            assert result.retrieval_id == "11111111-1111-4111-8111-111111111111"
            assert result.hits[0].episode_id == "22222222-2222-4222-8222-222222222222"
            assert result.hits[0].sources == ("semantic",)
        finally:
            await client.close()

    asyncio.run(run())


def test_memory_client_writes_episode_and_returns_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/memory-graph/v1/episodes"
        body = request.read().decode()
        assert '"sessionId":"s1"' in body
        assert request.headers["idempotency-key"] == "turn:1:user"
        return httpx.Response(201, json={"episodeId": "33333333-3333-4333-8333-333333333333"})

    async def run() -> None:
        client = HttpMemoryClient("http://memory.test", transport=httpx.MockTransport(handler))
        try:
            episode_id = await client.write_episode(
                session_id="s1",
                content="hello",
                occurred_at=datetime(2026, 11, 11, tzinfo=UTC),
                source="conversation",
                idempotency_key="turn:1:user",
            )
            assert episode_id == "33333333-3333-4333-8333-333333333333"
        finally:
            await client.close()

    asyncio.run(run())


def test_memory_client_maps_404_to_none_and_http_errors_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/episodes/missing"):
            return httpx.Response(404, json={"code": "MEMORY_GRAPH_EPISODE_NOT_FOUND"})
        return httpx.Response(500, text="boom")

    async def run() -> None:
        client = HttpMemoryClient("http://memory.test", transport=httpx.MockTransport(handler))
        try:
            assert await client.get_episode("missing") is None
            with pytest.raises(MemoryUnavailableError):
                await client.retrieve("tea", 10)
        finally:
            await client.close()

    asyncio.run(run())


def test_persona_client_reads_snapshot_and_creates_proposal() -> None:
    from hla_orchestrator.infrastructure.persona_client import HttpPersonaClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/persona-state/v1/identity":
            return httpx.Response(
                200,
                json={
                    "version": 3,
                    "traits": [{"trait": "tone", "value": "温和", "confidence": 0.8}],
                    "narrative": "耐心",
                    "effectiveFrom": "2026-11-10T00:00:00Z",
                    "createdAt": "2026-11-10T00:00:00Z",
                    "createdBy": "dev-user",
                },
            )
        if request.url.path == "/api/persona-state/v1/adaptation":
            return httpx.Response(
                200,
                json={"version": 7, "values": {"warmth": 0.6}, "updatedAt": "2026-11-10T00:00:00Z", "drift": 0.1},
            )
        assert request.url.path == "/api/persona-state/v1/proposals"
        assert request.headers["idempotency-key"] == "turn-1:persona-proposal"
        body = request.read().decode()
        assert '"rationale":"用户希望更直接"' in body
        assert '"evidenceEpisodeIds":["ep-1"]' in body
        return httpx.Response(201, json={"proposalId": "55555555-5555-4555-8555-555555555555"})

    async def run() -> None:
        client = HttpPersonaClient("http://persona.test", transport=httpx.MockTransport(handler))
        try:
            profile = await client.fetch_profile()
            assert profile.identity_version == 3
            assert profile.adaptation_version == 7
            assert profile.traits[0].value == "温和"
            proposal_id = await client.create_identity_proposal(
                turn_id="turn-1",
                rationale="用户希望更直接",
                changes={"traits": [], "narrative": "直接"},
                evidence_episode_ids=["ep-1"],
            )
            assert proposal_id == "55555555-5555-4555-8555-555555555555"
        finally:
            await client.close()

    asyncio.run(run())


def test_persona_client_surfaces_bounded_rejection_as_domain_error() -> None:
    from hla_orchestrator.application.errors import PersonaRejectedError
    from hla_orchestrator.infrastructure.persona_client import HttpPersonaClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/persona-state/v1/adaptation":
            return httpx.Response(
                409,
                json={"code": "PERSONA_STATE_ADAPTATION_DRIFT_EXCEEDED", "message": "drift exceeded"},
            )
        return httpx.Response(
            422,
            json={"code": "PERSONA_STATE_PROPOSAL_CHANGES_INVALID", "message": "incomplete changes"},
        )

    async def run() -> None:
        client = HttpPersonaClient("http://persona.test", transport=httpx.MockTransport(handler))
        try:
            try:
                await client.update_adaptation(expected_version=2, deltas={"warmth": 0.1}, reason="r")
            except PersonaRejectedError as exc:
                assert exc.code == "PERSONA_STATE_ADAPTATION_DRIFT_EXCEEDED"
            else:
                raise AssertionError("expected PersonaRejectedError")

            try:
                await client.create_identity_proposal(
                    turn_id="t",
                    rationale="r",
                    changes={},
                    evidence_episode_ids=[],
                )
            except PersonaRejectedError as exc:
                assert exc.code == "PERSONA_STATE_PROPOSAL_CHANGES_INVALID"
            else:
                raise AssertionError("expected PersonaRejectedError")
        finally:
            await client.close()

    asyncio.run(run())
