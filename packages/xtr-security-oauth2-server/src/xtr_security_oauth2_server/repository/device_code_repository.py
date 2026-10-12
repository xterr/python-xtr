"""The one credential this server reads back: a device code, poll after poll."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)

from xtr_security_oauth2_server.converter.scope_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.entity.device_code import DeviceCode as DeviceCodeEntity
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.manager.device_code_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.model.device_code import DeviceCode as DeviceCodeModel

from ._stored_client import stored_client_of

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )

    from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface

__all__ = ["DeviceCodeRepository"]


@final
class DeviceCodeRepository(DeviceCodeRepositoryInterface):
    """Mints the device-code entity, stores it, and reads it back for each poll.

    The only bridge with one store method instead of two, because a poll
    writes to the very code it just read: the first call creates the record,
    and every later one updates what changed — when it was last polled, and
    whether its owner has approved it.

    Reading one back is the other half, and it rebuilds the whole entity,
    client and scopes included, because the grant handling the poll has
    nothing but the code the device sent.
    """

    def __init__(
        self,
        device_code_manager: DeviceCodeManagerInterface,
        client_manager: ClientManagerInterface,
        scope_converter: ScopeConverterInterface,
        client_repository: ClientRepositoryInterface,
    ) -> None:
        """Store codes through the manager; rebuild clients through the repository."""
        self._device_code_manager = device_code_manager
        self._client_manager = client_manager
        self._scope_converter = scope_converter
        self._client_repository = client_repository

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_new_device_code(self) -> DeviceCodeEntityInterface:
        """Return a new, unstored device code."""
        return DeviceCodeEntity()

    @override
    async def persist_device_code(self, device_code_entity: DeviceCodeEntityInterface) -> None:
        """Store ``device_code_entity``, new or already known.

        Raises:
            InvalidArgumentError: When no client is stored under the
                identifier a *new* code names.
        """
        stored = await self._device_code_manager.find(device_code_entity.get_identifier())
        if stored is None:
            stored = await self._new_model(device_code_entity)
        else:
            _record_progress(stored, device_code_entity)

        await self._device_code_manager.save(stored)

    @override
    async def get_device_code_entity_by_device_code(
        self,
        device_code: str,
    ) -> DeviceCodeEntityInterface | None:
        """Return the stored code named ``device_code`` as an entity, or ``None``."""
        stored = await self._device_code_manager.find(device_code)
        if stored is None:
            return None

        return await self._entity_of(stored)

    @override
    async def revoke_device_code(self, code_id: str) -> None:
        """Stop accepting the device code named ``code_id``."""
        stored = await self._device_code_manager.find(code_id)
        if stored is None:
            return

        await self._device_code_manager.save(stored.revoke())

    @override
    async def is_device_code_revoked(self, code_id: str) -> bool:
        """Tell whether the device code named ``code_id`` was revoked.

        A code nobody stored counts as revoked: a device polls with a code
        this server wrote down, so one with no record was never issued here.
        """
        stored = await self._device_code_manager.find(code_id)
        if stored is None:
            return True

        return stored.is_revoked()

    async def _new_model(self, entity: DeviceCodeEntityInterface) -> DeviceCodeModel:
        """Return the record to store for a code that was just issued.

        Whether the device asked for the pre-filled verification URI is read
        off the shipped entity, which carries that flag, rather than off the
        contract, which does not: an application bringing its own device-code
        entity therefore gets everything stored but that one answer, and the
        device is sent the plain verification URI.
        """
        client = await stored_client_of(self._client_manager, entity.get_client())
        include_complete = (
            entity.get_verification_uri_complete_in_auth_response()
            if isinstance(entity, DeviceCodeEntity)
            else False
        )

        return DeviceCodeModel(
            entity.get_identifier(),
            entity.get_expiry_date_time(),
            client,
            entity.get_user_identifier(),
            self._scope_converter.to_domain_sequence(entity.get_scopes()),
            entity.get_user_code(),
            entity.get_user_approved(),
            entity.get_verification_uri(),
            entity.get_last_polled_at(),
            entity.get_interval(),
            include_verification_uri_complete=include_complete,
        )

    async def _entity_of(self, stored: DeviceCodeInterface) -> DeviceCodeEntity:
        """Return the entity a grant reads, rebuilt from what was stored."""
        entity = DeviceCodeEntity()
        entity.set_identifier(stored.get_identifier())
        entity.set_expiry_date_time(stored.get_expiry())
        client = await self._client_repository.get_client_entity(
            stored.get_client().get_identifier(),
        )
        if client is not None:
            entity.set_client(client)
        user_identifier = stored.get_user_identifier()
        if user_identifier is not None:
            entity.set_user_identifier(user_identifier)
        entity.set_user_code(stored.get_user_code())
        entity.set_user_approved(stored.get_user_approved())
        entity.set_verification_uri(stored.get_verification_uri())
        entity.set_verification_uri_complete_in_auth_response(
            stored.get_include_verification_uri_complete(),
        )
        last_polled_at = stored.get_last_polled_at()
        if last_polled_at is not None:
            entity.set_last_polled_at(last_polled_at)
        entity.set_interval(stored.get_interval())
        for scope in stored.get_scopes():
            entity.add_scope(self._scope_converter.to_entity(scope))

        return entity


def _record_progress(stored: DeviceCodeInterface, entity: DeviceCodeEntityInterface) -> None:
    """Put onto ``stored`` the two things a live device flow changes.

    Nothing else is copied over. The scopes, the client, the user code and the
    expiry were all settled when the code was issued, and a poll that could
    rewrite them would let a device widen its own grant.

    The approval is only taken when the entity names a resource owner, because
    that is what tells an approval apart from an ordinary poll: a poll carries
    no user, and copying its ``False`` would undo an approval given a moment
    earlier.
    """
    last_polled_at = entity.get_last_polled_at()
    if last_polled_at is not None:
        _ = stored.set_last_polled_at(last_polled_at)

    user_identifier = entity.get_user_identifier()
    if user_identifier:
        _ = stored.set_user_identifier(user_identifier)
        _ = stored.set_user_approved(entity.get_user_approved())
