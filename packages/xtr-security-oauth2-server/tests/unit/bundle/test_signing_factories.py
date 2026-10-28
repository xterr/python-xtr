"""The key loader reports a missing key file in this server's own terms."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_jwt.exception import MissingKeyError

from tests.support.signing import SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import AuthorizationServerConfig, ResourceServerConfig
from xtr_security_oauth2_server.bundle._signing_factories import key_loader_factory
from xtr_security_oauth2_server.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from pathlib import Path


def _build(private_key: str, public_key: str | None = None) -> object:
    factory = key_loader_factory(
        AuthorizationServerConfig(private_key=private_key),
        ResourceServerConfig(public_key=public_key),
    )

    return factory()


def test_a_missing_private_key_file_names_this_servers_setting(tmp_path: Path) -> None:
    missing = str(tmp_path / "secrets" / "oauth2.pem")

    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _build(missing)

    message = str(refused.value)
    assert missing in message
    assert "authorization_server.private_key" in message
    assert "config/packages/oauth2_server.py" in message
    assert "OAUTH2_SERVER_PRIVATE_KEY_PATH" in message
    assert "oauth2-server:generate-keypair" in message


def test_a_missing_private_key_file_never_points_at_the_token_package(tmp_path: Path) -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _build(str(tmp_path / "oauth2.pem"))

    message = str(refused.value)
    assert "jwt" not in message.lower()
    assert isinstance(refused.value.__cause__, MissingKeyError)


def test_a_missing_public_key_file_names_the_resource_server_setting(tmp_path: Path) -> None:
    missing = str(tmp_path / "public.pem")

    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _build(SIGNING_KEY_PEM, missing)

    assert missing in str(refused.value)
    assert "resource_server.public_key" in str(refused.value)


def test_a_key_file_in_place_builds_the_loader(tmp_path: Path) -> None:
    key_file = tmp_path / "oauth2.pem"
    _ = key_file.write_text(SIGNING_KEY_PEM, encoding="utf-8")

    loader = key_loader_factory(
        AuthorizationServerConfig(private_key=str(key_file)),
        ResourceServerConfig(),
    )()

    assert loader.get_signing_key() == SIGNING_KEY_PEM
