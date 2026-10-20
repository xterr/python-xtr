"""A provider factory serving ``dummy://``, as a bridge library would ship one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.transport import AbstractTransportFactory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.transport import Dsn

__all__ = ["DummyTransportFactory"]


@final
class DummyTransportFactory(AbstractTransportFactory):
    """Builds a :class:`FakeTransport` named after the DSN's host, for ``dummy://``."""

    @override
    def create(self, dsn: Dsn) -> FakeTransport:
        if dsn.scheme != "dummy":
            raise UnsupportedSchemeError(dsn.scheme, "dummy", self._get_supported_schemes())
        return FakeTransport(dsn.host)

    def exposed_ssl(self, dsn: Dsn) -> bool | None:
        return self._get_ssl(dsn)

    def exposed_user(self, dsn: Dsn) -> str:
        return self._get_user(dsn)

    def exposed_password(self, dsn: Dsn) -> str:
        return self._get_password(dsn)

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("dummy",)
