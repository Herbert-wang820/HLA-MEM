"""OpenAI-compatible chat completion adapter."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from hla_orchestrator.application.errors import LLMDisabledError, LLMUnavailableError
from hla_orchestrator.domain.models import Generation, MemoryHit
from hla_orchestrator.infrastructure.llm_config import LLMConfigStore


class OpenAICompatibleCompleter:
    def __init__(self, store: LLMConfigStore, *, timeout: float = 20.0) -> None:
        self._store = store
        self._timeout = timeout

    async def complete(
        self,
        *,
        message: str,
        memories: Sequence[MemoryHit],
        persona: str,
    ) -> Generation:
        config = await self._store.get()
        if not config.enabled:
            raise LLMDisabledError("LLM is disabled in admin settings")
        if not config.api_key:
            raise LLMDisabledError("LLM API key is not configured")

        context_lines = [f"- {memory.excerpt}" for memory in memories if memory.excerpt]
        system = persona
        if context_lines:
            system += "\n\n以下是可能相关的长期记忆，仅在确实相关时使用：\n" + "\n".join(context_lines)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{config.base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": message},
                        ],
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                    },
                )
                response.raise_for_status()
                body = response.json()
            text = body["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise LLMUnavailableError("empty completion")
            return Generation(text=text.strip())
        except LLMUnavailableError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMUnavailableError("LLM request failed") from exc
