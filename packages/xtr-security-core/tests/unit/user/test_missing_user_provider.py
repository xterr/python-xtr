"""The missing-user provider refuses to exist, naming the firewall."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import BadMethodCallError, InvalidArgumentError
from xtr_security_core.user import InMemoryUser, MissingUserProvider, UserProviderInterface


def test_it_inherits_the_user_provider_interface() -> None:
    assert UserProviderInterface in MissingUserProvider.__mro__


def test_building_it_names_the_firewall_missing_a_provider() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=r'"main" firewall requires a user provider but none was defined\.',
    ):
        _ = MissingUserProvider("main")


@pytest.mark.anyio
async def test_every_method_refuses_to_run() -> None:
    provider = object.__new__(MissingUserProvider)

    with pytest.raises(BadMethodCallError):
        _ = await provider.load_user_by_identifier("alice")
    with pytest.raises(BadMethodCallError):
        _ = await provider.refresh_user(InMemoryUser("alice"))
    with pytest.raises(BadMethodCallError):
        _ = provider.supports_class(InMemoryUser)
