"""Map persona domain records to API DTOs."""

from __future__ import annotations

from hla_persona_state.api.schemas import Adaptation, IdentityChangeSet, PersonaIdentity, Proposal, TraitValue
from hla_persona_state.domain.models import Adaptation as AdaptationRecord
from hla_persona_state.domain.models import IdentityVersion, Trait
from hla_persona_state.domain.models import Proposal as ProposalRecord


def to_trait(trait: Trait) -> TraitValue:
    return TraitValue(trait=trait.trait, value=trait.value, confidence=trait.confidence)


def to_identity(record: IdentityVersion) -> PersonaIdentity:
    return PersonaIdentity(
        version=record.version,
        traits=[to_trait(trait) for trait in record.traits],
        narrative=record.narrative,
        effective_from=record.effective_from,
        created_at=record.created_at,
        created_by=record.created_by,
    )


def to_adaptation(record: AdaptationRecord) -> Adaptation:
    return Adaptation(
        version=record.version,
        values=record.values,
        updated_at=record.updated_at,
        drift=record.drift,
    )


def to_proposal(record: ProposalRecord) -> Proposal:
    return Proposal(
        proposal_id=record.proposal_id,
        status=record.status,
        proposer=record.proposer,
        rationale=record.rationale,
        changes=IdentityChangeSet.model_validate(record.changes),
        evidence_episode_ids=list(record.evidence_episode_ids),
        created_at=record.created_at,
        reviewed_at=record.reviewed_at,
        reviewer=record.reviewer,
        review_note=record.review_note,
    )
