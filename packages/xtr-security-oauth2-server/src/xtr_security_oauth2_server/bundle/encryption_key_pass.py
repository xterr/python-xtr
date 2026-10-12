"""Settling which key this server seals its own payloads with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_oauth2_server.token_server import TokenServer

from ._parameters import ENCRYPTION_KEY, ENCRYPTION_KEY_TYPE

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["EncryptionKeyPass"]

#: The two kinds of ``encryption_key`` there are: a password to be stretched
#: into a key, or the base64url of a key's bytes to be used as it is.
_KEY_TYPES: Final = ("plain", "key")


@final
class EncryptionKeyPass(CompilerPassInterface):
    """Reads the encryption key's final value, and hands it to the servers that use it.

    An authorization code and a refresh token are this server's own payloads
    handed to a client and read back later, so they are sealed rather than
    stored — and both the server that issues them and the server that answers
    about them have to seal and read with the same key.

    The value could have been baked into those definitions while services were
    being defined, and it would resolve. This exists because an application may
    override the two parameters after this bundle has had its say, and then the
    value baked in would be the one nobody chose. A pass runs once every bundle
    has finished, so what it reads is final — which also makes it the one place
    worth validating the kind of key, instead of discovering it is unreadable
    the first time a client redeems a code.

    The key itself is never derived here. Stretching a password costs real time
    on purpose, so it is done once where each server is built, not at build
    time and not per request.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Give each server the encryption key and the kind of key it is.

        Raises:
            InvalidConfigurationError: When the kind of key is not one this
                server knows how to read.
        """
        if not builder.has_parameter(ENCRYPTION_KEY):
            # The bundle reports a missing key itself, naming it beside every
            # other setting a deployment still owes; there is nothing to add.
            return
        key = builder.get_parameter(ENCRYPTION_KEY)
        key_type = builder.get_parameter(ENCRYPTION_KEY_TYPE)
        if key_type not in _KEY_TYPES:
            raise InvalidConfigurationError(
                f"The setting authorization_server.encryption_key_type is {key_type!r}, which "
                f"is not a kind of key this server can read; name one of {list(_KEY_TYPES)} — "
                "'plain' for a password to stretch, 'key' for the base64url of 32 random "
                "bytes.",
            )
        for service in (AuthorizationServer, TokenServer):
            if not builder.has_definition(service):
                continue
            _ = (
                builder.get_definition(service)
                .set_argument("encryption_key", key)
                .set_argument("encryption_key_type", key_type)
            )
        builder.log(self, f"Sealed this server's own payloads with a {key_type!r} key.")
