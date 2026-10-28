"""Authenticates the client with a certificate an authority issued to it."""

from __future__ import annotations

from xtr_security_http.oauth2 import TlsClientAuth


def test_the_method_is_tls_client_auth() -> None:
    assert TlsClientAuth().get_method() == "tls_client_auth"


def test_the_request_options_are_left_to_the_http_client() -> None:
    options: dict[str, object] = {"local_cert": "/certs/client.pem"}

    assert (
        TlsClientAuth().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )
        is options
    )
