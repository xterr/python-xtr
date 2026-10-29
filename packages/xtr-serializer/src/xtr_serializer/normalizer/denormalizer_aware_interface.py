"""Something that is handed the denormalizer for the values nested in the ones it builds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .denormalizer_interface import DenormalizerInterface

__all__ = ["DenormalizerAwareInterface"]


@runtime_checkable
class DenormalizerAwareInterface(Protocol):
    """Accepts, through a setter, the denormalizer that builds the parts of what it builds.

    A denormalizer for an object made of other objects builds the object and hands the data for
    each part back to the serializer's denormalizers, so whichever builds that part's type
    builds it. Those denormalizers include this one, so the serializer that holds them cannot be
    a constructor argument: once built, it hands itself to each one that implements this.
    """

    def set_denormalizer(self, denormalizer: DenormalizerInterface, /) -> None:
        """Hand the data for nested values to ``denormalizer`` from now on."""
        ...
