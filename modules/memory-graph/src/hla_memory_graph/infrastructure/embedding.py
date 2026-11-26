"""Deterministic embedding adapter for development and tests.

This is **not** BGE-M3 and has no semantic quality claim: it hashes tokens and
CJK bigrams into a fixed-size vector so the retrieval pipeline can be exercised
without model weights.  Production must replace it via configuration.
"""

from __future__ import annotations

import hashlib
import math
import re

_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class HashingEmbedder:
    def __init__(self, dimension: int = 256) -> None:
        if dimension < 16:
            raise ValueError("embedding dimension must be at least 16")
        self.dimension = dimension

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    cjk = _CJK_RE.findall(lowered)
    bigrams = [left + right for left, right in zip(cjk, cjk[1:], strict=False)]
    return words + cjk + bigrams
