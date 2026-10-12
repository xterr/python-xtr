"""The columns of every table this package keeps a client or a credential in.

A client's registration is described once, here, and built twice: into the
table this package ships and onto the class an application maps itself. The
two cannot share the objects — a column belongs to one table — so each asks
the description for its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Generic, TypeVar, final

from sqlalchemy import CHAR, Boolean, Column, ForeignKey, Integer, String, Table, false
from sqlalchemy.orm import mapped_column

from xtr_security_oauth2_server.persistence.type.grant import Grant
from xtr_security_oauth2_server.persistence.type.redirect_uri import RedirectUri
from xtr_security_oauth2_server.persistence.type.scope import Scope
from xtr_security_oauth2_server.persistence.type.utc_datetime import UtcDateTime

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement, MetaData
    from sqlalchemy.orm import MappedColumn
    from sqlalchemy.sql.schema import SchemaItem
    from sqlalchemy.types import TypeEngine

__all__ = [
    "ACTIVE_COLUMN",
    "ALLOW_PLAIN_TEXT_PKCE_COLUMN",
    "CREDENTIAL",
    "GRANTS_COLUMN",
    "IDENTIFIER",
    "NAME",
    "NAME_COLUMN",
    "REDIRECT_URIS_COLUMN",
    "REGISTRATION_COLUMNS",
    "SCOPES_COLUMN",
    "SECRET",
    "SECRET_COLUMN",
    "URI",
    "access_token_table",
    "authorization_code_table",
    "client_table",
    "device_code_table",
    "refresh_token_table",
]

_ValueT = TypeVar("_ValueT")

IDENTIFIER: Final = 32
"""How long a client identifier may be. A client picks its own, or is given one."""

CREDENTIAL: Final = 80
"""How long a credential identifier is: fixed, because this server mints them all."""

NAME: Final = 128
"""How long a client's name and a user identifier may be."""

SECRET: Final = 255
"""How long a stored secret may be: a hash, with room for a slower one later."""

URI: Final = 255
"""How long a verification URI and a user code may be."""


@final
@dataclass(frozen=True, slots=True)
class _Registered(Generic[_ValueT]):
    """One column a client's registration is kept in, and how to build it.

    Two kinds of client are stored through these: the one this package ships,
    whose table it builds itself, and the one an application writes on its own
    declarative base. Both get the same column — same name, same type, same
    nullability, same default — from this one description, and each gets it as
    its own object, because a column belongs to a single table.
    """

    attribute: str
    """The private attribute of the model the value is kept in."""

    name: str
    """What the column is called, in either table."""

    type: TypeEngine[_ValueT]
    """What the column holds. Shared: a column type belongs to no table."""

    nullable: bool
    """Whether the column may be left empty."""

    server_default: ColumnElement[bool] | None = None
    """What the database fills in for a row written before the column existed."""

    def for_table(self) -> Column[_ValueT]:
        """Return this column for a table this package builds itself."""
        return Column(
            self.name,
            self.type,
            nullable=self.nullable,
            server_default=self.server_default,
        )

    def for_class(self) -> MappedColumn[_ValueT]:
        """Return this column for a class an application maps declaratively."""
        return mapped_column(
            self.name,
            self.type,
            nullable=self.nullable,
            server_default=self.server_default,
        )


NAME_COLUMN: Final = _Registered("_name", "name", String(NAME), nullable=False)
"""What the client is called, which is what a consent screen shows."""

SECRET_COLUMN: Final = _Registered("_secret", "secret", String(SECRET), nullable=True)
"""The hash of the client's secret; empty for a public client, which has none."""

REDIRECT_URIS_COLUMN: Final = _Registered(
    "_redirect_uris",
    "redirect_uris",
    RedirectUri(),
    nullable=True,
)
"""Where the client may be sent back to; empty when it is sent back nowhere."""

GRANTS_COLUMN: Final = _Registered("_grants", "grants", Grant(), nullable=True)
"""Which flows the client may use; empty means every one of them."""

SCOPES_COLUMN: Final = _Registered("_scopes", "scopes", Scope(), nullable=True)
"""What the client may ask for; empty means whatever it asks for."""

ACTIVE_COLUMN: Final = _Registered("_active", "active", Boolean(), nullable=False)
"""Whether the registration is honoured at all."""

