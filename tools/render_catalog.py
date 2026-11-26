"""Render docs/module-catalog.md from module manifests and contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "reasoning-orchestrator",
    "memory-graph",
    "persona-state",
    "async-consolidator",
    "conversation-web",
    "admin-web",
]
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def load_yaml(path: Path):
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def capability_endpoints(module_dir: Path) -> dict[str, list[str]]:
    spec = load_yaml(module_dir / "contracts" / "openapi.yaml")
    mapping: dict[str, list[str]] = {}
    if not isinstance(spec, dict):
        return mapping
    paths = spec.get("paths") or {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method not in METHODS or not isinstance(operation, dict):
                continue
            capability = operation.get("x-capability")
            if isinstance(capability, str):
                mapping.setdefault(capability, []).append(f"`{method.upper()} {path}`")
    return mapping


def main() -> None:
    modules: list[dict] = []
    for module_id in MODULES:
        module_dir = ROOT / "modules" / module_id
        manifest = load_yaml(module_dir / "module.yaml")
        if not isinstance(manifest, dict):
            continue
        permissions = load_yaml(module_dir / "contracts" / "permissions.yaml") or {}
        menu = load_yaml(module_dir / "contracts" / "menu.yaml") or {}
        modules.append(
            {
                "id": module_id,
                "manifest": manifest,
                "permissions": permissions.get("permissions", []),
                "menu": menu.get("menus", []),
                "endpoints": capability_endpoints(module_dir),
            }
        )

    lines = [
        "# 模块目录（自动生成）",
        "",
        "> 由 `make catalog` 从各模块的 `module.yaml` 与 `contracts/` 生成，请勿手工编辑。",
        "> 生成命令：`python tools/render_catalog.py`",
        "",
        "## 1. 模块",
        "",
        "| 模块 ID | 名称 | 类型 | 版本 | 入口 | 能力数 | 事件数 |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in modules:
        manifest = item["manifest"]
        entry = manifest["entrypoints"]
        entrypoint = entry.get("apiBasePath") or entry.get("webBasePath") or "-"
        lines.append(
            f"| `{item['id']}` | {manifest['metadata']['name']} | {manifest['metadata']['kind']} | "
            f"{manifest['metadata']['version']} | `{entrypoint}` | {len(manifest['provides']['capabilities'])} | "
            f"{len(manifest['provides']['events'])} |"
        )

    lines.extend(
        [
            "",
            "## 2. 能力与端点",
            "",
            "| 模块 | 能力 | 权限 | 端点 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in modules:
        manifest = item["manifest"]
        for capability in manifest["provides"]["capabilities"]:
            endpoints = item["endpoints"].get(capability, [])
            permission = "-"
            for operation in _operations(ROOT / "modules" / item["id"] / "contracts" / "openapi.yaml"):
                if operation.get("x-capability") == capability:
                    permission = f"`{operation.get('x-permission')}`"
                    break
            lines.append(
                f"| `{item['id']}` | `{capability}` | {permission} | {', '.join(endpoints) or '-'} |"
            )

    lines.extend(
        [
            "",
            "## 3. 事件",
            "",
            "| 事件 | 提供方 | 发布时机 |",
            "| --- | --- | --- |",
        ]
    )
    event_notes = {
        "episode.written": "情景写入成功提交后",
        "episode.retracted": "追加撤回标记后",
        "coactivation.recorded": "检索形成共激活批次",
        "identity.versioned": "新身份版本提交",
        "identity.rolled-back": "身份回滚完成",
        "adaptation.updated": "适应层有界更新提交",
        "proposal.created": "身份变更提案创建",
        "proposal.reviewed": "提案审批完成",
        "experience.appended": "经历日志追加",
        "turn.processed": "回合完成（含降级完成）",
        "turn.degraded": "回合发生降级",
        "job.completed": "作业成功",
        "job.failed": "作业失败",
        "job.deadlettered": "进入死信",
        "edge.reinforced": "边权批量应用",
        "hub.distilled": "枢纽蒸馏完成",
    }
    for item in modules:
        manifest = item["manifest"]
        for event_type in manifest["provides"]["events"]:
            short = ".".join(event_type.split(".")[1:-1])
            lines.append(f"| `{event_type}` | `{item['id']}` | {event_notes.get(short, '-')} |")

    lines.extend(
        [
            "",
            "## 4. 权限",
            "",
            "| 权限 | 所属模块 | 类型 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in modules:
        for permission in item["permissions"]:
            lines.append(
                f"| `{permission['id']}` | `{item['id']}` | {permission.get('kind', '-')} | "
                f"{permission.get('description', '-')} |"
            )

    menu_rows = []
    for item in modules:
        for entry in item["menu"]:
            menu_rows.append((item["id"], entry))

    lines.extend(
        [
            "",
            "## 5. 前端菜单",
            "",
            "| 模块 | 菜单 ID | 路由 | 权限 | 所需能力 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for module_id, entry in menu_rows:
        lines.append(
            f"| `{module_id}` | `{entry['id']}` | `{entry['route']}` | `{entry.get('permission', '-')}` | "
            f"`{entry.get('requiredCapability', '-')}` |"
        )

    lines.extend(["", "## 6. 依赖", "", "| 模块 | 必选（仅宿主） | 可选集成 |", "| --- | --- | --- |"])
    for item in modules:
        manifest = item["manifest"]
        mandatory = ", ".join(f"`{cap}`" for cap in manifest["requires"]["mandatory"])
        optional = ", ".join(f"`{cap}`" for cap in manifest["requires"]["optional"]) or "-"
        lines.append(f"| `{item['id']}` | {mandatory} | {optional} |")
    lines.append("")

    output = ROOT / "docs" / "module-catalog.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[written] {output.relative_to(ROOT)}")


def _operations(path: Path):
    spec = load_yaml(path)
    if not isinstance(spec, dict):
        return
    for item in (spec.get("paths") or {}).values():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method in METHODS and isinstance(operation, dict):
                yield operation


if __name__ == "__main__":
    main()
