"""Authenticates the client with a certificate it signed itself."""

from __future__ import annotations

from xtr_security_http.oauth2 import SelfSignedTlsClientAuth


def test_the_method_is_self_signed_tls_client_auth() -> None:
    assert SelfSignedTlsClientAuth().get_method() == "self_signed_tls_client_auth"


def test_the_request_options_are_left_to_the_http_client() -> None:
    options: dict[str, object] = {"local_cert": "/certs/client.pem"}

    assert (
        SelfSignedTlsClientAuth().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )
        is options
    )
