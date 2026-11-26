"""Module settings and declared development permissions."""

from __future__ import annotations

from dataclasses import dataclass

from hla_host.config import ConfigField, HostSettings, ModuleConfig, module_port

MODULE_ID = "reasoning-orchestrator"
MODULE_VERSION = "0.1.0"

DEV_PERMISSIONS = (
    "reasoning-orchestrator.turn.create",
    "reasoning-orchestrator.turn.read",
    "reasoning-orchestrator.audit.read",
    "reasoning-orchestrator.admin.read",
    "reasoning-orchestrator.admin.write",
)

CONFIG_FIELDS = (
    ConfigField(
        "reasoning-orchestrator.memory.baseUrl",
        str,
        default="http://127.0.0.1:8082",
        description="memory-graph base URL (optional dependency).",
    ),
    ConfigField(
        "reasoning-orchestrator.persona.baseUrl",
        str,
        default="http://127.0.0.1:8083",
        description="persona-state base URL (optional dependency).",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.configPath",
        str,
        default="var/reasoning-orchestrator/llm.json",
        description="File-backed LLM configuration saved by admin-web (contains the API key).",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.baseUrl",
        str,
        default="https://api.openai.com/v1",
        description="Default OpenAI-compatible base URL before admin configuration.",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.model",
        str,
        default="gpt-4o-mini",
        description="Default model name before admin configuration.",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.apiKey",
        str,
        default="",
        sensitive=True,
        description="Optional bootstrap API key; admin-saved value takes precedence.",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.temperature",
        float,
        default=0.7,
        description="Default sampling temperature.",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.maxTokens",
        int,
        default=512,
        description="Default completion token budget.",
    ),
    ConfigField(
        "reasoning-orchestrator.persona.static",
        str,
        default="你是一位耐心、务实、重视长期记忆的对话伙伴。回答简洁，并明确说明你记得什么。",
        description="Static persona used until persona-state is implemented.",
    ),
    ConfigField(
        "reasoning-orchestrator.consolidator.baseUrl",
        str,
        default="http://127.0.0.1:8084",
        description="async-consolidator base URL (optional dependency).",
    ),
    ConfigField(
        "reasoning-orchestrator.gate.tau",
        float,
        default=0.2,
        description="Default memory-gate threshold tau.",
    ),
    ConfigField(
        "reasoning-orchestrator.gate.beta",
        float,
        default=0.40,
        description="Weight of spreading activation in gate scoring.",
    ),
    ConfigField(
        "reasoning-orchestrator.retrieval.topK",
        int,
        default=8,
        description="Top-K passed to the LLM after gating.",
    ),
    ConfigField(
        "reasoning-orchestrator.memory.timeoutMs",
        int,
        default=800,
        description="Budget for the memory-graph call before degradation.",
    ),
    ConfigField(
        "reasoning-orchestrator.persona.timeoutMs",
        int,
        default=500,
        description="Budget for the persona-state call before degradation.",
    ),
    ConfigField(
        "reasoning-orchestrator.llm.timeoutMs",
        int,
        default=20000,
        description="Budget for the LLM call.",
    ),
    ConfigField(
        "reasoning-orchestrator.sse.idleTimeoutMs",
        int,
        default=120000,
        description="SSE idle timeout (contract: 120s).",
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
            port=module_port(MODULE_ID, 8081),
        )
