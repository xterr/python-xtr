"""The attributes-based provider interface refines the provider interface."""

from __future__ import annotations

from xtr_security_core.user import (
    AttributesBasedUserProviderInterface,
    ChainUserProvider,
    UserProviderInterface,
)


def test_the_chain_provider_also_satisfies_the_provider_interface() -> None:
    provider = ChainUserProvider([])

    assert isinstance(provider, AttributesBasedUserProviderInterface)
    assert isinstance(provider, UserProviderInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AttributesBasedUserProviderInterface)
