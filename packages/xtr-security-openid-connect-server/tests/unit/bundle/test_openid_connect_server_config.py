"""The configuration builds on its defaults and refuses what no provider could run with."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from tests.support.identity_provider import InMemoryIdentityProvider
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerConfig
from xtr_security_openid_connect_server.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_the_defaults_name_the_usual_login_firewall_and_paths() -> None:
    config = OpenIdConnectServerConfig()

    assert (config.login_path, config.login_firewall, config.authorize_path) == (
        "/login",
        "main",
        "/authorize",
    )


def test_by_default_nothing_the_application_supplies_is_set() -> None:
    config = OpenIdConnectServerConfig()

    assert (config.identity_provider, dict(config.claim_sets), config.id_token_ttl) == (
        None,
        {},
        None,
    )


def test_every_setting_can_be_given() -> None:
    config = OpenIdConnectServerConfig(
        identity_provider=InMemoryIdentityProvider,
        claim_sets={"company": ("company_id",)},
        id_token_ttl=timedelta(minutes=5),
    )

    assert config.identity_provider is InMemoryIdentityProvider
    assert dict(config.claim_sets) == {"company": ("company_id",)}
    assert config.id_token_ttl == timedelta(minutes=5)


@pytest.mark.parametrize(
    ("setting", "build"),
    [
        ("login_path", lambda: OpenIdConnectServerConfig(login_path="")),
        ("login_firewall", lambda: OpenIdConnectServerConfig(login_firewall="")),
        ("authorize_path", lambda: OpenIdConnectServerConfig(authorize_path="")),
    ],
)
def test_an_empty_name_is_refused_naming_the_setting(
    setting: str,
    build: Callable[[], OpenIdConnectServerConfig],
) -> None:
    with pytest.raises(InvalidConfigurationError, match=setting):
        _ = build()


@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-1)])
def test_an_id_token_lifetime_that_is_not_positive_is_refused(ttl: timedelta) -> None:
    with pytest.raises(InvalidConfigurationError, match="id_token_ttl"):
        _ = OpenIdConnectServerConfig(id_token_ttl=ttl)


@pytest.mark.parametrize("scope", ["profile", "email", "address", "phone"])
def test_a_claim_set_for_a_scope_the_protocol_defines_is_refused(scope: str) -> None:
    with pytest.raises(InvalidConfigurationError, match=f"claim_sets.*{scope}"):
        _ = OpenIdConnectServerConfig(claim_sets={scope: ("anything",)})


def test_a_claim_set_for_an_empty_scope_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="claim_sets"):
        _ = OpenIdConnectServerConfig(claim_sets={"": ("anything",)})


def test_a_refusal_names_the_file_the_setting_belongs_in() -> None:
    with pytest.raises(
        InvalidConfigurationError, match=r"<app>/config/packages/openid_connect_server\.py"
    ):
        _ = OpenIdConnectServerConfig(login_path="")
