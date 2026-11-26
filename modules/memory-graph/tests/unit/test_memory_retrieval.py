from __future__ import annotations

from hla_memory_graph.domain.models import CoactivationEdge
from hla_memory_graph.domain.retrieval import cosine, fuse_candidates, spreading_scores


def _edge(source: str, target: str, weight: float) -> CoactivationEdge:
    from datetime import UTC, datetime

    return CoactivationEdge(
        edge_id=f"{source}-{target}",
        tenant_id="t",
        source_id=source,
        target_id=target,
        weight=weight,
        last_activated_at=datetime(2026, 11, 10, tzinfo=UTC),
        activation_count=1,
    )


def test_cosine_is_bounded_and_handles_zero_vectors() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert cosine((1.0, 0.0), (0.0, 1.0)) == 0.0
    assert cosine((0.0, 0.0), (1.0, 0.0)) == 0.0
    assert cosine((1.0,), (1.0, 0.0)) == 0.0


def test_spreading_decays_by_hop_and_respects_visibility() -> None:
    edges = [_edge("a", "b", 0.5), _edge("b", "c", 0.8)]
    scores = spreading_scores({"a": 1.0}, edges, decay=0.5, max_hops=2, visible_ids={"a", "b", "c"})
    assert scores["b"] == (0.25, 1)
    assert scores["c"][1] == 2
    assert abs(scores["c"][0] - 0.05) < 1e-9

    hidden = spreading_scores({"a": 1.0}, edges, decay=0.5, max_hops=2, visible_ids={"a"})
    assert hidden == {}


def test_seed_episodes_are_not_returned_as_spreading_candidates() -> None:
    edges = [_edge("a", "b", 0.5)]
    scores = spreading_scores({"a": 1.0, "b": 1.0}, edges, decay=0.5, max_hops=2, visible_ids={"a", "b"})
    assert scores == {}


def test_fusion_uses_probabilistic_or_and_keeps_sources() -> None:
    candidates = fuse_candidates(
        {"a": 0.6, "b": 0.1},
        {"a": (0.5, 1), "b": (0.2, 2)},
        min_score=0.05,
        limit=10,
    )
    by_id = {candidate.episode_id: candidate for candidate in candidates}
    assert abs(by_id["a"].score - 0.8) < 1e-9
    assert by_id["a"].sources == ("semantic", "spreading")
    assert by_id["a"].hop_count == 1
    assert by_id["b"].sources == ("semantic", "spreading")


def test_fusion_drops_low_scores_and_respects_limit() -> None:
    candidates = fuse_candidates(
        {"a": 0.9, "b": 0.8, "c": 0.01},
        {},
        min_score=0.05,
        limit=1,
    )
    assert [candidate.episode_id for candidate in candidates] == ["a"]
