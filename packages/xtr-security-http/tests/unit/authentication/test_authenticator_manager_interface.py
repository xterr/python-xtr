"""The authenticator-manager interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security_core.authentication.token.storage.token_storage import TokenStorage

from tests.support.dispatchers import RecordingDispatcher
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authentication.authenticator_manager_interface import (
    AuthenticatorManagerInterface,
)


def test_the_manager_satisfies_the_interface() -> None:
    manager = AuthenticatorManager([], TokenStorage(), RecordingDispatcher(), "api")

    assert isinstance(manager, AuthenticatorManagerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthenticatorManagerInterface)
