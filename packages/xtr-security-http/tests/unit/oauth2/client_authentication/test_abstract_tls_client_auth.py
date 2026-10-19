"""The TLS client-authentication base: nothing is added to the request."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_security_http.oauth2.client_authentication import AbstractTlsClientAuth


@final
class _TlsAuth(AbstractTlsClientAuth):
    """A concrete TLS method, for the base's own behaviour."""

    @override
    def get_method(self) -> str:
        return "tls_client_auth"


def test_the_options_are_returned_unchanged() -> None:
    options: dict[str, object] = {"body": {"grant_type": "authorization_code"}}

    assert (
        _TlsAuth().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )
        is options
    )


def test_a_request_with_no_options_at_all_passes_through() -> None:
    assert _TlsAuth().authenticate("my-client", "https://issuer.example/token", {}) == {}
