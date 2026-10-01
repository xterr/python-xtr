"""The trust-resolver interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authentication import (
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
)


def test_the_resolver_satisfies_the_interface() -> None:
    assert isinstance(AuthenticationTrustResolver(), AuthenticationTrustResolverInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthenticationTrustResolverInterface)
