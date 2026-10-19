"""The shape of a client-authentication method."""

from __future__ import annotations

from typing import final

from xtr_security_http.oauth2 import ClientSecretBasic, NoClientAuthentication
from xtr_security_http.oauth2.client_authentication import ClientAuthenticationInterface


@final
class _Method:
    """A method answering every member of the interface."""

    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        del client_id, token_endpoint
        return options

    def get_method(self) -> str:
        return "example"


def test_a_method_answering_every_member_is_a_client_authentication() -> None:
    assert isinstance(_Method(), ClientAuthenticationInterface)


def test_the_shipped_methods_are_client_authentications() -> None:
    assert isinstance(ClientSecretBasic("secret"), ClientAuthenticationInterface)
    assert isinstance(NoClientAuthentication(), ClientAuthenticationInterface)
