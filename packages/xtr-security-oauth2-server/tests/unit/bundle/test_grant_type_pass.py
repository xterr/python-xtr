"""The grants a deployment runs, collected with the lifetime each issues for."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.building import processing_builder
from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.bundle._parameters import ACCESS_TOKEN_TTL_DEFAULT
from xtr_security_oauth2_server.bundle.grant_type_pass import GRANT_TAG, GrantTypePass
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server.grant.grant_type_interface import GrantTypeInterface
from xtr_security_oauth2_server.grant.refresh_token_grant import RefreshTokenGrant

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

_HOUR = timedelta(hours=1)
_DAY = timedelta(days=1)


def _builder(default_ttl: object = _HOUR) -> ContainerBuilder:
    """Return a builder holding the server and the fallback lifetime."""
    builder = processing_builder({"oauth2_server": {"access_token_ttl": {"default": default_ttl}}})
    _ = builder.register(AuthorizationServer)

    return builder


def _enabled(builder: ContainerBuilder) -> tuple[tuple[str, timedelta], ...]:
    """Return what the server was told to enable, in order."""
    read = builder.get_definition(AuthorizationServer).arguments["grants"]
    assert isinstance(read, tuple)

    return cast("tuple[tuple[str, timedelta], ...]", read)


def test_the_fallback_lifetime_is_the_parameter_the_bundle_set() -> None:
    assert _builder().get_parameter(ACCESS_TOKEN_TTL_DEFAULT) == _HOUR


def test_a_deployment_with_no_grant_tagged_is_refused() -> None:
    # A server that can issue nothing is a deployment mistake, not a
    # configuration.
    with pytest.raises(InvalidConfigurationError, match=r"runs no OAuth 2\.0 grant"):
        GrantTypePass().process(_builder())


def test_with_no_server_registered_nothing_is_handed_over() -> None:
    builder = processing_builder({"oauth2_server": {"access_token_ttl": {"default": _HOUR}}})
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG)

    GrantTypePass().process(builder)

    # There is nothing to hand them to, so nothing is aliased either;
    # whatever left the server unregistered reports itself.
    assert not builder.has_alias(GrantTypeInterface, "oauth2_server_grant_0")
    assert not builder.has_definition(AuthorizationServer)


def test_every_tagged_grant_is_reachable_under_its_own_qualifier() -> None:
    builder = _builder()
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG)
    _ = builder.register(RefreshTokenGrant).add_tag(GRANT_TAG)

    GrantTypePass().process(builder)

    assert [qualifier for qualifier, _ttl in _enabled(builder)] == [
        "oauth2_server_grant_0",
        "oauth2_server_grant_1",
    ]
    for qualifier, _ttl in _enabled(builder):
        assert builder.has_alias(GrantTypeInterface, qualifier)


def test_a_grant_carrying_its_own_lifetime_keeps_it() -> None:
    builder = _builder()
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG, access_token_ttl=_DAY)

    GrantTypePass().process(builder)

    assert _enabled(builder) == (("oauth2_server_grant_0", _DAY),)


def test_a_grant_tagged_with_no_lifetime_gets_the_deployments_default() -> None:
    builder = _builder()
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG)

    GrantTypePass().process(builder)

    assert _enabled(builder) == (("oauth2_server_grant_0", _HOUR),)


def test_a_lifetime_that_is_not_a_length_of_time_is_refused_naming_the_grant() -> None:
    builder = _builder()
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG, access_token_ttl=3600)

    with pytest.raises(InvalidConfigurationError) as refused:
        GrantTypePass().process(builder)

    message = str(refused.value)
    assert "ClientCredentialsGrant" in message
    assert "3600" in message


def test_a_fallback_lifetime_that_is_not_a_length_of_time_is_refused_too() -> None:
    builder = _builder(default_ttl="an hour")
    _ = builder.register(ClientCredentialsGrant).add_tag(GRANT_TAG)

    with pytest.raises(InvalidConfigurationError, match=r"'an hour'"):
        GrantTypePass().process(builder)
