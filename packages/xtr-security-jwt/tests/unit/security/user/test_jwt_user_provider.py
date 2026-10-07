"""The stateless provider builds a fresh user from each token's claims."""

from __future__ import annotations

from typing import cast

import pytest
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)

from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_provider import JwtUserProvider

pytestmark = pytest.mark.anyio


def test_it_implements_the_attributes_based_provider() -> None:
    assert AttributesBasedUserProviderInterface in JwtUserProvider.__mro__


async def test_it_builds_a_user_from_the_payload() -> None:
    provider = JwtUserProvider()

    user = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_USER"]})

    assert user.get_user_identifier() == "ada"
    assert list(user.get_roles()) == ["ROLE_USER"]


async def test_the_same_subject_with_different_roles_yields_different_roles() -> None:
    provider = JwtUserProvider()

    first = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_USER"]})
    second = await provider.load_user_by_identifier("ada", {"roles": ["ROLE_ADMIN"]})

    assert first is not second
    assert list(first.get_roles()) == ["ROLE_USER"]
    assert list(second.get_roles()) == ["ROLE_ADMIN"]


def test_it_supports_its_user_class() -> None:
    provider = JwtUserProvider()

    assert provider.supports_class(JwtUser) is True
    assert provider.supports_class(str) is False


def test_it_supports_nothing_that_is_not_a_class() -> None:
    provider = JwtUserProvider()

    assert provider.supports_class(cast("type", cast("object", "JwtUser"))) is False
