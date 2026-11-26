"""Module settings and declared development permissions."""

from __future__ import annotations

from dataclasses import dataclass

from hla_host.config import ConfigField, HostSettings, ModuleConfig, module_port

MODULE_ID = "persona-state"
MODULE_VERSION = "0.1.0"

DEV_PERMISSIONS = (
    "persona-state.identity.read",
    "persona-state.identity.write",
    "persona-state.identity.rollback",
    "persona-state.adaptation.read",
    "persona-state.adaptation.write",
    "persona-state.proposal.create",
    "persona-state.proposal.read",
    "persona-state.proposal.review",
    "persona-state.experience.append",
    "persona-state.experience.read",
    "persona-state.admin.read",
    "persona-state.admin.write",
)

CONFIG_FIELDS = (
    ConfigField(
        "persona-state.db.dsn",
        str,
        default="postgresql://persona_state:persona_state@localhost:5432/persona_state",
        sensitive=True,
        description="PostgreSQL DSN owned exclusively by this module.",
    ),
    ConfigField(
        "persona-state.adaptation.maxDelta",
        float,
        default=0.15,
        description="Largest single bounded adaptation delta.",
    ),
    ConfigField(
        "persona-state.adaptation.windowHours",
        int,
        default=24,
        description="Rolling window used to cap cumulative adaptation drift.",
    ),
    ConfigField(
        "persona-state.adaptation.maxDrift",
        float,
        default=0.30,
        description="Maximum cumulative drift per window before writes are rejected.",
    ),
    ConfigField(
        "persona-state.identity.maxVersions",
        int,
        default=200,
        description="Retained identity versions before archival.",
    ),
    ConfigField(
        "persona-state.retention.experienceDays",
        int,
        default=365,
        description="Experience log retention in days.",
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
            port=module_port(MODULE_ID, 8083),
        )
