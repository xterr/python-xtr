"""The pre-authenticated tagged union: the type field picks the branch."""

from __future__ import annotations

from xtr_security.bundle import RemoteUserConfig, X509Config


def test_the_remote_user_branch_carries_its_key_and_type() -> None:
    config = RemoteUserConfig()

    assert config.type == "remote_user"
    assert config.user_key == "REMOTE_USER"


def test_the_x509_branch_carries_its_certificate_keys_and_type() -> None:
    config = X509Config()

    assert config.type == "x509"
    assert config.user_key == "SSL_CLIENT_S_DN_Email"
    assert config.credentials_key == "SSL_CLIENT_S_DN"
    assert config.credential_user_identifier == "emailAddress"


def test_the_type_field_tells_the_branches_apart() -> None:
    assert RemoteUserConfig().type != X509Config().type
