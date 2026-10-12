"""Finding the stored client a protocol entity names, and refusing to guess."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["stored_client_of"]


async def stored_client_of(
    client_manager: ClientManagerInterface,
    client_entity: ClientEntityInterface,
) -> ClientInterface:
    """Return the stored client ``client_entity`` stands for.

    Every bridge that writes a credential has to put the *stored* client on
    it, because that is what a row points at, and every one of them is handed
    the protocol's entity instead.

    Raises:
        InvalidArgumentError: When no client is stored under that identifier.
            The request got this far by being validated against a client, so
            finding none now means the repository and the manager are reading
            different stores, or a client was removed mid-flow. Answering a
            protocol error would tell the client to try again at something
            that cannot work; failing loudly names the deployment's mistake.
    """
    identifier = client_entity.get_identifier()
    client = await client_manager.find(identifier)
    if client is None:
        raise InvalidArgumentError(
            f"No client is stored under the identifier {identifier!r}, although the "
            "request was validated against one; the client repository and the client "
            "manager are reading different stores.",
        )

    return client
