"""A tag a mail provider files the email under."""

from __future__ import annotations

from typing import ClassVar, final

from xtr_mime import UnstructuredHeader

__all__ = ["TagHeader"]


@final
class TagHeader(UnstructuredHeader):
    """``X-Tag``: a tag a provider files the email under, one header per tag.

    A provider transport turns it into the provider's own tag; any other sends it as it is.
    """

    __slots__: ClassVar[tuple[str, ...]] = ()

    def __init__(self, value: str) -> None:
        """Tag the email with ``value``, refused when written if it would break the header."""
        super().__init__("X-Tag", value)
