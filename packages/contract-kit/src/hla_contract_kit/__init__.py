"""HLA-MEM contract validation toolkit."""

__version__ = "0.1.0"

from hla_contract_kit.checks import RepoCheck, check_module, check_repo
from hla_contract_kit.manifest import Manifest, ManifestError, load_manifest
from hla_contract_kit.naming import (
    CAPABILITY_PATTERN,
    EVENT_TYPE_PATTERN,
    MODULE_ID_PATTERN,
    PERMISSION_PATTERN,
    error_code,
    is_capability,
    is_event_type,
    is_permission,
    validate_capability,
    validate_event_type,
    validate_permission,
)

__all__ = [
    "CAPABILITY_PATTERN",
    "EVENT_TYPE_PATTERN",
    "MODULE_ID_PATTERN",
    "PERMISSION_PATTERN",
    "Manifest",
    "ManifestError",
    "RepoCheck",
    "check_module",
    "check_repo",
    "error_code",
    "is_capability",
    "is_event_type",
    "is_permission",
    "load_manifest",
    "validate_capability",
    "validate_event_type",
    "validate_permission",
]
