"""Users and the providers and checkers around them.

The password-carrying user contract is re-exported here too, alongside the
password-upgrading one this package owns, so an application imports every user
contract from one place.
"""

from __future__ import annotations

from xtr_password_hasher import PasswordAuthenticatedUserInterface

from .attributes_based_user_provider_interface import AttributesBasedUserProviderInterface
from .chain_user_checker import ChainUserChecker
from .chain_user_provider import ChainUserProvider
from .equatable_interface import EquatableInterface
from .in_memory_user import InMemoryUser
from .in_memory_user_checker import InMemoryUserChecker
from .in_memory_user_provider import InMemoryUserProvider
from .oidc_user import OidcUser
from .password_upgrader_interface import PasswordUpgraderInterface
from .user_checker_interface import UserCheckerInterface
from .user_interface import UserInterface
from .user_provider_interface import UserProviderInterface

__all__ = [
    "AttributesBasedUserProviderInterface",
    "ChainUserChecker",
    "ChainUserProvider",
    "EquatableInterface",
    "InMemoryUser",
    "InMemoryUserChecker",
    "InMemoryUserProvider",
    "OidcUser",
    "PasswordAuthenticatedUserInterface",
    "PasswordUpgraderInterface",
    "UserCheckerInterface",
    "UserInterface",
    "UserProviderInterface",
]
