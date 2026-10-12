"""The key this server seals its own payloads with, settled once every bundle has had its say."""

from __future__ import annotations

import pytest

from tests.support.building import processing_builder
from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.bundle._parameters import ENCRYPTION_KEY, ENCRYPTION_KEY_TYPE
from xtr_security_oauth2_server.bundle.encryption_key_pass import EncryptionKeyPass
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.token_server import TokenServer

_KEY = "a-password-long-enough-to-stretch-into-a-key"


def _parameters(key: str = _KEY, key_type: str = "plain") -> dict[str, object]:
    """Return the two parameters the pass reads, as the bundle sets them."""
    return {"oauth2_server": {"encryption_key": key, "encryption_key_type": key_type}}


def test_the_parameters_are_the_leaves_the_pass_reads() -> None:
    builder = processing_builder(_parameters())

    assert builder.get_parameter(ENCRYPTION_KEY) == _KEY
    assert builder.get_parameter(ENCRYPTION_KEY_TYPE) == "plain"


def test_with_no_key_parameter_at_all_the_pass_leaves_everything_alone() -> None:
    # Nothing registered the key, so there is nothing to hand over and nothing
    # to validate; whatever left it unset reports itself where it is used.
    builder = processing_builder()
    _ = builder.register(AuthorizationServer)

    EncryptionKeyPass().process(builder)

    assert "encryption_key" not in builder.get_definition(AuthorizationServer).arguments


def test_both_servers_are_handed_the_key_and_the_kind_of_key_it_is() -> None:
    builder = processing_builder(_parameters(key_type="key"))
    _ = builder.register(AuthorizationServer)
    _ = builder.register(TokenServer)

    EncryptionKeyPass().process(builder)

    for service in (AuthorizationServer, TokenServer):
        arguments = builder.get_definition(service).arguments
        assert arguments["encryption_key"] == _KEY
        assert arguments["encryption_key_type"] == "key"


def test_a_server_that_is_not_registered_is_skipped() -> None:
    builder = processing_builder(_parameters())
    _ = builder.register(TokenServer)

    EncryptionKeyPass().process(builder)

    assert builder.get_definition(TokenServer).arguments["encryption_key"] == _KEY
    assert not builder.has_definition(AuthorizationServer)


def test_a_kind_of_key_this_server_cannot_read_is_refused_naming_both_kinds() -> None:
    # The one place the final value of the parameter is read, which is why it
    # is also the one place worth checking: an application may override it
    # after this bundle has had its say, and a key that cannot be read would
    # otherwise be discovered the first time a client redeems a code.
    builder = processing_builder(_parameters(key_type="rot13"))

    with pytest.raises(InvalidConfigurationError) as refused:
        EncryptionKeyPass().process(builder)

    message = str(refused.value)
    assert "encryption_key_type is 'rot13'" in message
    assert "'plain'" in message
    assert "'key'" in message
