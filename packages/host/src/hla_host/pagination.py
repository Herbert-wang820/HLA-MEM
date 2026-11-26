"""Cursor and page pagination helpers.

Each module picks one style; the contract forbids mixing both within one module.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 100


class CursorPage[T](BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[T]
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(alias="hasMore")


class Page[T](BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[T]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    has_more: bool = Field(alias="hasMore")


@dataclass(frozen=True, slots=True)
class CursorParams:
    cursor: str | None
    limit: int


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    page_size: int


def cursor_params(
    cursor: Annotated[str | None, Query(max_length=512, description="Opaque cursor from a previous response.")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum items to return.")] = 20,
) -> CursorParams:
    return CursorParams(cursor=cursor, limit=limit)


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, alias="pageSize")] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


def encode_cursor(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, object]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(decoded, dict):
        raise ValueError("invalid cursor payload")
    return decoded
