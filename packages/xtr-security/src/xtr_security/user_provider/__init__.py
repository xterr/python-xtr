"""User-provider factories: building the provider a firewall loads users through.

A :class:`UserProviderFactoryInterface` turns a user-provider configuration into
the service a firewall loads users from; the built-ins are an in-memory provider,
a chain of providers, and one a container supplies. A third-party bundle
registers its own through :func:`add_user_provider_factory`.
"""

from __future__ import annotations

from .chain_factory import ChainUserProviderFactory
from .in_memory_factory import InMemoryUserProviderFactory
from .service_factory import ServiceUserProviderFactory
from .user_provider_factory_interface import UserProviderFactoryInterface

__all__ = [
    "ChainUserProviderFactory",
    "InMemoryUserProviderFactory",
    "ServiceUserProviderFactory",
    "UserProviderFactoryInterface",
]
