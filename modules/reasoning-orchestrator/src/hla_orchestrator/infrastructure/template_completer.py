"""Deterministic demo composer.  It is explicitly not a language model."""

from __future__ import annotations

from collections.abc import Sequence

from hla_orchestrator.domain.models import Generation, MemoryHit

LABEL = "（演示模式：未接入大模型）"


class TemplateCompleter:
    async def complete(
        self,
        *,
        message: str,
        memories: Sequence[MemoryHit],
        persona: str,
    ) -> Generation:
        if memories:
            lines = [LABEL, "我记得你提到过："]
            for index, memory in enumerate(memories, start=1):
                excerpt = (memory.excerpt or memory.episode_id).strip().replace("\n", " ")
                if len(excerpt) > 160:
                    excerpt = excerpt[:160] + "…"
                lines.append(f"{index}. {excerpt}")
            lines.append("")
            lines.append(f"你刚才问的是「{message}」。我会把这些记忆保留下来，下一轮仍可引用；如果记错了，请直接纠正我。")
            return Generation(text="\n".join(lines))
        return Generation(
            text=(
                f"{LABEL}\n"
                f"我还没有找到相关记忆。你刚才说：「{message}」。\n"
                "这条对话会被写入记忆，下一轮再问我时我应该能想起来。"
            )
        )
