"""The authenticator for a user their TLS certificate identifies."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_core.exception import BadCredentialsError

from .abstract_pre_authenticated_authenticator import AbstractPreAuthenticatedAuthenticator

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["X509Authenticator"]

#: The identifier a certificate's email address is carried under in the
#: distinguished name, and the dotted OID spelling of the same identifier.
_EMAIL_ADDRESS_IDENTIFIER: Final = "emailAddress"
_OID_EMAIL_ADDRESS: Final = "1.2.840.113549.1.9.1"


@final
class X509Authenticator(AbstractPreAuthenticatedAuthenticator):
    """Authenticates the user the server verified a certificate for.

    A request the server accepted on a client certificate arrives with what
    the server verified of it in the environment: the email the certificate
    names, ready to use, and the whole distinguished name the certificate
    was issued under. This authenticator reads the email first, and the
    configured identifier out of the distinguished name when the email is
    not there — the username is whichever the certificate carries.
    """

    __slots__ = ("_credentials_key", "_credentials_pattern", "_user_key")

    def __init__(  # noqa: PLR0913, PLR0917 -- the wiring constructor's shape: every parameter names a certificate key
        self,
        user_provider: UserProviderInterface,
        token_storage: TokenStorageInterface,
        firewall_name: str,
        user_key: str = "SSL_CLIENT_S_DN_Email",
        credentials_key: str = "SSL_CLIENT_S_DN",
        logger: LoggerInterface | None = None,
        credential_user_identifier: str = "emailAddress",
    ) -> None:
        """Record the provider, the storage, the firewall and the certificate keys.

        Args:
            user_provider: Loads the user the certificate names.
            token_storage: Read for a token that already vouches for the
                same user, and cleared when a failure invalidates one.
            firewall_name: The firewall this authenticator runs for.
            user_key: The environment key the server wrote the verified
                certificate's email under.
            credentials_key: The environment key the server wrote the whole
                distinguished name under.
            logger: Names what the authenticator skipped and cleared, when
                one is given.
            credential_user_identifier: The distinguished-name identifier the
                username is read out of when the email key is absent;
                ``emailAddress`` also answers its dotted OID spelling.
        """
        super().__init__(user_provider, token_storage, firewall_name, logger)
        self._user_key = user_key
        self._credentials_key = credentials_key
        self._credentials_pattern = (
            re.compile(
                rf"(?:^|[,/])\s*(?:{_EMAIL_ADDRESS_IDENTIFIER}|{_OID_EMAIL_ADDRESS})="
                r"([^,/@]+@[^,/]+)",
            )
            if credential_user_identifier == _EMAIL_ADDRESS_IDENTIFIER
            else re.compile(rf"(?:^|[,/])\s*{re.escape(credential_user_identifier)}=([^,/]+)")
        )

    @override
    def extract_username(self, request: ServerRequestInterface) -> str:
        """Read the user the request's certificate identifies, from the environment.

        The email key is read first, as it is; the distinguished name is
        searched for the configured identifier when the email is not there,
        and the value it carries becomes the username, whitespace trimmed.
        A request whose environment carries neither — or a name that carries
        no such identifier — is refused.

        Raises:
            BadCredentialsError: When the environment carries neither
                certificate key, or the name carries no such identifier.
        """
        server = request.get_server_params()
        username: str | None = None
        if self._user_key in server:
            value = server[self._user_key]
            username = value if isinstance(value, str) else None
        elif self._credentials_key in server:
            credentials = server[self._credentials_key]
            if isinstance(credentials, str):
                matched = self._credentials_pattern.search(credentials)
                if matched is not None:
                    username = matched.group(1).strip()
        if username is None:
            raise BadCredentialsError(
                f'SSL credentials not found: "{self._user_key}", "{self._credentials_key}".',
            )
        return username
