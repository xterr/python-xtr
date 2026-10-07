"""The user-provider configuration defaults to the plain stateless JWT user."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.bundle.jwt_user_provider_config import JwtUserProviderConfig
from xtr_security_jwt.security.user.jwt_user import JwtUser

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def test_it_defaults_to_the_plain_jwt_user() -> None:
    assert JwtUserProviderConfig().user_class is JwtUser


def test_it_carries_a_custom_user_class() -> None:
    class _CustomUser:
        @classmethod
        def create_from_payload(cls, username: str, payload: Mapping[str, object]) -> Self:
            del username, payload
            return cls()

        def get_user_identifier(self) -> str:
            return "ada"

        def get_roles(self) -> Sequence[str]:
            return ()

    assert JwtUserProviderConfig(user_class=_CustomUser).user_class is _CustomUser


def test_it_refuses_a_user_class_that_cannot_be_built_from_a_payload() -> None:
    class _NotAJwtUser: ...

    with pytest.raises(InvalidArgumentError):
        _ = JwtUserProviderConfig(user_class=_NotAJwtUser)


def test_it_refuses_a_user_class_that_is_not_a_class() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JwtUserProviderConfig(user_class=cast("type", cast("object", "JwtUser")))
