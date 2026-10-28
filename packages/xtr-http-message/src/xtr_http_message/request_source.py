"""Where a connected request reads its late answers from.

A request built over a connection is born before anything has read its
body: the head is already on the connection, but the body, the parsed
form and the uploaded files arrive only as the body is read. This is
the seam between the two moments — framework-free, so the message
package stays tied to no web framework, and small enough that a
connection adapter is all an integration needs to write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RequestSource"]


@runtime_checkable
class RequestSource(Protocol):
    """Where a connected request reads its late answers from.

    A request built over a connection materialises its body side
    lazily: the sync getters answer what materialisation has yielded so
    far, and the body stream reads the rest through here on its first
    read. The head — method, URI, headers, cookies, query, environment —
    never comes from here: it is passed eagerly when the request is
    built, because it costs no input and never changes mid-request.
    """

    async def materialise(self) -> bytes:
        """Read the whole body once, and answer its bytes.

        Runs at most once — the implementation memoises — filling the
        parsed side and the uploaded files as a side effect, so the sync
        peeks answer from then on. The bytes answered are the raw body
        bytes: for a submitted form, the raw form bytes, with the form
        itself landing in the parsed side.

        Returns:
            The raw bytes of the body.
        """
        ...

    def parsed_body(self) -> object | None:
        """Return what parsing the body yielded, or ``None`` until it has.

        A sync peek at what :meth:`materialise` has yielded so far: the
        form for form content types, a JSON object for JSON, ``None``
        before any body read.
        """
        ...

    def uploaded_files(self) -> Mapping[str, object]:
        """Return the files that came with the body, empty until it is read.

        A sync peek, as :meth:`parsed_body` is one: the files are
        gathered when the body is materialised, so before any body read
        this answers an empty mapping.
        """
        ...

    def attributes(self) -> Mapping[str, object]:
        """Return what has been derived from the request while handling it.

        A live view: routing fills the named path parameters after the
        request exists, and each read answers them as they are now.
        """
        ...
