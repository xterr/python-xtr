"""Builders that see a chosen set of peer bundles, for wiring code exercised without a kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["NO_PEERS", "with_peers"]


@final
class _Peers:
    """Answers ``kernel.bundles`` as the given names, which is all ``bundle_active`` reads."""

    def __init__(self, names: tuple[str, ...]) -> None:
        self._bundles = dict.fromkeys(names, True)

    def has_parameter(self, name: str) -> bool:
        return name == "kernel.bundles" and bool(self._bundles)

    def get_parameter(self, name: str) -> object:
        del name
        return self._bundles


def with_peers(*names: str) -> ContainerBuilder:
    """Return a builder on which exactly the bundles ``names`` are active."""
    return cast("ContainerBuilder", cast("object", _Peers(names)))


NO_PEERS = with_peers()
