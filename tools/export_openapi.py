"""Export FastAPI OpenAPI documents to each module's contracts/openapi.yaml.

Usage:
    python tools/export_openapi.py --all
    python tools/export_openapi.py memory-graph
    python tools/export_openapi.py --all --check
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "reasoning-orchestrator": "hla_orchestrator",
    "memory-graph": "hla_memory_graph",
    "persona-state": "hla_persona_state",
    "async-consolidator": "hla_consolidator",
}


def render(module_id: str) -> str:
    package = MODULES[module_id]
    module = importlib.import_module(f"{package}.app")
    app = module.create_app()
    spec = app.openapi()
    return yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*", choices=sorted(MODULES), help="module ids (default: all with --all)")
    parser.add_argument("--all", action="store_true", help="export every backend module")
    parser.add_argument("--check", action="store_true", help="fail if committed OpenAPI differs from generated output")
    args = parser.parse_args(argv)

    targets = sorted(MODULES) if args.all or not args.modules else sorted(set(args.modules))
    failed = False
    for module_id in targets:
        output = ROOT / "modules" / module_id / "contracts" / "openapi.yaml"
        generated = render(module_id)
        if args.check:
            existing = output.read_text(encoding="utf-8") if output.is_file() else ""
            if existing != generated:
                failed = True
                print(f"[drift] {module_id}: {output.relative_to(ROOT)}")
                diff = difflib.unified_diff(
                    existing.splitlines(),
                    generated.splitlines(),
                    fromfile=f"{module_id}/contracts/openapi.yaml (committed)",
                    tofile=f"{module_id}/contracts/openapi.yaml (generated)",
                    lineterm="",
                )
                print("\n".join(list(diff)[:60]))
            else:
                print(f"[ok] {module_id}")
        else:
            output.write_text(generated, encoding="utf-8")
            print(f"[written] {output.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
