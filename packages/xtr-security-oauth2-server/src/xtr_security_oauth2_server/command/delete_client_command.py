"""``oauth2-server:delete-client``: withdraw a registered client."""

from __future__ import annotations

from typing import Annotated, final

from xtr_console import Argument, ConsoleStyle, ExitCode, as_command, escape

from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    ClientManagerInterface,
)

from ._registry import OAUTH2_SERVER_COMMANDS

__all__ = ["DeleteClientCommand"]


@as_command("oauth2-server:delete-client", registry=OAUTH2_SERVER_COMMANDS)
@final
class DeleteClientCommand:
    """Forgets a client's registration, so nothing it holds can authenticate again.

    The client is read first and reported when there is none, rather than
    answering as if a registration that never existed had been withdrawn: a
    mistyped identifier is the likeliest reason for either, and an operator
    withdrawing a client needs to know which it was.
    """

    __slots__ = ("_client_manager",)

    def __init__(self, client_manager: ClientManagerInterface) -> None:
        """Read and withdraw the registrations through ``client_manager``."""
        self._client_manager = client_manager

    async def __call__(
        self,
        io: ConsoleStyle,
        identifier: Annotated[str, Argument(help="The client to withdraw.")],
    ) -> int:
        """Withdraw a registered client, so nothing it holds authenticates again."""
        client = await self._client_manager.find(identifier)
        if client is None:
            io.error(f'OAuth2 client identified as "{escape(identifier)}" does not exist.')

            return ExitCode.FAILURE
        await self._client_manager.remove(client)
        io.success("OAuth2 client deleted successfully.")

        return ExitCode.SUCCESS
