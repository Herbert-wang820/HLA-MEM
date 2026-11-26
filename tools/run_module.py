"""Run one backend module with uvicorn, e.g. python tools/run_module.py memory-graph."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGES = {
    "reasoning-orchestrator": "hla_orchestrator",
    "memory-graph": "hla_memory_graph",
    "persona-state": "hla_persona_state",
    "async-consolidator": "hla_consolidator",
}

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in PACKAGES:
        print(f"usage: python tools/run_module.py {{{'|'.join(sorted(PACKAGES))}}}", file=sys.stderr)
        return 2
    package = PACKAGES[argv[0]]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "modules" / argv[0] / "src") + os.pathsep + env.get("PYTHONPATH", "")
    os.execvpe(sys.executable, [sys.executable, "-m", package], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
