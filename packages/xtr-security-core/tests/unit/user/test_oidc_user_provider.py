"""The OIDC user provider builds users from the claims authentication collected."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError
from xtr_security_core.user import (
    AttributesBasedUserProviderInterface,
    InMemoryUser,
    OidcUser,
    OidcUserProvider,
)


def test_it_is_an_attributes_based_provider() -> None:
    assert AttributesBasedUserProviderInterface in OidcUserProvider.__mro__


@pytest.mark.anyio
async def test_it_builds_the_user_from_the_claims_under_the_validated_identifier() -> None:
    user = await OidcUserProvider().load_user_by_identifier(
        "alice@example.test",
        {"sub": "alice", "email": "alice@example.test"},
    )

    assert user.get_user_identifier() == "alice@example.test"
    assert user.get_sub() == "alice"
    assert user.get_email() == "alice@example.test"


@pytest.mark.anyio
async def test_the_claims_cannot_grant_roles_nor_change_the_identifier() -> None:
    user = await OidcUserProvider().load_user_by_identifier(
        "alice",
        {"sub": "alice", "Roles": ["ROLE_ADMIN"], "user-identifier": "root", "userIdentifier": "x"},
    )

    assert user.get_roles() == ("ROLE_USER",)
    assert user.get_user_identifier() == "alice"
    assert dict(user.get_additional_claims()) == {}


@pytest.mark.anyio
@pytest.mark.parametrize("attributes", [None, {}, {"sub": ""}, {"sub": 42}])
async def test_without_a_usable_sub_the_user_is_not_found(
    attributes: dict[str, object] | None,
) -> None:
    with pytest.raises(UserNotFoundError, match="cannot load a user by its identifier alone"):
        _ = await OidcUserProvider().load_user_by_identifier("alice", attributes)


@pytest.mark.anyio
async def test_refresh_user_returns_the_oidc_user_as_is() -> None:
    user = OidcUser(sub="alice")

    assert await OidcUserProvider().refresh_user(user) is user


@pytest.mark.anyio
async def test_refresh_user_refuses_another_kind_of_user() -> None:
    with pytest.raises(UnsupportedUserError, match='Instances of "InMemoryUser"'):
        _ = await OidcUserProvider().refresh_user(InMemoryUser("alice"))


def test_it_supports_only_the_oidc_user() -> None:
    provider = OidcUserProvider()

    assert provider.supports_class(OidcUser) is True
    assert provider.supports_class(InMemoryUser) is False
