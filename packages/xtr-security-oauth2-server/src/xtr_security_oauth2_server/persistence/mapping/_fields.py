"""Which column of a table each attribute of a model is kept in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ._tables import REGISTRATION_COLUMNS

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TypeAlias

    from sqlalchemy import Table

    Properties: TypeAlias = dict[str, object]

__all__ = [
    "BESIDE",
    "CLIENT",
    "CREDENTIAL",
    "DEVICE_CODE",
    "HOLDER",
    "REFRESH_TOKEN",
    "REGISTRATION",
    "columns",
]

REGISTRATION: Final[Mapping[str, str]] = {
    column.attribute: column.name for column in REGISTRATION_COLUMNS
}
"""Where a client's registration lives — the columns an application inherits.

Read off the one description of those columns, so the attribute a value is
kept in and the column it is kept in cannot drift apart.
"""

CLIENT: Final[Mapping[str, str]] = {"_identifier": "identifier", **REGISTRATION}
"""The same, for the client this package ships, whose identifier it owns too."""

CREDENTIAL: Final[Mapping[str, str]] = {
    "_identifier": "identifier",
    "_expiry": "expiry",
    "_user_identifier": "user_identifier",
    "_scopes": "scopes",
    "_revoked": "revoked",
}
"""Where a credential's attributes live: an access token, a code, a device code."""

DEVICE_CODE: Final[Mapping[str, str]] = {
    "_user_code": "user_code",
    "_user_approved": "user_approved",
    "_include_verification_uri_complete": "include_verification_uri_complete",
    "_verification_uri": "verification_uri",
    "_last_polled_at": "last_polled_at",
    "_interval": "interval",
}
"""What a live device flow writes on top of a credential's attributes."""

REFRESH_TOKEN: Final[Mapping[str, str]] = {
    "_identifier": "identifier",
    "_expiry": "expiry",
    "_revoked": "revoked",
}
"""Where a refresh token's attributes live.

Fewer than a credential's: a refresh token names neither a user nor a scope,
because both belong to the access token it was issued beside.
"""

HOLDER: Final = "_client_identifier"
"""Where the client column lands, beside the client the relationship reads.

The relationship is what a credential answers with, but a many-to-one is
written through a mapped column, so the column is mapped too — privately,
under a name the model never reads, rather than publicly under the column's
own name.
"""

BESIDE: Final = "_access_token_identifier"
"""Where the access-token column of a refresh token lands, for the same reason."""


def columns(table: Table, fields: Mapping[str, str]) -> Properties:
    """Return which column of ``table`` each attribute named by ``fields`` is."""
    return {attribute: table.c[column] for attribute, column in fields.items()}
