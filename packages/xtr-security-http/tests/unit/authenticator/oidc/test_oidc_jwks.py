"""The static provider reads a JWKS document once and always answers it."""

from __future__ import annotations

import json
from typing import cast

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.oidc import make_key, public_jwks
from xtr_security_http.authenticator.oidc.oidc_jwks import (
    OidcKeySetProviderInterface,
    StaticOidcKeySetProvider,
)


def test_a_conforming_provider_satisfies_the_interface() -> None:
    provider = StaticOidcKeySetProvider(public_jwks(make_key()))
    assert isinstance(provider, OidcKeySetProviderInterface)
    assert OidcKeySetProviderInterface in type(provider).__mro__


def test_a_bare_object_does_not_satisfy_the_interface() -> None:
    assert not isinstance(object(), OidcKeySetProviderInterface)


@pytest.mark.anyio
async def test_it_answers_the_key_set_from_a_json_string() -> None:
    key = make_key()
    provider = StaticOidcKeySetProvider(public_jwks(key))

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_it_answers_the_key_set_from_a_mapping() -> None:
    key = make_key()
    provider = StaticOidcKeySetProvider(cast("dict[str, object]", json.loads(public_jwks(key))))

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_a_forced_refresh_answers_the_same_fixed_set() -> None:
    key = make_key()
    provider = StaticOidcKeySetProvider(public_jwks(key))

    first = await provider.get_key_set()
    second = await provider.get_key_set(force_refresh=True)

    assert first is second


def test_a_document_that_is_not_json_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StaticOidcKeySetProvider("not json")


def test_a_document_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StaticOidcKeySetProvider("[]")
