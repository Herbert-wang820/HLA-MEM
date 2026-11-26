"""HLA-MEM host capability adapters.

These are *local* adapters for development and tests. Production deployments must
inject implementations of the host capabilities declared in each module.yaml:
host.auth.identity.v1, host.config.v1 and host.event.bus.v1.
"""

__version__ = "0.1.0"

from hla_host.app import create_module_app
from hla_host.auth import IdentityProvider, StaticIdentityProvider, require_identity, require_permission
from hla_host.config import ConfigField, HostSettings, ModuleConfig
from hla_host.context import Identity
from hla_host.errors import ErrorResponse, ModuleError
from hla_host.events import DomainEvent, InMemoryEventBus, new_event

__all__ = [
    "ConfigField",
    "DomainEvent",
    "ErrorResponse",
    "HostSettings",
    "Identity",
    "IdentityProvider",
    "InMemoryEventBus",
    "ModuleConfig",
    "ModuleError",
    "StaticIdentityProvider",
    "create_module_app",
    "new_event",
    "require_identity",
    "require_permission",
]
