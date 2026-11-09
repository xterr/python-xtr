"""When the end-user signed in, read off the firewall's token onto the sign-in request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from xtr_security import Security
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

import xtr_security_openid_connect_server
from xtr_security_openid_connect_server.event_listener.auth_time_listener import (
    AUTH_TIME_LISTENER_PRIORITY,
    stamp_auth_time,
)
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )

pytestmark = pytest.mark.anyio

_USER: Final = InMemoryUser("alice", roles=["ROLE_USER"])
_PASSWORD_PROOF: Final = 1_772_600_000
_SECOND_FACTOR_PROOF: Final = 1_772_600_060


def _event(request: AuthorizationRequestInterface) -> AuthorizationRequestResolveEvent:
    """Return the consent event raised for ``request``, shown to the signed-in user."""
    client = Client("A client", "my-client", None)

    return AuthorizationRequestResolveEvent(request, (), client, _USER)


def _security(proofs: Mapping[str, int] | None) -> Security:
    """Return the facade over a firewall token proving ``proofs``, or over nobody for ``None``."""
    storage = TokenStorage()
    if proofs is not None:
        token = UsernamePasswordToken(_USER, "main", ["ROLE_USER"])
        token.set_authentication_proofs(proofs)
        storage.set_token(token)

    return Security(storage, _NoDecision())


async def test_the_newest_proof_is_when_the_end_user_signed_in() -> None:
    # A re-login adds a newer proof beside the older ones; the sign-in the
    # ID token reports is the latest of them.
    request = OpenIdAuthorizationRequest()
    security = _security({"password": _PASSWORD_PROOF, "otp": _SECOND_FACTOR_PROOF})

    await stamp_auth_time(_event(request), security)

    assert request.get_auth_time() == _SECOND_FACTOR_PROOF


async def test_a_token_proving_nothing_leaves_the_sign_in_time_unknown() -> None:
    # A remembered login proves no credential, so nothing says when one was shown.
    request = OpenIdAuthorizationRequest()

    await stamp_auth_time(_event(request), _security({}))

    assert request.get_auth_time() is None


async def test_nobody_signed_in_leaves_the_sign_in_time_unknown() -> None:
    request = OpenIdAuthorizationRequest()

    await stamp_auth_time(_event(request), _security(None))

    assert request.get_auth_time() is None


async def test_a_request_that_is_not_a_sign_in_is_left_alone() -> None:
    request = AuthorizationRequest()
    request.set_state("xyz")
    event = _event(request)

    await stamp_auth_time(event, _security({"password": _PASSWORD_PROOF}))

    assert event.get_authorization_request() is request
    assert request.get_state() == "xyz"


async def test_it_leaves_the_consent_decision_to_the_listeners_after_it() -> None:
    event = _event(OpenIdAuthorizationRequest())

    await stamp_auth_time(event, _security({"password": _PASSWORD_PROOF}))

    assert event.get_response() is None
    assert event.get_authorization_resolution() is AuthorizationRequestResolveEvent.DENIED
    assert event.is_propagation_stopped() is False


def test_it_runs_ahead_of_a_consent_listener_at_the_default_priority() -> None:
    assert AUTH_TIME_LISTENER_PRIORITY == 2048


def test_its_priority_is_public_from_the_package() -> None:
    assert xtr_security_openid_connect_server.AUTH_TIME_LISTENER_PRIORITY == 2048


class _NoDecision:
    """An authorization checker nothing asks."""

    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: object = None,
    ) -> bool:
        del attribute, subject, access_decision

        raise AssertionError("nothing is checked here")  # pragma: no cover
