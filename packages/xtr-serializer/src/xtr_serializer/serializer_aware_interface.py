"""Something that is handed the serializer it is part of, once that serializer exists."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .serializer_interface import SerializerInterface

__all__ = ["SerializerAwareInterface"]


@runtime_checkable
class SerializerAwareInterface(Protocol):
    """Accepts the serializer it is part of, through a setter.

    For a normalizer or an encoder that needs the whole serializer for part of its work — one
    that embeds a value already written as text, say. The serializer cannot be a constructor
    argument: it is built from its normalizers and encoders, so it does not exist yet when they
    do. Once built, the serializer hands itself to each one that implements this.
    """

    def set_serializer(self, serializer: SerializerInterface, /) -> None:
        """Use ``serializer``, the one this is part of, from now on."""
        ...
