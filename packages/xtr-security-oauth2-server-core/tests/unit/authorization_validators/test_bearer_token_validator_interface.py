"""The reading contract is what judges one access token, header or no header."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server_core.authorization_validators import (
    BearerTokenValidatorInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface


@final
class _PassingValidator:
    """A reading that accepts everything, claiming nothing."""

    async def validate_bearer_token(
        self,
        request: ServerRequestInterface,
        token: str,
    ) -> Mapping[str, object]:
        del request, token

        return {}


@final
class _NotAValidator:
    """Something that reads a token, but not the way a reading is asked to."""

    async def validate(self, token: str) -> Mapping[str, object]:
        del token

        return {}


def test_a_reading_satisfies_the_contract() -> None:
    validator: BearerTokenValidatorInterface = _PassingValidator()

    assert isinstance(validator, BearerTokenValidatorInterface)


def test_something_without_the_method_does_not_satisfy_it() -> None:
    assert not isinstance(_NotAValidator(), BearerTokenValidatorInterface)
