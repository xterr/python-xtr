"""What every multipart shares: its parts, in order, and a boundary between them."""

from __future__ import annotations

import secrets
from abc import ABCMeta
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from xtr_mime._engine import build_multipart, set_fields

from .abstract_part import AbstractPart

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["AbstractMultipartPart"]


class AbstractMultipartPart(AbstractPart, metaclass=ABCMeta):
    """A ``multipart/*`` part: other parts, each opened by a boundary line.

    The boundary is made up once per part — eight URL-safe characters from six random
    bytes — and given to the engine, which never picks one of its own.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_boundary", "_parts")

    def __init__(self, *parts: AbstractPart) -> None:
        """Keep ``parts``, in order."""
        super().__init__()
        self._parts: list[AbstractPart] = list(parts)
        self._boundary: str | None = None

    def get_parts(self) -> Sequence[AbstractPart]:
        """Return the parts, in order."""
        return list(self._parts)

    @override
    def get_media_type(self) -> str:
        """Return ``multipart``."""
        return "multipart"

    @override
    def get_prepared_headers(self) -> Headers:
        """Return the headers with the boundary set on Content-Type."""
        headers = super().get_prepared_headers()
        headers.set_header_parameter("Content-Type", "boundary", self._get_boundary())
        return headers

    @override
    def as_debug_string(self) -> str:
        """Describe the part and, indented below it, each of its parts."""
        description = super().as_debug_string()
        for part in self.get_parts():
            first, *rest = part.as_debug_string().split("\n")
            description += f"\n  └ {first}"
            for line in rest:
                description += f"\n  |{line}"
        return description

    @override
    def _to_engine(self) -> EnginePart:
        # A part's engine tree stays inside the part classes: a multipart builds its own.
        children = [part._to_engine() for part in self.get_parts()]  # noqa: SLF001 — see above.
        multipart = build_multipart(self.get_media_subtype(), self._get_boundary(), children)
        set_fields(multipart, self.get_prepared_headers().to_array())
        return multipart

    def _get_boundary(self) -> str:
        if self._boundary is None:
            self._boundary = secrets.token_urlsafe(6)
        return self._boundary
