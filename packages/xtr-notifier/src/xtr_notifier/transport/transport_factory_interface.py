"""What turns a DSN into a transport."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .dsn import Dsn
    from .transport_interface import TransportInterface

__all__ = ["TransportFactoryInterface"]


@runtime_checkable
class TransportFactoryInterface(Protocol):
    """Builds the transport a DSN describes, for the schemes it serves."""

    def create(self, dsn: Dsn) -> TransportInterface:
        """Build the transport ``dsn`` describes.

        Implementations raise
        :class:`~xtr_notifier.exception.UnsupportedSchemeError` for a scheme they
        do not serve, and
        :class:`~xtr_notifier.exception.IncompleteDsnError` (or its
        :class:`~xtr_notifier.exception.MissingRequiredOptionError`) for a DSN
        missing what the transport needs.
        """
        ...

    def supports(self, dsn: Dsn) -> bool:
        """Tell whether this factory serves ``dsn``'s scheme."""
        ...
