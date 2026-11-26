"""File-backed LLM configuration shared with the admin console.

The API key is written with mode 0600 and never returned by the API.  The file
is intentionally simple JSON so a single-process demo can persist settings
without a database; production should move this to a secret manager.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMConfig:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 512
    updated_at: datetime | None = None


class LLMConfigStore:
    def __init__(self, path: Path | None, default: LLMConfig) -> None:
        self._path = path
        self._config = self._load(default)
        self._lock = asyncio.Lock()

    async def get(self) -> LLMConfig:
        async with self._lock:
            return self._config

    async def update(
        self,
        *,
        enabled: bool,
        base_url: str,
        model: str,
        api_key: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMConfig:
        async with self._lock:
            key = self._config.api_key if api_key is None else api_key
            config = LLMConfig(
                enabled=enabled,
                base_url=base_url.strip(),
                model=model.strip(),
                api_key=key.strip(),
                temperature=temperature,
                max_tokens=max_tokens,
                updated_at=datetime.now(UTC),
            )
            self._persist(config)
            self._config = config
            return config

    def _load(self, default: LLMConfig) -> LLMConfig:
        if self._path is None or not self._path.is_file():
            return default
        try:
            raw: Any = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return default
            return LLMConfig(
                enabled=bool(raw.get("enabled", default.enabled)),
                base_url=str(raw.get("baseUrl", default.base_url)),
                model=str(raw.get("model", default.model)),
                api_key=str(raw.get("apiKey", default.api_key)),
                temperature=float(raw.get("temperature", default.temperature)),
                max_tokens=int(raw.get("maxTokens", default.max_tokens)),
                updated_at=datetime.fromisoformat(raw["updatedAt"]) if raw.get("updatedAt") else None,
            )
        except (OSError, ValueError, TypeError):
            return default

    def _persist(self, config: LLMConfig) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "enabled": config.enabled,
            "baseUrl": config.base_url,
            "model": config.model,
            "apiKey": config.api_key,
            "temperature": config.temperature,
            "maxTokens": config.max_tokens,
            "updatedAt": (config.updated_at or datetime.now(UTC)).isoformat(),
        }
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self._path)
        os.chmod(self._path, 0o600)
