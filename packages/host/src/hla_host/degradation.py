"""Degradation flags shared by orchestrator responses and frontends."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DegradationFlags(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    memory_degraded: bool = Field(False, alias="memoryDegraded")
    persona_degraded: bool = Field(False, alias="personaDegraded")
    llm_degraded: bool = Field(False, alias="llmDegraded")
    reasons: list[str] = Field(default_factory=list)

    @property
    def any_degraded(self) -> bool:
        return self.memory_degraded or self.persona_degraded or self.llm_degraded
