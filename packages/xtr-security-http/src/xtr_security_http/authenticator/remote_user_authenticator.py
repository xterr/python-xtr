"""The authenticator for a user the server in front already authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

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

__all__ = ["RemoteUserAuthenticator"]


@final
class RemoteUserAuthenticator(AbstractPreAuthenticatedAuthenticator):
    """Authenticates the user the server in front of the application names.

    A server that authenticated the request before the application saw it —
    a reverse proxy against the company directory, a gateway by source
    address — writes the account it identified as into the environment the
    request arrives with, under one key. This authenticator reads that key:
    the value it finds is the username, taken as proven because the server
    in front already vouched for it.
    """

    __slots__ = ("_user_key",)

    def __init__(
        self,
        user_provider: UserProviderInterface,
        token_storage: TokenStorageInterface,
        firewall_name: str,
        user_key: str = "REMOTE_USER",
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the provider, the storage, the firewall and the environment key.

        Args:
            user_provider: Loads the user the environment names.
            token_storage: Read for a token that already vouches for the
                same user, and cleared when a failure invalidates one.
            firewall_name: The firewall this authenticator runs for.
            user_key: The environment key the server in front wrote the
                authenticated account under.
            logger: Names what the authenticator skipped and cleared, when
                one is given.
        """
        super().__init__(user_provider, token_storage, firewall_name, logger)
        self._user_key = user_key

    @override
    def extract_username(self, request: ServerRequestInterface) -> str | None:
        """Read the account the server in front authenticated, from the environment.

        A request whose environment does not carry the key is refused: the
        server in front never vouched for anyone. A key whose value is empty
        reads as no user — the request goes unauthenticated rather than
        failing on it.

        Raises:
            BadCredentialsError: When the environment carries no ``user_key``.
        """
        server = request.get_server_params()
        if self._user_key not in server:
            raise BadCredentialsError(f'User key was not found: "{self._user_key}".')
        value = server[self._user_key]
        return value if isinstance(value, str) and value != "" else None
