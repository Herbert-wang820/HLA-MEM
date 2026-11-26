"""Turn use case: persona snapshot, retrieve, gate, compose, persist and audit."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from hla_host.errors import IdempotencyConflictError, NotFoundError
from hla_host.events import DomainEvent, new_event
from hla_orchestrator.application.errors import (
    LLMDisabledError,
    LLMUnavailableError,
    MemoryUnavailableError,
    PersonaRejectedError,
    PersonaUnavailableError,
)
from hla_orchestrator.application.ports import CompleterPort, MemoryPort, PersonaPort
from hla_orchestrator.domain.gate import gate_memories
from hla_orchestrator.domain.models import MemoryHit, MemoryRetrieval, TurnAudit, TurnOutcome
from hla_orchestrator.domain.persona import PERSONA_INSTRUCTION, PersonaProfile, extract_persona_actions
from hla_orchestrator.infrastructure.turn_store import TurnStore

MODULE_ID = "reasoning-orchestrator"
Publish = Callable[[DomainEvent], Awaitable[None]]


@dataclass(slots=True)
class GateSettings:
    tau: float = 0.2
    beta: float = 0.4
    top_k: int = 8
    calibrator: str = "identity"
    updated_at: datetime | None = None


class TurnService:
    def __init__(
        self,
        *,
        memory: MemoryPort,
        template: CompleterPort,
        llm: CompleterPort | None,
        store: TurnStore,
        publish: Publish,
        gate: GateSettings,
        persona: PersonaPort | None = None,
        persona_fallback: str = "你是一位耐心、务实、重视长期记忆的对话伙伴。",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._memory = memory
        self._template = template
        self._llm = llm
        self._store = store
        self._publish = publish
        self._gate = gate
        self._persona = persona
        self._persona_fallback = persona_fallback
        self._clock = clock or (lambda: datetime.now(UTC))
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def process(
        self,
        *,
        session_id: str,
        message: str,
        subject: str,
        tenant_id: str,
        idempotency_key: str,
        request_id: str | None = None,
    ) -> TurnOutcome:
        fingerprint = hashlib.sha256(f"{session_id}\0{message}".encode()).hexdigest()
        scope = f"{subject}\0{tenant_id}\0turn.process\0{idempotency_key}"
        async with await self._lock_for(scope):
            cached = await self._store.get_cached(scope)
            if cached is not None:
                if cached.fingerprint != fingerprint:
                    raise IdempotencyConflictError(MODULE_ID)
                return cached.outcome
            outcome = await self._run(
                session_id=session_id,
                message=message,
                tenant_id=tenant_id,
                request_id=request_id,
            )
            await self._store.save(outcome, scope=scope, fingerprint=fingerprint)
            return outcome

    async def _persona_prompt(self) -> tuple[str, PersonaProfile | None]:
        if self._persona is None:
            return self._persona_fallback, None
        try:
            profile = await self._persona.fetch_profile()
        except PersonaUnavailableError:
            return self._persona_fallback, None
        return profile.prompt() + PERSONA_INSTRUCTION, profile

    async def _run(
        self,
        *,
        session_id: str,
        message: str,
        tenant_id: str,
        request_id: str | None,
    ) -> TurnOutcome:
        started = time.perf_counter()
        created_at = self._clock()
        turn_id = str(uuid.uuid4())
        reasons: list[str] = []
        memory_degraded = False
        llm_degraded = False
        persona_degraded = False
        persona_updated = False
        adaptation_version: int | None = None
        identity_proposal_id: str | None = None

        persona_prompt, profile = await self._persona_prompt()
        if self._persona is not None and profile is None:
            persona_degraded = True
            reasons.append("PERSONA_UNAVAILABLE")

        retrieval: MemoryRetrieval | None = None
        try:
            retrieval = await self._memory.retrieve(message, top_k=20, request_id=request_id)
        except MemoryUnavailableError:
            memory_degraded = True
            reasons.append("MEMORY_UNAVAILABLE")

        hits = retrieval.hits if retrieval is not None else ()
        gate_score, used = gate_memories(
            hits,
            tau=self._gate.tau,
            top_k=self._gate.top_k,
            beta=self._gate.beta,
        )

        enriched: list[MemoryHit] = []
        for hit in used[:5]:
            try:
                content = await self._memory.get_episode(hit.episode_id)
            except MemoryUnavailableError:
                memory_degraded = True
                reasons.append("MEMORY_READ_FAILED")
                content = None
            if content:
                enriched.append(replace(hit, excerpt=content[:200]))
            else:
                enriched.append(hit)
        for hit in used[5:]:
            enriched.append(hit)

        generation = None
        if self._llm is not None:
            try:
                generation = await self._llm.complete(message=message, memories=enriched, persona=persona_prompt)
            except LLMDisabledError:
                generation = None
            except LLMUnavailableError:
                llm_degraded = True
                reasons.append("LLM_UNAVAILABLE")
                generation = None
        if generation is None:
            generation = await self._template.complete(message=message, memories=enriched, persona=persona_prompt)

        # Markers are always stripped, even when persona-state was unavailable,
        # so a hidden control payload can never leak into the visible reply.
        text, adaptation_request, proposal_request = extract_persona_actions(generation.text)
        if profile is not None and adaptation_request is not None:
            try:
                adaptation_version = await self._persona.update_adaptation(  # type: ignore[union-attr]
                    expected_version=profile.adaptation_version,
                    deltas=adaptation_request.deltas,
                    reason=adaptation_request.reason,
                )
                persona_updated = True
            except PersonaRejectedError:
                persona_degraded = True
                reasons.append("PERSONA_UPDATE_REJECTED")
            except PersonaUnavailableError:
                persona_degraded = True
                reasons.append("PERSONA_UPDATE_FAILED")
        if profile is not None and proposal_request is not None:
            try:
                identity_proposal_id = await self._persona.create_identity_proposal(  # type: ignore[union-attr]
                    turn_id=turn_id,
                    rationale=proposal_request.rationale,
                    changes=proposal_request.changes,
                    evidence_episode_ids=proposal_request.evidence_episode_ids,
                )
                persona_updated = True
            except PersonaRejectedError:
                persona_degraded = True
                reasons.append("PERSONA_PROPOSAL_REJECTED")
            except PersonaUnavailableError:
                persona_degraded = True
                reasons.append("PERSONA_PROPOSAL_FAILED")

        now = self._clock()
        try:
            await self._memory.write_episode(
                session_id=session_id,
                content=message,
                occurred_at=now,
                source="conversation",
                idempotency_key=f"{turn_id}:user",
            )
            await self._memory.write_episode(
                session_id=session_id,
                content=text,
                occurred_at=now,
                source="orchestrator",
                idempotency_key=f"{turn_id}:assistant",
            )
        except MemoryUnavailableError:
            memory_degraded = True
            reasons.append("MEMORY_WRITE_FAILED")

        completed_at = self._clock()
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        unique_reasons = tuple(dict.fromkeys(reasons))
        degraded = memory_degraded or llm_degraded or persona_degraded
        audit = TurnAudit(
            turn_id=turn_id,
            retrieval_id=retrieval.retrieval_id if retrieval is not None else "",
            gate_score=gate_score,
            gate_threshold=self._gate.tau,
            candidates_considered=len(hits),
            used_episode_ids=tuple(hit.episode_id for hit in used),
            latency_ms=latency_ms,
            degraded=degraded,
            reasons=unique_reasons,
            created_at=completed_at,
        )
        outcome = TurnOutcome(
            turn_id=turn_id,
            session_id=session_id,
            text=text,
            status="degraded" if degraded else "completed",
            created_at=created_at,
            completed_at=completed_at,
            memory_degraded=memory_degraded,
            llm_degraded=llm_degraded,
            persona_degraded=persona_degraded,
            persona_updated=persona_updated,
            reasons=unique_reasons,
            memories=tuple(enriched),
            audit=audit,
            persona_version=profile.identity_version if profile is not None else None,
            adaptation_version=(
                adaptation_version
                if adaptation_version is not None
                else (profile.adaptation_version if profile is not None else None)
            ),
            identity_proposal_id=identity_proposal_id,
        )
        await self._publish_outcome(outcome, tenant_id=tenant_id, used=used)
        return outcome

    async def _publish_outcome(self, outcome: TurnOutcome, *, tenant_id: str, used: Sequence[MemoryHit]) -> None:
        try:
            if outcome.status == "degraded":
                event = new_event(
                    type="reasoning-orchestrator.turn.degraded.v1",
                    source=MODULE_ID,
                    subject=outcome.turn_id,
                    tenant_id=tenant_id,
                    data={"turnId": outcome.turn_id, "reasons": list(outcome.reasons)},
                )
            else:
                route = "slow" if used else "fast"
                event = new_event(
                    type="reasoning-orchestrator.turn.processed.v1",
                    source=MODULE_ID,
                    subject=outcome.turn_id,
                    tenant_id=tenant_id,
                    data={
                        "turnId": outcome.turn_id,
                        "sessionId": outcome.session_id,
                        "path": route,
                        "gateDecision": {
                            "route": route,
                            "confidence": min(1.0, max(0.0, outcome.audit.gate_score if outcome.audit else 0.0)),
                            "reasonCode": "MEMORY_USED" if used else "NO_RELEVANT_MEMORY",
                        },
                        "latencyMs": outcome.audit.latency_ms if outcome.audit else 0.0,
                        "degradedFlags": {
                            "memoryDegraded": outcome.memory_degraded,
                            "personaDegraded": outcome.persona_degraded,
                            "llmDegraded": outcome.llm_degraded,
                            "reasons": list(outcome.reasons),
                        },
                        "memoryRefs": [hit.episode_id for hit in used],
                        "personaVersion": outcome.persona_version,
                    },
                )
            await self._publish(event)
        except Exception:  # noqa: BLE001 - event loss must not fail the user's turn
            return

    async def get_turn(self, turn_id: str) -> TurnOutcome:
        outcome = await self._store.get_turn(turn_id)
        if outcome is None:
            raise NotFoundError(MODULE_ID, "TURN", turn_id)
        return outcome

    async def get_audit(self, turn_id: str) -> TurnAudit:
        audit = await self._store.get_audit(turn_id)
        if audit is None:
            raise NotFoundError(MODULE_ID, "AUDIT", turn_id)
        return audit

    async def _lock_for(self, scope: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(scope)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[scope] = lock
            return lock
