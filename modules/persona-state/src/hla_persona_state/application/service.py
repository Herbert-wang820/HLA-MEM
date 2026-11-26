"""Persona use cases: identity versioning, bounded adaptation and proposal review."""

from __future__ import annotations

import asyncio
import math
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from hla_host.errors import ModuleError
from hla_host.events import DomainEvent, new_event
from hla_host.pagination import decode_cursor, encode_cursor
from hla_persona_state.domain.models import Adaptation, IdentityState, IdentityVersion, Proposal, Trait
from hla_persona_state.infrastructure.store import InMemoryPersonaStore

MODULE_ID = "persona-state"
Publish = Callable[[DomainEvent], Awaitable[None]]

MAX_TRAITS = 64
MAX_NARRATIVE = 8_000
MAX_RATIONALE = 2_000
MAX_EVIDENCE = 50


def _invalid_changes(detail: str) -> ModuleError:
    return ModuleError(
        "PERSONA_STATE_PROPOSAL_CHANGES_INVALID",
        "proposal changes must be a complete identity snapshot",
        422,
        details={"field": "changes", "reason": detail},
    )


def parse_identity_changes(changes: dict[str, Any]) -> tuple[tuple[Trait, ...], str]:
    """Validate the proposed identity snapshot used by model/admin proposals."""
    if not isinstance(changes, dict):
        raise _invalid_changes("changes must be an object")
    unknown = set(changes) - {"traits", "narrative"}
    if unknown:
        raise _invalid_changes(f"unknown fields: {', '.join(sorted(unknown))}")
    raw_traits = changes.get("traits")
    if not isinstance(raw_traits, list) or not 1 <= len(raw_traits) <= MAX_TRAITS:
        raise _invalid_changes(f"traits must be a list with 1..{MAX_TRAITS} items")
    traits: list[Trait] = []
    for index, item in enumerate(raw_traits):
        if not isinstance(item, dict):
            raise _invalid_changes(f"traits[{index}] must be an object")
        if set(item) - {"trait", "value", "confidence"}:
            raise _invalid_changes(f"traits[{index}] has unknown fields")
        trait = item.get("trait")
        value = item.get("value")
        confidence = item.get("confidence")
        if not isinstance(trait, str) or not 1 <= len(trait) <= 64:
            raise _invalid_changes(f"traits[{index}].trait must be 1..64 characters")
        if not isinstance(value, str) or not 1 <= len(value) <= 512:
            raise _invalid_changes(f"traits[{index}].value must be 1..512 characters")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise _invalid_changes(f"traits[{index}].confidence must be within 0..1")
        traits.append(Trait(trait=trait, value=value, confidence=float(confidence)))
    narrative = changes.get("narrative", "")
    if not isinstance(narrative, str) or len(narrative) > MAX_NARRATIVE:
        raise _invalid_changes(f"narrative must be a string of at most {MAX_NARRATIVE} characters")
    return tuple(traits), narrative


