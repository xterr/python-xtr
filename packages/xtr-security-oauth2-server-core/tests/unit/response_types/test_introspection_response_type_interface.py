"""The document contract is what a question about a token is answered through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server_core.response_types.introspection_response_type_interface import (
    IntrospectionResponseTypeInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface


@final
class _BareDocument:
    """A document that takes everything it is told and answers a plain 200."""

    def set_active(self, active: bool) -> None:
        del active

    def set_token_type(self, token_type: str) -> None:
        del token_type

    def set_token_data(self, token_data: Mapping[str, object]) -> None:
        del token_data

    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        return response.with_status(200)


@final
class _NotADocument:
    """Something that produces a response, but is told none of what a document is."""

    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        return response


def test_a_document_satisfies_the_contract() -> None:
    response_type: IntrospectionResponseTypeInterface = _BareDocument()

    assert isinstance(response_type, IntrospectionResponseTypeInterface)


def test_something_that_is_only_told_nothing_does_not_satisfy_it() -> None:
    assert not isinstance(_NotADocument(), IntrospectionResponseTypeInterface)
