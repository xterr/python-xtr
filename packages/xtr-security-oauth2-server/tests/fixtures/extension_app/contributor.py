"""What the add-on says about itself where a client reads this server's description."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["CONTRIBUTED_FIELD", "NonceMetadataContributor"]

#: The one field the add-on adds to the description this server publishes.
CONTRIBUTED_FIELD: Final[str] = "nonce_parameter_supported"


@final
class NonceMetadataContributor(MetadataContributorInterface):
    """Publishes that this server carries the add-on's parameter through a code.

    A capability nothing in this package knows about, so nothing in this
    package could publish it: the add-on registers this tagged, and the
    description endpoint merges what it answers underneath this server's own
    fields.
    """

    @override
    def get_metadata(self) -> Mapping[str, object]:
        """Return the one field the add-on adds."""
        return {CONTRIBUTED_FIELD: True}

    @override
    def __repr__(self) -> str:
        """Name the type, which is the whole of what there is to say."""
        return f"{type(self).__name__}()"
