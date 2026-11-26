"""Application-level failures that the API maps to stable error codes."""

from __future__ import annotations


class MemoryUnavailableError(RuntimeError):
    """memory-graph was unreachable, timed out, or returned an unexpected payload."""


class LLMDisabledError(RuntimeError):
    """No usable LLM configuration exists; callers should use the template path."""


class LLMUnavailableError(RuntimeError):
    """A configured LLM endpoint failed; callers should degrade explicitly."""


class PersonaUnavailableError(RuntimeError):
    """persona-state was unreachable, timed out, or returned an unexpected payload."""


class PersonaRejectedError(RuntimeError):
    """persona-state rejected a bounded write (conflict, drift, or validation)."""

    def __init__(self, message: str, *, code: str = "PERSONA_STATE_REJECTED") -> None:
        super().__init__(message)
        self.code = code
