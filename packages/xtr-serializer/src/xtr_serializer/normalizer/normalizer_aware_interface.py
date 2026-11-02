"""Something that is handed the normalizer for the values nested in the ones it writes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .normalizer_interface import NormalizerInterface

__all__ = ["NormalizerAwareInterface"]


@runtime_checkable
class NormalizerAwareInterface(Protocol):
    """Accepts, through a setter, the normalizer that writes the parts of what it writes.

    A normalizer for an object made of other objects writes the object and hands each part back
    to the serializer's normalizers, so whichever handles that part's type writes it. Those
    normalizers include this one, so the serializer that holds them cannot be a constructor
    argument: once built, it hands itself to each one that implements this.
    """

    def set_normalizer(self, normalizer: NormalizerInterface, /) -> None:
        """Hand nested values to ``normalizer`` from now on."""
        ...
