"""Request/response DTOs for reasoning-orchestrator."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TurnCreateRequest(APIModel):
    session_id: str = Field(alias="sessionId", min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8_000)
    stream: bool = True
    client_timezone: str | None = Field(None, alias="clientTimezone", max_length=64)


class Degradation(APIModel):
    memory_degraded: bool = Field(False, alias="memoryDegraded")
    persona_degraded: bool = Field(False, alias="personaDegraded")
    llm_degraded: bool = Field(False, alias="llmDegraded")
    reasons: list[str] = Field(default_factory=list)


class Turn(APIModel):
    turn_id: str = Field(alias="turnId")
    session_id: str = Field(alias="sessionId")
    status: Literal["queued", "running", "completed", "failed", "degraded"]
    created_at: datetime = Field(alias="createdAt")
    completed_at: datetime | None = Field(None, alias="completedAt")
    degradation: Degradation = Field(default_factory=Degradation)
    persona_version: int | None = Field(None, alias="personaVersion", ge=1)
    adaptation_version: int | None = Field(None, alias="adaptationVersion", ge=1)
    identity_proposal_id: str | None = Field(None, alias="identityProposalId")


class TurnAudit(APIModel):
    turn_id: str = Field(alias="turnId")
    retrieval_ids: list[str] = Field(default_factory=list, alias="retrievalIds")
    gate_score: float | None = Field(None, alias="gateScore", ge=0.0, le=1.0)
    gate_threshold: float | None = Field(None, alias="gateThreshold", ge=0.0, le=1.0)
    candidates_considered: int = Field(0, alias="candidatesConsidered", ge=0, le=50)
    used_episode_ids: list[str] = Field(default_factory=list, alias="usedEpisodeIds")
    latency_ms: float = Field(0.0, alias="latencyMs", ge=0.0)
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list, alias="degradationReasons")


class GateConfig(APIModel):
    tau: float = Field(ge=0.0, le=1.0)
    beta: float = Field(ge=0.0, le=1.0)
    top_k: int = Field(alias="topK", ge=1, le=50)
    calibrator: Literal["identity", "isotonic", "platt"] = "identity"
    updated_at: datetime = Field(alias="updatedAt")


class GateConfigUpdate(APIModel):
    tau: float = Field(ge=0.0, le=1.0)
    beta: float = Field(ge=0.0, le=1.0)
    top_k: int = Field(alias="topK", ge=1, le=50)
    calibrator: Literal["identity", "isotonic", "platt"] = "identity"
    expected_version: int | None = Field(None, alias="expectedVersion", ge=1)


class LLMConfigView(APIModel):
    enabled: bool
    base_url: str = Field(alias="baseUrl")
    model: str
    api_key_set: bool = Field(alias="apiKeySet")
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(alias="maxTokens", ge=1, le=8192)
    updated_at: datetime | None = Field(None, alias="updatedAt")


class LLMConfigUpdate(APIModel):
    enabled: bool = False
    base_url: str = Field("https://api.openai.com/v1", alias="baseUrl", max_length=500)
    model: str = Field("gpt-4o-mini", max_length=200)
    api_key: str | None = Field(None, alias="apiKey", max_length=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(512, alias="maxTokens", ge=1, le=8192)

    @model_validator(mode="after")
    def _validate_enabled(self) -> LLMConfigUpdate:
        if self.enabled:
            if not self.base_url.startswith(("http://", "https://")):
                raise ValueError("baseUrl must be an http(s) URL when enabled")
            if not self.model.strip():
                raise ValueError("model is required when enabled")
        return self
