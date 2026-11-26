"""Minimal System-One gate for the demo.

The real classifier is an optimization item; this version uses the best
retrieved score plus a small spreading-source bonus and is fully explainable.
"""

from __future__ import annotations

from collections.abc import Sequence

from hla_orchestrator.domain.models import MemoryHit


def gate_memories(
    hits: Sequence[MemoryHit],
    *,
    tau: float,
    top_k: int,
    beta: float = 0.0,
) -> tuple[float, list[MemoryHit]]:
    if not hits:
        return 0.0, []
    score = max(0.0, min(1.0, max(hit.score for hit in hits)))
    if any("spreading" in hit.sources for hit in hits):
        score = min(1.0, score + max(0.0, beta) * 0.05)
    if score < tau:
        return score, []
    return score, list(hits[: max(1, top_k)])
