"""A transport factory kept out of the container with ``@exclude``."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import exclude
from xtr_messenger import Dsn, TransportConfig, TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_messenger import SenderInterface

__all__ = ["UnusedTransportFactory"]


@final
@exclude
class UnusedTransportFactory(TransportFactoryInterface):
    """Kept out of the container with ``@exclude``.

    The messenger bundle registers *every* concrete ``TransportFactoryInterface`` its scan
    finds. ``@exclude`` is how a scanned module keeps one that is not meant for the kernel —
    a stub for container-less scripts, say — out of every scan.
    """

    @override
    def supports(self, dsn: Dsn) -> bool:
        return False

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        return {}
