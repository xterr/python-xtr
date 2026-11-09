"""The bundle puts the provider in place of the shipped flow, and refuses to be undone."""

from __future__ import annotations

from datetime import timedelta
from typing import TypeVar

import pytest
from xtr_dependency_injection import unit_of_work
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_event_dispatcher_contracts import EventDispatcherInterface, ListenerIntrospectionInterface
from xtr_security_oauth2_server.bundle import OAuth2ServerConfig
from xtr_security_oauth2_server.exception import (
    InvalidConfigurationError as OAuth2InvalidConfigurationError,
)
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server_core.response_types.response_type_interface import (
    ResponseTypeInterface,
)

from tests.fixtures.openid_app.config import (
    ALGORITHM,
    AUTH_CODE_BACK_ON_ENV,
    BEARER_ANSWER_ENV,
    ED448_ENV,
    ED25519_ENV,
    ID_TOKEN_TTL,
    IDENTITY_PROVIDER_ENV,
    NO_METADATA_ENV,
    NO_SCOPES_ENV,
    SCOPED_IDENTITY_PROVIDER_ENV,
    SHORT_ID_TOKEN_ENV,
)
from tests.fixtures.openid_app.services import ScopedIdentityProvider
from tests.support.identity_provider import InMemoryIdentityProvider
from tests.support.served import openid_kernel
from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.event_listener import AUTH_TIME_LISTENER_PRIORITY
from xtr_security_openid_connect_server.exception import InvalidConfigurationError
from xtr_security_openid_connect_server.id_token_settings import IdTokenSettings
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,
)
from xtr_security_openid_connect_server.response_types.id_token_response import IdTokenResponse

pytestmark = pytest.mark.anyio

T = TypeVar("T")


async def _resolved(service: type[T], env: str = "test") -> T:
    """Return ``service`` as the deployment served in ``env`` builds it."""
    async with await openid_kernel(env).boot() as booted:
        return await booted.container.get(service)


async def test_the_openid_scope_is_added_to_the_scopes_the_deployment_named() -> None:
    config = await _resolved(OAuth2ServerConfig)

    assert config.scopes.available == ("read", "openid")


async def test_a_deployment_naming_no_scope_is_left_naming_none() -> None:
    config = await _resolved(OAuth2ServerConfig, NO_SCOPES_ENV)

    assert config.scopes.available == ()


async def test_a_deployment_naming_no_scope_still_hears_the_servers_refusal() -> None:
    async with await openid_kernel(NO_SCOPES_ENV).boot() as booted:
        with pytest.raises(ServiceResolutionError) as reported:
            _ = await booted.container.get(ScopeManagerInterface)

    assert isinstance(reported.value.__cause__, OAuth2InvalidConfigurationError)
    assert "scopes.available" in str(reported.value.__cause__)


async def test_the_shipped_redirect_flow_is_turned_off() -> None:
    config = await _resolved(OAuth2ServerConfig)

    assert config.authorization_server.enable_auth_code_grant is False


async def test_the_sign_in_time_is_recorded_ahead_of_the_deployments_consent_listener() -> None:
    # The build refuses a listener service that is not a singleton; the one
    # reading the request's facade is a function, so the kernel builds.
    dispatcher = await _resolved(EventDispatcherInterface)
    assert isinstance(dispatcher, ListenerIntrospectionInterface)

    event = OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE
    priorities = [
        dispatcher.get_listener_priority(event, listener)
        for listener in dispatcher.get_listeners(event)
    ]

    # The fixture's consent listener runs at the default priority, after it.
    assert priorities == [AUTH_TIME_LISTENER_PRIORITY, 0]


async def test_the_token_endpoint_answers_with_an_id_token_response() -> None:
    answer = await _resolved(ResponseTypeInterface)

    assert isinstance(answer, IdTokenResponse)


async def test_id_tokens_take_the_servers_algorithm_and_its_access_token_lifetime() -> None:
    settings = await _resolved(IdTokenSettings)

    assert settings == IdTokenSettings(algorithm=ALGORITHM, ttl=None)


async def test_id_tokens_last_as_long_as_the_deployment_set() -> None:
    settings = await _resolved(IdTokenSettings, SHORT_ID_TOKEN_ENV)

    assert settings.ttl == ID_TOKEN_TTL
    assert settings.ttl == timedelta(minutes=5)


@pytest.mark.parametrize(("env", "curve"), [(ED25519_ENV, "Ed25519"), (ED448_ENV, "Ed448")])
async def test_eddsa_id_tokens_take_the_curve_of_the_servers_key(env: str, curve: str) -> None:
    settings = await _resolved(IdTokenSettings, env)

    assert settings.curve == curve


async def test_the_claim_extractor_holds_the_claim_sets_the_deployment_configured() -> None:
    extractor = await _resolved(ClaimExtractor, IDENTITY_PROVIDER_ENV)

    company = extractor.get_claim_set("company")
    assert company is not None
    assert company.get_claim_names() == ("company_id",)


async def test_the_claim_extractor_holds_only_the_protocols_sets_by_default() -> None:
    extractor = await _resolved(ClaimExtractor)

    scopes = [claim_set.get_scope() for claim_set in extractor.get_claim_sets()]
    assert scopes == ["profile", "email", "address", "phone"]


async def test_the_configured_identity_provider_is_built_by_the_container() -> None:
    async with (
        await openid_kernel(IDENTITY_PROVIDER_ENV).boot() as booted,
        unit_of_work(booted.container) as unit,
    ):
        provider = await unit.get(IdentityProviderInterface)

    assert isinstance(provider, InMemoryIdentityProvider)


async def test_the_identity_provider_is_built_per_request() -> None:
    async with await openid_kernel(SCOPED_IDENTITY_PROVIDER_ENV).boot() as booted:
        async with unit_of_work(booted.container) as first:
            one = await first.get(IdentityProviderInterface)
            same = await first.get(IdentityProviderInterface)
        async with unit_of_work(booted.container) as second:
            other = await second.get(IdentityProviderInterface)

    assert isinstance(one, ScopedIdentityProvider)
    assert one is same
    assert one is not other


async def test_asking_for_an_unconfigured_identity_provider_names_the_setting() -> None:
    async with await openid_kernel().boot() as booted:
        with pytest.raises(ServiceResolutionError) as reported:
            _ = await booted.container.get(IdentityProviderInterface)

    refusal = reported.value.__cause__
    assert isinstance(refusal, InvalidConfigurationError)
    assert "identity_provider" in str(refusal)
    assert "<app>/config/packages/openid_connect_server.py" in str(refusal)


def test_turning_the_shipped_redirect_flow_back_on_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="enable_auth_code_grant"):
        _ = openid_kernel(AUTH_CODE_BACK_ON_ENV).build()


def test_putting_another_token_answer_back_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="response_type_class"):
        _ = openid_kernel(BEARER_ANSWER_ENV).build()


def test_turning_the_servers_description_off_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="enable_metadata_endpoint"):
        _ = openid_kernel(NO_METADATA_ENV).build()
