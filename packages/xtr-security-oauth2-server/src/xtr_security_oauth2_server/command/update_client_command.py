"""``oauth2-server:update-client``: amend a registered client's lists and its state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, TypeVar, final

from xtr_console import Argument, ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

from ._registry import OAUTH2_SERVER_COMMANDS

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["UpdateClientCommand"]

_T = TypeVar("_T")


@as_command("oauth2-server:update-client", registry=OAUTH2_SERVER_COMMANDS)
@final
class UpdateClientCommand:
    """Adds to and removes from a client's registration, and turns it on or off.

    Every list is amended rather than replaced — a redirect URI is added or
    taken away, never the whole set rewritten — because a registration is
    administered one change at a time and a replacement would silently drop
    whatever the caller did not happen to name.

    The secret is not among the fields: a stored secret is a hash, so there is
    nothing here that could change it to something an operator knows. A client
    that needs a new secret is registered again.

    Taking the *last* scope away does not leave the client scope-less where a
    deployment configured default scopes: an amendment is saved through the
    client manager, which announces it, and the listener this package ships
    reads a scope-less client as one registered with no scopes and hands it
    those defaults. The run reports the client amended, because it was — just
    not left as the options read. A deployment wanting scope-less clients
    configures no default scopes.
    """

    __slots__ = ("_client_manager",)

    def __init__(self, client_manager: ClientManagerInterface) -> None:
        """Read and write the registrations through ``client_manager``."""
        self._client_manager = client_manager

    async def __call__(  # noqa: PLR0913 — three amendable lists, each two options
        self,
        io: ConsoleStyle,
        identifier: Annotated[str, Argument(help="The client to amend.")],
        *,
        add_redirect_uri: Annotated[
            list[str] | None,
            Option(help="A redirect URI to allow. Repeat for several."),
        ] = None,
        remove_redirect_uri: Annotated[
            list[str] | None,
            Option(help="A redirect URI to stop allowing. Repeat for several."),
        ] = None,
        add_grant_type: Annotated[
            list[str] | None,
            Option(help="A grant to allow. Repeat for several."),
        ] = None,
        remove_grant_type: Annotated[
            list[str] | None,
            Option(help="A grant to stop allowing. Repeat for several."),
        ] = None,
        add_scope: Annotated[
            list[str] | None,
            Option(help="A scope to allow. Repeat for several."),
        ] = None,
        remove_scope: Annotated[
            list[str] | None,
            Option(
                help="A scope to stop allowing. Repeat for several; taking the last one away "
                "hands the client this deployment's default scopes, if it configured any.",
            ),
        ] = None,
        activate: Annotated[bool, Option(help="Let this client authenticate.")] = False,
        deactivate: Annotated[bool, Option(help="Stop this client authenticating.")] = False,
    ) -> int:
        """Amend a registered client's lists, and turn it on or off."""
        client = await self._client_manager.find(identifier)
        if client is None:
            io.error(f'OAuth2 client identified as "{escape(identifier)}" does not exist.')

            return ExitCode.FAILURE
        try:
            active = _state(client.is_active(), activate=activate, deactivate=deactivate)
            redirect_uris = _amended(
                client.get_redirect_uris(),
                add_redirect_uri or [],
                remove_redirect_uri or [],
                RedirectUri,
                "redirect-uri",
            )
            grants = _amended(
                client.get_grants(),
                add_grant_type or [],
                remove_grant_type or [],
                Grant,
                "grant-type",
            )
            scopes = _amended(
                client.get_scopes(),
                add_scope or [],
                remove_scope or [],
                Scope,
                "scope",
            )
        except InvalidArgumentError as error:
            io.error(escape(str(error)))

            return ExitCode.FAILURE
        _ = client.set_active(active)
        _ = client.set_redirect_uris(*redirect_uris)
        _ = client.set_grants(*grants)
        _ = client.set_scopes(*scopes)
        await self._client_manager.save(client)
        io.success("OAuth2 client updated successfully.")

        return ExitCode.SUCCESS


def _state(current: bool, *, activate: bool, deactivate: bool) -> bool:
    """Return whether the client may authenticate after this amendment.

    Raises:
        InvalidArgumentError: When both options were given, which name
            opposite outcomes and so cannot both be meant.
    """
    if activate and deactivate:
        raise InvalidArgumentError(
            'Cannot specify "--activate" and "--deactivate" at the same time.',
        )
    if activate:
        return True
    if deactivate:
        return False

    return current


def _amended(
    held: Sequence[_T],
    to_add: Sequence[str],
    to_remove: Sequence[str],
    value_object: Callable[[str], _T],
    option: str,
) -> tuple[_T, ...]:
    """Return ``held`` without ``to_remove`` and with ``to_add``, in that order.

    Removing something the client never held is not an error: the outcome the
    caller asked for — that it does not hold it — is the outcome either way.

    Raises:
        InvalidArgumentError: When one value is named in both options, which
            name opposite outcomes; or when a value added is not one its value
            object will accept.
    """
    colliding = [one for one in to_add if one in to_remove]
    if colliding:
        named = '", "'.join(colliding)
        raise InvalidArgumentError(
            f'Cannot specify "{named}" in either "--add-{option}" and "--remove-{option}".',
        )
    kept = tuple(one for one in held if str(one) not in to_remove)

    return (*kept, *(value_object(one) for one in to_add))
