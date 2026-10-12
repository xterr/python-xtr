"""The contributor of a deployment that adds nothing to its own description."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["NullMetadataContributor"]

#: One shared empty mapping: there is nothing to say, and saying it should not
#: allocate.
_NOTHING: Final[Mapping[str, object]] = MappingProxyType({})


@final
class NullMetadataContributor(MetadataContributorInterface):
    """Contributes no fields, so that the collection of contributors is never empty.

    Nothing can be injected as an empty collection, and the ordinary deployment
    has no extension adding fields to its description — so without this, the
    endpoint publishing that description could not ask for the contributors at
    all, and an add-on appearing later would have nothing to join.

    This is that one member. It answers with no fields, so a deployment with no
    extension publishes exactly what it decided itself.
    """

    @override
    def get_metadata(self) -> Mapping[str, object]:
        """Return no fields at all."""
        return _NOTHING

    @override
    def __repr__(self) -> str:
        """Name the type, which is the whole of what there is to say."""
        return f"{type(self).__name__}()"
