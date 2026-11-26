"""Module settings and declared development permissions."""

from __future__ import annotations

from dataclasses import dataclass

from hla_host.config import ConfigField, HostSettings, ModuleConfig, module_port

MODULE_ID = "async-consolidator"
MODULE_VERSION = "0.1.0"

DEV_PERMISSIONS = (
    "async-consolidator.job.create",
    "async-consolidator.job.read",
    "async-consolidator.job.retry",
    "async-consolidator.deadletter.read",
    "async-consolidator.deadletter.replay",
    "async-consolidator.admin.read",
)

CONFIG_FIELDS = (
    ConfigField(
        "async-consolidator.db.dsn",
        str,
        default="postgresql://consolidator:consolidator@localhost:5433/consolidator",
        sensitive=True,
        description="PostgreSQL DSN owned exclusively by this module.",
    ),
    ConfigField(
        "async-consolidator.queue.maxAttempts",
        int,
        default=5,
        description="Attempts before a job moves to the dead-letter queue.",
    ),
    ConfigField(
        "async-consolidator.queue.visibilityTimeoutSeconds",
        int,
        default=60,
        description="Lease duration for a claimed job before it is reclaimable.",
    ),
    ConfigField(
        "async-consolidator.queue.batchSize",
        int,
        default=50,
        description="Jobs claimed per polling cycle.",
    ),
    ConfigField(
        "async-consolidator.queue.pollIntervalMs",
        int,
        default=1000,
        description="Idle polling interval.",
    ),
    ConfigField(
        "async-consolidator.memory.baseUrl",
        str,
        default="http://127.0.0.1:8082",
        description="memory-graph base URL for consolidation.apply.",
    ),
    ConfigField(
        "async-consolidator.persona.baseUrl",
        str,
        default="http://127.0.0.1:8083",
        description="persona-state base URL for proposals/adaptation.",
    ),
    ConfigField(
        "async-consolidator.backlog.warnDepth",
        int,
        default=1000,
        description="Backlog depth that flips readiness to degraded.",
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
            port=module_port(MODULE_ID, 8084),
        )
