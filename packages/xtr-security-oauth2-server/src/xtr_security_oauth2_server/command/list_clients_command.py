"""``oauth2-server:list-clients``: show the registered clients, narrowed by criteria."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.manager.client_filter import ClientFilter
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

from ._registry import OAUTH2_SERVER_COMMANDS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["COLUMNS", "ListClientsCommand"]

COLUMNS: Final = ("name", "identifier", "secret", "scope", "redirect uri", "grant type")
"""Every column a listing can show, in the order a listing showing them all does."""

#: What stands in the secret column of a confidential client. The stored secret
#: is a hash, and a hash on a terminal is an offline guessing target, so no
#: option reveals it: there is nothing an operator could do with it.
_MASKED: Final = "****"

#: What stands there for a client that holds no secret at all.
_PUBLIC: Final = "(public)"


@as_command("oauth2-server:list-clients", registry=OAUTH2_SERVER_COMMANDS)
@final
class ListClientsCommand:
    """Shows the registered clients, with their secrets masked.

    A secret is never shown, not even as the hash that is stored: a listing is
    read over somebody's shoulder and copied into tickets, and the hash is of
    no use to an operator while being of considerable use to anybody guessing
    offline. A client that lost its secret is registered again.

    ``--columns`` narrows what is shown and ``--scope``, ``--grant-type`` and
    ``--redirect-uri`` narrow which clients are: a client has to hold
    everything named, so naming two scopes lists the clients holding both.
    """

    __slots__ = ("_client_manager",)

    def __init__(self, client_manager: ClientManagerInterface) -> None:
        """Read the registrations through ``client_manager``."""
        self._client_manager = client_manager

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        columns: Annotated[
            list[str] | None,
            Option(help="A column to show. Repeat for several; all of them when left out."),
        ] = None,
        redirect_uri: Annotated[
            list[str] | None,
            Option(help="List only the clients registered with this redirect URI."),
        ] = None,
        grant_type: Annotated[
            list[str] | None,
            Option(help="List only the clients allowed this grant."),
        ] = None,
        scope: Annotated[
            list[str] | None,
            Option(help="List only the clients allowed this scope."),
        ] = None,
    ) -> int:
        """Show the registered clients, with every secret masked."""
        try:
            shown = _requested_columns(columns)
            criteria = (
                ClientFilter.create()
                .add_grant_criteria(*(Grant(one) for one in grant_type or []))
                .add_redirect_uri_criteria(*(RedirectUri(one) for one in redirect_uri or []))
                .add_scope_criteria(*(Scope(one) for one in scope or []))
            )
        except InvalidArgumentError as error:
            io.error(escape(str(error)))

            return ExitCode.FAILURE
        clients = await self._client_manager.list(criteria)
        io.table(
            [escape(column) for column in shown],
            [[_cells(client)[column] for column in shown] for client in clients],
        )

        return ExitCode.SUCCESS


def _requested_columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    """Return the columns to show: the ones named, in that order, or every one.

    Raises:
        InvalidArgumentError: When a name is not a column, which would
            otherwise be dropped and leave a listing quietly missing what was
            asked for.
    """
    if columns is None:
        return COLUMNS
    named = tuple(dict.fromkeys(column.strip().lower() for column in columns))
    unknown = [column for column in named if column not in COLUMNS]
    if unknown:
        allowed = ", ".join(repr(column) for column in COLUMNS)
        raise InvalidArgumentError(
            f"{unknown[0]!r} is not a column of a client listing; the columns are {allowed}.",
        )

    return named


def _cells(client: ClientInterface) -> Mapping[str, str]:
    """Return what each column holds for ``client``, ready for a terminal."""
    return {
        "name": escape(client.get_name()),
        "identifier": escape(client.get_identifier()),
        "secret": _MASKED if client.is_confidential() else _PUBLIC,
        "scope": escape(", ".join(str(one) for one in client.get_scopes())),
        "redirect uri": escape(", ".join(str(one) for one in client.get_redirect_uris())),
        "grant type": escape(", ".join(str(one) for one in client.get_grants())),
    }
