"""Module settings and declared development permissions."""

from __future__ import annotations

from dataclasses import dataclass

from hla_host.config import ConfigField, HostSettings, ModuleConfig, module_port

MODULE_ID = "memory-graph"
MODULE_VERSION = "0.1.0"

DEV_PERMISSIONS = (
    "memory-graph.episode.read",
    "memory-graph.episode.write",
    "memory-graph.retrieval.read",
    "memory-graph.consolidation.write",
    "memory-graph.admin.read",
)

CONFIG_FIELDS = (
    ConfigField(
        "memory-graph.store.dsn",
        str,
        default="memory://in-memory",
        description="Graph store DSN; in-memory only for development.",
    ),
    ConfigField(
        "memory-graph.store.graph",
        str,
        default="hla_mem",
        description="FalkorDB/Neo4j graph name.",
    ),
    ConfigField(
        "memory-graph.retrieval.semanticTopK",
        int,
        default=20,
        description="Maximum semantic KNN candidates per retrieval.",
    ),
    ConfigField(
        "memory-graph.retrieval.spreadingTopK",
        int,
        default=20,
        description="Maximum spreading-activation candidates per retrieval.",
    ),
    ConfigField(
        "memory-graph.retrieval.topKMax",
        int,
        default=50,
        description="Hard cap for merged Top-K (contract: 50).",
    ),
    ConfigField(
        "memory-graph.embedding.dim",
        int,
        default=256,
        description="Development hashing-embedding dimension (BGE-M3 replaces this adapter).",
    ),
    ConfigField(
        "memory-graph.retrieval.minScore",
        float,
        default=0.05,
        description="Minimum fused score kept in retrieval results.",
    ),
    ConfigField(
        "memory-graph.retrieval.coactivationTopN",
        int,
        default=10,
        description="Top candidates paired into coactivation edges per retrieval.",
    ),
    ConfigField(
        "memory-graph.retrieval.spreadingDecay",
        float,
        default=0.6,
        description="Per-hop decay for spreading activation.",
    ),
    ConfigField(
        "memory-graph.retrieval.maxHops",
        int,
        default=2,
        description="Maximum spreading-activation hops (contract: 2).",
    ),
    ConfigField(
        "memory-graph.consolidation.batchSize",
        int,
        default=500,
        description="Maximum coactivation pairs applied per consolidation batch.",
    ),
    ConfigField(
        "memory-graph.fade.tFade",
        str,
        default="P30D",
        description="ISO-8601 duration after which an unreinforced edge may fade.",
    ),
    ConfigField(
        "memory-graph.fade.wMin",
        float,
        default=0.05,
        description="Minimum edge weight before fading removes or de-weights it.",
    ),
    ConfigField(
        "memory-graph.hub.degreeMin",
        int,
        default=8,
        description="Minimum degree for hub distillation.",
    ),
    ConfigField(
        "memory-graph.hub.clusterMin",
        int,
        default=5,
        description="Minimum cluster size for hub distillation.",
    ),
)


@dataclass(frozen=True, slots=True)
class Settings:
    host: HostSettings
    config: ModuleConfig
    port: int

    @classmethod
    def load(cls) -> Settings:
        return cls(
            host=HostSettings.from_env(),
            config=ModuleConfig(MODULE_ID, CONFIG_FIELDS),
            port=module_port(MODULE_ID, 8082),
        )
