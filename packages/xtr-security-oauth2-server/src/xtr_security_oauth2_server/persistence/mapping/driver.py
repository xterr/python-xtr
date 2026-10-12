"""The tables a stored deployment gets, and the models mapped onto them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy.orm import class_mapper, registry, relationship
from sqlalchemy.orm.exc import UnmappedClassError
from typing_extensions import override
from xtr_orm import MappingDriverInterface
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.refresh_token import RefreshToken

from ._fields import (
    BESIDE,
    CLIENT,
    CREDENTIAL,
    DEVICE_CODE,
    HOLDER,
    REFRESH_TOKEN,
    columns,
)
from ._tables import (
    access_token_table,
    authorization_code_table,
    client_table,
    device_code_table,
    refresh_token_table,
)
from .mapped_table import mapped_table

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import MetaData, Table

    from xtr_security_oauth2_server.model.abstract_client import AbstractClient

    from ._fields import Properties

__all__ = ["Driver"]


@final
class Driver(MappingDriverInterface):
    """Builds this package's tables and maps its models onto them.

    Four things about a deployment decide what there is to store, which is why
    none of it can be declared when this module is imported: which class a
    client row becomes, whether access tokens are written down at all, the
    prefix every table carries, and whether the device flow is on.

    Five tables, two of them always there. ``{prefix}client`` exists only
    where the shipped client class is the one configured — an application
    bringing its own maps that table itself, with
    :class:`~xtr_security_oauth2_server.persistence.mapping.client_mapping_mixin.ClientMappingMixin`
    for the columns — and the credentials point at whichever of the two it is.
    ``{prefix}access_token`` exists only where access tokens are persisted:
    without it a token is a signed document and nothing more, and the refresh
    tokens then have nothing to point at, so that column goes too.
    ``{prefix}device_code`` exists only where the device flow is enabled.

    A credential is deleted with the client it was issued to, because it can
    never be honoured again; a refresh token only loses the access token it
    was issued beside, because it outlives it by design.

    Both halves happen in :meth:`load_metadata` — the tables join the
    definitions it is handed, and the models are mapped against those very
    tables — because that is the one moment both are known: the definitions
    belong to the connection the application chose, and a credential table
    cannot point at a client table that is somewhere else.

    The mapping goes into a registry of this driver's own, so
    :meth:`_dispose` takes back exactly what this driver installed and leaves
    an application's own classes mapped. One deployment per process: a second
    driver mapping the same model onto a different table is refused rather
    than silently losing to the first.
    """

    __slots__ = (
        "_client_class",
        "_enable_device_code_grant",
        "_persist_access_token",
        "_registry",
        "_replaced",
        "_table_prefix",
    )

    def __init__(
        self,
        client_class: type[AbstractClient],
        persist_access_token: bool,
        table_prefix: str = "oauth2_",
        enable_device_code_grant: bool = True,
    ) -> None:
        """Build the tables of a deployment with these four settings.

        Args:
            client_class: The class a client row is read into.
            persist_access_token: Whether access tokens are written down.
            table_prefix: What every table name starts with.
            enable_device_code_grant: Whether the device flow is on.
        """
        self._client_class = client_class
        self._persist_access_token = persist_access_token
        self._table_prefix = table_prefix
        self._enable_device_code_grant = enable_device_code_grant
        self._registry = registry()
        self._replaced: list[tuple[type[object], str, object]] = []

    @override
    def load_metadata(self, metadata: MetaData, /) -> tuple[str, ...]:
        """Add this deployment's tables to ``metadata``, and map the models onto them.

        A table already there is left as it is, left out of the answer, and
        mapped against — so loading twice changes nothing and says so, and the
        managers always work on the very tables the connection migrates.
        """
        known = set(metadata.tables)
        self._load(metadata)

        return tuple(name for name in metadata.tables if name not in known)

    def _dispose(self) -> None:  # pyright: ignore[reportUnusedFunction] — only a test run resets.
        """Unmap the models this driver mapped, and nothing else.

        Kept to itself because a process that builds one deployment never
        needs it: it is for a test run, which builds many. An application's
        own client class is mapped in a registry of its own and stays mapped.

        The registry is replaced rather than only emptied, so the one that
        held the mapping is let go of: what the ORM remembers about a mapping
        is remembered for as long as its registry is, and this driver can be
        loaded again afterwards.

        Unmapping deletes every attribute the mapping installed, and one of
        those may have been the model's own beforehand — a default it declares
        for something this deployment maps no column for — so each of them is
        put back as it was found and the record emptied, leaving the models
        the way the next deployment finds them.
        """
        self._registry.dispose()
        self._registry = registry()
        for model, attribute, value in self._replaced:
            setattr(model, attribute, value)
        self._replaced.clear()

    def _load(self, metadata: MetaData) -> None:
        """Build and map each table this deployment has, clients first."""
        prefix = self._table_prefix
        clients = self._clients(metadata)
        codes = _loaded(
            metadata,
            f"{prefix}authorization_code",
            lambda: authorization_code_table(metadata, prefix, clients.fullname),
        )
        self._map(AuthorizationCode, codes, self._credential(codes))
        if self._persist_access_token:
            tokens = _loaded(
                metadata,
                f"{prefix}access_token",
                lambda: access_token_table(metadata, prefix, clients.fullname),
            )
            self._map(AccessToken, tokens, self._credential(tokens))
        refresh = _loaded(
            metadata,
            f"{prefix}refresh_token",
            lambda: refresh_token_table(
                metadata,
                prefix,
                beside_access_token=self._persist_access_token,
            ),
        )
        self._map(RefreshToken, refresh, self._refresh_token(refresh))
        if self._enable_device_code_grant:
            device = _loaded(
                metadata,
                f"{prefix}device_code",
                lambda: device_code_table(metadata, prefix, clients.fullname),
            )
            self._map(DeviceCode, device, self._device_code(device))

    def _clients(self, metadata: MetaData) -> Table:
        """Return the table the configured client class is read from.

        Built here for the client this package ships; for an application's own
        class it is the table the application mapped, which has to be among
        ``metadata``'s definitions — the credentials point at it.
        """
        if self._client_class is Client:
            built = _loaded(
                metadata,
                f"{self._table_prefix}client",
                lambda: client_table(metadata, self._table_prefix),
            )
            self._map(Client, built, columns(built, CLIENT))

            return built

        return mapped_table(self._client_class)

    def _credential(self, table: Table) -> Properties:
        """Return where a credential's attributes live, the client among them."""
        properties = columns(table, CREDENTIAL)
        properties[HOLDER] = table.c["client"]
        properties["_client"] = relationship(self._client_class, lazy="joined")

        return properties

    def _device_code(self, table: Table) -> Properties:
        """Return where a device code's attributes live, the polling state included."""
        return self._credential(table) | columns(table, DEVICE_CODE)

    def _refresh_token(self, table: Table) -> Properties:
        """Return where a refresh token's attributes live.

        Where access tokens are not persisted, the token reads back naming
        none — which is the truth: the one it was issued beside was never
        written down.
        """
        properties = columns(table, REFRESH_TOKEN)
        if self._persist_access_token:
            properties[BESIDE] = table.c["access_token"]
            properties["_access_token"] = relationship(AccessToken, lazy="joined")

        return properties

    def _map(self, model: type[object], table: Table, properties: Properties) -> None:
        """Map ``model`` onto ``table``, unless it is mapped onto it already.

        What the model declared itself and the mapping stands in for is
        written down, so :meth:`_dispose` can put it back. Which attributes
        those are is read off the instrumentation the mapper installed on the
        class — not off ``properties``, which says nothing about a column left
        to answer under its own name, and not off
        :attr:`~sqlalchemy.orm.Mapper.attrs`, which would configure every
        mapper in the process halfway through building this deployment.
        """
        if self._mapped_onto(model, table):
            return
        declared = dict(vars(model))
        mapper = self._registry.map_imperatively(model, table, properties=properties)
        self._replaced.extend(
            (model, name, declared[name]) for name in mapper.class_manager if name in declared
        )

    def _mapped_onto(self, model: type[object], table: Table) -> bool:
        """Tell whether ``model`` is already mapped onto ``table``.

        Raises:
            InvalidArgumentError: When it is mapped onto a different one. The
                mapping lives on the class, so two deployments in one process
                cannot both have it; the first one built keeps it, and this
                says so instead of leaving the second to write through tables
                belonging to the first.
        """
        try:
            mapper = class_mapper(model)
        except UnmappedClassError:
            return False
        if mapper.local_table is table:
            return True

        raise InvalidArgumentError(
            f"{model.__name__} is already mapped onto "
            f"{mapped_table(model).fullname!r}, so it cannot also be mapped onto "
            f"{table.fullname!r}; one deployment of this package per process.",
        )


def _loaded(metadata: MetaData, name: str, build: Callable[[], Table]) -> Table:
    """Return the table ``name`` of ``metadata``, building it when it is not there."""
    known = metadata.tables.get(name)

    return build() if known is None else known
