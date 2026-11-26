"""Command-line entry point for contract checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hla_contract_kit.checks import ModuleCheck, check_module, check_repo
from hla_contract_kit.manifest import ManifestError, load_manifest


def _print_module(check: ModuleCheck) -> None:
    status = "OK  " if check.ok else "FAIL"
    stats = ", ".join(f"{key}={value}" for key, value in sorted(check.stats.items())) or "no stats"
    print(f"{status} {check.module_id:24s} {stats}")
    for issue in check.issues:
        print(f"       - {issue}")
    for warning in check.warnings:
        print(f"       ! {warning}")


def _cmd_check(path: Path) -> int:
    check = check_module(path)
    _print_module(check)
    return 0 if check.ok else 1


def _cmd_check_all(root: Path) -> int:
    result = check_repo(root)
    print(f"HLA-MEM contract check: {result.root}")
    for module in result.modules:
        _print_module(module)
    for issue in result.issues:
        print(f"[repo] - {issue}")
    for warning in result.warnings:
        print(f"[repo] ! {warning}")
    print(f"Summary: {result.summary()}")
    return 0 if result.ok else 1


def _cmd_list(root: Path) -> int:
    module_dirs = sorted(path.parent for path in (root / "modules").glob("*/module.yaml"))
    if not module_dirs:
        print("no modules found", file=sys.stderr)
        return 1
    print(f"{'module':24s} {'kind':8s} {'version':8s} {'caps':>4s} {'events':>6s}")
    for module_dir in module_dirs:
        try:
            manifest = load_manifest(module_dir)
        except ManifestError as exc:
            print(f"{module_dir.name:24s} INVALID  {exc}")
            continue
        print(
            f"{manifest.module_id:24s} {manifest.kind:8s} {manifest.version:8s} "
            f"{len(manifest.capabilities):4d} {len(manifest.events):6d}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hla-contract-kit", description="Validate HLA-MEM module contracts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="validate one module directory")
    check_parser.add_argument("path", nargs="?", default=".", type=Path)

    all_parser = subparsers.add_parser("check-all", help="validate every module in a repository")
    all_parser.add_argument("root", nargs="?", default=".", type=Path)

    list_parser = subparsers.add_parser("list", help="list modules and contract counts")
    list_parser.add_argument("root", nargs="?", default=".", type=Path)

    args = parser.parse_args(argv)
    if args.command == "check":
        return _cmd_check(args.path)
    if args.command == "check-all":
        return _cmd_check_all(args.root)
    if args.command == "list":
        return _cmd_list(args.root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
