"""What an extension adds to the document this server describes itself with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["MetadataContributorInterface"]


@runtime_checkable
class MetadataContributorInterface(Protocol):
    """Adds fields of its own to the discovery document.

    An extension that adds a capability has to say so where a client looks:
    an OpenID Connect add-on publishes the claims and subject types it
    supports, a deployment behind a particular token profile publishes that.
    Neither is this package's to answer, so each contributes its own fields and
    the document merges them.

    What this server decides wins. A contributed ``issuer`` or
    ``token_endpoint`` is dropped rather than applied, because those describe
    the server itself and an extension that could overwrite them could point
    clients somewhere else.

    Register one as a service tagged ``oauth2_server.metadata``; the tag's
    ``priority`` attribute orders the contributors, highest first, so that two
    contributing the same field have a defined winner.
    """

    def get_metadata(self) -> Mapping[str, object]:
        """Return the fields this extension adds to the document.

        Called once per request for the document, so a contributor that has to
        read something expensive caches it itself.

        Returns:
            The fields to merge, each already in the shape it is published in —
            a string, a number, a list of strings — since what this returns is
            serialised as it stands.
        """
        ...
