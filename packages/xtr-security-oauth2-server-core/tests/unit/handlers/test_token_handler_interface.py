"""The handler contract is what the token server drives either endpoint through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

from xtr_security_oauth2_server_core.handlers.token_handler_interface import TokenHandlerInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.authorization_validators import (
        BearerTokenValidatorInterface,
    )
    from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )


@final
class _AnsweringHandler:
    """A handler that takes everything the token server hands over, and answers."""

    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        del request

        return response

    def set_client_repository(self, client_repository: ClientRepositoryInterface) -> None:
        del client_repository

    def set_access_token_repository(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
    ) -> None:
        del access_token_repository

    def set_refresh_token_repository(
        self,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        del refresh_token_repository

    def set_bearer_token_validator(
        self,
        bearer_token_validator: BearerTokenValidatorInterface,
    ) -> None:
        del bearer_token_validator

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        del key, key_type


@final
class _NotAHandler:
    """Something that answers a request, but takes none of what a handler is handed."""

    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        del request

        return response


def test_a_handler_satisfies_the_contract() -> None:
    handler: TokenHandlerInterface = _AnsweringHandler()

    assert isinstance(handler, TokenHandlerInterface)


def test_something_without_the_setters_does_not_satisfy_it() -> None:
    assert not isinstance(_NotAHandler(), TokenHandlerInterface)
