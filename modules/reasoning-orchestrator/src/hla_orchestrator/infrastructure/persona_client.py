"""HTTP client for persona-state identity, adaptation and proposal capabilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from hla_orchestrator.application.errors import PersonaRejectedError, PersonaUnavailableError
from hla_orchestrator.domain.persona import PersonaProfile, PersonaTrait


class HttpPersonaClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    async def fetch_profile(self) -> PersonaProfile:
        try:
            identity_response = await self._client.get(
                "/api/persona-state/v1/identity",
                timeout=self._timeout,
            )
            identity_response.raise_for_status()
            identity = identity_response.json()
            adaptation_response = await self._client.get(
                "/api/persona-state/v1/adaptation",
                timeout=self._timeout,
            )
            adaptation_response.raise_for_status()
            adaptation = adaptation_response.json()
            traits = tuple(
                PersonaTrait(
                    trait=str(item["trait"]),
                    value=str(item["value"]),
                    confidence=float(item.get("confidence", 0.0)),
                )
                for item in identity.get("traits", ())
            )
            return PersonaProfile(
                identity_version=int(identity["version"]),
                adaptation_version=int(adaptation["version"]),
                narrative=str(identity.get("narrative", "")),
                traits=traits,
                adaptation={str(key): float(value) for key, value in adaptation.get("values", {}).items()},
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise PersonaUnavailableError("persona-state read failed") from exc

    async def update_adaptation(
        self,
        *,
        expected_version: int,
        deltas: dict[str, float],
        reason: str,
    ) -> int:
        try:
            response = await self._client.patch(
                "/api/persona-state/v1/adaptation",
                json={"expectedVersion": expected_version, "deltas": deltas, "reason": reason},
                timeout=self._timeout,
            )
            self._raise_for_write(response, "adaptation update")
            return int(response.json()["version"])
        except PersonaRejectedError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise PersonaUnavailableError("persona-state adaptation update failed") from exc

    async def create_identity_proposal(
        self,
        *,
        turn_id: str,
        rationale: str,
        changes: dict[str, Any],
        evidence_episode_ids: Sequence[str],
    ) -> str:
        try:
            response = await self._client.post(
                "/api/persona-state/v1/proposals",
                headers={"Idempotency-Key": f"{turn_id}:persona-proposal"},
                json={
                    "rationale": rationale,
                    "changes": changes,
                    "evidenceEpisodeIds": list(evidence_episode_ids),
                },
                timeout=self._timeout,
            )
            self._raise_for_write(response, "identity proposal")
            return str(response.json()["proposalId"])
        except PersonaRejectedError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise PersonaUnavailableError("persona-state proposal creation failed") from exc

    @staticmethod
    def _raise_for_write(response: httpx.Response, operation: str) -> None:
        if response.status_code in (409, 422):
            code = "PERSONA_STATE_REJECTED"
            message = f"persona-state {operation} rejected"
            try:
                body = response.json()
                if isinstance(body, dict):
                    code = str(body.get("code", code))
                    message = str(body.get("message", message))
            except ValueError:
                pass
            raise PersonaRejectedError(message, code=code)
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
