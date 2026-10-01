"""The wiring helpers register the security services they own, and no more.

A genuine unit test of the ``register_voters`` and ``register_hashers`` helpers:
each is driven against a recording configurator that captures every ``set`` and
``alias``, so the surface each helper contributes is asserted directly — the
voters are tagged, the hasher factory and user hasher are aliased, and neither
helper registers the role hierarchy the bundle owns. The end-to-end wiring is
driven by the integration suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_password_hasher import PasswordHasherFactoryInterface, UserPasswordHasherInterface
from xtr_security_core import RoleHierarchyInterface

from xtr_security.bundle import SecurityConfig
from xtr_security.bundle._wiring import (
    VOTER_TAG,
    register_hashers,
    register_voters,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable

    from xtr_dependency_injection import ServiceConfigurator


@final
class _RecordingDefinition:
    """A stand-in definition recording the tags a helper adds to a service."""

    def __init__(self, tags: list[str]) -> None:
        self._tags: list[str] = tags

    def add_tag(self, name: str, **attributes: object) -> _RecordingDefinition:
        del attributes
        self._tags.append(name)
        return self


@final
class _RecordingConfigurator:
    """A configurator recording every ``set`` target and ``alias`` a helper makes."""

    def __init__(self) -> None:
        self.set_targets: list[object] = []
        self.aliases: list[type] = []
        self.tags: list[str] = []

    def set(
        self,
        target: type | Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> _RecordingDefinition:
        del qualifier, lifetime
        self.set_targets.append(target)
        return _RecordingDefinition(self.tags)

    def alias(
        self,
        alias: type,
        target: type,
        /,
        *,
        alias_qualifier: Hashable | None = None,
        target_qualifier: Hashable | None = None,
    ) -> None:
        del target, alias_qualifier, target_qualifier
        self.aliases.append(alias)


def test_the_voter_tag_is_named() -> None:
    assert VOTER_TAG == "security.voter"


def test_register_voters_tags_every_built_in_voter() -> None:
    services = _RecordingConfigurator()

    register_voters(cast("ServiceConfigurator", cast("object", services)))

    assert services.tags == [VOTER_TAG, VOTER_TAG, VOTER_TAG, VOTER_TAG]


def test_register_hashers_aliases_the_factory_and_the_user_hasher() -> None:
    services = _RecordingConfigurator()

    register_hashers(cast("ServiceConfigurator", cast("object", services)), SecurityConfig())

    assert PasswordHasherFactoryInterface in services.aliases
    assert UserPasswordHasherInterface in services.aliases


def test_the_role_hierarchy_is_not_registered_by_the_helpers() -> None:
    services = _RecordingConfigurator()

    register_voters(cast("ServiceConfigurator", cast("object", services)))
    register_hashers(cast("ServiceConfigurator", cast("object", services)), SecurityConfig())

    assert RoleHierarchyInterface not in services.aliases
    assert RoleHierarchyInterface not in services.set_targets
