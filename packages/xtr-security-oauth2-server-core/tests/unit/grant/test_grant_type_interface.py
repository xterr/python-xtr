"""The contract the authorization server runs every flow through."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, final

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.grants import Storage
from tests.support.signing import make_clock
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server_core.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server_core.grant.device_code_grant import DeviceCodeGrant
from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface
from xtr_security_oauth2_server_core.grant.implicit_grant import ImplicitGrant
from xtr_security_oauth2_server_core.grant.password_grant import PasswordGrant
from xtr_security_oauth2_server_core.grant.refresh_token_grant import RefreshTokenGrant

if TYPE_CHECKING:
    from collections.abc import Sequence

_TEN_MINUTES = timedelta(minutes=10)


@final
class _OnlyNamesItself:
    """Something that knows what it is called and can do nothing else."""

    def get_identifier(self) -> str:
        return "nothing"


def _shipped_grants() -> Sequence[GrantTypeInterface]:
    dispatcher = RecordingEventDispatcher()
    clock = make_clock()
    storage = Storage()

    return (
        AuthCodeGrant(dispatcher, clock, storage.auth_codes, storage.refresh_tokens, _TEN_MINUTES),
        ClientCredentialsGrant(dispatcher, clock),
        DeviceCodeGrant(
            dispatcher,
            clock,
            storage.device_codes,
            storage.refresh_tokens,
            _TEN_MINUTES,
            "https://example.com/device",
        ),
        ImplicitGrant(dispatcher, clock, _TEN_MINUTES),
        PasswordGrant(dispatcher, clock, storage.users, storage.refresh_tokens),
        RefreshTokenGrant(dispatcher, clock, storage.refresh_tokens),
    )


def _name_of(grant: GrantTypeInterface) -> str:
    return type(grant).__name__


@pytest.mark.parametrize("grant", _shipped_grants(), ids=_name_of)
def test_every_shipped_grant_satisfies_the_contract(grant: GrantTypeInterface) -> None:
    assert isinstance(grant, GrantTypeInterface)


def test_the_shipped_grants_are_each_asked_for_by_a_name_of_their_own() -> None:
    identifiers = [grant.get_identifier() for grant in _shipped_grants()]

    assert len(set(identifiers)) == len(identifiers)


def test_something_missing_the_rest_of_the_contract_does_not_satisfy_it() -> None:
    assert not isinstance(_OnlyNamesItself(), GrantTypeInterface)