ALLOW_PLAIN_TEXT_PKCE_COLUMN: Final = _Registered(
    "_allow_plain_text_pkce",
    "allow_plain_text_pkce",
    Boolean(),
    nullable=False,
    server_default=false(),
)
"""Whether the client may send its code verifier unhashed.

Defaulted by the database as well as by the model, so a registration stored
before this column existed reads back as refusing it rather than as empty.
"""

REGISTRATION_COLUMNS: Final = (
    NAME_COLUMN,
    SECRET_COLUMN,
    REDIRECT_URIS_COLUMN,
    GRANTS_COLUMN,
    SCOPES_COLUMN,
    ACTIVE_COLUMN,
    ALLOW_PLAIN_TEXT_PKCE_COLUMN,
)
"""Every column a client's registration is kept in, in the order declared."""


def client_table(metadata: MetaData, prefix: str) -> Table:
    """Return the table a whole client registration is kept in.

    Built only where the shipped client class is the one configured: an
    application bringing its own maps the table itself, and the registration
    columns come from the same description, through
    :class:`~xtr_security_oauth2_server.persistence.mapping.client_mapping_mixin.ClientMappingMixin`.
    """
    return Table(
        f"{prefix}client",
        metadata,
        Column("identifier", String(IDENTIFIER), primary_key=True),
        *(column.for_table() for column in REGISTRATION_COLUMNS),
    )


def access_token_table(metadata: MetaData, prefix: str, clients: str) -> Table:
    """Return the table the issued access tokens are kept in."""
    return Table(f"{prefix}access_token", metadata, *_credential(clients))


def authorization_code_table(metadata: MetaData, prefix: str, clients: str) -> Table:
    """Return the table the issued authorization codes are kept in."""
    return Table(f"{prefix}authorization_code", metadata, *_credential(clients))


def device_code_table(metadata: MetaData, prefix: str, clients: str) -> Table:
    """Return the table the issued device codes are kept in.

    A credential plus what a live flow writes to it: the short code its owner
    types in, their decision, where they go to make it, and when the device
    last asked.
    """
    return Table(
        f"{prefix}device_code",
        metadata,
        *_credential(clients),
        Column("user_code", String(URI), nullable=True),
        Column("user_approved", Boolean(), nullable=False),
        Column("include_verification_uri_complete", Boolean(), nullable=False),
        Column("verification_uri", String(URI), nullable=True),
        Column("last_polled_at", UtcDateTime(), nullable=True),
        Column("interval", Integer(), nullable=False),
    )


def refresh_token_table(metadata: MetaData, prefix: str, *, beside_access_token: bool) -> Table:
    """Return the refresh-token table, pointing at an access token when there is one.

    A refresh token outlives the access token it was issued beside — that is
    the point of it — so the row loses the pointer rather than going with it.
    Where access tokens are not written down there is nothing to point at, so
    the column is left out altogether.
    """
    beside: tuple[SchemaItem, ...] = (
        (
            Column(
                "access_token",
                CHAR(CREDENTIAL),
                ForeignKey(f"{prefix}access_token.identifier", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        if beside_access_token
        else ()
    )

    return Table(
        f"{prefix}refresh_token",
        metadata,
        Column("identifier", CHAR(CREDENTIAL), primary_key=True),
        Column("expiry", UtcDateTime(), nullable=False),
        Column("revoked", Boolean(), nullable=False),
        *beside,
    )


def _credential(clients: str) -> tuple[SchemaItem, ...]:
    """Return the columns a credential issued to a client has.

    Access tokens, authorization codes and device codes are the same record
    with different lifetimes — who it is for, what it is good for, until when,
    and whether it has been withdrawn — so they are built from one list and
    the device code adds its own. A credential is deleted with the client it
    was issued to, because it can never be honoured again.
    """
    return (
        Column("identifier", CHAR(CREDENTIAL), primary_key=True),
        Column("expiry", UtcDateTime(), nullable=False),
        Column("user_identifier", String(NAME), nullable=True),
        Column("scopes", Scope(), nullable=True),
        Column("revoked", Boolean(), nullable=False),
        Column(
            "client",
            String(IDENTIFIER),
            ForeignKey(f"{clients}.identifier", ondelete="CASCADE"),
            nullable=False,
        ),
    )
