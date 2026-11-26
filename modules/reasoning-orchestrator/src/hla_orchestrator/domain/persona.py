"""Persona profile prompt plus the model-facing persona action markers.

The marker protocol is the v1 contract documented in
``contracts/persona-actions.v1.yaml``.  Adaptation changes are applied
directly (bounded by persona-state); identity changes are always proposals and
require an administrator to approve them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from hla_orchestrator.domain.models import AdaptationRequest, IdentityProposalRequest

_UPDATE_TAG = "persona_update"
_PROPOSAL_TAG = "persona_proposal"
_MAX_MARKER_JSON = 20_000

PERSONA_INSTRUCTION = (
    "\n\n你可以通过隐藏标记调整人格，标记不会展示给用户：\n"
    '适应层（直接生效且有界）：<persona_update>{"deltas":{"warmth":0.1},"reason":"简短原因"}</persona_update>\n'
    '身份层（只能提案，需管理员审批）：<persona_proposal>{"rationale":"原因","changes":'
    '{"traits":[{"trait":"tone","value":"温和","confidence":0.8}],"narrative":"完整身份叙事"},'
    '"evidenceEpisodeIds":[]}</persona_proposal>\n'
    "规则：每轮最多输出一个标记；适应层每维 |delta| ≤ 0.15、单轮最多 4 个维度；"
    "身份层必须提交完整 traits 与 narrative，不得直接改写已发布版本。"
)

# Backwards-compatible name for callers that only need the adaptation guidance.
ADAPTATION_INSTRUCTION = PERSONA_INSTRUCTION


@dataclass(frozen=True, slots=True)
class PersonaTrait:
    trait: str
    value: str
    confidence: float


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    identity_version: int
    adaptation_version: int
    narrative: str
    traits: tuple[PersonaTrait, ...]
    adaptation: dict[str, float]

    def prompt(self) -> str:
        traits = "；".join(f"{item.trait}={item.value}" for item in self.traits) or "无"
        adaptation = "，".join(f"{key}={value:.2f}" for key, value in sorted(self.adaptation.items())) or "无"
        return (
            f"人格身份 v{self.identity_version}：{self.narrative}\n"
            f"稳定特质：{traits}\n"
            f"当前适应层 v{self.adaptation_version}：{adaptation}"
        )


def _take_markers(text: str, tag: str) -> tuple[str, list[str]]:
    """Remove every ``<tag>{json}</tag>`` block and return its JSON payloads."""
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    payloads: list[str] = []
    pieces: list[str] = []
    cursor = 0
    while True:
        start = text.find(open_tag, cursor)
        if start < 0:
            break
        end = text.find(close_tag, start + len(open_tag))
        if end < 0:
            break
        payloads.append(text[start + len(open_tag) : end].strip())
        pieces.append(text[cursor:start])
        cursor = end + len(close_tag)
    pieces.append(text[cursor:])
    return "".join(pieces).strip(), payloads


def _bounded_reason(value: Any, default: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    return value.strip()[:200]


def extract_persona_update(text: str) -> tuple[str, AdaptationRequest | None]:
    cleaned, payloads = _take_markers(text, _UPDATE_TAG)
    if not payloads:
        return text, None
    try:
        payload = json.loads(payloads[-1])
        if not isinstance(payload, dict):
            return cleaned, None
        raw_deltas = payload.get("deltas")
        if not isinstance(raw_deltas, dict):
            return cleaned, None
        deltas: dict[str, float] = {}
        for key, value in list(raw_deltas.items())[:4]:
            if not isinstance(key, str) or not key.strip() or isinstance(value, bool):
                return cleaned, None
            if not isinstance(value, (int, float)):
                return cleaned, None
            delta = float(value)
            if not math.isfinite(delta) or abs(delta) > 0.15:
                return cleaned, None
            deltas[key.strip()[:64]] = delta
        if not deltas:
            return cleaned, None
        return cleaned or "（已记录人格适应层调整）", AdaptationRequest(
            deltas=deltas,
            reason=_bounded_reason(payload.get("reason"), "model_request"),
        )
    except (ValueError, TypeError):
        return cleaned, None


def extract_persona_proposal(text: str) -> tuple[str, IdentityProposalRequest | None]:
    cleaned, payloads = _take_markers(text, _PROPOSAL_TAG)
    if not payloads:
        return text, None
    payload_text = payloads[-1]
    if len(payload_text) > _MAX_MARKER_JSON:
        return cleaned, None
    try:
        payload = json.loads(payload_text)
    except (ValueError, TypeError):
        return cleaned, None
    if not isinstance(payload, dict):
        return cleaned, None
    rationale = payload.get("rationale")
    changes = payload.get("changes")
    evidence = payload.get("evidenceEpisodeIds", [])
    if not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 2_000:
        return cleaned, None
    if not isinstance(changes, dict) or not changes:
        return cleaned, None
    if set(changes) - {"traits", "narrative"}:
        return cleaned, None
    traits = changes.get("traits")
    narrative = changes.get("narrative", "")
    if not isinstance(traits, list) or not 1 <= len(traits) <= 64:
        return cleaned, None
    if not isinstance(narrative, str) or len(narrative) > 8_000:
        return cleaned, None
    if not isinstance(evidence, list) or len(evidence) > 50:
        return cleaned, None
    episode_ids = tuple(str(item) for item in evidence if isinstance(item, (str, int)))
    if len(episode_ids) != len(evidence):
        return cleaned, None
    return cleaned or "（已提交人格身份变更提案，等待管理员审批）", IdentityProposalRequest(
        rationale=rationale.strip(),
        changes=changes,
        evidence_episode_ids=episode_ids,
    )


def extract_persona_actions(
    text: str,
) -> tuple[str, AdaptationRequest | None, IdentityProposalRequest | None]:
    cleaned, adaptation = extract_persona_update(text)
    cleaned, proposal = extract_persona_proposal(cleaned)
    return cleaned, adaptation, proposal
