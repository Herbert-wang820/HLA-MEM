"""Map orchestrator domain objects to API DTOs."""

from __future__ import annotations

from hla_orchestrator.api.schemas import Degradation, GateConfig, LLMConfigView, Turn, TurnAudit
from hla_orchestrator.application.service import GateSettings
from hla_orchestrator.domain.models import TurnAudit as TurnAuditRecord
from hla_orchestrator.domain.models import TurnOutcome
from hla_orchestrator.infrastructure.llm_config import LLMConfig


def to_turn(outcome: TurnOutcome) -> Turn:
    return Turn(
        turn_id=outcome.turn_id,
        session_id=outcome.session_id,
        status=outcome.status,
        created_at=outcome.created_at,
        completed_at=outcome.completed_at,
        degradation=Degradation(
            memory_degraded=outcome.memory_degraded,
            persona_degraded=outcome.persona_degraded,
            llm_degraded=outcome.llm_degraded,
            reasons=list(outcome.reasons),
        ),
        persona_version=outcome.persona_version,
        adaptation_version=outcome.adaptation_version,
        identity_proposal_id=outcome.identity_proposal_id,
    )


def to_audit(audit: TurnAuditRecord) -> TurnAudit:
    return TurnAudit(
        turn_id=audit.turn_id,
        retrieval_ids=[audit.retrieval_id] if audit.retrieval_id else [],
        gate_score=audit.gate_score,
        gate_threshold=audit.gate_threshold,
        candidates_considered=audit.candidates_considered,
        used_episode_ids=list(audit.used_episode_ids),
        latency_ms=audit.latency_ms,
        degraded=audit.degraded,
        degradation_reasons=list(audit.reasons),
    )


def to_gate(gate: GateSettings, updated_at) -> GateConfig:
    return GateConfig(
        tau=gate.tau,
        beta=gate.beta,
        top_k=gate.top_k,
        calibrator=gate.calibrator,  # type: ignore[arg-type]
        updated_at=updated_at,
    )


def to_llm_view(config: LLMConfig) -> LLMConfigView:
    return LLMConfigView(
        enabled=config.enabled,
        base_url=config.base_url,
        model=config.model,
        api_key_set=bool(config.api_key),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        updated_at=config.updated_at,
    )