class PersonaService:
    def __init__(
        self,
        *,
        store: InMemoryPersonaStore,
        publish: Publish,
        max_delta: float = 0.15,
        window_hours: int = 24,
        max_drift: float = 0.30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._publish = publish
        self._max_delta = max_delta
        self._window = timedelta(hours=window_hours)
        self._max_drift = max_drift
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    async def get_identity(self, tenant_id: str) -> IdentityVersion:
        state = await self._store.get(tenant_id)
        return state.current

    async def create_identity_version(
        self,
        tenant_id: str,
        *,
        subject: str,
        traits: Sequence[Trait],
        narrative: str,
        reason: str,
    ) -> IdentityVersion:
        async with self._lock:
            state = await self._store.get(tenant_id)
            return await self._create_identity_version_locked(
                state,
                tenant_id,
                subject=subject,
                traits=traits,
                narrative=narrative,
                reason=reason,
            )

    async def _create_identity_version_locked(
        self,
        state: IdentityState,
        tenant_id: str,
        *,
        subject: str,
        traits: Sequence[Trait],
        narrative: str,
        reason: str,
    ) -> IdentityVersion:
        now = self._clock()
        previous = state.current
        version = IdentityVersion(
            version=previous.version + 1,
            traits=tuple(traits),
            narrative=narrative,
            effective_from=now,
            created_at=now,
            created_by=subject,
        )
        state.versions.append(version)
        await self._publish(
            new_event(
                type="persona-state.identity.versioned.v1",
                source=MODULE_ID,
                subject=state.identity_id,
                tenant_id=tenant_id,
                data={
                    "identityId": state.identity_id,
                    "version": version.version,
                    "previousVersion": previous.version,
                    "reasonCode": reason,
                },
            )
        )
        return version

    async def rollback_identity(
        self,
        tenant_id: str,
        *,
        subject: str,
        target_version: int,
        reason: str,
    ) -> IdentityVersion:
        async with self._lock:
            state = await self._store.get(tenant_id)
            target = next((item for item in state.versions if item.version == target_version), None)
            if target is None:
                raise ModuleError(
                    "PERSONA_STATE_IDENTITY_VERSION_NOT_FOUND",
                    "identity version not found",
                    404,
                    details={"version": target_version},
                )
            now = self._clock()
            version = IdentityVersion(
                version=state.current.version + 1,
                traits=target.traits,
                narrative=target.narrative,
                effective_from=now,
                created_at=now,
                created_by=subject,
            )
            state.versions.append(version)
            await self._publish(
                new_event(
                    type="persona-state.identity.rolled-back.v1",
                    source=MODULE_ID,
                    subject=state.identity_id,
                    tenant_id=tenant_id,
                    data={
                        "identityId": state.identity_id,
                        "version": version.version,
                        "targetVersion": target_version,
                        "reasonCode": reason,
                    },
                )
            )
            return version

    async def get_adaptation(self, tenant_id: str) -> Adaptation:
        state = await self._store.get(tenant_id)
        assert state.adaptation is not None
        return state.adaptation

    async def update_adaptation(
        self,
        tenant_id: str,
        *,
        expected_version: int,
        deltas: dict[str, float],
        reason: str,
    ) -> Adaptation:
        async with self._lock:
            state = await self._store.get(tenant_id)
            current = state.adaptation
            assert current is not None
            if current.version != expected_version:
                raise ModuleError(
                    "PERSONA_STATE_ADAPTATION_VERSION_CONFLICT",
                    "adaptation version does not match expectedVersion",
                    409,
                    details={"expectedVersion": expected_version, "currentVersion": current.version},
                )
            for dimension, delta in deltas.items():
                if not math.isfinite(delta) or abs(delta) > self._max_delta:
                    raise ModuleError(
                        "PERSONA_STATE_ADAPTATION_DELTA_TOO_LARGE",
                        f"delta for {dimension!r} exceeds the allowed step",
                        422,
                        details={"dimension": dimension, "maxDelta": self._max_delta},
                    )
            now = self._clock()
            if state.window_start is None or now - state.window_start >= self._window:
                state.window_start = now
                state.drift = 0.0
            total = sum(abs(delta) for delta in deltas.values())
            if state.drift + total > self._max_drift:
                raise ModuleError(
                    "PERSONA_STATE_ADAPTATION_DRIFT_EXCEEDED",
                    "cumulative adaptation drift exceeds the configured window limit",
                    409,
                    details={"drift": round(state.drift, 6), "maxDrift": self._max_drift},
                )

            values = dict(current.values)
            applied = []
            max_step = 0.0
            for dimension, delta in deltas.items():
                before = values.get(dimension, 0.0)
                after = min(1.0, max(0.0, before + delta))
                values[dimension] = round(after, 6)
                clamped = abs(after - (before + delta)) > 1e-9
                applied.append({"dimension": dimension, "delta": delta, "clamped": clamped})
                max_step = max(max_step, abs(delta))
            state.drift = round(state.drift + total, 6)
            updated = Adaptation(
                version=current.version + 1,
                values=values,
                updated_at=now,
                drift=state.drift,
            )
            state.adaptation = updated
            await self._publish(
                new_event(
                    type="persona-state.adaptation.updated.v1",
                    source=MODULE_ID,
                    subject=state.identity_id,
                    tenant_id=tenant_id,
                    data={
                        "identityId": state.identity_id,
                        "version": updated.version,
                        "jobId": str(uuid.uuid4()),
                        "applied": applied,
                        "maxStep": max_step,
                    },
                )
            )
            return updated

    async def create_proposal(
        self,
        tenant_id: str,
        *,
        proposer: str,
        rationale: str,
        changes: dict[str, Any],
        evidence_episode_ids: Sequence[str],
    ) -> Proposal:
        # Reject malformed proposals at creation time so reviewers never see
        # a proposal that cannot be applied.
        parse_identity_changes(changes)
        if not rationale.strip() or len(rationale) > MAX_RATIONALE:
            raise ModuleError(
                "PERSONA_STATE_PROPOSAL_RATIONALE_INVALID",
                f"rationale must be 1..{MAX_RATIONALE} characters",
                422,
                details={"field": "rationale"},
            )
        if len(evidence_episode_ids) > MAX_EVIDENCE:
            raise ModuleError(
                "PERSONA_STATE_PROPOSAL_EVIDENCE_TOO_LONG",
                f"evidenceEpisodeIds supports at most {MAX_EVIDENCE} items",
                422,
                details={"field": "evidenceEpisodeIds"},
            )
        async with self._lock:
            state = await self._store.get(tenant_id)
            now = self._clock()
            proposal = Proposal(
                proposal_id=str(uuid.uuid4()),
                status="pending",
                proposer=proposer,
                rationale=rationale,
                changes=changes,
                evidence_episode_ids=tuple(evidence_episode_ids),
                created_at=now,
            )
            state.proposals.append(proposal)
            await self._publish(
                new_event(
                    type="persona-state.proposal.created.v1",
                    source=MODULE_ID,
                    subject=state.identity_id,
                    tenant_id=tenant_id,
                    data={
                        "proposalId": proposal.proposal_id,
                        "identityId": state.identity_id,
                        "status": proposal.status,
                    },
                )
            )
            return proposal

    async def list_proposals(
        self,
        tenant_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Proposal], str | None]:
        offset = 0
        if cursor:
            try:
                payload = decode_cursor(cursor)
                raw_offset = payload.get("offset")
                if not isinstance(raw_offset, int) or isinstance(raw_offset, bool) or raw_offset < 0:
                    raise ValueError("invalid offset")
                offset = raw_offset
            except ValueError as exc:
                raise ModuleError(
                    "PERSONA_STATE_PROPOSAL_CURSOR_INVALID",
                    "cursor is invalid",
                    422,
                    details={"field": "cursor"},
                ) from exc
        state = await self._store.get(tenant_id)
        ordered = sorted(state.proposals, key=lambda item: (item.created_at, item.proposal_id), reverse=True)
        page = ordered[offset : offset + limit]
        next_cursor = encode_cursor({"offset": offset + limit}) if offset + limit < len(ordered) else None
        return page, next_cursor

    async def review_proposal(
        self,
        tenant_id: str,
        *,
        proposal_id: str,
        reviewer: str,
        decision: str,
        note: str | None,
    ) -> Proposal:
        async with self._lock:
            state = await self._store.get(tenant_id)
            index = next(
                (position for position, item in enumerate(state.proposals) if item.proposal_id == proposal_id),
                None,
            )
            if index is None:
                raise ModuleError(
                    "PERSONA_STATE_PROPOSAL_NOT_FOUND",
                    "proposal not found",
                    404,
                    details={"proposalId": proposal_id},
                )
            proposal = state.proposals[index]
            if proposal.status != "pending":
                raise ModuleError(
                    "PERSONA_STATE_PROPOSAL_ALREADY_REVIEWED",
                    "proposal has already been reviewed",
                    409,
                    details={"proposalId": proposal_id, "status": proposal.status},
                )
            now = self._clock()
            if decision == "approve":
                traits, narrative = parse_identity_changes(proposal.changes)
                await self._create_identity_version_locked(
                    state,
                    tenant_id,
                    subject=reviewer,
                    traits=traits,
                    narrative=narrative,
                    reason=f"proposal:{proposal.proposal_id}",
                )
                status = "approved"
            else:
                status = "rejected"
            reviewed = replace(
                proposal,
                status=status,
                reviewed_at=now,
                reviewer=reviewer,
                review_note=note,
            )
            state.proposals[index] = reviewed
            await self._publish(
                new_event(
                    type="persona-state.proposal.reviewed.v1",
                    source=MODULE_ID,
                    subject=state.identity_id,
                    tenant_id=tenant_id,
                    data={
                        "proposalId": reviewed.proposal_id,
                        "decision": decision,
                        "reviewerSubject": reviewer,
                    },
                )
            )
            return reviewed
