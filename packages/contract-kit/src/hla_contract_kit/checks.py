"""Semantic contract checks for HLA-MEM modules and the repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from hla_contract_kit.manifest import Manifest, ManifestError, load_manifest
from hla_contract_kit.naming import HOST_CAPABILITIES, is_capability, is_permission
from hla_contract_kit.openapi import HEALTH_PATHS, iter_operations, load_openapi
from hla_contract_kit.schema import load_json, load_yaml, validate_instance

EXPECTED_MODULES = frozenset(
    {
        "reasoning-orchestrator",
        "memory-graph",
        "persona-state",
        "async-consolidator",
        "conversation-web",
        "admin-web",
    }
)

REQUIRED_DOCS = ("AGENTS.md", "DESIGN.md", "README.md")


@dataclass(slots=True)
class ModuleCheck:
    module_id: str
    module_dir: Path
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def add(self, message: str) -> None:
        self.issues.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(slots=True)
class RepoIndex:
    capabilities: dict[str, str] = field(default_factory=dict)
    events: dict[str, str] = field(default_factory=dict)
    permissions: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RepoCheck:
    root: Path
    modules: list[ModuleCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues and all(module.ok for module in self.modules)

    @property
    def all_issues(self) -> list[str]:
        lines = [f"[{module.module_id}] {issue}" for module in self.modules for issue in module.issues]
        lines.extend(f"[repo] {issue}" for issue in self.issues)
        return lines

    def summary(self) -> str:
        capabilities = sum(module.stats.get("capabilities", 0) for module in self.modules)
        events = sum(module.stats.get("events", 0) for module in self.modules)
        permissions = sum(module.stats.get("permissions", 0) for module in self.modules)
        issues = len(self.all_issues)
        warnings = sum(len(module.warnings) for module in self.modules) + len(self.warnings)
        return (
            f"{len(self.modules)} modules, {capabilities} capabilities, {events} events, "
            f"{permissions} permissions; {issues} issue(s), {warnings} warning(s)"
        )


def _load_contract_yaml(path: Path, schema_name: str, check: ModuleCheck, label: str) -> dict[str, Any] | None:
    try:
        data = load_yaml(path)
    except ValueError as exc:
        check.add(f"{label}: {exc}")
        return None
    if not isinstance(data, dict):
        check.add(f"{label}: top-level value must be a mapping")
        return None
    for issue in validate_instance(data, schema_name):
        check.add(f"{label}: {issue}")
    return data


def _load_event_schema(path: Path, check: ModuleCheck) -> dict[str, Any] | None:
    try:
        data = load_json(path)
    except ValueError as exc:
        check.add(f"{path.name}: {exc}")
        return None
    if not isinstance(data, dict):
        check.add(f"{path.name}: top-level value must be a mapping")
        return None
    try:
        Draft202012Validator.check_schema(data)
    except SchemaError as exc:
        check.add(f"{path.name}: invalid JSON Schema: {exc.message}")
        return None
    return data


def _check_event_schemas(events_dir: Path, provided: set[str], check: ModuleCheck) -> set[str]:
    seen: set[str] = set()
    for path in sorted(events_dir.glob("*.schema.json")):
        data = _load_event_schema(path, check)
        if data is None:
            continue
        properties = data.get("properties")
        if not isinstance(properties, dict):
            check.add(f"{path.name}: missing properties")
            continue
        type_property = properties.get("type")
        type_const = type_property.get("const") if isinstance(type_property, dict) else None
        expected = path.name.removesuffix(".schema.json")
        if type_const != expected:
            check.add(f"{path.name}: properties.type.const must be {expected!r}, found {type_const!r}")
        if not isinstance(type_const, str):
            continue
        if type_const not in provided:
            check.add(f"{path.name}: event type {type_const} is not declared in module.yaml provides.events")
        if type_const in seen:
            check.add(f"{path.name}: duplicate event schema for {type_const}")
        seen.add(type_const)

        required = data.get("required", [])
        if not isinstance(required, list) or "type" not in required or "data" not in required:
            check.add(f"{path.name}: schema must require both 'type' and 'data'")
        data_schema = properties.get("data")
        if not isinstance(data_schema, dict):
            check.add(f"{path.name}: missing properties.data schema")
        elif "$ref" in data_schema:
            ref = data_schema["$ref"]
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                def_name = ref.split("/")[-1]
                if def_name not in data.get("$defs", {}):
                    check.add(f"{path.name}: unresolved $ref {ref}")
        elif data_schema.get("type") != "object":
            check.add(f"{path.name}: properties.data must be an object schema or $ref")
    missing = provided - seen
    for event_type in sorted(missing):
        check.add(f"contracts/events/{event_type}.schema.json is missing")
    return seen


def _check_permissions(path: Path, manifest: Manifest, check: ModuleCheck) -> set[str]:
    data = _load_contract_yaml(path, "permissions.schema.json", check, path.name)
    if data is None:
        return set()
    if data.get("module") != manifest.module_id:
        check.add(f"{path.name}: module must be {manifest.module_id!r}, found {data.get('module')!r}")
    permissions: set[str] = set()
    raw_permissions = data.get("permissions")
    if not isinstance(raw_permissions, list):
        return permissions
    for entry in raw_permissions:
        if not isinstance(entry, dict):
            continue
        permission_id = entry.get("id")
        if not isinstance(permission_id, str) or not is_permission(permission_id):
            check.add(f"{path.name}: invalid permission id {permission_id!r}")
            continue
        if not permission_id.startswith(f"{manifest.module_id}."):
            check.add(f"{path.name}: permission {permission_id} must start with {manifest.module_id}.")
        if permission_id in permissions:
            check.add(f"{path.name}: duplicate permission {permission_id}")
        permissions.add(permission_id)
        kind = entry.get("kind")
        is_admin = ".admin." in permission_id
        if kind == "admin" and not is_admin:
            check.warn(f"{path.name}: {permission_id} has kind=admin but no .admin. segment")
        if kind != "admin" and is_admin:
            check.warn(f"{path.name}: {permission_id} looks administrative but kind={kind!r}")
    if not permissions:
        check.add(f"{path.name}: permissions list must not be empty")
    return permissions


def _check_menu(
    path: Path,
    manifest: Manifest,
    permissions: set[str],
    index: RepoIndex | None,
    check: ModuleCheck,
) -> None:
    data = _load_contract_yaml(path, "menu.schema.json", check, path.name)
    if data is None:
        return
    if data.get("module") != manifest.module_id:
        check.add(f"{path.name}: module must be {manifest.module_id!r}, found {data.get('module')!r}")
    menus = data.get("menus")
    if not isinstance(menus, list):
        return
    web_base = manifest.entrypoints.get("webBasePath", "")
    seen: set[str] = set()

    def walk(items: list[Any]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            menu_id = item.get("id")
            if isinstance(menu_id, str):
                if menu_id in seen:
                    check.add(f"{path.name}: duplicate menu id {menu_id}")
                seen.add(menu_id)
            route = item.get("route")
            if isinstance(route, str) and web_base and not route.startswith(web_base):
                check.add(f"{path.name}: menu route {route} must start with webBasePath {web_base}")
            permission = item.get("permission")
            if permission is not None:
                if not isinstance(permission, str) or not is_permission(permission):
                    check.add(f"{path.name}: menu {menu_id} has invalid permission {permission!r}")
                elif permission not in permissions:
                    check.add(f"{path.name}: menu {menu_id} permission {permission} is not declared in permissions.yaml")
            capability = item.get("requiredCapability")
            if capability is not None:
                if not isinstance(capability, str) or not is_capability(capability):
                    check.add(f"{path.name}: menu {menu_id} has invalid requiredCapability {capability!r}")
                elif index is not None and capability not in index.capabilities and capability not in HOST_CAPABILITIES:
                    check.add(f"{path.name}: menu {menu_id} requiredCapability {capability} is not provided by any module")
            children = item.get("children")
            if isinstance(children, list):
                walk(children)

    walk(menus)
    if not seen:
        check.add(f"{path.name}: menus must not be empty")


def _check_openapi(
    path: Path,
    manifest: Manifest,
    permissions: set[str],
    check: ModuleCheck,
) -> tuple[set[str], dict[str, Any] | None]:
    try:
        spec = load_openapi(path)
    except ValueError as exc:
        check.add(f"{path.name}: {exc}")
        return set(), None
    if not str(spec.get("openapi", "")).startswith("3."):
        check.add(f"{path.name}: openapi must be 3.x")
    info = spec.get("info")
    if not isinstance(info, dict):
        check.add(f"{path.name}: missing info")
    else:
        if not info.get("title"):
            check.add(f"{path.name}: info.title is required")
        if info.get("version") != manifest.version:
            check.add(f"{path.name}: info.version {info.get('version')!r} must match module version {manifest.version!r}")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        check.add(f"{path.name}: paths must be a non-empty object")
        return set(), spec
    for health_path in HEALTH_PATHS:
        if health_path not in paths:
            check.add(f"{path.name}: missing operational endpoint {health_path}")

    provided = set(manifest.capabilities)
    api_base = manifest.entrypoints.get("apiBasePath", "")
    used_capabilities: set[str] = set()
    operation_ids: set[str] = set()

    for path_name, path_item in paths.items():
        if not isinstance(path_item, dict):
            check.add(f"{path.name}: path {path_name} must be an object")
            continue
        if "$ref" in path_item:
            check.add(f"{path.name}: path {path_name} uses $ref path items, which this checker does not resolve")
            continue
        for operation in iter_operations({ "paths": {path_name: path_item } }):
            if operation.operation_id:
                if operation.operation_id in operation_ids:
                    check.add(f"{path.name}: duplicate operationId {operation.operation_id}")
                operation_ids.add(operation.operation_id)
            if path_name in HEALTH_PATHS:
                continue
            if (
                not path_name.startswith("/internal/")
                and api_base
                and not path_name.startswith(f"{api_base}/")
                and path_name != api_base
            ):
                check.add(f"{path.name}: business path {path_name} must start with {api_base}/")
            if not operation.capability:
                check.add(f"{path.name}: {operation.method} {path_name} is missing x-capability")
            elif operation.capability not in provided:
                check.add(
                    f"{path.name}: {operation.method} {path_name} declares x-capability "
                    f"{operation.capability!r} not listed in provides.capabilities"
                )
            else:
                used_capabilities.add(operation.capability)
            if not operation.permission:
                check.add(f"{path.name}: {operation.method} {path_name} is missing x-permission")
            elif operation.permission not in permissions:
                check.add(
                    f"{path.name}: {operation.method} {path_name} declares x-permission "
                    f"{operation.permission!r} not listed in permissions.yaml"
                )
            responses = operation.raw.get("responses")
            if not isinstance(responses, dict) or not responses:
                check.add(f"{path.name}: {operation.method} {path_name} must declare responses")

    for capability in sorted(provided - used_capabilities):
        check.add(f"{path.name}: capability {capability} has no operation declaring x-capability")
    return used_capabilities, spec


def _check_tests_and_web(module_dir: Path, manifest: Manifest, check: ModuleCheck) -> None:
    if manifest.kind == "backend":
        tests_dir = module_dir / "tests"
        if not tests_dir.is_dir():
            check.add("tests/ directory is required for backend modules")
        elif not any(tests_dir.rglob("test_*.py")):
            check.add("tests/ must contain at least one test_*.py")
        if not (module_dir / "pyproject.toml").is_file():
            check.add("pyproject.toml is required for backend modules")
    else:
        web_dir = module_dir / "web"
        package_json = web_dir / "package.json"
        if not package_json.is_file():
            check.add("web/package.json is required for frontend modules")
            return
        try:
            data = load_json(package_json)
        except ValueError as exc:
            check.add(str(exc))
            return
        scripts = data.get("scripts") if isinstance(data, dict) else None
        if not isinstance(scripts, dict):
            check.add("web/package.json must declare scripts")
            return
        for script in ("build", "test"):
            if script not in scripts:
                check.add(f"web/package.json must declare a {script!r} script")


def _check_dependencies(manifest: Manifest, index: RepoIndex | None, check: ModuleCheck) -> None:
    for capability in manifest.mandatory:
        if capability not in HOST_CAPABILITIES:
            check.add(f"requires.mandatory may only contain host capabilities, found {capability!r}")
    for capability in ("host.auth.identity.v1", "host.config.v1"):
        if capability not in manifest.mandatory:
            check.warn(f"requires.mandatory does not include {capability}")
    if manifest.events and "host.event.bus.v1" not in manifest.mandatory:
        check.warn("module publishes events but requires.mandatory does not include host.event.bus.v1")
    for capability in manifest.optional:
        if capability in manifest.capabilities:
            check.add(f"optional dependency {capability} is provided by the module itself")
        if index is not None and capability not in index.capabilities and capability not in HOST_CAPABILITIES:
            check.add(f"optional dependency {capability} is not provided by any module in the repository")


def check_module(
    module_dir: Path,
    repo_root: Path | None = None,
    index: RepoIndex | None = None,
    manifest: Manifest | None = None,
) -> ModuleCheck:
    module_dir = module_dir.resolve()
    if manifest is None:
        try:
            manifest = load_manifest(module_dir)
        except ManifestError as exc:
            return ModuleCheck(module_id=module_dir.name, module_dir=module_dir, issues=[str(exc)])
    check = ModuleCheck(module_id=manifest.module_id, module_dir=module_dir)
    if manifest.module_dir.resolve() != module_dir:
        check.warn(f"manifest path {manifest.module_dir} differs from checked directory {module_dir}")
    if manifest.module_id != module_dir.name:
        check.add(f"metadata.id {manifest.module_id!r} must equal directory name {module_dir.name!r}")

    for doc in REQUIRED_DOCS:
        if not (module_dir / doc).is_file():
            check.add(f"{doc} is required")

    contracts = manifest.contracts
    resolved: dict[str, Path] = {}
    for key, relative in contracts.items():
        candidate = (module_dir / relative).resolve()
        if not candidate.is_relative_to(module_dir):
            check.add(f"contracts.{key} path escapes the module directory: {relative!r}")
            continue
        if not candidate.exists():
            check.add(f"contracts.{key} path does not exist: {relative!r}")
            continue
        resolved[key] = candidate

    entrypoints = manifest.entrypoints
    if manifest.kind == "backend":
        if "apiBasePath" not in entrypoints:
            check.add("backend module must declare entrypoints.apiBasePath")
        if "openapi" not in contracts:
            check.add("backend module must declare contracts.openapi")
        if "menu" in contracts:
            check.warn("backend module declares contracts.menu; menus are normally frontend-only")
    else:
        if "webBasePath" not in entrypoints:
            check.add("frontend module must declare entrypoints.webBasePath")
        if "menu" not in contracts:
            check.add("frontend module must declare contracts.menu")
        if "openapi" in contracts:
            check.warn("frontend module declares contracts.openapi; keep it only if it has a real HTTP API")

    api_base = entrypoints.get("apiBasePath")
    if api_base:
        expected_prefix = f"/api/{manifest.module_id}/"
        if not api_base.startswith(expected_prefix):
            check.add(f"entrypoints.apiBasePath {api_base!r} must start with {expected_prefix}")

    permissions: set[str] = set()
    permissions_path = resolved.get("permissions")
    if permissions_path is not None:
        if not permissions_path.is_file():
            check.add("contracts.permissions must point to a file")
        else:
            permissions = _check_permissions(permissions_path, manifest, check)
    check.stats["permissions"] = len(permissions)

    events_path = resolved.get("events")
    if manifest.events:
        if events_path is None:
            check.add("module provides events but contracts.events is not declared")
        elif not events_path.is_dir():
            check.add("contracts.events must point to a directory")
        else:
            _check_event_schemas(events_path, set(manifest.events), check)
    elif events_path is not None and events_path.is_dir() and any(events_path.glob("*.schema.json")):
        check.warn("contracts.events contains schemas but provides.events is empty")
    check.stats["capabilities"] = len(manifest.capabilities)
    check.stats["events"] = len(manifest.events)

    openapi_path = resolved.get("openapi")
    if openapi_path is not None:
        if not openapi_path.is_file():
            check.add("contracts.openapi must point to a file")
        else:
            _check_openapi(openapi_path, manifest, permissions, check)

    menu_path = resolved.get("menu")
    if menu_path is not None:
        if not menu_path.is_file():
            check.add("contracts.menu must point to a file")
        else:
            _check_menu(menu_path, manifest, permissions, index, check)

    _check_dependencies(manifest, index, check)
    _check_tests_and_web(module_dir, manifest, check)
    return check


def build_index(manifests: list[Manifest]) -> tuple[RepoIndex, list[str]]:
    index = RepoIndex()
    issues: list[str] = []

    def insert(mapping: dict[str, str], key: str, module_id: str, label: str) -> None:
        previous = mapping.get(key)
        if previous is not None:
            issues.append(f"duplicate {label} {key!r} provided by {previous!r} and {module_id!r}")
        else:
            mapping[key] = module_id

    for manifest in manifests:
        for capability in manifest.capabilities:
            insert(index.capabilities, capability, manifest.module_id, "capability")
        for event_type in manifest.events:
            insert(index.events, event_type, manifest.module_id, "event type")
        permission_file = manifest.module_dir / manifest.contracts.get("permissions", "")
        if not permission_file.is_file():
            continue
        try:
            data = load_yaml(permission_file)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        for entry in data.get("permissions", []):
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                insert(index.permissions, entry["id"], manifest.module_id, "permission")
    return index, issues


def check_repo(root: Path) -> RepoCheck:
    root = root.resolve()
    modules_dir = root / "modules"
    if not modules_dir.is_dir():
        return RepoCheck(root=root, issues=[f"modules/ directory not found at {modules_dir}"])

    module_dirs = sorted(
        path for path in modules_dir.iterdir() if path.is_dir() and (path / "module.yaml").is_file()
    )
    manifests: list[Manifest] = []
    failures: list[ModuleCheck] = []
    for module_dir in module_dirs:
        try:
            manifests.append(load_manifest(module_dir))
        except ManifestError as exc:
            failures.append(ModuleCheck(module_id=module_dir.name, module_dir=module_dir, issues=[str(exc)]))

    index, duplicate_issues = build_index(manifests)
    results = [
        check_module(manifest.module_dir, repo_root=root, index=index, manifest=manifest) for manifest in manifests
    ]
    results.extend(failures)

    issues: list[str] = list(duplicate_issues)
    warnings: list[str] = []
    seen_ids: dict[str, Path] = {}
    for manifest in manifests:
        if manifest.module_id in seen_ids:
            issues.append(f"duplicate module id {manifest.module_id!r} in {seen_ids[manifest.module_id]} and {manifest.module_dir}")
        seen_ids[manifest.module_id] = manifest.module_dir

    present = {manifest.module_id for manifest in manifests}
    for expected in sorted(EXPECTED_MODULES - present):
        issues.append(f"expected module {expected!r} is missing from modules/")
    for extra in sorted(present - EXPECTED_MODULES):
        warnings.append(f"module {extra!r} is not part of the six-module architecture")

    for doc in ("模块开发契约.md", "HLM-MEM开发计划.md", "docs/contract-alignment.md"):
        if not (root / doc).is_file():
            warnings.append(f"expected repository document is missing: {doc}")

    results.sort(key=lambda item: item.module_id)
    return RepoCheck(root=root, modules=results, issues=issues, warnings=warnings)
