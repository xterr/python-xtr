"""The stateless provider builds a user from a token's claims and caches it."""

from __future__ import annotations

import pytest
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_service_contracts import ResetInterface

from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_provider import JwtUserProvider

pytestmark = pytest.mark.anyio


def test_it_implements_the_attributes_based_provider_and_reset() -> None:
    assert AttributesBasedUserProviderInterface in JwtUserProvider.__mro__
    assert ResetInterface in JwtUserProvider.__mro__


async def test_it_builds_a_user_from_the_payload() -> None:
    provider = JwtUserProvider()

    user = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_USER"]})

    assert user.get_user_identifier() == "ada"
    assert list(user.get_roles()) == ["ROLE_USER"]


async def test_it_caches_a_user_by_identifier() -> None:
    provider = JwtUserProvider()

    first = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_USER"]})
    second = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_ADMIN"]})

    assert first is second


async def test_reset_clears_the_cache() -> None:
    provider = JwtUserProvider()

    first = await provider.load_user_by_identifier("ada", {})
    provider.reset()
    second = await provider.load_user_by_identifier("ada", {})

    assert first is not second


def test_it_supports_its_user_class() -> None:
    provider = JwtUserProvider()

    assert provider.supports_class(JwtUser) is True
    assert provider.supports_class(str) is False
