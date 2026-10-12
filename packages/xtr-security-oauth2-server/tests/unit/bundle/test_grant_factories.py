"""Each shipped grant, built as the deployment asked for it."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

import pytest
from xtr_clock import MockClock
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server_core.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server_core.grant.device_code_grant import DeviceCodeGrant
from xtr_security_oauth2_server_core.grant.implicit_grant import ImplicitGrant
from xtr_security_oauth2_server_core.grant.password_grant import PasswordGrant
from xtr_security_oauth2_server_core.grant.refresh_token_grant import RefreshTokenGrant
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants

from tests.support.grants import Storage
from tests.support.messages import server_request
from tests.support.signing import FROZEN_NOW
from xtr_security_oauth2_server.bundle._grant_factories import (
    auth_code_grant_factory,
    client_credentials_grant_factory,
    device_code_grant_factory,
    implicit_grant_factory,
    password_grant_factory,
    refresh_token_grant_factory,
)
from xtr_security_oauth2_server.bundle.authorization_server_config import (
    AuthorizationServerConfig,
)
from xtr_security_oauth2_server.exception import InvalidConfigurationError

pytestmark = pytest.mark.anyio

_VERIFICATION_URI: Final = "https://auth.test/device"


def _clock() -> MockClock:
    """Return the suite's frozen clock."""
    return MockClock(FROZEN_NOW)


def _dispatcher() -> object:
    """Return something a grant announces through; nothing here listens."""
    from tests.support.dispatcher import RecordingEventDispatcher  # noqa: PLC0415 -- used only here

    return RecordingEventDispatcher()


def test_the_client_credentials_grant_answers_for_its_own_name() -> None:
    grant = client_credentials_grant_factory()(_dispatcher(), _clock())

    assert isinstance(grant, ClientCredentialsGrant)
    assert grant.get_identifier() == OAuth2Grants.CLIENT_CREDENTIALS


def test_the_refresh_token_grant_is_built_with_the_configured_lifetime() -> None:
    storage = Storage()
    config = AuthorizationServerConfig(refresh_token_ttl=timedelta(days=7))

    grant = refresh_token_grant_factory(config)(
        _dispatcher(),
        _clock(),
        storage.refresh_tokens,
    )

    assert isinstance(grant, RefreshTokenGrant)
    assert grant.get_identifier() == OAuth2Grants.REFRESH_TOKEN


def test_the_password_grant_answers_for_its_own_name() -> None:
    storage = Storage()

    grant = password_grant_factory(AuthorizationServerConfig())(
        _dispatcher(),
        _clock(),
        storage.users,
        storage.refresh_tokens,
    )

    assert isinstance(grant, PasswordGrant)
    assert grant.get_identifier() == OAuth2Grants.PASSWORD


def test_the_implicit_grant_answers_for_its_own_name() -> None:
    grant = implicit_grant_factory(AuthorizationServerConfig())(_dispatcher(), _clock())

    assert isinstance(grant, ImplicitGrant)
    assert grant.get_identifier() == OAuth2Grants.IMPLICIT


def _auth_code_grant(*, require_code_challenge: bool) -> AuthCodeGrant:
    """Return the redirect-flow grant of a deployment with that proof-key rule."""
    storage = Storage()
    config = AuthorizationServerConfig(
        require_code_challenge_for_public_clients=require_code_challenge,
    )
    built = auth_code_grant_factory(config)(
        _dispatcher(),
        _clock(),
        storage.auth_codes,
        storage.refresh_tokens,
    )
    assert isinstance(built, AuthCodeGrant)

    return built


def test_a_public_client_must_commit_to_a_proof_key_by_default() -> None:
    grant = _auth_code_grant(require_code_challenge=True)

    assert grant.get_identifier() == OAuth2Grants.AUTHORIZATION_CODE
    assert grant._require_code_challenge_for_public_clients is True


def test_a_deployment_may_turn_the_proof_key_requirement_off() -> None:
    # A deployment that does so is saying its public clients cannot do a proof
    # key; every one of them is then open to an intercepted code being
    # redeemed by whoever intercepted it.
    grant = _auth_code_grant(require_code_challenge=False)

    assert grant._require_code_challenge_for_public_clients is False


def test_the_device_code_grant_needs_somewhere_to_send_a_person() -> None:
    # The answer to a device names where its owner should go, and a device puts
    # that on a screen.
    storage = Storage()
    factory = device_code_grant_factory(AuthorizationServerConfig())

    with pytest.raises(
        InvalidConfigurationError,
        match=r"device_code_verification_uri",
    ):
        _ = factory(_dispatcher(), _clock(), storage.device_codes, storage.refresh_tokens)


def test_the_device_code_grant_is_built_once_a_verification_uri_is_configured() -> None:
    storage = Storage()
    config = AuthorizationServerConfig(device_code_verification_uri=_VERIFICATION_URI)

    grant = device_code_grant_factory(config)(
        _dispatcher(),
        _clock(),
        storage.device_codes,
        storage.refresh_tokens,
    )

    assert isinstance(grant, DeviceCodeGrant)
    assert grant.get_identifier() == OAuth2Grants.DEVICE_CODE


def test_a_request_for_another_grant_is_not_claimed() -> None:
    grant = client_credentials_grant_factory()(_dispatcher(), _clock())
    asking = server_request(parsed_body={"grant_type": OAuth2Grants.REFRESH_TOKEN})

    assert grant.can_respond_to_access_token_request(asking) is False
