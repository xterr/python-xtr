"""The validator contract is what a resource server reads a request through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server.authorization_validators.authorization_validator_interface import (
    AuthorizationValidatorInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface


@final
class _PassingValidator:
    """A validator that accepts everything, annotating nothing."""

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        return request


@final
class _NotAValidator:
    """Something that reads a request, but not the way a validator is asked to."""

    async def validate(self, request: ServerRequestInterface) -> ServerRequestInterface:
        return request


def test_a_validator_satisfies_the_contract() -> None:
    validator: AuthorizationValidatorInterface = _PassingValidator()

    assert isinstance(validator, AuthorizationValidatorInterface)


def test_something_without_the_method_does_not_satisfy_it() -> None:
    assert not isinstance(_NotAValidator(), AuthorizationValidatorInterface)
