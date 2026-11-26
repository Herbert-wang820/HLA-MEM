"""Pure retrieval algorithms: cosine, spreading activation and fusion."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from hla_memory_graph.domain.models import (
    Candidate,
    CoactivationEdge,
)


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def spreading_scores(
    seeds: Mapping[str, float],
    edges: Sequence[CoactivationEdge],
    *,
    decay: float,
    max_hops: int,
    visible_ids: set[str],
) -> dict[str, tuple[float, int]]:
    """Breadth-first activation from seed episodes.

    Score at hop h is ``seed_score * edge_weight * decay**h``; the best score
    per episode wins.  Retracted/invisible episodes are never activated.
    """
    if not seeds or max_hops <= 0 or not 0.0 < decay <= 1.0:
        return {}
    by_source: dict[str, list[CoactivationEdge]] = {}
    for edge in edges:
        by_source.setdefault(edge.source_id, []).append(edge)
        by_source.setdefault(edge.target_id, []).append(edge)

    best: dict[str, tuple[float, int]] = {}
    frontier: dict[str, float] = {episode_id: score for episode_id, score in seeds.items() if score > 0}
    for hop in range(1, max_hops + 1):
        next_frontier: dict[str, float] = {}
        for node_id, node_score in frontier.items():
            for edge in by_source.get(node_id, ()):
                neighbor = edge.target_id if edge.source_id == node_id else edge.source_id
                if neighbor not in visible_ids or neighbor in seeds:
                    continue
                score = node_score * edge.weight * (decay**hop)
                if score <= 0:
                    continue
                previous = best.get(neighbor)
                if previous is None or score > previous[0]:
                    best[neighbor] = (score, hop)
                    next_frontier[neighbor] = max(next_frontier.get(neighbor, 0.0), score)
        if not next_frontier:
            break
        frontier = next_frontier
    return best


def fuse_candidates(
    semantic: Mapping[str, float],
    spreading: Mapping[str, tuple[float, int]],
    *,
    min_score: float,
    limit: int,
) -> list[Candidate]:
    """Fuse two paths with a probabilistic OR and keep the best ``limit``."""
    merged: dict[str, dict[str, object]] = {}
    for episode_id, score in semantic.items():
        if score < min_score:
            continue
        merged[episode_id] = {"score": score, "sources": ["semantic"], "hop": None}
    for episode_id, (score, hop) in spreading.items():
        if score < min_score:
            continue
        entry = merged.get(episode_id)
        if entry is None:
            merged[episode_id] = {"score": score, "sources": ["spreading"], "hop": hop}
            continue
        previous = float(entry["score"])  # type: ignore[arg-type]
        entry["score"] = 1.0 - (1.0 - previous) * (1.0 - score)
        sources = entry["sources"]
        assert isinstance(sources, list)
        sources.append("spreading")
        entry["hop"] = hop

    candidates = [
        Candidate(
            episode_id=episode_id,
            score=min(1.0, max(0.0, float(entry["score"]))),  # type: ignore[arg-type]
            sources=tuple(str(item) for item in entry["sources"]),  # type: ignore[union-attr]
            hop_count=entry["hop"] if isinstance(entry["hop"], int) else None,
        )
        for episode_id, entry in merged.items()
    ]
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.episode_id))
    return candidates[:limit]
