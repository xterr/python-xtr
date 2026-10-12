"""Reading a client the protocol can use, and saying whether it proved itself."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, final

import anyio.to_thread
from typing_extensions import override
from xtr_password_hasher import (
    PasswordHasherInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)

from xtr_security_oauth2_server.entity.client import Client as ClientEntity
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["ClientRepository"]


@final
class ClientRepository(ClientRepositoryInterface):
    """Turns a stored client into one the protocol reads, and authenticates it.

    Two jobs, deliberately separate, because the grants need them separate:
    every grant has to *find* the client a request names in order to read its
    redirect URIs, while only a request that carried credentials — or that
    must have — goes on to prove them.

    A secret is never compared here. It is handed to the password hasher the
    deployment configured, on a worker thread, because hashing a password is
    exactly the kind of CPU-bound work that must not stall an event loop — a
    deliberately expensive hash would otherwise block every other request for
    as long as it takes. There is no plaintext path: a stored secret is a
    hash, and a registration holding anything else simply never matches.

    A hash the hasher calls out of date is replaced after a successful proof,
    which is the one moment the plaintext is in hand. If that write fails, the
    authentication still succeeds: the secret was already verified, the client
    has done nothing wrong, and the upgrade will be tried again next time.

    A deactivated client is not found at all. A client holding no secret is
    never asked to prove one, so the lookup is the one place every request
    passes through — and a client nobody can find is refused as
    ``invalid_client`` on every path, whether or not it holds a secret.
    """

    def __init__(
        self,
        client_manager: ClientManagerInterface,
        password_hasher: PasswordHasherInterface,
    ) -> None:
        """Read clients from ``client_manager``, prove secrets with ``password_hasher``."""
        self._client_manager = client_manager
        self._password_hasher = password_hasher

    @override
    def __repr__(self) -> str:
        """Name the type; neither collaborator says anything a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        """Return the active client registered as ``client_identifier``, or ``None``."""
        client = await self._client_manager.find(client_identifier)
        if client is None or not client.is_active():
            return None

        return _entity_of(client)

    @override
    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        """Tell whether ``client_identifier`` proved itself for ``grant_type``."""
        client = await self._client_manager.find(client_identifier)
        if client is None or not client.is_active():
            return False
        if not _may_use(client, grant_type):
            return False
        if not client.is_confidential():
            return True

        stored = client.get_secret() or ""
        presented = client_secret or ""
        proved = await anyio.to_thread.run_sync(
            self._password_hasher.verify,
            stored,
            presented,
        )
        if proved and self._password_hasher.needs_rehash(stored):
            await self._rehash(client, presented)

        return proved

    async def _rehash(self, client: ClientInterface, presented: str) -> None:
        """Replace ``client``'s stored hash with a fresh one, if that can be done.

        A failure here is swallowed on purpose. The secret has already been
        verified, so refusing the request would punish a client for a storage
        problem it cannot see, and the next successful proof will try again.
        """
        fresh = await anyio.to_thread.run_sync(self._password_hasher.hash, presented)
        client.set_secret(fresh)
        with contextlib.suppress(Exception):
            await self._client_manager.save(client)


def _may_use(client: ClientInterface, grant_type: str | None) -> bool:
    """Tell whether ``client`` is allowed ``grant_type``.

    A caller acting for no particular grant — a revocation or an
    introspection request, which authenticate a client without redeeming
    anything — is allowed, and so is a client registered for no grant in
    particular.
    """
    if grant_type is None:
        return True
    grants = client.get_grants()
    if not grants:
        return True

    return any(str(grant) == grant_type for grant in grants)


def _entity_of(client: ClientInterface) -> ClientEntity:
    """Return the entity a grant reads, built from the stored registration."""
    entity = ClientEntity()
    entity.set_identifier(client.get_identifier())
    entity.set_name(client.get_name())
    entity.set_redirect_uri(tuple(str(uri) for uri in client.get_redirect_uris()))
    entity.set_confidential(client.is_confidential())
    entity.set_allow_plain_text_pkce(client.is_plain_text_pkce_allowed())
    entity.set_allowed_grant_types(tuple(str(grant) for grant in client.get_grants()))

    return entity
