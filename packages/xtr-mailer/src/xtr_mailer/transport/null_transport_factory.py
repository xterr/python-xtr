"""Builds the null transport from ``null://null``."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mailer.exception import UnsupportedSchemeError

from .abstract_transport_factory import AbstractTransportFactory
from .null_transport import NullTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .dsn import Dsn

__all__ = ["NullTransportFactory"]


@final
class NullTransportFactory(AbstractTransportFactory):
    """Builds a :class:`NullTransport` for ``null://``.

    The null transport reaches no server, so this factory needs no HTTP client: it accepts one
    only because every factory is built with the same keywords, and hands nothing of it on.
    ``null://`` therefore works in an application that has no HTTP client at all.
    """

    @override
    def create(self, dsn: Dsn) -> NullTransport:
        """Build a null transport.

        Raises:
            UnsupportedSchemeError: ``dsn``'s scheme is not ``null``.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "null", self._get_supported_schemes())
        return NullTransport(self._event_dispatcher, self._logger)

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return ``null``, the one scheme served."""
        return ("null",)
