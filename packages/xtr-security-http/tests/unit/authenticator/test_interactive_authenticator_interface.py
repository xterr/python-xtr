"""The interactive authenticator interface is a runtime-checkable protocol."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)


@final
class _Interactive(InteractiveAuthenticatorInterface):
    @override
    def is_interactive(self) -> bool:
        return True


def test_a_conforming_authenticator_satisfies_the_interface() -> None:
    assert isinstance(_Interactive(), InteractiveAuthenticatorInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), InteractiveAuthenticatorInterface)
