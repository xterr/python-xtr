"""A piece of metadata a mail provider keeps with the email."""

from __future__ import annotations

from typing import ClassVar, final

from xtr_mime import UnstructuredHeader

__all__ = ["MetadataHeader"]


@final
class MetadataHeader(UnstructuredHeader):
    """``X-Metadata-<key>``: a value a provider keeps with the email and hands back in its events.

    A provider transport turns it into the provider's own variable; any other sends it as it is.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_key",)

    def __init__(self, key: str, value: str) -> None:
        """Keep ``key`` and ``value``.

        Raises:
            xtr_mime.RfcComplianceError: ``key`` cannot be part of a header name: it is not
                printable ASCII, or holds a space.
        """
        super().__init__(f"X-Metadata-{key}", value)
        self._key: str = key

    def get_key(self) -> str:
        """Return the key, without the ``X-Metadata-`` the header name starts with."""
        return self._key
